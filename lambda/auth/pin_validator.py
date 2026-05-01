"""PIN validation against Secrets Manager."""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from aws_lambda_powertools import Logger

# Add parent directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.aws_clients import AWSClients
from shared.retry_logic import exponential_backoff


@exponential_backoff(max_attempts=3)
def retrieve_pin_from_secrets_manager(
    secret_arn: str,
    logger: Logger = None
) -> str:
    """
    Retrieve supervisor PIN from AWS Secrets Manager.
    
    Args:
        secret_arn: ARN of the secret containing the PIN
        logger: Logger instance for logging
        
    Returns:
        PIN value
        
    Raises:
        Exception: If secret retrieval fails
    """
    if not secret_arn:
        raise ValueError("Secret ARN is not configured")
    
    secrets_client = AWSClients.get_secrets_manager_client()
    
    try:
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        
        if 'SecretString' in response:
            secret_data = json.loads(response['SecretString'])
            pin = secret_data.get('pin', '')
            
            if not pin:
                raise ValueError("PIN not found in secret")
            
            if logger:
                logger.info("Successfully retrieved PIN from Secrets Manager")
            
            return pin
        else:
            raise ValueError("Secret does not contain SecretString")
            
    except Exception as e:
        if logger:
            logger.error(
                "Failed to retrieve PIN from Secrets Manager",
                extra={
                    "secretArn": secret_arn,
                    "error": str(e),
                    "errorType": type(e).__name__
                }
            )
        raise


def validate_pin(
    provided_pin: str,
    secret_arn: str,
    logger: Logger = None
) -> bool:
    """
    Validate provided PIN against stored PIN in Secrets Manager.
    
    Args:
        provided_pin: PIN provided by caller
        secret_arn: ARN of the secret containing the correct PIN
        logger: Logger instance for logging
        
    Returns:
        True if PIN matches, False otherwise
    """
    if not provided_pin:
        if logger:
            logger.warning("Empty PIN provided")
        return False
    
    try:
        stored_pin = retrieve_pin_from_secrets_manager(
            secret_arn=secret_arn,
            logger=logger
        )
        
        is_valid = provided_pin == stored_pin
        
        if logger:
            logger.info(
                f"PIN validation result: {'VALID' if is_valid else 'INVALID'}",
                extra={"result": "VALID" if is_valid else "INVALID"}
            )
        
        return is_valid
        
    except Exception as e:
        if logger:
            logger.error(
                "PIN validation failed due to error",
                extra={
                    "error": str(e),
                    "errorType": type(e).__name__
                }
            )
        # Fail closed - deny access on error
        return False
