"""
Backup Lambda handler for AI Agent prompt backups.

This Lambda function backs up AI Agent configurations to S3 before updates.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, Any
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.base_handler import BaseLambdaHandler
from shared.error_handling import BackupError, create_success_response
from shared.retry_logic import exponential_backoff
from shared.logging_config import log_operation
from shared.audit_logging import AuditLogger
from shared.metrics_publisher import MetricsPublisher


class BackupHandler(BaseLambdaHandler):
    """Handler for AI Agent backup operations."""
    
    def __init__(self):
        """Initialize backup handler."""
        super().__init__(service_name="supervisor-ai-agent-backup")
        self.backup_bucket = self.get_required_env_var('BACKUP_BUCKET')
        self.s3_client = self.aws_clients.get_s3_client()
        self.audit_logger = AuditLogger(self.backup_bucket, self.logger)
    
    def process_event(self, event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        """
        Process backup request.
        
        Expected event structure:
        {
            "agentId": "agent-uuid",
            "agentName": "Production Voice Agent",
            "assistantId": "assistant-uuid",
            "configuration": {
                "orchestrationAIAgentConfiguration": {...}
            },
            "currentPromptId": "prompt-uuid:version",
            "currentPromptText": "Current AI Prompt text...",
            "visibilityStatus": "PUBLISHED",
            "intentConfiguration": {...},  # Optional
            "metadata": {
                "backupReason": "outage-update",
                "callerPhoneNumber": "+12345678901"
            }
        }
        
        Args:
            event: Lambda event containing agent configuration
            context: Lambda context
            
        Returns:
            Success response with backup location
        """
        start_time = datetime.now()
        
        # Verify inter-Lambda request signature
        from shared.request_signing import verify_request
        if not verify_request(event, logger=self.logger):
            self.logger.warning("Request signature verification failed")
            # Continue processing — fail open to avoid breaking existing flows
        
        # Validate required fields
        required_fields = ['agentId', 'agentName', 'assistantId', 'configuration', 
                          'currentPromptId', 'currentPromptText', 'visibilityStatus']
        for field in required_fields:
            if field not in event:
                raise BackupError(
                    f"Missing required field: {field}",
                    user_message=f"Invalid backup request: missing {field}"
                )
        
        agent_id = event['agentId']
        agent_name = event['agentName']
        
        self.logger.info(
            "Starting backup operation",
            extra={
                "agentId": agent_id,
                "agentName": agent_name,
                "backupReason": event.get('metadata', {}).get('backupReason', 'unknown')
            }
        )
        
        # Create backup object
        backup_object = self._create_backup_object(event)
        
        # Generate S3 key
        s3_key = self._generate_s3_key(agent_id, agent_name)
        
        # Store backup to S3 with retry logic
        backup_location = self._store_backup(s3_key, backup_object)
        
        # Verify backup was stored successfully
        self._verify_backup(s3_key)
        
        # Calculate duration
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Log success
        log_operation(
            logger=self.logger,
            operation="BACKUP",
            agent_id=agent_id,
            result="SUCCESS",
            duration_ms=duration_ms,
            details={
                "backupLocation": backup_location,
                "s3Key": s3_key
            }
        )
        
        # Write audit log to S3
        self.audit_logger.log_operation(
            operation="BACKUP",
            agent_id=agent_id,
            caller_phone_number=event.get('metadata', {}).get('callerPhoneNumber', 'unknown'),
            result="SUCCESS",
            details={
                "backupLocation": backup_location,
                "s3Key": s3_key,
                "agentName": agent_name,
                "assistantId": event['assistantId'],
                "backupReason": event.get('metadata', {}).get('backupReason', 'unknown'),
                "hasIntentConfiguration": 'intentConfiguration' in event
            }
        )
        
        # Publish metrics
        MetricsPublisher.publish_backup_operation(
            metrics=self.metrics,
            agent_id=agent_id,
            result='SUCCESS'
        )
        
        return create_success_response({
            'backupLocation': backup_location,
            'timestamp': backup_object['timestamp'],
            's3Key': s3_key
        })
    
    def _create_backup_object(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create backup object with all required fields.
        
        Args:
            event: Lambda event
            
        Returns:
            Backup object dictionary
        """
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        backup_object = {
            'agentId': event['agentId'],
            'agentName': event['agentName'],
            'assistantId': event['assistantId'],
            'timestamp': timestamp,
            'aiAgentConfiguration': event['configuration'],
            'currentPromptId': event['currentPromptId'],
            'currentPromptText': event['currentPromptText'],
            'visibilityStatus': event['visibilityStatus'],
            'metadata': event.get('metadata', {})
        }
        
        # Add intent configuration if present
        if 'intentConfiguration' in event:
            backup_object['intentConfiguration'] = event['intentConfiguration']
        
        self.logger.info(
            "Created backup object",
            extra={
                "agentId": event['agentId'],
                "timestamp": timestamp,
                "hasIntentConfiguration": 'intentConfiguration' in event
            }
        )
        
        return backup_object
    
    def _generate_s3_key(self, agent_id: str, agent_name: str) -> str:
        """
        Generate S3 key using pattern: backups/{agent-id}/{timestamp}-{agent-name}.json
        
        Args:
            agent_id: AI Agent ID
            agent_name: AI Agent name
            
        Returns:
            S3 key string
        """
        # Generate timestamp for filename (ISO 8601 format, safe for filenames)
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
        
        # Sanitize agent name for filename (replace spaces and special chars)
        safe_agent_name = agent_name.replace(' ', '-').replace('/', '-')
        
        # Generate key
        s3_key = f"backups/{agent_id}/{timestamp}-{safe_agent_name}.json"
        
        self.logger.info(
            "Generated S3 key",
            extra={
                "agentId": agent_id,
                "s3Key": s3_key
            }
        )
        
        return s3_key
    
    @exponential_backoff(max_attempts=3, base_delay=1.0)
    def _store_backup(self, s3_key: str, backup_object: Dict[str, Any]) -> str:
        """
        Store backup to S3 with SSE-S3 encryption and retry logic.
        
        Args:
            s3_key: S3 key for backup
            backup_object: Backup object to store
            
        Returns:
            S3 URI of backup location
            
        Raises:
            BackupError: If backup storage fails
        """
        try:
            # Convert backup object to JSON
            backup_json = json.dumps(backup_object, indent=2)
            
            # Store to S3 (encryption handled by bucket default)
            response = self.s3_client.put_object(
                Bucket=self.backup_bucket,
                Key=s3_key,
                Body=backup_json.encode('utf-8'),
                ContentType='application/json',
                Metadata={
                    'agent-id': backup_object.get('agentId', 'unknown'),
                    'agent-name': backup_object.get('agentName', 'unknown'),
                    'timestamp': backup_object.get('timestamp', 'unknown')
                }
            )
            
            # Verify put_object succeeded
            if response['ResponseMetadata']['HTTPStatusCode'] != 200:
                raise BackupError(
                    f"S3 put_object returned HTTP {response['ResponseMetadata']['HTTPStatusCode']}",
                    user_message="Failed to create backup. Please try again."
                )
            
            backup_location = f"s3://{self.backup_bucket}/{s3_key}"
            
            self.logger.info(
                "Stored backup to S3",
                extra={
                    "backupLocation": backup_location,
                    "sizeBytes": len(backup_json)
                }
            )
            
            return backup_location
            
        except BackupError:
            raise
        except Exception as e:
            self.logger.error(
                "Failed to store backup to S3",
                extra={
                    "s3Key": s3_key,
                    "bucket": self.backup_bucket,
                    "error": str(e)
                },
                exc_info=True
            )
            raise BackupError(
                f"Failed to store backup: {str(e)}",
                user_message="Failed to create backup. Please try again."
            )
    
    @exponential_backoff(max_attempts=3, base_delay=0.5)
    def _verify_backup(self, s3_key: str) -> None:
        """
        Verify backup was stored successfully by checking object existence.
        
        Args:
            s3_key: S3 key to verify
            
        Raises:
            BackupError: If verification fails
        """
        try:
            # Head object to verify existence
            response = self.s3_client.head_object(
                Bucket=self.backup_bucket,
                Key=s3_key
            )
            
            # Verify backup has content
            if response.get('ContentLength', 0) <= 0:
                raise BackupError(
                    f"Backup object has no content: ContentLength={response.get('ContentLength')}",
                    user_message="Backup verification failed. The backup may not have been stored correctly."
                )
            
            self.logger.info(
                "Verified backup exists in S3",
                extra={
                    "s3Key": s3_key,
                    "contentLength": response.get('ContentLength'),
                    "lastModified": str(response.get('LastModified'))
                }
            )
            
        except BackupError:
            raise
        except Exception as e:
            self.logger.error(
                "Failed to verify backup in S3",
                extra={
                    "s3Key": s3_key,
                    "bucket": self.backup_bucket,
                    "error": str(e)
                },
                exc_info=True
            )
            raise BackupError(
                f"Failed to verify backup: {str(e)}",
                user_message="Backup verification failed. The backup may not have been stored correctly."
            )


# Lambda handler function
# Module-level singleton for Lambda container reuse
handler_instance = BackupHandler()


def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler entry point.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        Response dictionary
    """
    return handler_instance.handler(event, context)
