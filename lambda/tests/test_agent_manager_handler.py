"""Tests for Agent Manager Lambda handler."""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from botocore.exceptions import ClientError

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agent_manager.handler import AgentManagerHandler


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up environment variables for tests."""
    monkeypatch.setenv('AWS_REGION', 'us-east-1')
    monkeypatch.setenv('ASSISTANT_ID', 'test-assistant-id')
    monkeypatch.setenv('BACKUP_BUCKET', 'test-backup-bucket')
    monkeypatch.setenv('BACKUP_LAMBDA_ARN', 'arn:aws:lambda:us-east-1:123456789012:function:backup')
    monkeypatch.setenv('TESTER_LAMBDA_ARN', 'arn:aws:lambda:us-east-1:123456789012:function:tester')
    monkeypatch.setenv('CONNECT_INSTANCE_ARN', 'arn:aws:connect:us-east-1:123456789012:instance/test-instance')
    monkeypatch.setenv('LOG_LEVEL', 'INFO')


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


@pytest.fixture
def lambda_context():
    """Create mock Lambda context."""
    context = Mock()
    context.request_id = 'test-request-id'
    context.function_name = 'test-function'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test'
    return context


class TestListAgents:
    """Tests for list_agents operation."""
    
    def test_list_agents_success(self, handler):
        """Test successful agent listing."""
        # Mock API response
        handler.q_connect.list_ai_agents.return_value = {
            'aiAgentSummaries': [
                {
                    'aiAgentId': 'agent-1',
                    'name': 'Production Voice Agent',
                    'type': 'ORCHESTRATION',
                    'status': 'ACTIVE',
                    'description': 'Main voice agent',
                    'visibilityStatus': 'PUBLISHED'
                },
                {
                    'aiAgentId': 'agent-2',
                    'name': 'Production Chat Agent',
                    'type': 'ORCHESTRATION',
                    'status': 'ACTIVE',
                    'description': 'Main chat agent',
                    'visibilityStatus': 'PUBLISHED'
                }
            ]
        }
        
        # Call list_agents
        event = {'operation': 'list_agents'}
        result = handler.list_agents(event)
        
        # Verify result
        assert result['success'] is True
        assert result['count'] == 2
        assert len(result['agents']) == 2
        
        # Verify first agent
        agent1 = result['agents'][0]
        assert agent1['agentId'] == 'agent-1'
        assert agent1['agentName'] == 'Production Voice Agent'
        assert agent1['type'] == 'ORCHESTRATION'
        assert agent1['status'] == 'ACTIVE'
        assert agent1['description'] == 'Main voice agent'
        assert agent1['visibilityStatus'] == 'PUBLISHED'
        
        # Verify API was called correctly
        handler.q_connect.list_ai_agents.assert_called_once()
        call_args = handler.q_connect.list_ai_agents.call_args[1]
        assert call_args['assistantId'] == 'test-assistant-id'
        assert call_args['origin'] == 'CUSTOMER'
        assert call_args['maxResults'] == 100
    
    def test_list_agents_with_origin_filter(self, handler):
        """Test agent listing with origin filter."""
        handler.q_connect.list_ai_agents.return_value = {
            'aiAgentSummaries': []
        }
        
        # Call with SYSTEM origin
        event = {
            'operation': 'list_agents',
            'filters': {'origin': 'SYSTEM'}
        }
        result = handler.list_agents(event)
        
        # Verify origin filter was applied
        call_args = handler.q_connect.list_ai_agents.call_args[1]
        assert call_args['origin'] == 'SYSTEM'
    
    def test_list_agents_pagination(self, handler):
        """Test agent listing with pagination."""
        # Mock paginated responses
        handler.q_connect.list_ai_agents.side_effect = [
            {
                'aiAgentSummaries': [
                    {
                        'aiAgentId': 'agent-1',
                        'name': 'Agent 1',
                        'type': 'ORCHESTRATION',
                        'status': 'ACTIVE',
                        'description': 'First agent'
                    }
                ],
                'nextToken': 'token-1'
            },
            {
                'aiAgentSummaries': [
                    {
                        'aiAgentId': 'agent-2',
                        'name': 'Agent 2',
                        'type': 'ORCHESTRATION',
                        'status': 'ACTIVE',
                        'description': 'Second agent'
                    }
                ]
            }
        ]
        
        # Call list_agents
        event = {'operation': 'list_agents'}
        result = handler.list_agents(event)
        
        # Verify both pages were retrieved
        assert result['count'] == 2
        assert len(result['agents']) == 2
        assert handler.q_connect.list_ai_agents.call_count == 2
        
        # Verify second call included nextToken
        second_call_args = handler.q_connect.list_ai_agents.call_args_list[1][1]
        assert second_call_args['nextToken'] == 'token-1'
    
    def test_list_agents_empty_result(self, handler):
        """Test agent listing with no agents."""
        handler.q_connect.list_ai_agents.return_value = {
            'aiAgentSummaries': []
        }
        
        event = {'operation': 'list_agents'}
        result = handler.list_agents(event)
        
        assert result['success'] is True
        assert result['count'] == 0
        assert result['agents'] == []
    
    def test_list_agents_api_error(self, handler):
        """Test agent listing with API error."""
        # Mock API error
        error_response = {
            'Error': {
                'Code': 'ResourceNotFoundException',
                'Message': 'Assistant not found'
            }
        }
        handler.q_connect.list_ai_agents.side_effect = ClientError(
            error_response,
            'ListAIAgents'
        )
        
        # Verify error is raised
        event = {'operation': 'list_agents'}
        with pytest.raises(ClientError):
            handler.list_agents(event)


class TestGetAgent:
    """Tests for get_agent operation."""
    
    def test_get_agent_success(self, handler):
        """Test successful agent retrieval."""
        # Mock API response
        handler.q_connect.get_ai_agent.return_value = {
            'aiAgent': {
                'aiAgentId': 'agent-1',
                'name': 'Production Voice Agent',
                'type': 'ORCHESTRATION',
                'status': 'ACTIVE',
                'visibilityStatus': 'PUBLISHED',
                'description': 'Main voice agent',
                'configuration': {
                    'orchestrationAIAgentConfiguration': {
                        'orchestrationAIPromptId': 'prompt-1:v2',
                        'locale': 'en_US'
                    }
                },
                'modifiedTime': '2025-02-18T10:00:00Z'
            }
        }
        
        # Call get_agent
        event = {
            'operation': 'get_agent',
            'agentId': 'agent-1'
        }
        result = handler.get_agent(event)
        
        # Verify result
        assert result['success'] is True
        assert result['agentId'] == 'agent-1'
        assert result['agentName'] == 'Production Voice Agent'
        assert result['agentType'] == 'ORCHESTRATION'
        assert result['status'] == 'ACTIVE'
        assert result['visibilityStatus'] == 'PUBLISHED'
        assert result['description'] == 'Main voice agent'
        assert 'configuration' in result
        assert result['modifiedTime'] == '2025-02-18T10:00:00Z'
        
        # Verify API was called correctly
        handler.q_connect.get_ai_agent.assert_called_once_with(
            assistantId='test-assistant-id',
            aiAgentId='agent-1',
            logger=handler.logger
        )
    
    def test_get_agent_missing_agent_id(self, handler):
        """Test get_agent with missing agentId."""
        event = {'operation': 'get_agent'}
        
        with pytest.raises(ValueError, match="Missing required field: agentId"):
            handler.get_agent(event)
    
    def test_get_agent_not_found(self, handler):
        """Test get_agent with invalid agent ID."""
        # Mock ResourceNotFoundException
        error_response = {
            'Error': {
                'Code': 'ResourceNotFoundException',
                'Message': 'Agent not found'
            }
        }
        handler.q_connect.get_ai_agent.side_effect = ClientError(
            error_response,
            'GetAIAgent'
        )
        
        event = {
            'operation': 'get_agent',
            'agentId': 'invalid-agent'
        }
        
        with pytest.raises(ValueError, match="Agent not found: invalid-agent"):
            handler.get_agent(event)
    
    def test_get_agent_api_error(self, handler):
        """Test get_agent with API error."""
        # Mock API error
        error_response = {
            'Error': {
                'Code': 'ThrottlingException',
                'Message': 'Rate exceeded'
            }
        }
        handler.q_connect.get_ai_agent.side_effect = ClientError(
            error_response,
            'GetAIAgent'
        )
        
        event = {
            'operation': 'get_agent',
            'agentId': 'agent-1'
        }
        
        with pytest.raises(ClientError):
            handler.get_agent(event)


class TestProcessEvent:
    """Tests for process_event routing."""
    
    def test_process_event_list_agents(self, handler, lambda_context):
        """Test process_event routes to list_agents."""
        handler.q_connect.list_ai_agents.return_value = {
            'aiAgentSummaries': []
        }
        
        event = {'operation': 'list_agents'}
        result = handler.process_event(event, lambda_context)
        
        assert result['success'] is True
        assert 'agents' in result
    
    def test_process_event_get_agent(self, handler, lambda_context):
        """Test process_event routes to get_agent."""
        handler.q_connect.get_ai_agent.return_value = {
            'aiAgent': {
                'aiAgentId': 'agent-1',
                'name': 'Test Agent',
                'type': 'ORCHESTRATION',
                'status': 'ACTIVE',
                'configuration': {}
            }
        }
        
        event = {
            'operation': 'get_agent',
            'agentId': 'agent-1'
        }
        result = handler.process_event(event, lambda_context)
        
        assert result['success'] is True
        assert result['agentId'] == 'agent-1'
    
    def test_process_event_missing_operation(self, handler, lambda_context):
        """Test process_event with missing operation."""
        event = {}
        
        with pytest.raises(ValueError, match="Missing required field: operation"):
            handler.process_event(event, lambda_context)
    
    def test_process_event_unknown_operation(self, handler, lambda_context):
        """Test process_event with unknown operation."""
        event = {'operation': 'unknown_operation'}
        
        with pytest.raises(ValueError, match="Unknown operation: unknown_operation"):
            handler.process_event(event, lambda_context)



class TestRestoreAllIntents:
    """Tests for restore_all_intents operation."""
    
    def test_restore_all_intents_success(self, handler, lambda_context):
        """Test successful restoration of all intents."""
        # Mock Intent_Configuration with disabled intents
        from agent_manager.intent_configuration import IntentConfiguration, Intent
        
        config = IntentConfiguration(
            agent_id='agent-1',
            timestamp='2025-02-18T10:00:00Z',
            intents=[
                Intent(
                    name='check_balance',
                    description='Check account balance',
                    enabled=False,
                    disabled_at='2025-02-18T09:00:00Z',
                    disabled_by='+12345678901'
                ),
                Intent(
                    name='transfer_funds',
                    description='Transfer funds',
                    enabled=True
                ),
                Intent(
                    name='change_pin',
                    description='Change card PIN',
                    enabled=False,
                    disabled_at='2025-02-18T09:30:00Z',
                    disabled_by='+12345678901'
                )
            ],
            version=3
        )
        
        # Mock intent persistence
        handler.intent_persistence = Mock()
        handler.intent_persistence.load_configuration.return_value = config
        handler.intent_persistence.save_configuration.return_value = True
        
        # Mock S3 backup retrieval
        backup_data = {
            'agentId': 'agent-1',
            'agentName': 'Production Voice Agent',
            'timestamp': '2025-02-18T08:00:00Z',
            'currentPromptText': 'Original AI Prompt text before any intent modifications...',
            'currentPromptId': 'prompt-1:v1'
        }
        
        mock_body = Mock()
        mock_body.read.return_value = json.dumps(backup_data).encode('utf-8')
        handler.s3_client.get_object.return_value = {'Body': mock_body}
        
        # Mock S3 list_objects_v2 for finding most recent backup
        handler.s3_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'backups/agent-1/2025-02-18T08-00-00-Production-Voice-Agent.json',
                    'LastModified': datetime(2025, 2, 18, 8, 0, 0)
                }
            ]
        }
        
        # Mock get_agent
        handler.q_connect.get_ai_agent.return_value = {
            'aiAgent': {
                'aiAgentId': 'agent-1',
                'name': 'Production Voice Agent',
                'type': 'ORCHESTRATION',
                'status': 'ACTIVE',
                'configuration': {
                    'orchestrationAIAgentConfiguration': {
                        'orchestrationAIPromptId': 'prompt-1:v3',
                        'locale': 'en_US'
                    }
                }
            }
        }
        
        # Mock create_ai_prompt_version
        handler.q_connect.create_ai_prompt_version.return_value = {
            'aiPrompt': {
                'aiPromptId': 'prompt-1:v4'
            }
        }
        
        # Mock update_ai_agent
        handler.q_connect.update_ai_agent.return_value = {
            'aiAgent': {
                'aiAgentId': 'agent-1'
            }
        }
        
        # Call restore_all_intents
        event = {
            'operation': 'restore_all_intents',
            'agentId': 'agent-1',
            'callerPhoneNumber': '+12345678901'
        }
        result = handler.restore_all_intents(event, lambda_context)
        
        # Verify result
        assert result['success'] is True
        assert result['agentId'] == 'agent-1'
        assert len(result['restoredIntents']) == 3
        assert 'check_balance' in result['restoredIntents']
        assert 'transfer_funds' in result['restoredIntents']
        assert 'change_pin' in result['restoredIntents']
        assert 'outageDuration' in result
        assert result['testResults']['message'] == 'All intents restored successfully'
        
        # Verify Intent_Configuration was loaded
        handler.intent_persistence.load_configuration.assert_called_once_with('agent-1')
        
        # Verify most recent backup was found
        handler.s3_client.list_objects_v2.assert_called_once_with(
            Bucket='test-backup-bucket',
            Prefix='backups/agent-1/'
        )
        
        # Verify backup was retrieved
        handler.s3_client.get_object.assert_called_once_with(
            Bucket='test-backup-bucket',
            Key='backups/agent-1/2025-02-18T08-00-00-Production-Voice-Agent.json'
        )
        
        # Verify new AI Prompt version was created with original text
        handler.q_connect.create_ai_prompt_version.assert_called_once()
        create_call_args = handler.q_connect.create_ai_prompt_version.call_args[1]
        assert create_call_args['aiPromptId'] == 'prompt-1'
        assert create_call_args['templateConfiguration']['textFullAIPromptEditTemplateConfiguration']['text'] == backup_data['currentPromptText']
        
        # Verify AI Agent was updated
        handler.q_connect.update_ai_agent.assert_called_once()
        update_call_args = handler.q_connect.update_ai_agent.call_args[1]
        assert update_call_args['aiAgentId'] == 'agent-1'
        assert update_call_args['visibilityStatus'] == 'PUBLISHED'
        assert update_call_args['configuration']['orchestrationAIAgentConfiguration']['orchestrationAIPromptId'] == 'prompt-1:v4'
        
        # Verify Intent_Configuration was saved
        handler.intent_persistence.save_configuration.assert_called_once()
        saved_config = handler.intent_persistence.save_configuration.call_args[0][0]
        assert saved_config.agent_id == 'agent-1'
        assert saved_config.version == 4  # Incremented
        # Verify all intents are enabled
        for intent in saved_config.intents:
            assert intent.enabled is True
            assert intent.disabled_at is None
            assert intent.disabled_by is None
        
        # Verify audit log was written
        handler.audit_logger.log_intent_operation.assert_called_once()
        audit_call_args = handler.audit_logger.log_intent_operation.call_args[1]
        assert audit_call_args['operation'] == 'INTENT_RESTORE_ALL'
        assert audit_call_args['agent_id'] == 'agent-1'
        assert audit_call_args['intent_name'] == 'all'
        assert audit_call_args['caller_phone_number'] == '+12345678901'
        assert audit_call_args['result'] == 'SUCCESS'
    
    def test_restore_all_intents_missing_agent_id(self, handler, lambda_context):
        """Test restore_all_intents with missing agentId."""
        event = {
            'operation': 'restore_all_intents',
            'callerPhoneNumber': '+12345678901'
        }
        
        with pytest.raises(ValueError, match="Missing required field: agentId"):
            handler.restore_all_intents(event, lambda_context)
    
    def test_restore_all_intents_no_configuration(self, handler, lambda_context):
        """Test restore_all_intents when Intent_Configuration doesn't exist."""
        # Mock no configuration found
        handler.intent_persistence = Mock()
        handler.intent_persistence.load_configuration.return_value = None
        
        event = {
            'operation': 'restore_all_intents',
            'agentId': 'agent-1',
            'callerPhoneNumber': '+12345678901'
        }
        
        with pytest.raises(ValueError, match="Intent_Configuration not found for agent agent-1"):
            handler.restore_all_intents(event, lambda_context)
    
    def test_restore_all_intents_no_backup_found(self, handler, lambda_context):
        """Test restore_all_intents when no backup exists."""
        from agent_manager.intent_configuration import IntentConfiguration, Intent
        
        config = IntentConfiguration(
            agent_id='agent-1',
            timestamp='2025-02-18T10:00:00Z',
            intents=[
                Intent(name='check_balance', description='Check balance', enabled=False)
            ],
            version=1
        )
        
        handler.intent_persistence = Mock()
        handler.intent_persistence.load_configuration.return_value = config
        
        # Mock no backups found
        handler.s3_client.list_objects_v2.return_value = {}
        
        event = {
            'operation': 'restore_all_intents',
            'agentId': 'agent-1',
            'callerPhoneNumber': '+12345678901'
        }
        
        with pytest.raises(ValueError, match="No backup found for agent agent-1"):
            handler.restore_all_intents(event, lambda_context)
    
    def test_restore_all_intents_no_prompt_in_backup(self, handler, lambda_context):
        """Test restore_all_intents when backup doesn't contain prompt text."""
        from agent_manager.intent_configuration import IntentConfiguration, Intent
        
        config = IntentConfiguration(
            agent_id='agent-1',
            timestamp='2025-02-18T10:00:00Z',
            intents=[
                Intent(name='check_balance', description='Check balance', enabled=False)
            ],
            version=1
        )
        
        handler.intent_persistence = Mock()
        handler.intent_persistence.load_configuration.return_value = config
        
        # Mock backup without prompt text
        backup_data = {
            'agentId': 'agent-1',
            'agentName': 'Production Voice Agent',
            'timestamp': '2025-02-18T08:00:00Z'
            # Missing currentPromptText
        }
        
        mock_body = Mock()
        mock_body.read.return_value = json.dumps(backup_data).encode('utf-8')
        handler.s3_client.get_object.return_value = {'Body': mock_body}
        
        handler.s3_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'backups/agent-1/2025-02-18T08-00-00.json',
                    'LastModified': datetime(2025, 2, 18, 8, 0, 0)
                }
            ]
        }
        
        event = {
            'operation': 'restore_all_intents',
            'agentId': 'agent-1',
            'callerPhoneNumber': '+12345678901'
        }
        
        with pytest.raises(ValueError, match="Original prompt text not found in backup"):
            handler.restore_all_intents(event, lambda_context)
    
    def test_restore_all_intents_calculates_outage_duration(self, handler, lambda_context):
        """Test that restore_all_intents correctly calculates outage duration."""
        from agent_manager.intent_configuration import IntentConfiguration, Intent
        from datetime import timedelta
        
        # Create config with disabled intent from 30 minutes ago
        disabled_time = datetime.utcnow().replace(microsecond=0) - timedelta(minutes=30)
        disabled_time_str = disabled_time.isoformat() + 'Z'
        
        config = IntentConfiguration(
            agent_id='agent-1',
            timestamp='2025-02-18T10:00:00Z',
            intents=[
                Intent(
                    name='check_balance',
                    description='Check balance',
                    enabled=False,
                    disabled_at=disabled_time_str,
                    disabled_by='+12345678901'
                )
            ],
            version=1
        )
        
        handler.intent_persistence = Mock()
        handler.intent_persistence.load_configuration.return_value = config
        handler.intent_persistence.save_configuration.return_value = True
        
        # Mock backup
        backup_data = {
            'agentId': 'agent-1',
            'currentPromptText': 'Original prompt',
            'currentPromptId': 'prompt-1:v1'
        }
        
        mock_body = Mock()
        mock_body.read.return_value = json.dumps(backup_data).encode('utf-8')
        handler.s3_client.get_object.return_value = {'Body': mock_body}
        
        handler.s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'backups/agent-1/backup.json', 'LastModified': datetime.utcnow()}
            ]
        }
        
        # Mock other required calls
        handler.q_connect.get_ai_agent.return_value = {
            'aiAgent': {
                'aiAgentId': 'agent-1',
                'name': 'Test Agent',
                'type': 'ORCHESTRATION',
                'status': 'ACTIVE',
                'configuration': {
                    'orchestrationAIAgentConfiguration': {
                        'orchestrationAIPromptId': 'prompt-1:v2'
                    }
                }
            }
        }
        
        handler.q_connect.create_ai_prompt_version.return_value = {
            'aiPrompt': {'aiPromptId': 'prompt-1:v3'}
        }
        
        handler.q_connect.update_ai_agent.return_value = {
            'aiAgent': {'aiAgentId': 'agent-1'}
        }
        
        event = {
            'operation': 'restore_all_intents',
            'agentId': 'agent-1',
            'callerPhoneNumber': '+12345678901'
        }
        
        result = handler.restore_all_intents(event, lambda_context)
        
        # Verify outage duration is calculated (should be around 30 minutes)
        assert result['outageDuration'] != 'unknown'
        assert 'minutes' in result['outageDuration']
        # Allow some tolerance for test execution time
        duration_value = int(result['outageDuration'].split()[0])
        assert 29 <= duration_value <= 31
