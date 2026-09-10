"""Unit tests for Tester Lambda handler."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from tester.handler import TesterHandler, TestQuery, TestResult, TestExecution


@pytest.fixture
def tester_handler():
    """Create TesterHandler instance with mocked dependencies."""
    with patch.dict(os.environ, {
        'ASSISTANT_ID': 'test-assistant-id',
        'BACKUP_BUCKET': 'test-bucket',
        'LOG_LEVEL': 'INFO'
    }):
        handler = TesterHandler()
        handler.audit_logger = Mock()
        return handler


@pytest.fixture
def mock_context():
    """Create mock Lambda context."""
    context = Mock()
    context.request_id = 'test-request-id'
    context.function_name = 'test-function'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test'
    return context


@pytest.fixture
def sample_test_queries():
    """Sample test queries for testing."""
    return [
        TestQuery(
            query="I need to make a payment",
            expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
            keywords=["unavailable", "currently", "apologize"],
            critical=True
        ),
        TestQuery(
            query="What's my account balance?",
            expected_behavior="SHOULD_HANDLE_NORMALLY",
            keywords=["balance", "account"],
            critical=False
        ),
        TestQuery(
            query="What else can I do?",
            expected_behavior="SHOULD_OFFER_ALTERNATIVE",
            keywords=["available", "can", "help"],
            critical=False
        )
    ]


class TestTesterHandler:
    """Test suite for TesterHandler."""
    
    def test_load_default_test_config(self, tester_handler):
        """Test loading default test configuration."""
        # Load config through ConfigLoader
        config = tester_handler.config_loader.load_config(agent_id=None)
        
        assert config.test_queries is not None
        assert len(config.test_queries) > 0
        
        # Verify structure of first query
        first_query = config.test_queries[0]
        assert 'query' in first_query
        assert 'expectedBehavior' in first_query
        assert 'keywords' in first_query
        assert 'critical' in first_query
    
    def test_get_test_queries_for_scenario(self, tester_handler):
        """Test getting test queries for a scenario."""
        test_queries = tester_handler._get_test_queries_for_scenario(
            test_scenario='default',
            outage_info={}
        )
        
        assert len(test_queries) > 0
        assert all(isinstance(q, TestQuery) for q in test_queries)
    
    def test_customize_queries_for_outage(self, tester_handler, sample_test_queries):
        """Test customizing queries based on outage information."""
        outage_info = {
            'affectedServices': ['payment', 'transfer'],
            'availableServices': ['balance check', 'order status']
        }
        
        customized = tester_handler._customize_queries_for_outage(
            sample_test_queries,
            outage_info
        )
        
        # Should have original queries plus customized ones
        assert len(customized) > len(sample_test_queries)
        
        # Check for affected service queries
        affected_queries = [q for q in customized if 'payment' in q.query.lower()]
        assert len(affected_queries) > 0
        assert affected_queries[0].expected_behavior == "SHOULD_EXPLAIN_UNAVAILABLE"
    
    def test_evaluate_response_unavailable(self, tester_handler):
        """Test evaluating response for unavailable service."""
        test_query = TestQuery(
            query="I need to make a payment",
            expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
            keywords=["unavailable", "currently", "apologize"],
            critical=True
        )
        
        response = "I apologize, but payment services are currently unavailable."
        
        result = tester_handler._evaluate_response(test_query, response)
        
        assert result.passed is True
        assert result.critical is True
        assert result.expected_behavior == "SHOULD_EXPLAIN_UNAVAILABLE"
        assert result.evaluation_details['keywordMatches'] >= 1
    
    def test_evaluate_response_unavailable_missing_keywords(self, tester_handler):
        """Test evaluating response missing unavailability keywords."""
        test_query = TestQuery(
            query="I need to make a payment",
            expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
            keywords=["unavailable", "currently", "apologize"],
            critical=True
        )
        
        response = "Sure, I can help you with that!"
        
        result = tester_handler._evaluate_response(test_query, response)
        
        assert result.passed is False
        assert result.critical is True
    
    def test_evaluate_response_handle_normally(self, tester_handler):
        """Test evaluating response for normal handling."""
        test_query = TestQuery(
            query="What's my account balance?",
            expected_behavior="SHOULD_HANDLE_NORMALLY",
            keywords=["balance", "account"],
            critical=False
        )
        
        response = "I can help you check your account balance. Let me look that up for you."
        
        result = tester_handler._evaluate_response(test_query, response)
        
        assert result.passed is True
        assert result.critical is False
    
    def test_evaluate_response_handle_normally_with_unavailable(self, tester_handler):
        """Test evaluating response that incorrectly mentions unavailability."""
        test_query = TestQuery(
            query="What's my account balance?",
            expected_behavior="SHOULD_HANDLE_NORMALLY",
            keywords=["balance", "account"],
            critical=False
        )
        
        response = "I apologize, but that service is currently unavailable."
        
        result = tester_handler._evaluate_response(test_query, response)
        
        assert result.passed is False
    
    def test_evaluate_response_offer_alternative(self, tester_handler):
        """Test evaluating response offering alternatives."""
        test_query = TestQuery(
            query="What else can I do?",
            expected_behavior="SHOULD_OFFER_ALTERNATIVE",
            keywords=["available", "can", "help"],
            critical=False
        )
        
        response = "You can check your balance, view order status, or I can help with other available services."
        
        result = tester_handler._evaluate_response(test_query, response)
        
        assert result.passed is True
        assert result.evaluation_details['keywordMatches'] >= 1
    
    def test_build_test_execution_report(self, tester_handler):
        """Test building test execution report."""
        test_results = [
            TestResult(
                query="Query 1",
                expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
                actual_response="Response 1",
                passed=True,
                critical=True
            ),
            TestResult(
                query="Query 2",
                expected_behavior="SHOULD_HANDLE_NORMALLY",
                actual_response="Response 2",
                passed=True,
                critical=False
            ),
            TestResult(
                query="Query 3",
                expected_behavior="SHOULD_OFFER_ALTERNATIVE",
                actual_response="Response 3",
                passed=False,
                critical=False
            )
        ]
        
        report = tester_handler._build_test_execution_report(
            agent_id='test-agent-id',
            test_results=test_results
        )
        
        assert report.agent_id == 'test-agent-id'
        assert report.total_tests == 3
        assert report.passed == 2
        assert report.failed == 1
        assert report.critical_failures == 0
        assert len(report.sample_responses) <= 3
    
    def test_build_test_execution_report_with_critical_failure(self, tester_handler):
        """Test building report with critical failure."""
        test_results = [
            TestResult(
                query="Critical query",
                expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
                actual_response="Wrong response",
                passed=False,
                critical=True
            )
        ]
        
        report = tester_handler._build_test_execution_report(
            agent_id='test-agent-id',
            test_results=test_results
        )
        
        assert report.critical_failures == 1
        assert report.failed == 1
    
    @patch('tester.handler.AWSClients.get_q_connect_client')
    def test_query_agent_success(self, mock_get_client, tester_handler):
        """Test querying agent successfully."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Mock session creation
        mock_client.create_session.return_value = {
            'session': {'sessionId': 'test-session-id'}
        }
        
        # Mock query response
        mock_client.query_assistant.return_value = {
            'results': [
                {
                    'document': {
                        'content': {
                            'text': 'Test response from agent'
                        }
                    }
                }
            ]
        }
        
        response = tester_handler._query_agent('test-agent-id', 'Test query')
        
        assert response == 'Test response from agent'
        mock_client.create_session.assert_called_once()
        mock_client.query_assistant.assert_called_once()
        mock_client.delete_session.assert_called_once()
    
    @patch('tester.handler.AWSClients.get_q_connect_client')
    def test_query_agent_empty_response(self, mock_get_client, tester_handler):
        """Test querying agent with empty response."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        mock_client.create_session.return_value = {
            'session': {'sessionId': 'test-session-id'}
        }
        
        mock_client.query_assistant.return_value = {
            'results': []
        }
        
        response = tester_handler._query_agent('test-agent-id', 'Test query')
        
        assert response == ''
    
    @patch('tester.handler.TesterHandler._query_agent')
    def test_execute_test_queries(self, mock_query, tester_handler, sample_test_queries):
        """Test executing multiple test queries."""
        # Mock agent responses
        mock_query.side_effect = [
            "I apologize, payment services are currently unavailable.",
            "Your account balance is $1,234.56.",
            "You can check your balance or view order status."
        ]
        
        results = tester_handler._execute_test_queries(
            agent_id='test-agent-id',
            test_queries=sample_test_queries
        )
        
        assert len(results) == 3
        assert all(isinstance(r, TestResult) for r in results)
        assert mock_query.call_count == 3
    
    @patch('tester.handler.TesterHandler._query_agent')
    def test_execute_test_queries_with_error(self, mock_query, tester_handler, sample_test_queries):
        """Test executing test queries with an error."""
        # First query succeeds, second fails, third succeeds
        mock_query.side_effect = [
            "Response 1",
            Exception("API Error"),
            "Response 3"
        ]
        
        results = tester_handler._execute_test_queries(
            agent_id='test-agent-id',
            test_queries=sample_test_queries
        )
        
        assert len(results) == 3
        assert results[0].passed is False  # Might fail evaluation
        assert results[1].passed is False  # Error case
        assert "ERROR" in results[1].actual_response
    
    @patch('tester.handler.TesterHandler._execute_test_queries')
    @patch('tester.handler.TesterHandler._get_test_queries_for_scenario')
    def test_process_event_success(
        self,
        mock_get_queries,
        mock_execute,
        tester_handler,
        mock_context,
        sample_test_queries
    ):
        """Test processing event successfully."""
        mock_get_queries.return_value = sample_test_queries
        
        mock_execute.return_value = [
            TestResult(
                query="Query 1",
                expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
                actual_response="Response 1",
                passed=True,
                critical=True
            ),
            TestResult(
                query="Query 2",
                expected_behavior="SHOULD_HANDLE_NORMALLY",
                actual_response="Response 2",
                passed=True,
                critical=False
            )
        ]
        
        event = {
            'agentId': 'test-agent-id',
            'testScenario': 'outage-update',
            'outageInfo': {
                'affectedServices': ['payment'],
                'availableServices': ['balance']
            }
        }
        
        response = tester_handler.process_event(event, mock_context)
        
        assert response['success'] is True
        assert response['agentId'] == 'test-agent-id'
        assert response['totalTests'] == 2
        assert response['passed'] == 2
        assert response['failed'] == 0
        assert response['criticalFailures'] == 0
    
    @patch('tester.handler.TesterHandler._execute_test_queries')
    @patch('tester.handler.TesterHandler._get_test_queries_for_scenario')
    def test_process_event_with_critical_failure(
        self,
        mock_get_queries,
        mock_execute,
        tester_handler,
        mock_context,
        sample_test_queries
    ):
        """Test processing event with critical failure."""
        mock_get_queries.return_value = sample_test_queries
        
        mock_execute.return_value = [
            TestResult(
                query="Critical query",
                expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
                actual_response="Wrong response",
                passed=False,
                critical=True
            )
        ]
        
        event = {
            'agentId': 'test-agent-id',
            'testScenario': 'outage-update'
        }
        
        response = tester_handler.process_event(event, mock_context)
        
        assert response['success'] is False
        assert response['criticalFailures'] == 1
    
    def test_process_event_missing_agent_id(self, tester_handler, mock_context):
        """Test processing event without agent ID."""
        event = {
            'testScenario': 'outage-update'
        }
        
        with pytest.raises(ValueError, match="agentId is required"):
            tester_handler.process_event(event, mock_context)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
