"""Audit logging utilities for S3."""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from aws_lambda_powertools import Logger

from .aws_clients import AWSClients
from .retry_logic import exponential_backoff


class AuditLogger:
    """Utility for writing audit logs to S3."""
    
    def __init__(self, bucket_name: str, logger: Logger):
        """
        Initialize audit logger.
        
        Args:
            bucket_name: S3 bucket name for audit logs
            logger: Logger instance
        """
        self.bucket_name = bucket_name
        self.logger = logger
        self.s3_client = AWSClients.get_s3_client()
    
    def log_operation(
        self,
        operation: str,
        agent_id: str,
        caller_phone_number: str,
        result: str,
        details: Dict[str, Any],
        error_message: Optional[str] = None
    ) -> None:
        """
        Log operation to S3 audit logs.
        
        Args:
            operation: Operation type (BACKUP, UPDATE, RESTORE, TEST, etc.)
            agent_id: AI Agent ID
            caller_phone_number: Caller phone number
            result: Operation result (SUCCESS, FAILURE)
            details: Additional operation details
            error_message: Error message if operation failed
        """
        try:
            # Create audit log entry
            audit_entry = self._create_audit_entry(
                operation=operation,
                agent_id=agent_id,
                caller_phone_number=caller_phone_number,
                result=result,
                details=details,
                error_message=error_message
            )
            
            # Generate S3 key
            s3_key = self._generate_audit_key(operation)
            
            # Write to S3 with retry logic
            self._write_audit_log(s3_key, audit_entry)
            
        except Exception as e:
            # Log error but don't fail the operation
            # Graceful degradation: audit log failure shouldn't break the workflow
            self.logger.warning(
                "Failed to write audit log to S3",
                extra={
                    "operation": operation,
                    "agentId": agent_id,
                    "error": str(e)
                }
            )
    
    def _create_audit_entry(
        self,
        operation: str,
        agent_id: str,
        caller_phone_number: str,
        result: str,
        details: Dict[str, Any],
        error_message: Optional[str]
    ) -> Dict[str, Any]:
        """
        Create structured audit log entry.
        
        Args:
            operation: Operation type
            agent_id: AI Agent ID
            caller_phone_number: Caller phone number
            result: Operation result
            details: Additional details
            error_message: Error message if failed
            
        Returns:
            Audit log entry dictionary
        """
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        audit_entry = {
            'timestamp': timestamp,
            'operation': operation,
            'agentId': agent_id,
            'callerPhoneNumber': caller_phone_number,
            'result': result,
            'details': details
        }
        
        if error_message:
            audit_entry['errorMessage'] = error_message
        
        return audit_entry
    
    def _generate_audit_key(self, operation: str) -> str:
        """
        Generate S3 key for audit log using pattern:
        audit-logs/{year}/{month}/{day}/{operation}-{timestamp}.json
        
        Args:
            operation: Operation type
            
        Returns:
            S3 key string
        """
        now = datetime.utcnow()
        year = now.strftime('%Y')
        month = now.strftime('%m')
        day = now.strftime('%d')
        timestamp = now.strftime('%H-%M-%S-%f')[:15]  # Include microseconds
        
        operation_lower = operation.lower().replace('_', '-')
        
        s3_key = f"audit-logs/{year}/{month}/{day}/{operation_lower}-{timestamp}.json"
        
        return s3_key
    
    @exponential_backoff(max_attempts=3, base_delay=0.5)
    def _write_audit_log(self, s3_key: str, audit_entry: Dict[str, Any]) -> None:
        """
        Write audit log to S3 with retry logic.
        
        Args:
            s3_key: S3 key for audit log
            audit_entry: Audit log entry
        """
        try:
            # Convert to JSON
            audit_json = json.dumps(audit_entry, indent=2)
            
            # Write to S3 (bucket default KMS encryption applies)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=audit_json.encode('utf-8'),
                ContentType='application/json',
                Metadata={
                    'operation': audit_entry['operation'],
                    'agent-id': audit_entry['agentId'],
                    'result': audit_entry['result']
                },
            )
            
            self.logger.info(
                "Wrote audit log to S3",
                extra={
                    "s3Key": s3_key,
                    "operation": audit_entry['operation'],
                    "result": audit_entry['result']
                }
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to write audit log to S3",
                extra={
                    "s3Key": s3_key,
                    "error": str(e)
                },
                exc_info=True
            )
            # Re-raise for retry logic
            raise
    
    def log_intent_operation(
        self,
        operation: str,
        agent_id: str,
        intent_name: str,
        caller_phone_number: str,
        before_config: Optional[Dict[str, Any]],
        after_config: Dict[str, Any],
        result: str,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log intent management operation to S3 audit logs.
        
        Args:
            operation: Operation type (INTENT_DISABLE, INTENT_ENABLE, INTENT_RESTORE_ALL)
            agent_id: AI Agent ID
            intent_name: Intent name
            caller_phone_number: Caller phone number
            before_config: Intent configuration before operation
            after_config: Intent configuration after operation
            result: Operation result (SUCCESS, FAILURE)
            error_message: Error message if operation failed
        """
        details = {
            'intentName': intent_name,
            'beforeConfig': before_config,
            'afterConfig': after_config
        }
        
        self.log_operation(
            operation=operation,
            agent_id=agent_id,
            caller_phone_number=caller_phone_number,
            result=result,
            details=details,
            error_message=error_message
        )
