"""
Tests for Agent Manager multi-agent support.

Tests the update_agents operation that handles multiple agents in a single call.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from botocore.exceptions import ClientError

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from agent_manager.handler import AgentManagerHandler


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv('AWS_REGION', 'us-east-1')
    monkeypatch.setenv('ASSISTANT_ID', 'test-assistant-id')
    monkeypatch.setenv('BACKUP_BUCKET', 'test-backup-bucket')
    monkeypatch.setenv('BACKUP_LAMBDA_ARN', 'arn:aws:lambda:us-east-1:123456789012:function:backup')
    monkeypatch.setenv('TESTER_LAMBDA_ARN', 'arn:aws:lambda:us-east-1:123456789012:function:tester')
    monkeypatch.setenv('CONNECT_INSTANCE_ARN', 'arn:aws:connect:us-east-1:123456789012:instance/test-instance')
    monkeypatch.setenv('LOG_LEVEL', 'INFO')


@pytest.fixture
def mock_context():
    """Create mock Lambda context."""
    context = Mock()
    context.function_name = 'test-agent-manager'
    context.request_id = 'test-request-id'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-agent-manager'
    return context


@pytest.fixture
def handler(mock_env_vars):
    """Create handler instance with mocked AWS clients."""
    with patch('shared.aws_clients.AWSClients') as mock_aws_clients:
        # Mock the client factory methods
        mock_aws_clients.get_q_connect_client.return_value = Mock()
        mock_aws_clients.get_lambda_client.return_value = Mock()
        mock_aws_clients.get_s3_client.return_value = Mock()
        
        handler = AgentManagerHandler()
        handler.q_connect = Mock()
        handler.lambda_client = Mock()
        handler.s3_client = Mock()
        handler.audit_logger = Mock()
        return handler


class TestMultiAgentUpdate:
    """Test multi-agent update functionality."""
    
    def test_update_agents_missing_agent_ids(self, handler, mock_context):
        """Test that update_agents raises error when agentIds is missing."""
        event = {
            'operation': 'update_agents',
            'outageInfo': {
                'affectedServices': ['payment'],
                'availableServices': ['inquiry'],
                'estimatedRecoveryTime': '2 hours'
            },
            'callerPhoneNumber': '+12345678901'
        }
        
        with pytest.raises(ValueError, match="Missing required field: agentIds"):
            handler.update_agents(event, mock_context)
    
    def test_update_agents_invalid_agent_ids_type(self, handler, mock_context):
        """Test that update_agents raises error when agentIds is not a list."""
        event = {
            'operation': 'update_agents',
            'agentIds': 'not-a-list',
            'outageInfo': {
                'affectedServices': ['payment'],
                'availableServices': ['inquiry']
            },
            'callerPhoneNumber': '+12345678901'
        }
        
        with pytest.raises(ValueError, match="agentIds must be a list"):
            handler.update_agents(event, mock_context)
    
    def test_update_agents_missing_outage_info(self, handler, mock_context):
        """Test that update_agents raises error when outageInfo is missing."""
        event = {
            'operation': 'update_agents',
            'agentIds': ['agent-1', 'agent-2'],
            'callerPhoneNumber': '+12345678901'
        }
        
        with pytest.raises(ValueError, match="Missing required field: outageInfo"):
            handler.update_agents(event, mock_context)
    
    def test_update_agents_empty_list(self, handler, mock_context):
        """Test that update_agents raises error when agentIds is empty."""
        event = {
            'operation': 'update_agents',
            'agentIds': [],
            'outageInfo': {
                'affectedServices': ['payment'],
                'availableServices': ['inquiry']
            },
            'callerPhoneNumber': '+12345678901'
        }
        
        with pytest.raises(ValueError, match="Missing required field: agentIds"):
            handler.update_agents(event, mock_context)
    
    def test_update_agents_single_agent_success(self, handler, mock_context):
        """Test update_agents with single agent (successful update)."""
        # Mock _get_ai_agent_with_retry response
        with patch.object(handler, '_get_ai_agent_with_retry') as mock_get_agent:
            mock_get_agent.return_value = {
                'aiAgent': {
                    'aiAgentId': 'agent-1',
                    'name': 'Voice Agent',
                    'type': 'ORCHESTRATION',
                    'status': 'ACTIVE'
                }
            }
            
            # Mock update_agent to return success
            with patch.object(handler, 'update_agent') as mock_update:
                mock_update.return_value = {
                    'success': True,
                    'backupLocation': 's3://bucket/backups/agent-1/backup.json',
                    'testResults': {
                        'totalTests': 5,
                        'passed': 5,
                        'failed': 0
                    }
                }
                
                event = {
                    'operation': 'update_agents',
                    'agentIds': ['agent-1'],
                    'outageInfo': {
                        'affectedServices': ['payment'],
                        'availableServices': ['inquiry'],
                        'estimatedRecoveryTime': '2 hours'
                    },
                    'callerPhoneNumber': '+12345678901'
                }
                
                result = handler.update_agents(event, mock_context)
                
                assert result['success'] is True
                assert result['totalAgents'] == 1
                assert result['successfulUpdates'] == 1
                assert result['failedUpdates'] == 0
                assert len(result['results']) == 1
                
                agent_result = result['results'][0]
                assert agent_result['agentId'] == 'agent-1'
                assert agent_result['agentName'] == 'Voice Agent'
                assert agent_result['agentType'] == 'ORCHESTRATION'
                assert agent_result['success'] is True
                assert 'backupLocation' in agent_result
                assert 'testResults' in agent_result
    
    def test_update_agents_multiple_agents_all_success(self, handler, mock_context):
        """Test update_agents with multiple agents (all successful)."""
        # Mock _get_ai_agent_with_retry responses
        def mock_get_agent(agent_id):
            agents = {
                'agent-1': {'aiAgent': {'aiAgentId': 'agent-1', 'name': 'Voice Agent', 'type': 'ORCHESTRATION'}},
                'agent-2': {'aiAgent': {'aiAgentId': 'agent-2', 'name': 'Chat Agent', 'type': 'ORCHESTRATION'}},
                'agent-3': {'aiAgent': {'aiAgentId': 'agent-3', 'name': 'Email Agent', 'type': 'ORCHESTRATION'}}
            }
            return agents[agent_id]
        
        with patch.object(handler, '_get_ai_agent_with_retry') as mock_get:
            mock_get.side_effect = mock_get_agent
            
            # Mock update_agent to return success for all
            with patch.object(handler, 'update_agent') as mock_update:
                mock_update.return_value = {
                    'success': True,
                    'backupLocation': 's3://bucket/backups/backup.json',
                    'testResults': {'totalTests': 5, 'passed': 5, 'failed': 0}
                }
                
                event = {
                    'operation': 'update_agents',
                    'agentIds': ['agent-1', 'agent-2', 'agent-3'],
                    'outageInfo': {
                        'affectedServices': ['payment'],
                        'availableServices': ['inquiry']
                    },
                    'callerPhoneNumber': '+12345678901'
                }
                
                result = handler.update_agents(event, mock_context)
                
                assert result['success'] is True
                assert result['totalAgents'] == 3
                assert result['successfulUpdates'] == 3
                assert result['failedUpdates'] == 0
                assert len(result['results']) == 3
                
                # Verify each agent result
                for agent_result in result['results']:
                    assert agent_result['success'] is True
                    assert 'agentName' in agent_result
                    assert 'agentType' in agent_result
    
    def test_update_agents_multiple_agents_partial_failure(self, handler, mock_context):
        """Test update_agents with multiple agents (some failures)."""
        # Mock _get_ai_agent_with_retry responses
        def mock_get_agent(agent_id):
            agents = {
                'agent-1': {'aiAgent': {'aiAgentId': 'agent-1', 'name': 'Voice Agent', 'type': 'ORCHESTRATION'}},
                'agent-2': {'aiAgent': {'aiAgentId': 'agent-2', 'name': 'Chat Agent', 'type': 'ORCHESTRATION'}},
                'agent-3': {'aiAgent': {'aiAgentId': 'agent-3', 'name': 'Email Agent', 'type': 'ORCHESTRATION'}}
            }
            return agents[agent_id]
        
        with patch.object(handler, '_get_ai_agent_with_retry') as mock_get:
            mock_get.side_effect = mock_get_agent
            
            # Mock update_agent to return mixed results
            def mock_update_side_effect(event, context):
                agent_id = event['agentId']
                if agent_id == 'agent-2':
                    return {
                        'success': False,
                        'error': 'Backup failed'
                    }
                return {
                    'success': True,
                    'backupLocation': f's3://bucket/backups/{agent_id}/backup.json',
                    'testResults': {'totalTests': 5, 'passed': 5, 'failed': 0}
                }
            
            with patch.object(handler, 'update_agent') as mock_update:
                mock_update.side_effect = mock_update_side_effect
                
                event = {
                    'operation': 'update_agents',
                    'agentIds': ['agent-1', 'agent-2', 'agent-3'],
                    'outageInfo': {
                        'affectedServices': ['payment'],
                        'availableServices': ['inquiry']
                    },
                    'callerPhoneNumber': '+12345678901'
                }
                
                result = handler.update_agents(event, mock_context)
                
                assert result['success'] is False  # Overall failure due to partial failure
                assert result['totalAgents'] == 3
                assert result['successfulUpdates'] == 2
                assert result['failedUpdates'] == 1
                assert len(result['results']) == 3
                
                # Verify agent-2 failed
                agent_2_result = next(r for r in result['results'] if r['agentId'] == 'agent-2')
                assert agent_2_result['success'] is False
                assert 'error' in agent_2_result
    
    def test_update_agents_continues_after_single_failure(self, handler, mock_context):
        """Test that update_agents continues processing other agents after one fails."""
        # Mock _get_ai_agent_with_retry to fail for agent-2
        def mock_get_agent(agent_id):
            if agent_id == 'agent-2':
                raise ClientError(
                    {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Agent not found'}},
                    'GetAIAgent'
                )
            return {
                'aiAgent': {
                    'aiAgentId': agent_id,
                    'name': f'Agent {agent_id}',
                    'type': 'ORCHESTRATION'
                }
            }
        
        with patch.object(handler, '_get_ai_agent_with_retry') as mock_get:
            mock_get.side_effect = mock_get_agent
            
            with patch.object(handler, 'update_agent') as mock_update:
                mock_update.return_value = {
                    'success': True,
                    'backupLocation': 's3://bucket/backups/backup.json',
                    'testResults': {'totalTests': 5, 'passed': 5, 'failed': 0}
                }
                
                event = {
                    'operation': 'update_agents',
                    'agentIds': ['agent-1', 'agent-2', 'agent-3'],
                    'outageInfo': {
                        'affectedServices': ['payment'],
                        'availableServices': ['inquiry']
                    },
                    'callerPhoneNumber': '+12345678901'
                }
                
                result = handler.update_agents(event, mock_context)
                
                # Should have processed all 3 agents despite agent-2 failure
                assert result['totalAgents'] == 3
                assert result['successfulUpdates'] == 2
                assert result['failedUpdates'] == 1
                assert len(result['results']) == 3
                
                # Verify agent-2 has error
                agent_2_result = next(r for r in result['results'] if r['agentId'] == 'agent-2')
                assert agent_2_result['success'] is False
                assert 'error' in agent_2_result
    
    def test_update_agents_supports_different_agent_types(self, handler, mock_context):
        """Test that update_agents supports voice, chat, and email agent types."""
        # Mock _get_ai_agent_with_retry responses with different types
        def mock_get_agent(agent_id):
            agents = {
                'voice-agent': {'aiAgent': {'aiAgentId': 'voice-agent', 'name': 'Voice Agent', 'type': 'ORCHESTRATION'}},
                'chat-agent': {'aiAgent': {'aiAgentId': 'chat-agent', 'name': 'Chat Agent', 'type': 'ORCHESTRATION'}},
                'email-agent': {'aiAgent': {'aiAgentId': 'email-agent', 'name': 'Email Agent', 'type': 'ORCHESTRATION'}}
            }
            return agents[agent_id]
        
        with patch.object(handler, '_get_ai_agent_with_retry') as mock_get:
            mock_get.side_effect = mock_get_agent
            
            with patch.object(handler, 'update_agent') as mock_update:
                mock_update.return_value = {
                    'success': True,
                    'backupLocation': 's3://bucket/backups/backup.json',
                    'testResults': {'totalTests': 5, 'passed': 5, 'failed': 0}
                }
                
                event = {
                    'operation': 'update_agents',
                    'agentIds': ['voice-agent', 'chat-agent', 'email-agent'],
                    'outageInfo': {
                        'affectedServices': ['payment'],
                        'availableServices': ['inquiry']
                    },
                    'callerPhoneNumber': '+12345678901'
                }
                
                result = handler.update_agents(event, mock_context)
                
                assert result['success'] is True
                assert result['totalAgents'] == 3
                
                # Verify all agent types are present
                agent_types = [r['agentType'] for r in result['results']]
                assert all(t == 'ORCHESTRATION' for t in agent_types)
    
    def test_update_agents_individual_status_reporting(self, handler, mock_context):
        """Test that update_agents reports status individually for each agent."""
        # Mock _get_ai_agent_with_retry responses
        def mock_get_agent(agent_id):
            return {
                'aiAgent': {
                    'aiAgentId': agent_id,
                    'name': f'Agent {agent_id}',
                    'type': 'ORCHESTRATION'
                }
            }
        
        with patch.object(handler, '_get_ai_agent_with_retry') as mock_get:
            mock_get.side_effect = mock_get_agent
            
            # Mock update_agent with different results
            def mock_update_side_effect(event, context):
                agent_id = event['agentId']
                if agent_id == 'agent-2':
                    return {'success': False, 'error': 'Test execution failed'}
                return {
                    'success': True,
                    'backupLocation': f's3://bucket/backups/{agent_id}/backup.json',
                    'testResults': {'totalTests': 5, 'passed': 5, 'failed': 0}
                }
            
            with patch.object(handler, 'update_agent') as mock_update:
                mock_update.side_effect = mock_update_side_effect
                
                event = {
                    'operation': 'update_agents',
                    'agentIds': ['agent-1', 'agent-2', 'agent-3'],
                    'outageInfo': {
                        'affectedServices': ['payment'],
                        'availableServices': ['inquiry']
                    },
                    'callerPhoneNumber': '+12345678901'
                }
                
                result = handler.update_agents(event, mock_context)
                
                # Verify individual status for each agent
                for agent_result in result['results']:
                    assert 'agentId' in agent_result
                    assert 'agentName' in agent_result
                    assert 'agentType' in agent_result
                    assert 'success' in agent_result
                    
                    if agent_result['success']:
                        assert 'backupLocation' in agent_result
                        assert 'testResults' in agent_result
                    else:
                        assert 'error' in agent_result


class TestMultiAgentRouting:
    """Test that update_agents operation is properly routed."""
    
    def test_process_event_routes_to_update_agents(self, handler, mock_context):
        """Test that process_event routes update_agents operation correctly."""
        with patch.object(handler, 'update_agents') as mock_update_agents:
            mock_update_agents.return_value = {
                'success': True,
                'totalAgents': 2,
                'successfulUpdates': 2,
                'failedUpdates': 0,
                'results': []
            }
            
            event = {
                'operation': 'update_agents',
                'agentIds': ['agent-1', 'agent-2'],
                'outageInfo': {'affectedServices': ['payment']},
                'callerPhoneNumber': '+12345678901'
            }
            
            result = handler.process_event(event, mock_context)
            
            mock_update_agents.assert_called_once_with(event, mock_context)
            assert result['success'] is True
