"""
Tester Lambda handler for validating updated AI agents.

This Lambda function executes test queries against updated AI agents
and evaluates responses to ensure correct behavior.
"""

import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.base_handler import BaseLambdaHandler
from shared.aws_clients import AWSClients
from shared.retry_logic import exponential_backoff
from shared.audit_logging import AuditLogger
from shared.metrics_publisher import MetricsPublisher
from tester.config_loader import ConfigLoader, TestQueryConfig


@dataclass
class TestQuery:
    """Test query configuration."""
    query: str
    expected_behavior: str  # SHOULD_EXPLAIN_UNAVAILABLE, SHOULD_HANDLE_NORMALLY, SHOULD_OFFER_ALTERNATIVE
    keywords: List[str]
    critical: bool
    intent_name: Optional[str] = None  # Intent being tested (for intent-specific tests)
    negative_keywords: List[str] = field(default_factory=list)


@dataclass
class TestResult:
    """Individual test result."""
    query: str
    expected_behavior: str
    actual_response: str
    passed: bool
    critical: bool
    evaluation_details: Optional[Dict[str, Any]] = None
    intent_name: Optional[str] = None  # Intent being tested


@dataclass
class TestExecution:
    """Complete test execution results."""
    agent_id: str
    timestamp: str
    total_tests: int
    passed: int
    failed: int
    critical_failures: int
    results: List[TestResult]
    sample_responses: List[Dict[str, Any]]


class TesterHandler(BaseLambdaHandler):
    """Handler for testing AI agent updates."""
    
    def __init__(self):
        super().__init__(service_name="supervisor-ai-agent-tester")
        self.assistant_id = self.get_required_env_var('ASSISTANT_ID')
        self.config_loader = ConfigLoader(
            aws_clients=self.aws_clients,
            logger=self.logger
        )
        backup_bucket = os.environ.get('BACKUP_BUCKET', '')
        self.audit_logger = AuditLogger(
            bucket_name=backup_bucket,
            logger=self.logger
        )
    
    def process_event(self, event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        """
        Process test execution request.
        
        Args:
            event: Lambda event containing agentId, testScenario, and optional outageInfo or intentTestConfig
            context: Lambda context
            
        Returns:
            Test execution results
        """
        agent_id = event.get('agentId')
        test_scenario = event.get('testScenario', 'default')
        outage_info = event.get('outageInfo', {})
        intent_test_config = event.get('intentTestConfig', {})
        
        if not agent_id:
            raise ValueError("agentId is required")
        
        self.logger.info(
            "Starting test execution",
            extra={
                "agentId": agent_id,
                "testScenario": test_scenario,
                "hasIntentTestConfig": bool(intent_test_config)
            }
        )
        
        # Load test queries for this scenario
        test_queries = self._get_test_queries_for_scenario(
            test_scenario, 
            outage_info, 
            intent_test_config,
            agent_id=agent_id
        )
        
        # Execute test queries
        test_results = self._execute_test_queries(agent_id, test_queries)
        
        # Build test execution report
        test_execution = self._build_test_execution_report(agent_id, test_results)
        
        # Log test execution to audit logs
        self._log_test_execution(agent_id, test_execution, event)
        
        # Publish test execution metrics
        test_result = 'CRITICAL_FAILURE' if test_execution.critical_failures > 0 else (
            'FAILURE' if test_execution.failed > 0 else 'SUCCESS'
        )
        MetricsPublisher.publish_test_execution(
            metrics=self.metrics,
            agent_id=agent_id,
            result=test_result,
            total_tests=test_execution.total_tests,
            passed=test_execution.passed,
            failed=test_execution.failed,
            critical_failures=test_execution.critical_failures
        )
        
        self.logger.info(
            "Test execution completed",
            extra={
                "agentId": agent_id,
                "totalTests": test_execution.total_tests,
                "passed": test_execution.passed,
                "failed": test_execution.failed,
                "criticalFailures": test_execution.critical_failures
            }
        )
        
        return {
            "success": test_execution.critical_failures == 0,
            "agentId": agent_id,
            "totalTests": test_execution.total_tests,
            "passed": test_execution.passed,
            "failed": test_execution.failed,
            "criticalFailures": test_execution.critical_failures,
            "results": [asdict(r) for r in test_execution.results],
            "sampleResponses": test_execution.sample_responses,
            "intentResults": self._build_intent_results_summary(test_results)
        }
    
    def _build_intent_results_summary(
        self,
        test_results: List[TestResult]
    ) -> Dict[str, Any]:
        """
        Build summary of test results grouped by intent.
        
        Args:
            test_results: List of test results
            
        Returns:
            Dictionary with intent-specific results
        """
        intent_results = {}
        
        for result in test_results:
            if result.intent_name:
                if result.intent_name not in intent_results:
                    intent_results[result.intent_name] = {
                        "intentName": result.intent_name,
                        "totalTests": 0,
                        "passed": 0,
                        "failed": 0,
                        "expectedBehavior": result.expected_behavior
                    }
                
                intent_results[result.intent_name]["totalTests"] += 1
                if result.passed:
                    intent_results[result.intent_name]["passed"] += 1
                else:
                    intent_results[result.intent_name]["failed"] += 1
        
        return intent_results
    
    def _get_test_queries_for_scenario(
        self,
        test_scenario: str,
        outage_info: Dict[str, Any],
        intent_test_config: Dict[str, Any] = None,
        agent_id: str = None
    ) -> List[TestQuery]:
        """
        Get test queries for the specified scenario.
        
        Args:
            test_scenario: Test scenario name
            outage_info: Outage information for customizing test queries
            intent_test_config: Intent-specific test configuration
            agent_id: Agent ID for loading per-agent configuration
            
        Returns:
            List of TestQuery objects
        """
        # If intent test config provided, generate intent-specific tests
        if intent_test_config:
            return self._generate_intent_test_queries(intent_test_config)
        
        # Load configuration (per-agent or global)
        config = self.config_loader.load_config(agent_id=agent_id)
        
        # Convert to TestQuery objects
        test_queries = []
        for query_data in config.test_queries:
            test_query = TestQuery(
                query=query_data['query'],
                expected_behavior=query_data['expectedBehavior'],
                keywords=query_data['keywords'],
                critical=query_data.get('critical', False),
                intent_name=query_data.get('intentName')
            )
            test_queries.append(test_query)
        
        # Customize queries based on outage info if provided
        if outage_info:
            test_queries = self._customize_queries_for_outage(test_queries, outage_info)
        
        return test_queries
    
    def _generate_intent_test_queries(
        self,
        intent_test_config: Dict[str, Any]
    ) -> List[TestQuery]:
        """
        Generate test queries for intent-specific testing.
        
        Args:
            intent_test_config: Configuration containing disabled_intents and enabled_intents
            
        Returns:
            List of TestQuery objects for intent testing
        """
        test_queries = []
        
        # Get disabled and enabled intents
        disabled_intents = intent_test_config.get('disabledIntents', [])
        enabled_intents = intent_test_config.get('enabledIntents', [])
        
        # Generate tests for disabled intents (expect rejection)
        for intent in disabled_intents:
            intent_name = intent.get('name', '')
            test_query = intent.get('testQuery', f"I want to {intent_name}")
            
            test_queries.append(TestQuery(
                query=test_query,
                expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
                keywords=["unavailable", "temporarily", "currently", "apologize", "not available"],
                critical=True,
                intent_name=intent_name
            ))
        
        # Generate tests for enabled intents (expect normal handling)
        for intent in enabled_intents:
            intent_name = intent.get('name', '')
            test_query = intent.get('testQuery', f"I want to {intent_name}")
            
            test_queries.append(TestQuery(
                query=test_query,
                expected_behavior="SHOULD_HANDLE_NORMALLY",
                keywords=[intent_name.lower(), "help", "can", "available"],
                critical=True,
                intent_name=intent_name
            ))
        
        return test_queries
    
    def _customize_queries_for_outage(
        self,
        test_queries: List[TestQuery],
        outage_info: Dict[str, Any]
    ) -> List[TestQuery]:
        """
        Customize test queries based on outage information.
        
        Args:
            test_queries: Base test queries
            outage_info: Outage information
            
        Returns:
            Customized test queries
        """
        affected_services = outage_info.get('affectedServices', [])
        available_services = outage_info.get('availableServices', [])
        
        customized_queries = list(test_queries)
        
        # Add specific queries for affected services
        for service in affected_services[:2]:  # Limit to 2 for performance
            customized_queries.append(TestQuery(
                query=f"Can I use {service}?",
                expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
                keywords=["unavailable", "currently", "apologize", "temporarily"],
                critical=True
            ))
        
        # Add specific queries for available services
        for service in available_services[:2]:  # Limit to 2 for performance
            customized_queries.append(TestQuery(
                query=f"Can I use {service}?",
                expected_behavior="SHOULD_HANDLE_NORMALLY",
                keywords=[service.lower(), "available", "can", "help"],
                critical=False
            ))
        
        return customized_queries
    
    def _execute_test_queries(
        self,
        agent_id: str,
        test_queries: List[TestQuery]
    ) -> List[TestResult]:
        """
        Execute test queries against the AI agent.
        
        Args:
            agent_id: AI Agent ID
            test_queries: List of test queries to execute
            
        Returns:
            List of TestResult objects
        """
        results = []
        
        for test_query in test_queries:
            try:
                # Execute query against agent
                response = self._query_agent(agent_id, test_query.query)
                
                # Evaluate response
                test_result = self._evaluate_response(test_query, response)
                results.append(test_result)
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                self.logger.error(
                    "Infrastructure error during test query",
                    extra={
                        "agentId": agent_id,
                        "query": test_query.query,
                        "errorCode": error_code,
                        "error": str(e)
                    }
                )
                # Infrastructure errors are NOT agent behavioral failures
                results.append(TestResult(
                    query=test_query.query,
                    expected_behavior=test_query.expected_behavior,
                    actual_response=f"INFRA_ERROR: {error_code} - {str(e)}",
                    passed=False,
                    critical=False,  # Infra errors don't count as critical agent failures
                    evaluation_details={"error": str(e), "error_type": "infrastructure", "error_code": error_code}
                ))
            except Exception as e:
                self.logger.error(
                    "Failed to execute test query",
                    extra={
                        "agentId": agent_id,
                        "query": test_query.query,
                        "error": str(e)
                    }
                )
                # Create failed test result
                results.append(TestResult(
                    query=test_query.query,
                    expected_behavior=test_query.expected_behavior,
                    actual_response=f"ERROR: {str(e)}",
                    passed=False,
                    critical=test_query.critical,
                    evaluation_details={"error": str(e), "error_type": "test_execution"}
                ))
        
        return results
    
    @exponential_backoff(max_attempts=3)
    def _query_agent(self, agent_id: str, query: str) -> str:
        """
        Query the AI agent with a test query.
        
        Args:
            agent_id: AI Agent ID
            query: Test query text
            
        Returns:
            Agent response text
        """
        q_connect_client = self.aws_clients.get_q_connect_client()
        
        # Create a session for testing
        session_response = q_connect_client.create_session(
            assistantId=self.assistant_id,
            name=f"test-session-{datetime.now(timezone.utc).isoformat()}",
            tags={"purpose": "testing", "agentId": agent_id}
        )
        
        session_id = session_response['session']['sessionId']
        
        try:
            # Query the agent
            query_response = q_connect_client.query_assistant(
                assistantId=self.assistant_id,
                sessionId=session_id,
                queryText=query
            )
            
            # Extract response text from results
            results = query_response.get('results', [])
            if results:
                # Get the first result's document text
                document = results[0].get('document', {})
                excerpt = document.get('excerpt', {})
                text = excerpt.get('text', '')
                return text
            
            return ""
            
        finally:
            # Clean up session
            try:
                q_connect_client.delete_session(
                    assistantId=self.assistant_id,
                    sessionId=session_id
                )
            except Exception as e:
                self.logger.warning(
                    "Failed to delete test session",
                    extra={"sessionId": session_id, "error": str(e)}
                )
    
    def _evaluate_response(
        self,
        test_query: TestQuery,
        response: str
    ) -> TestResult:
        """
        Evaluate agent response against expected behavior.
        
        Args:
            test_query: Test query with expected behavior
            response: Agent response text
            
        Returns:
            TestResult with evaluation
        """
        response_lower = response.lower()
        
        # Count keyword matches
        keyword_matches = sum(
            1 for keyword in test_query.keywords
            if keyword.lower() in response_lower
        )
        
        # Evaluate based on expected behavior
        passed = False
        evaluation_details = {
            "keywordMatches": keyword_matches,
            "totalKeywords": len(test_query.keywords),
            "matchedKeywords": [
                kw for kw in test_query.keywords
                if kw.lower() in response_lower
            ]
        }
        
        if test_query.expected_behavior == "SHOULD_EXPLAIN_UNAVAILABLE":
            # Should contain unavailability keywords
            passed = keyword_matches >= 2
            
            # For intent-specific tests, add more context
            if test_query.intent_name:
                evaluation_details["intentName"] = test_query.intent_name
                evaluation_details["reason"] = (
                    f"Intent '{test_query.intent_name}' correctly rejected with unavailability explanation"
                    if passed else f"Intent '{test_query.intent_name}' not properly rejected"
                )
            else:
                evaluation_details["reason"] = (
                    "Response contains unavailability explanation"
                    if passed else "Response missing unavailability explanation"
                )
        
        elif test_query.expected_behavior == "SHOULD_HANDLE_NORMALLY":
            # Should NOT contain unavailability keywords
            unavailable_keywords = ["unavailable", "currently unavailable", "apologize", "temporarily"]
            has_unavailable = any(kw in response_lower for kw in unavailable_keywords)
            passed = not has_unavailable and len(response) > 0
            
            # For intent-specific tests, add more context
            if test_query.intent_name:
                evaluation_details["intentName"] = test_query.intent_name
                evaluation_details["reason"] = (
                    f"Intent '{test_query.intent_name}' handled normally"
                    if passed else f"Intent '{test_query.intent_name}' incorrectly mentions unavailability"
                )
            else:
                evaluation_details["reason"] = (
                    "Response handles query normally"
                    if passed else "Response incorrectly mentions unavailability"
                )
        
        elif test_query.expected_behavior == "SHOULD_OFFER_ALTERNATIVE":
            # Should contain alternative suggestions
            passed = keyword_matches >= 1
            evaluation_details["reason"] = (
                "Response offers alternatives"
                if passed else "Response missing alternative suggestions"
            )
        
        # Negative keyword check
        if test_query.negative_keywords:
            found_negative = [
                nk for nk in test_query.negative_keywords
                if nk.lower() in response_lower
            ]
            evaluation_details["negativeKeywords"] = test_query.negative_keywords
            if found_negative:
                passed = False
                evaluation_details["negativeKeywordFound"] = found_negative
        
        # Minimum response length check
        evaluation_details["responseLength"] = len(response)
        if len(response) < 20:
            passed = False
        
        return TestResult(
            query=test_query.query,
            expected_behavior=test_query.expected_behavior,
            actual_response=response,
            passed=passed,
            critical=test_query.critical,
            evaluation_details=evaluation_details,
            intent_name=test_query.intent_name
        )
    
    def _build_test_execution_report(
        self,
        agent_id: str,
        test_results: List[TestResult]
    ) -> TestExecution:
        """
        Build test execution report from results.
        
        Args:
            agent_id: AI Agent ID
            test_results: List of test results
            
        Returns:
            TestExecution report
        """
        total_tests = len(test_results)
        passed = sum(1 for r in test_results if r.passed)
        failed = total_tests - passed
        critical_failures = sum(1 for r in test_results if not r.passed and r.critical)
        
        # Build sample responses (first 3 results)
        sample_responses = []
        for result in test_results[:3]:
            sample_responses.append({
                "query": result.query,
                "response": result.actual_response[:200],  # Truncate for brevity
                "passed": result.passed,
                "intentName": result.intent_name
            })
        
        return TestExecution(
            agent_id=agent_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            critical_failures=critical_failures,
            results=test_results,
            sample_responses=sample_responses
        )
    
    def _log_test_execution(
        self,
        agent_id: str,
        test_execution: TestExecution,
        event: Dict[str, Any]
    ):
        """
        Log test execution to audit logs.
        
        Args:
            agent_id: AI Agent ID
            test_execution: Test execution results
            event: Original Lambda event
        """
        try:
            caller_phone = event.get('metadata', {}).get('callerPhoneNumber', 'system')
            
            self.audit_logger.log_operation(
                operation="TEST",
                agent_id=agent_id,
                caller_phone_number=caller_phone,
                result="SUCCESS" if test_execution.critical_failures == 0 else "FAILURE",
                details={
                    "totalTests": test_execution.total_tests,
                    "passed": test_execution.passed,
                    "failed": test_execution.failed,
                    "criticalFailures": test_execution.critical_failures,
                    "timestamp": test_execution.timestamp
                }
            )
        except Exception as e:
            self.logger.warning(
                "Failed to write test execution audit log",
                extra={"error": str(e)}
            )


# Lambda handler instance (lazy initialization)
_handler_instance = None


def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler entry point.
    
    Args:
        event: Lambda event
        context: Lambda context
        
        Returns:
        Test execution results
    """
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = TesterHandler()
    return _handler_instance.handler(event, context)
