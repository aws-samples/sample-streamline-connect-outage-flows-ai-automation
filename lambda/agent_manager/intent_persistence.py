"""
Intent Configuration persistence layer for S3 storage.

Handles storing and retrieving Intent_Configuration objects from S3
with versioning, retry logic, and error handling.
"""

import json
from typing import Optional
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger

from agent_manager.intent_configuration import IntentConfiguration
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from shared.retry_logic import exponential_backoff


class IntentConfigurationPersistence:
    """Handles Intent_Configuration persistence to S3."""
    
    def __init__(self, s3_client, bucket_name: str, logger: Logger):
        """
        Initialize persistence layer.
        
        Args:
            s3_client: Boto3 S3 client
            bucket_name: S3 bucket name for storage
            logger: Logger instance
        """
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.logger = logger
    
    def get_s3_key(self, agent_id: str) -> str:
        """
        Generate S3 key for Intent_Configuration.
        
        Args:
            agent_id: AI Agent ID
            
        Returns:
            S3 key following pattern: intent-configs/{agent-id}/current.json
        """
        return f"intent-configs/{agent_id}/current.json"
    
    def load_configuration(self, agent_id: str) -> Optional[IntentConfiguration]:
        """
        Load Intent_Configuration from S3.
        
        Args:
            agent_id: AI Agent ID
            
        Returns:
            IntentConfiguration if exists, None otherwise
        """
        s3_key = self.get_s3_key(agent_id)
        
        self.logger.info(
            "Loading Intent_Configuration from S3",
            extra={
                "agentId": agent_id,
                "bucket": self.bucket_name,
                "key": s3_key
            }
        )
        
        try:
            response = self._get_object_with_retry(s3_key)
            json_content = response['Body'].read().decode('utf-8')
            
            config = IntentConfiguration.from_json(json_content)
            
            self.logger.info(
                "Successfully loaded Intent_Configuration",
                extra={
                    "agentId": agent_id,
                    "intentCount": len(config.intents),
                    "version": config.version
                }
            )
            
            return config
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            if error_code == 'NoSuchKey':
                self.logger.info(
                    "Intent_Configuration not found in S3",
                    extra={"agentId": agent_id, "key": s3_key}
                )
                return None
            
            self.logger.error(
                "Failed to load Intent_Configuration",
                extra={
                    "agentId": agent_id,
                    "errorCode": error_code,
                    "errorMessage": str(e)
                }
            )
            raise
    
    def save_configuration(self, config: IntentConfiguration) -> bool:
        """
        Save Intent_Configuration to S3.
        
        Args:
            config: IntentConfiguration to save
            
        Returns:
            True if successful
            
        Raises:
            ClientError: If S3 operation fails after retries
        """
        s3_key = self.get_s3_key(config.agent_id)
        
        self.logger.info(
            "Saving Intent_Configuration to S3",
            extra={
                "agentId": config.agent_id,
                "bucket": self.bucket_name,
                "key": s3_key,
                "intentCount": len(config.intents),
                "version": config.version
            }
        )
        
        try:
            # Serialize configuration
            json_content = config.to_json()
            
            # Store to S3 with retry
            self._put_object_with_retry(s3_key, json_content)
            
            # Verify successful storage
            if not self._verify_storage(s3_key, json_content):
                raise RuntimeError("Failed to verify Intent_Configuration storage")
            
            self.logger.info(
                "Successfully saved Intent_Configuration",
                extra={
                    "agentId": config.agent_id,
                    "key": s3_key
                }
            )
            
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            self.logger.error(
                "Failed to save Intent_Configuration",
                extra={
                    "agentId": config.agent_id,
                    "errorCode": error_code,
                    "errorMessage": str(e)
                }
            )
            raise
    
    @exponential_backoff(max_attempts=3, base_delay=1.0)
    def _get_object_with_retry(self, s3_key: str) -> dict:
        """
        Get object from S3 with retry logic.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            S3 GetObject response
        """
        return self.s3_client.get_object(
            Bucket=self.bucket_name,
            Key=s3_key
        )
    
    @exponential_backoff(max_attempts=3, base_delay=1.0)
    def _put_object_with_retry(self, s3_key: str, content: str) -> dict:
        """
        Put object to S3 with retry logic.
        
        Args:
            s3_key: S3 object key
            content: JSON content to store
            
        Returns:
            S3 PutObject response
        """
        return self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=content.encode('utf-8'),
            ContentType='application/json',
            ServerSideEncryption='AES256'  # SSE-S3 encryption
        )
    
    def _verify_storage(self, s3_key: str, expected_content: str) -> bool:
        """
        Verify that the object was stored successfully.
        
        Args:
            s3_key: S3 object key
            expected_content: Expected JSON content
            
        Returns:
            True if verification succeeds
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            stored_content = response['Body'].read().decode('utf-8')
            
            # Compare JSON objects (not strings, to handle formatting differences)
            stored_json = json.loads(stored_content)
            expected_json = json.loads(expected_content)
            
            return stored_json == expected_json
            
        except Exception as e:
            self.logger.error(
                "Failed to verify Intent_Configuration storage",
                extra={
                    "key": s3_key,
                    "error": str(e)
                }
            )
            return False
