"""
Restore Lambda handler for AI Agent prompt restoration.

This Lambda function restores AI Agent configurations from S3 backups.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.metrics import MetricUnit

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.base_handler import BaseLambdaHandler
from shared.error_handling import RestoreError, create_success_response
from shared.retry_logic import exponential_backoff
from shared.logging_config import log_operation
from shared.audit_logging import AuditLogger
from shared.metrics_publisher import MetricsPublisher


class RestoreHandler(BaseLambdaHandler):
    """Handler for AI Agent restore operations."""
    
    def __init__(self):
        """Initialize restore handler."""
        super().__init__(service_name="supervisor-ai-agent-restore")
        self.backup_bucket = self.get_required_env_var('BACKUP_BUCKET')
        self.agent_manager_lambda_arn = self.get_required_env_var('AGENT_MANAGER_LAMBDA_ARN')
        self.tester_lambda_arn = self.get_required_env_var('TESTER_LAMBDA_ARN')
        self.s3_client = self.aws_clients.get_s3_client()
        self.lambda_client = self.aws_clients.get_lambda_client()
        self.q_connect_client = self.aws_clients.get_q_connect_client()
        self.audit_logger = AuditLogger(self.backup_bucket, self.logger)
    
    def process_event(self, event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        """
        Process restore request.
        
        Expected event structure:
        {
            "agentId": "agent-uuid",
            "callerPhoneNumber": "+12345678901"
        }
        
        Args:
            event: Lambda event containing agent ID
            context: Lambda context
            
        Returns:
            Success response with restore details
        """
        start_time = datetime.now()
        
        # Validate required fields
        if 'agentId' not in event:
            raise RestoreError(
                "Missing required field: agentId",
                user_message="Invalid restore request: missing agent ID"
            )
        
        agent_id = event['agentId']
        caller_phone_number = event.get('callerPhoneNumber', 'unknown')
        
        self.logger.info(
            "Starting restore operation",
            extra={
                "agentId": agent_id,
                "callerPhoneNumber": caller_phone_number
            }
        )
        
        # Step 1: List all backups for agent
        backups = self._list_agent_backups(agent_id)
        
        if not backups:
            raise RestoreError(
                f"No backups found for agent {agent_id}",
                user_message=f"No backups available for this agent. Cannot restore."
            )
        
        # Step 2: Identify most recent backup
        most_recent_backup = self._select_most_recent_backup(backups)
        
        self.logger.info(
            "Selected most recent backup",
            extra={
                "agentId": agent_id,
                "backupKey": most_recent_backup['key'],
                "backupTimestamp": most_recent_backup['timestamp']
            }
        )
        
        # Step 3: Retrieve and parse backup
        backup_data = self._retrieve_backup(most_recent_backup['key'])
        
        # Step 4: Restore prompt using Agent Manager Lambda
        restore_result = self._restore_prompt(agent_id, backup_data, caller_phone_number)
        
        # Step 5: Test restored agent
        test_results = self._test_restored_agent(agent_id, backup_data)
        
        # Step 6: Calculate outage duration
        outage_duration = self._calculate_outage_duration(
            backup_data.get('timestamp'),
            datetime.now(timezone.utc)
        )
        
        # Calculate total duration
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Prepare response
        backup_location = f"s3://{self.backup_bucket}/{most_recent_backup['key']}"
        
        # Extract Intent_Configuration from backup if present
        intent_config = self.get_intent_configuration_from_backup(backup_data)
        
        response_data = {
            'agentId': agent_id,
            'restoredFrom': backup_location,
            'outageDuration': outage_duration,
            'testResults': test_results,
            'restoredPromptVersion': restore_result.get('newPromptVersion'),
            'backupTimestamp': backup_data.get('timestamp')
        }
        
        # Include Intent_Configuration in response if present
        if intent_config:
            response_data['intentConfiguration'] = intent_config
            response_data['hasIntentConfiguration'] = True
        else:
            response_data['hasIntentConfiguration'] = False
        
        # Log success
        log_operation(
            logger=self.logger,
            operation="RESTORE",
            agent_id=agent_id,
            result="SUCCESS",
            duration_ms=duration_ms,
            details={
                "backupLocation": backup_location,
                "outageDuration": outage_duration,
                "testsPassed": test_results.get('passed', 0),
                "testsFailed": test_results.get('failed', 0)
            }
        )
        
        # Write audit log
        self.audit_logger.log_operation(
            operation="RESTORE",
            agent_id=agent_id,
            caller_phone_number=caller_phone_number,
            result="SUCCESS",
            details={
                "backupLocation": backup_location,
                "backupTimestamp": backup_data.get('timestamp'),
                "outageDuration": outage_duration,
                "restoredPromptVersion": restore_result.get('newPromptVersion'),
                "hasIntentConfiguration": intent_config is not None,
                "testResults": {
                    "total": test_results.get('totalTests', 0),
                    "passed": test_results.get('passed', 0),
                    "failed": test_results.get('failed', 0)
                }
            }
        )
        
        # Publish metrics
        MetricsPublisher.publish_restore_operation(
            metrics=self.metrics,
            agent_id=agent_id,
            result='SUCCESS'
        )
        MetricsPublisher.publish_workflow_duration(
            metrics=self.metrics,
            operation='RESTORE_AGENT',
            duration_ms=duration_ms
        )
        
        return create_success_response(response_data)

    
    @exponential_backoff(max_attempts=3, base_delay=1.0)
    def _list_agent_backups(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        List all backups for agent from S3.
        
        Args:
            agent_id: AI Agent ID
            
        Returns:
            List of backup metadata dictionaries
            
        Raises:
            RestoreError: If listing fails
        """
        try:
            prefix = f"backups/{agent_id}/"
            
            self.logger.info(
                "Listing backups from S3",
                extra={
                    "agentId": agent_id,
                    "bucket": self.backup_bucket,
                    "prefix": prefix
                }
            )
            
            # List objects with prefix
            response = self.s3_client.list_objects_v2(
                Bucket=self.backup_bucket,
                Prefix=prefix
            )
            
            # Extract backup metadata
            backups = []
            for obj in response.get('Contents', []):
                key = obj['Key']
                # Skip if it's just the prefix (directory marker)
                if key == prefix:
                    continue
                
                backups.append({
                    'key': key,
                    'lastModified': obj['LastModified'],
                    'size': obj['Size']
                })
            
            self.logger.info(
                "Found backups",
                extra={
                    "agentId": agent_id,
                    "backupCount": len(backups)
                }
            )
            
            return backups
            
        except Exception as e:
            self.logger.error(
                "Failed to list backups from S3",
                extra={
                    "agentId": agent_id,
                    "bucket": self.backup_bucket,
                    "error": str(e)
                },
                exc_info=True
            )
            raise RestoreError(
                f"Failed to list backups: {str(e)}",
                user_message="Failed to retrieve backup list. Please try again."
            )
    
    def _select_most_recent_backup(self, backups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Select most recent backup by timestamp.
        
        Args:
            backups: List of backup metadata
            
        Returns:
            Most recent backup metadata
        """
        if not backups:
            raise RestoreError(
                "No backups available",
                user_message="No backups found for this agent"
            )
        
        # Sort by lastModified descending (most recent first)
        sorted_backups = sorted(
            backups,
            key=lambda b: b['lastModified'],
            reverse=True
        )
        
        most_recent = sorted_backups[0]
        
        # Extract timestamp from backup object for logging
        # Parse timestamp from S3 key if possible (format: backups/{agent-id}/{timestamp}-{name}.json)
        key_parts = most_recent['key'].split('/')
        if len(key_parts) >= 3:
            filename = key_parts[-1]
            # Extract timestamp from filename (format: YYYY-MM-DDTHH-MM-SS-{name}.json)
            # Split by '-' and reconstruct the ISO timestamp
            parts = filename.split('-')
            if len(parts) >= 6:
                # Reconstruct ISO timestamp: YYYY-MM-DDTHH:MM:SS
                timestamp_str = f"{parts[0]}-{parts[1]}-{parts[2]}T{parts[3]}:{parts[4]}:{parts[5]}"
                most_recent['timestamp'] = timestamp_str
            else:
                # Fallback to lastModified if filename parsing fails
                most_recent['timestamp'] = most_recent['lastModified'].isoformat()
        else:
            # Fallback to lastModified if key parsing fails
            most_recent['timestamp'] = most_recent['lastModified'].isoformat()
        
        return most_recent
    
    def _select_backup_before_intent_modifications(
        self,
        backups: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Select most recent backup that was created before any intent modifications.
        
        This is used for the restore_all_intents operation to find the original
        prompt before any intent-level changes were made.
        
        Priority:
        1. Most recent backup without Intent_Configuration (created before intent management)
        2. Most recent backup with all intents enabled (original state)
        3. Most recent backup overall (fallback)
        
        Args:
            backups: List of backup metadata
            
        Returns:
            Most recent backup without intent modifications, or None if not found
        """
        if not backups:
            return None
        
        # Sort by lastModified descending (most recent first)
        sorted_backups = sorted(
            backups,
            key=lambda b: b['lastModified'],
            reverse=True
        )
        
        # First pass: Find the most recent backup without Intent_Configuration
        backup_without_intents = None
        for backup_meta in sorted_backups:
            try:
                # Retrieve the backup to check if it has Intent_Configuration
                backup_data = self._retrieve_backup(backup_meta['key'])
                
                # If backup doesn't have intentConfiguration, it's from before intent modifications
                if 'intentConfiguration' not in backup_data:
                    self.logger.info(
                        "Found backup before intent modifications (no Intent_Configuration)",
                        extra={
                            "s3Key": backup_meta['key'],
                            "timestamp": backup_data.get('timestamp')
                        }
                    )
                    return backup_meta
                    
            except Exception as e:
                self.logger.warning(
                    "Failed to check backup for intent modifications",
                    extra={
                        "s3Key": backup_meta['key'],
                        "error": str(e)
                    }
                )
                continue
        
        # Second pass: Find the most recent backup with all intents enabled
        for backup_meta in sorted_backups:
            try:
                backup_data = self._retrieve_backup(backup_meta['key'])
                
                # If backup has intentConfiguration with all intents enabled,
                # it might be the original state
                intent_config = backup_data.get('intentConfiguration', {})
                intents = intent_config.get('intents', [])
                
                # Check if all intents are enabled
                all_enabled = all(intent.get('enabled', True) for intent in intents)
                
                if all_enabled and len(intents) > 0:
                    self.logger.info(
                        "Found backup with all intents enabled",
                        extra={
                            "s3Key": backup_meta['key'],
                            "timestamp": backup_data.get('timestamp'),
                            "intentCount": len(intents)
                        }
                    )
                    return backup_meta
                    
            except Exception as e:
                self.logger.warning(
                    "Failed to check backup for all intents enabled",
                    extra={
                        "s3Key": backup_meta['key'],
                        "error": str(e)
                    }
                )
                continue
        
        # Fallback: Return most recent backup
        self.logger.warning(
            "No backup found before intent modifications, using most recent",
            extra={"backupCount": len(sorted_backups)}
        )
        return sorted_backups[0] if sorted_backups else None
    
    def get_intent_configuration_from_backup(
        self,
        backup_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract Intent_Configuration from backup data.
        
        Handles both old backups (without Intent_Configuration) and new backups
        (with Intent_Configuration).
        
        Args:
            backup_data: Parsed backup data
            
        Returns:
            Intent_Configuration dictionary or None if not present
        """
        intent_config = backup_data.get('intentConfiguration')
        
        if intent_config:
            self.logger.info(
                "Retrieved Intent_Configuration from backup",
                extra={
                    "agentId": backup_data.get('agentId'),
                    "intentCount": len(intent_config.get('intents', []))
                }
            )
        else:
            self.logger.info(
                "Backup does not contain Intent_Configuration (old backup format)",
                extra={"agentId": backup_data.get('agentId')}
            )
        
        return intent_config
    
    @exponential_backoff(max_attempts=3, base_delay=1.0)
    def _retrieve_backup(self, s3_key: str) -> Dict[str, Any]:
        """
        Retrieve and parse backup object from S3.
        
        Supports both old backups (without Intent_Configuration) and new backups
        (with Intent_Configuration) for backward compatibility.
        
        Args:
            s3_key: S3 key of backup
            
        Returns:
            Parsed backup data with optional intentConfiguration field
            
        Raises:
            RestoreError: If retrieval or parsing fails
        """
        try:
            self.logger.info(
                "Retrieving backup from S3",
                extra={
                    "s3Key": s3_key,
                    "bucket": self.backup_bucket
                }
            )
            
            # Validate S3 key starts with backups/ prefix
            if not s3_key.startswith('backups/'):
                raise RestoreError(
                    f"Invalid backup key: must start with 'backups/' prefix",
                    user_message="Invalid backup location. Only verified backups can be restored."
                )

            # Get object from S3
            response = self.s3_client.get_object(
                Bucket=self.backup_bucket,
                Key=s3_key
            )
            
            # Read and parse JSON
            backup_json = response['Body'].read().decode('utf-8')
            backup_data = json.loads(backup_json)
            
            # Validate backup has required fields
            required_backup_fields = ['agentId', 'timestamp', 'currentPromptText', 'assistantId']
            missing = [f for f in required_backup_fields if f not in backup_data]
            if missing:
                raise RestoreError(
                    f"Backup missing required fields: {missing}",
                    user_message="Backup data is incomplete. Cannot restore."
                )
            
            # Check if backup contains Intent_Configuration
            has_intent_config = 'intentConfiguration' in backup_data
            
            self.logger.info(
                "Retrieved and parsed backup",
                extra={
                    "s3Key": s3_key,
                    "agentId": backup_data.get('agentId'),
                    "timestamp": backup_data.get('timestamp'),
                    "sizeBytes": len(backup_json),
                    "hasIntentConfiguration": has_intent_config
                }
            )
            
            return backup_data
            
        except json.JSONDecodeError as e:
            self.logger.error(
                "Failed to parse backup JSON",
                extra={
                    "s3Key": s3_key,
                    "error": str(e)
                },
                exc_info=True
            )
            raise RestoreError(
                f"Failed to parse backup data: {str(e)}",
                user_message="Backup data is corrupted. Cannot restore."
            )
        except Exception as e:
            self.logger.error(
                "Failed to retrieve backup from S3",
                extra={
                    "s3Key": s3_key,
                    "bucket": self.backup_bucket,
                    "error": str(e)
                },
                exc_info=True
            )
            raise RestoreError(
                f"Failed to retrieve backup: {str(e)}",
                user_message="Failed to retrieve backup. Please try again."
            )

    
    @exponential_backoff(max_attempts=3, base_delay=2.0)
    def _restore_prompt(
        self,
        agent_id: str,
        backup_data: Dict[str, Any],
        caller_phone_number: str
    ) -> Dict[str, Any]:
        """
        Restore AI Agent prompt by creating new AI Prompt version and updating agent.
        
        This method:
        1. Extracts original prompt text from backup
        2. Creates new AI Prompt version using CreateAIPromptVersion API
        3. Updates AI Agent configuration to reference new prompt version
        4. Sets visibilityStatus to PUBLISHED
        
        Args:
            agent_id: AI Agent ID
            backup_data: Backup data containing original configuration
            caller_phone_number: Caller phone number for logging
            
        Returns:
            Restore result with new prompt version
            
        Raises:
            RestoreError: If restoration fails
        """
        try:
            self.logger.info(
                "Starting prompt restoration",
                extra={
                    "agentId": agent_id,
                    "backupTimestamp": backup_data.get('timestamp')
                }
            )
            
            # Extract original prompt information
            original_prompt_text = backup_data.get('currentPromptText')
            if not original_prompt_text:
                raise RestoreError(
                    "Backup does not contain prompt text",
                    user_message="Backup is incomplete and cannot be restored. Please contact support."
                )
            
            assistant_id = backup_data.get('assistantId')
            if not assistant_id:
                raise RestoreError(
                    "Backup does not contain assistant ID",
                    user_message="Backup is incomplete. Cannot restore."
                )
            
            # Extract the base prompt ID (without version) from currentPromptId
            current_prompt_id = backup_data.get('currentPromptId', '')
            base_prompt_id = current_prompt_id.split(':')[0] if ':' in current_prompt_id else current_prompt_id
            
            # Step 1: Create new AI Prompt version with original text
            self.logger.info(
                "Creating new AI Prompt version",
                extra={
                    "agentId": agent_id,
                    "basePromptId": base_prompt_id,
                    "assistantId": assistant_id
                }
            )
            
            create_prompt_response = self.q_connect_client.create_ai_prompt_version(
                assistantId=assistant_id,
                aiPromptId=base_prompt_id,
                modifiedTime=datetime.now(timezone.utc)
            )
            
            new_prompt_version = create_prompt_response['aiPrompt']['aiPromptArn']
            new_prompt_id = create_prompt_response['aiPrompt']['aiPromptId']
            
            self.logger.info(
                "Created new AI Prompt version",
                extra={
                    "agentId": agent_id,
                    "newPromptVersion": new_prompt_version,
                    "newPromptId": new_prompt_id
                }
            )
            
            # Step 2: Update AI Agent configuration to reference new prompt version
            ai_agent_configuration = backup_data.get('aiAgentConfiguration', {})
            
            # Update the orchestrationAIPromptId to reference new version
            if 'orchestrationAIAgentConfiguration' in ai_agent_configuration:
                ai_agent_configuration['orchestrationAIAgentConfiguration']['orchestrationAIPromptId'] = new_prompt_id
            
            self.logger.info(
                "Updating AI Agent configuration",
                extra={
                    "agentId": agent_id,
                    "newPromptId": new_prompt_id
                }
            )
            
            update_response = self.q_connect_client.update_ai_agent(
                aiAgentId=agent_id,
                assistantId=assistant_id,
                configuration=ai_agent_configuration,
                visibilityStatus='PUBLISHED'
            )
            
            self.logger.info(
                "Updated AI Agent configuration",
                extra={
                    "agentId": agent_id,
                    "newPromptVersion": new_prompt_version,
                    "visibilityStatus": "PUBLISHED"
                }
            )
            
            return {
                'success': True,
                'newPromptVersion': new_prompt_version,
                'newPromptId': new_prompt_id,
                'agentId': agent_id
            }
            
        except RestoreError:
            # Re-raise RestoreError without modification to preserve user message
            raise
        except Exception as e:
            self.logger.error(
                "Failed to restore prompt",
                extra={
                    "agentId": agent_id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise RestoreError(
                f"Failed to restore prompt: {str(e)}",
                user_message="Failed to restore agent configuration. Please try again."
            )
    
    @exponential_backoff(max_attempts=2, base_delay=1.0)
    def _test_restored_agent(self, agent_id: str, backup_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test restored agent by invoking Tester Lambda.
        
        Args:
            agent_id: AI Agent ID
            backup_data: Backup data for context
            
        Returns:
            Test results
            
        Raises:
            RestoreError: If testing fails
        """
        try:
            self.logger.info(
                "Testing restored agent",
                extra={"agentId": agent_id}
            )
            
            # Prepare test request
            test_request = {
                'agentId': agent_id,
                'testScenario': 'restore-validation',
                'metadata': {
                    'operation': 'restore',
                    'backupTimestamp': backup_data.get('timestamp')
                }
            }
            
            # Invoke Tester Lambda
            response = self.lambda_client.invoke(
                FunctionName=self.tester_lambda_arn,
                InvocationType='RequestResponse',
                Payload=json.dumps(test_request).encode('utf-8')
            )
            
            # Parse response
            response_payload = json.loads(response['Payload'].read().decode('utf-8'))
            
            if not response_payload.get('success'):
                self.logger.warning(
                    "Test execution reported failure",
                    extra={
                        "agentId": agent_id,
                        "testResults": response_payload
                    }
                )
            
            self.logger.info(
                "Completed agent testing",
                extra={
                    "agentId": agent_id,
                    "totalTests": response_payload.get('totalTests', 0),
                    "passed": response_payload.get('passed', 0),
                    "failed": response_payload.get('failed', 0)
                }
            )
            
            return response_payload
            
        except Exception as e:
            self.logger.error(
                "Failed to test restored agent",
                extra={
                    "agentId": agent_id,
                    "error": str(e)
                },
                exc_info=True
            )
            # Don't fail restore if testing fails - log warning and return empty results
            self.logger.warning(
                "Continuing with restore despite test failure",
                extra={"agentId": agent_id}
            )
            return {
                'success': False,
                'totalTests': 0,
                'passed': 0,
                'failed': 0,
                'error': 'Testing failed but restore completed'
            }

    
    def _calculate_outage_duration(
        self,
        backup_timestamp_str: Optional[str],
        current_time: datetime
    ) -> str:
        """
        Calculate outage duration from backup timestamp to current time.
        
        Args:
            backup_timestamp_str: Backup timestamp (ISO 8601 format)
            current_time: Current time
            
        Returns:
            Human-readable duration string (e.g., "47 minutes", "2 hours 15 minutes")
        """
        if not backup_timestamp_str:
            return "unknown"
        
        try:
            # Parse backup timestamp
            # Handle both formats: with and without 'Z' suffix
            if backup_timestamp_str.endswith('Z'):
                backup_time = datetime.fromisoformat(backup_timestamp_str.replace('Z', '+00:00'))
            else:
                backup_time = datetime.fromisoformat(backup_timestamp_str)
            
            # Ensure both times are timezone-aware
            if backup_time.tzinfo is None:
                backup_time = backup_time.replace(tzinfo=timezone.utc)
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone.utc)
            
            # Calculate duration
            duration = current_time - backup_time
            total_seconds = int(duration.total_seconds())
            
            # Format duration
            if total_seconds < 60:
                return f"{total_seconds} seconds"
            elif total_seconds < 3600:
                minutes = total_seconds // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''}"
            else:
                hours = total_seconds // 3600
                remaining_minutes = (total_seconds % 3600) // 60
                if remaining_minutes > 0:
                    return f"{hours} hour{'s' if hours != 1 else ''} {remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"
                else:
                    return f"{hours} hour{'s' if hours != 1 else ''}"
        
        except Exception as e:
            self.logger.warning(
                "Failed to calculate outage duration",
                extra={
                    "backupTimestamp": backup_timestamp_str,
                    "error": str(e)
                }
            )
            return "unknown"
    
    def _parse_duration_minutes(self, duration_str: str) -> int:
        """
        Parse duration string to minutes for metrics.
        
        Args:
            duration_str: Duration string (e.g., "47 minutes", "2 hours 15 minutes")
            
        Returns:
            Duration in minutes
        """
        if duration_str == "unknown":
            return 0
        
        try:
            total_minutes = 0
            
            # Parse hours
            if "hour" in duration_str:
                hours_part = duration_str.split("hour")[0].strip().split()[-1]
                total_minutes += int(hours_part) * 60
            
            # Parse minutes
            if "minute" in duration_str:
                # Extract the number before "minute"
                parts = duration_str.split("minute")[0].strip().split()
                minutes_part = parts[-1]
                total_minutes += int(minutes_part)
            
            # Parse seconds (convert to minutes, round up)
            if "second" in duration_str and "minute" not in duration_str and "hour" not in duration_str:
                seconds_part = duration_str.split("second")[0].strip().split()[-1]
                total_minutes = max(1, int(seconds_part) // 60)  # At least 1 minute
            
            return total_minutes
        
        except Exception as e:
            self.logger.warning(
                "Failed to parse duration for metrics",
                extra={
                    "durationStr": duration_str,
                    "error": str(e)
                }
            )
            return 0


# Lambda handler function
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler entry point.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        Response dictionary
    """
    handler_instance = RestoreHandler()
    return handler_instance.handler(event, context)
