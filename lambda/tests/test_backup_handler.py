"""Unit tests for Backup Lambda handler."""

import json
import pytest
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backup.handler import BackupHandler
from shared.error_handling import BackupError


@pytest.fixture
def backup_handler():
    """Create BackupHandler instance with mocked dependencies."""
    with patch.dict('os.environ', {'BACKUP_BUCKET': 'test-backup-bucket', 'LOG_LEVEL': 'INFO'}):
        handler = BackupHandler()
        handler.s3_client = Mock()
        handler.audit_logger = Mock()
        return handler


@pytest.fixture
def sample_event():
    """Create sample backup event."""
    return {
        'agentId': 'agent-123',
        'agentName': 'Production Voice Agent',
        'assistantId': 'assistant-456',
        'configuration': {
            'orchestrationAIAgentConfiguration': {
                'orchestrationAIPromptId': 'prompt-789:1',
                'locale': 'en_US'
            }
        },
        'currentPromptId': 'prompt-789:1',
        'currentPromptText': 'You are a helpful AI assistant.',
        'visibilityStatus': 'PUBLISHED',
        'metadata': {
            'backupReason': 'outage-update',
            'callerPhoneNumber': '+12345678901'
        }
    }


@pytest.fixture
def lambda_context():
    """Create mock Lambda context."""
    context = Mock()
    context.request_id = 'test-request-123'
    context.function_name = 'supervisor-ai-agent-backup'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:supervisor-ai-agent-backup'
    return context


def test_create_backup_object(backup_handler, sample_event):
    """Test backup object creation with all required fields."""
    backup_object = backup_handler._create_backup_object(sample_event)
    
    # Verify all required fields are present
    assert backup_object['agentId'] == 'agent-123'
    assert backup_object['agentName'] == 'Production Voice Agent'
    assert backup_object['assistantId'] == 'assistant-456'
    assert 'timestamp' in backup_object
    assert backup_object['aiAgentConfiguration'] == sample_event['configuration']
    assert backup_object['currentPromptId'] == 'prompt-789:1'
    assert backup_object['currentPromptText'] == 'You are a helpful AI assistant.'
    assert backup_object['visibilityStatus'] == 'PUBLISHED'
    assert backup_object['metadata'] == sample_event['metadata']


def test_create_backup_object_with_intent_configuration(backup_handler, sample_event):
    """Test backup object creation includes intent configuration when present."""
    sample_event['intentConfiguration'] = {
        'intents': [
            {'name': 'check_balance', 'enabled': True},
            {'name': 'change_pin', 'enabled': False}
        ]
    }
    
    backup_object = backup_handler._create_backup_object(sample_event)
    
    assert 'intentConfiguration' in backup_object
    assert backup_object['intentConfiguration'] == sample_event['intentConfiguration']


def test_generate_s3_key(backup_handler):
    """Test S3 key generation follows correct pattern."""
    agent_id = 'agent-123'
    agent_name = 'Production Voice Agent'
    
    s3_key = backup_handler._generate_s3_key(agent_id, agent_name)
    
    # Verify key pattern: backups/{agent-id}/{timestamp}-{agent-name}.json
    assert s3_key.startswith(f'backups/{agent_id}/')
    assert s3_key.endswith('-Production-Voice-Agent.json')
    assert 'T' in s3_key  # ISO timestamp format


def test_generate_s3_key_sanitizes_agent_name(backup_handler):
    """Test S3 key generation sanitizes agent name for filename safety."""
    agent_id = 'agent-123'
    agent_name = 'Production/Voice Agent'
    
    s3_key = backup_handler._generate_s3_key(agent_id, agent_name)
    
    # Verify slashes are replaced with dashes
    assert '/' not in s3_key.split('/')[-1]  # Check filename part only
    assert 'Production-Voice-Agent' in s3_key


def test_store_backup_success(backup_handler):
    """Test successful backup storage to S3."""
    s3_key = 'backups/agent-123/2025-02-18T10-30-00-Test-Agent.json'
    backup_object = {
        'agentId': 'agent-123',
        'agentName': 'Test Agent',
        'timestamp': '2025-02-18T10:30:00Z'
    }
    
    backup_handler.s3_client.put_object = Mock(return_value={})
    
    backup_location = backup_handler._store_backup(s3_key, backup_object)
    
    # Verify S3 put_object was called with correct parameters
    backup_handler.s3_client.put_object.assert_called_once()
    call_kwargs = backup_handler.s3_client.put_object.call_args[1]
    
    assert call_kwargs['Bucket'] == 'test-backup-bucket'
    assert call_kwargs['Key'] == s3_key
    assert call_kwargs['ContentType'] == 'application/json'
    assert call_kwargs['ServerSideEncryption'] == 'AES256'
    assert 'Body' in call_kwargs
    
    # Verify backup location format
    assert backup_location == f's3://test-backup-bucket/{s3_key}'


def test_store_backup_with_encryption(backup_handler):
    """Test backup is stored with SSE-S3 encryption."""
    s3_key = 'backups/agent-123/test.json'
    backup_object = {'agentId': 'agent-123'}
    
    backup_handler.s3_client.put_object = Mock(return_value={})
    
    backup_handler._store_backup(s3_key, backup_object)
    
    call_kwargs = backup_handler.s3_client.put_object.call_args[1]
    assert call_kwargs['ServerSideEncryption'] == 'AES256'


def test_store_backup_failure_raises_error(backup_handler):
    """Test backup storage failure raises BackupError."""
    s3_key = 'backups/agent-123/test.json'
    backup_object = {'agentId': 'agent-123'}
    
    # Mock S3 failure
    backup_handler.s3_client.put_object = Mock(
        side_effect=ClientError(
            {'Error': {'Code': 'InternalError', 'Message': 'S3 error'}},
            'PutObject'
        )
    )
    
    with pytest.raises(BackupError) as exc_info:
        backup_handler._store_backup(s3_key, backup_object)
    
    assert 'Failed to store backup' in str(exc_info.value)


def test_verify_backup_success(backup_handler):
    """Test successful backup verification."""
    s3_key = 'backups/agent-123/test.json'
    
    backup_handler.s3_client.head_object = Mock(return_value={
        'ContentLength': 1024,
        'LastModified': datetime.now()
    })
    
    # Should not raise exception
    backup_handler._verify_backup(s3_key)
    
    backup_handler.s3_client.head_object.assert_called_once_with(
        Bucket='test-backup-bucket',
        Key=s3_key,
        logger=backup_handler.logger
    )


def test_verify_backup_failure_raises_error(backup_handler):
    """Test backup verification failure raises BackupError."""
    s3_key = 'backups/agent-123/test.json'
    
    # Mock verification failure
    backup_handler.s3_client.head_object = Mock(
        side_effect=ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}},
            'HeadObject'
        )
    )
    
    with pytest.raises(BackupError) as exc_info:
        backup_handler._verify_backup(s3_key)
    
    assert 'Failed to verify backup' in str(exc_info.value)


def test_process_event_missing_required_field(backup_handler, sample_event, lambda_context):
    """Test process_event raises error when required field is missing."""
    del sample_event['agentId']
    
    with pytest.raises(BackupError) as exc_info:
        backup_handler.process_event(sample_event, lambda_context)
    
    assert 'Missing required field: agentId' in str(exc_info.value)


def test_process_event_success(backup_handler, sample_event, lambda_context):
    """Test successful backup operation end-to-end."""
    # Mock S3 operations
    backup_handler.s3_client.put_object = Mock(return_value={})
    backup_handler.s3_client.head_object = Mock(return_value={
        'ContentLength': 1024,
        'LastModified': datetime.now()
    })
    
    response = backup_handler.process_event(sample_event, lambda_context)
    
    # Verify response
    assert response['success'] is True
    assert 'backupLocation' in response
    assert response['backupLocation'].startswith('s3://test-backup-bucket/backups/agent-123/')
    assert 'timestamp' in response
    assert 's3Key' in response
    
    # Verify audit log was written
    backup_handler.audit_logger.log_operation.assert_called_once()
    audit_call = backup_handler.audit_logger.log_operation.call_args[1]
    assert audit_call['operation'] == 'BACKUP'
    assert audit_call['agent_id'] == 'agent-123'
    assert audit_call['result'] == 'SUCCESS'


def test_process_event_logs_audit_on_failure(backup_handler, sample_event, lambda_context):
    """Test audit log is written on backup failure."""
    # Mock S3 failure
    backup_handler.s3_client.put_object = Mock(
        side_effect=ClientError(
            {'Error': {'Code': 'InternalError', 'Message': 'S3 error'}},
            'PutObject'
        )
    )
    
    with pytest.raises(BackupError):
        backup_handler.process_event(sample_event, lambda_context)


def test_backup_object_completeness_property():
    """
    Property test: Backup object should contain all required fields.
    
    Feature: supervisor-ai-agent-outage-management
    Property 13: Backup Object Completeness
    
    For any backup object created, it should contain timestamp, agent ID,
    agent name, complete prompt text, and metadata.
    """
    with patch.dict('os.environ', {'BACKUP_BUCKET': 'test-bucket', 'LOG_LEVEL': 'INFO'}):
        handler = BackupHandler()
        
        event = {
            'agentId': 'test-agent',
            'agentName': 'Test Agent',
            'assistantId': 'test-assistant',
            'configuration': {'test': 'config'},
            'currentPromptId': 'prompt-1',
            'currentPromptText': 'Test prompt',
            'visibilityStatus': 'PUBLISHED',
            'metadata': {'reason': 'test'}
        }
        
        backup_object = handler._create_backup_object(event)
        
        # Verify all required fields are present
        required_fields = [
            'agentId', 'agentName', 'assistantId', 'timestamp',
            'aiAgentConfiguration', 'currentPromptId', 'currentPromptText',
            'visibilityStatus', 'metadata'
        ]
        
        for field in required_fields:
            assert field in backup_object, f"Missing required field: {field}"


def test_s3_key_format_property():
    """
    Property test: S3 key should match pattern backups/{agent-id}/{timestamp}-{agent-name}.json
    
    Feature: supervisor-ai-agent-outage-management
    Property 14: Backup S3 Key Format
    
    For any backup stored in S3, the key should match the pattern
    backups/{agent-id}/{timestamp}-{agent-name}.json
    """
    with patch.dict('os.environ', {'BACKUP_BUCKET': 'test-bucket', 'LOG_LEVEL': 'INFO'}):
        handler = BackupHandler()
        
        agent_id = 'test-agent-123'
        agent_name = 'Test Agent Name'
        
        s3_key = handler._generate_s3_key(agent_id, agent_name)
        
        # Verify key pattern
        assert s3_key.startswith(f'backups/{agent_id}/')
        assert s3_key.endswith('.json')
        
        # Extract filename part
        filename = s3_key.split('/')[-1]
        
        # Verify timestamp format (ISO 8601 with hyphens)
        assert 'T' in filename
        assert filename.count('-') >= 5  # Date and time separators
        
        # Verify agent name is in filename
        sanitized_name = agent_name.replace(' ', '-')
        assert sanitized_name in filename
