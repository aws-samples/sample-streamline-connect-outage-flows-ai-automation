"""
Unit tests for Tester Lambda intent-specific testing support.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from tester.handler import TesterHandler, TestQuery, TestResult


@pytest.fixture
def tester_handler():
    """Create TesterHandler instance with mocked dependencies."""
    with patch.dict(os.environ, {
        'ASSISTANT_ID': 'test-assistant-id',
        'BACKUP_BUCKET': 'test-backup-bucket',
        'LOG_LEVEL': 'INFO'
    }):
        handler = TesterHandler()
        handler.aws_clients = Mock()
        handler.audit_logger = Mock()
        return handler


class TestIntentTestQueryGeneration:
    """Test intent-specific test query generation."""
    
    def test_generate_disabled_intent_queries(self, tester_handler):
        """Test generating queries for disabled intents."""
        intent_test_config = {
            'disabledIntents': [
                {
                    'name': 'change_pin',
                    'testQuery': 'I want to change my PIN'
                },
                {
                    'name': 'transfer_funds',
                    'testQuery': 'Can I transfer money?'
                }
            ],
            'enabledIntents': []
        }
        
        queries = tester_handler._generate_intent_test_queries(intent_test_config)
        
        assert len(queries) == 2
        assert all(q.expected_behavior == "SHOULD_EXPLAIN_UNAVAILABLE" for q in queries)
        assert all(q.critical for q in queries)
        assert queries[0].intent_name == 'change_pin'
        assert queries[1].intent_name == 'transfer_funds'
    
    def test_generate_enabled_intent_queries(self, tester_handler):
        """Test generating queries for enabled intents."""
        intent_test_config = {
            'disabledIntents': [],
            'enabledIntents': [
                {
                    'name': 'check_balance',
                    'testQuery': 'What is my balance?'
                },
                {
                    'name': 'view_transactions',
                    'testQuery': 'Show me my transactions'
                }
            ]
        }
        
        queries = tester_handler._generate_intent_test_queries(intent_test_config)
        
        assert len(queries) == 2
        assert all(q.expected_behavior == "SHOULD_HANDLE_NORMALLY" for q in queries)
        assert all(q.critical for q in queries)
        assert queries[0].intent_name == 'check_balance'
        assert queries[1].intent_name == 'view_transactions'
    
    def test_generate_mixed_intent_queries(self, tester_handler):
        """Test generating queries for both disabled and enabled intents."""
        intent_test_config = {
            'disabledIntents': [
                {
                    'name': 'change_pin',
                    'testQuery': 'I want to change my PIN'
                }
            ],
            'enabledIntents': [
                {
                    'name': 'check_balance',
                    'testQuery': 'What is my balance?'
                }
            ]
        }
        
        queries = tester_handler._generate_intent_test_queries(intent_test_config)
        
        assert len(queries) == 2
        
        # First query should be for disabled intent
        assert queries[0].intent_name == 'change_pin'
        assert queries[0].expected_behavior == "SHOULD_EXPLAIN_UNAVAILABLE"
        
        # Second query should be for enabled intent
        assert queries[1].intent_name == 'check_balance'
        assert queries[1].expected_behavior == "SHOULD_HANDLE_NORMALLY"
    
    def test_default_test_query_generation(self, tester_handler):
        """Test default query generation when no test query provided."""
        intent_test_config = {
            'disabledIntents': [
                {
                    'name': 'change_pin'
                    # No testQuery provided
                }
            ],
            'enabledIntents': []
        }
        
        queries = tester_handler._generate_intent_test_queries(intent_test_config)
        
        assert len(queries) == 1
        assert queries[0].query == "I want to change_pin"  # Default format


class TestIntentSpecificEvaluation:
    """Test intent-specific response evaluation."""
    
    def test_evaluate_disabled_intent_correct_rejection(self, tester_handler):
        """Test evaluation of correctly rejected disabled intent."""
        test_query = TestQuery(
            query="I want to change my PIN",
            expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
            keywords=["unavailable", "temporarily", "apologize"],
            critical=True,
            intent_name="change_pin"
        )
        
        response = "I apologize, but the PIN change feature is temporarily unavailable."
        
        result = tester_handler._evaluate_response(test_query, response)
        
        assert result.passed
        assert result.intent_name == "change_pin"
        assert "change_pin" in result.evaluation_details["reason"]
        assert "correctly rejected" in result.evaluation_details["reason"]
    
    def test_evaluate_disabled_intent_incorrect_handling(self, tester_handler):
        """Test evaluation of incorrectly handled disabled intent."""
        test_query = TestQuery(
            query="I want to change my PIN",
            expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
            keywords=["unavailable", "temporarily", "apologize"],
            critical=True,
            intent_name="change_pin"
        )
        
        response = "Sure, I can help you change your PIN. What would you like it to be?"
        
        result = tester_handler._evaluate_response(test_query, response)
        
        assert not result.passed
        assert result.intent_name == "change_pin"
        assert "change_pin" in result.evaluation_details["reason"]
        assert "not properly rejected" in result.evaluation_details["reason"]
    
    def test_evaluate_enabled_intent_normal_handling(self, tester_handler):
        """Test evaluation of correctly handled enabled intent."""
        test_query = TestQuery(
            query="What is my balance?",
            expected_behavior="SHOULD_HANDLE_NORMALLY",
            keywords=["balance", "account"],
            critical=True,
            intent_name="check_balance"
        )
        
        response = "Your current account balance is $1,234.56."
        
        result = tester_handler._evaluate_response(test_query, response)
        
        assert result.passed
        assert result.intent_name == "check_balance"
        assert "check_balance" in result.evaluation_details["reason"]
        assert "handled normally" in result.evaluation_details["reason"]
    
    def test_evaluate_enabled_intent_incorrect_unavailability(self, tester_handler):
        """Test evaluation of enabled intent incorrectly marked unavailable."""
        test_query = TestQuery(
            query="What is my balance?",
            expected_behavior="SHOULD_HANDLE_NORMALLY",
            keywords=["balance", "account"],
            critical=True,
            intent_name="check_balance"
        )
        
        response = "I apologize, but balance checking is currently unavailable."
        
        result = tester_handler._evaluate_response(test_query, response)
        
        assert not result.passed
        assert result.intent_name == "check_balance"
        assert "check_balance" in result.evaluation_details["reason"]
        assert "incorrectly mentions unavailability" in result.evaluation_details["reason"]


class TestIntentResultsSummary:
    """Test intent-specific results summary generation."""
    
    def test_build_intent_results_summary(self, tester_handler):
        """Test building summary of results grouped by intent."""
        test_results = [
            TestResult(
                query="Change PIN",
                expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
                actual_response="Unavailable",
                passed=True,
                critical=True,
                intent_name="change_pin"
            ),
            TestResult(
                query="Check balance",
                expected_behavior="SHOULD_HANDLE_NORMALLY",
                actual_response="Balance is $100",
                passed=True,
                critical=True,
                intent_name="check_balance"
            ),
            TestResult(
                query="Transfer funds",
                expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
                actual_response="Sure, transferring",
                passed=False,
                critical=True,
                intent_name="transfer_funds"
            )
        ]
        
        summary = tester_handler._build_intent_results_summary(test_results)
        
        assert len(summary) == 3
        assert summary["change_pin"]["totalTests"] == 1
        assert summary["change_pin"]["passed"] == 1
        assert summary["change_pin"]["failed"] == 0
        
        assert summary["check_balance"]["totalTests"] == 1
        assert summary["check_balance"]["passed"] == 1
        
        assert summary["transfer_funds"]["totalTests"] == 1
        assert summary["transfer_funds"]["passed"] == 0
        assert summary["transfer_funds"]["failed"] == 1
    
    def test_build_intent_results_summary_multiple_tests_per_intent(self, tester_handler):
        """Test summary with multiple tests for same intent."""
        test_results = [
            TestResult(
                query="Change PIN test 1",
                expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
                actual_response="Unavailable",
                passed=True,
                critical=True,
                intent_name="change_pin"
            ),
            TestResult(
                query="Change PIN test 2",
                expected_behavior="SHOULD_EXPLAIN_UNAVAILABLE",
                actual_response="Available",
                passed=False,
                critical=True,
                intent_name="change_pin"
            )
        ]
        
        summary = tester_handler._build_intent_results_summary(test_results)
        
        assert len(summary) == 1
        assert summary["change_pin"]["totalTests"] == 2
        assert summary["change_pin"]["passed"] == 1
        assert summary["change_pin"]["failed"] == 1
    
    def test_build_intent_results_summary_no_intent_tests(self, tester_handler):
        """Test summary with no intent-specific tests."""
        test_results = [
            TestResult(
                query="General query",
                expected_behavior="SHOULD_HANDLE_NORMALLY",
                actual_response="Response",
                passed=True,
                critical=False,
                intent_name=None
            )
        ]
        
        summary = tester_handler._build_intent_results_summary(test_results)
        
        assert len(summary) == 0


class TestIntentTestConfiguration:
    """Test intent test configuration handling."""
    
    def test_process_event_with_intent_test_config(self, tester_handler):
        """Test processing event with intent test configuration."""
        event = {
            'agentId': 'test-agent-id',
            'testScenario': 'intent-test',
            'intentTestConfig': {
                'disabledIntents': [
                    {
                        'name': 'change_pin',
                        'testQuery': 'I want to change my PIN'
                    }
                ],
                'enabledIntents': [
                    {
                        'name': 'check_balance',
                        'testQuery': 'What is my balance?'
                    }
                ]
            }
        }
        
        # Mock the query agent method
        tester_handler._query_agent = Mock(side_effect=[
            "I apologize, but PIN changes are temporarily unavailable.",
            "Your balance is $1,234.56."
        ])
        
        context = Mock()
        result = tester_handler.process_event(event, context)
        
        assert result['success']
        assert result['totalTests'] == 2
        assert result['passed'] == 2
        assert result['failed'] == 0
        assert result['criticalFailures'] == 0
        assert 'intentResults' in result
        assert len(result['intentResults']) == 2
    
    def test_get_test_queries_with_intent_config(self, tester_handler):
        """Test getting test queries with intent configuration."""
        intent_test_config = {
            'disabledIntents': [
                {
                    'name': 'change_pin',
                    'testQuery': 'Change my PIN'
                }
            ],
            'enabledIntents': []
        }
        
        queries = tester_handler._get_test_queries_for_scenario(
            'intent-test',
            {},
            intent_test_config
        )
        
        assert len(queries) == 1
        assert queries[0].intent_name == 'change_pin'
        assert queries[0].expected_behavior == "SHOULD_EXPLAIN_UNAVAILABLE"
    
    def test_get_test_queries_without_intent_config(self, tester_handler):
        """Test getting test queries without intent configuration (default behavior)."""
        queries = tester_handler._get_test_queries_for_scenario(
            'default',
            {},
            None
        )
        
        # Should return default test queries
        assert len(queries) > 0
        # Default queries don't have intent names
        assert all(q.intent_name is None for q in queries)
