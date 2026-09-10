"""Structured logging configuration using AWS Lambda Powertools."""

import os
from aws_lambda_powertools import Logger
from aws_lambda_powertools.logging import correlation_paths


def get_logger(service_name: str) -> Logger:
    """
    Get a configured logger with structured JSON output.
    
    Args:
        service_name: Name of the Lambda function/service
        
    Returns:
        Configured Logger instance with structured JSON format
    """
    log_level = os.environ.get('LOG_LEVEL', 'INFO')
    
    logger = Logger(
        service=service_name,
        level=log_level,
        json_default=str,  # Handle non-serializable objects
        utc=True,  # Use UTC timestamps
        log_uncaught_exceptions=True  # Automatically log uncaught exceptions
    )
    
    return logger


def log_authentication_attempt(
    logger: Logger,
    phone_number: str,
    result: str,
    request_id: str,
    details: dict = None
):
    """
    Log authentication attempt with structured format.
    
    Args:
        logger: Logger instance
        phone_number: Caller phone number (last 4 digits only for privacy)
        result: Authentication result (SUCCESS, FAILURE)
        request_id: AWS request ID
        details: Additional details to log
    """
    # Mask phone number for privacy (show last 4 digits only)
    masked_phone = f"***{phone_number[-4:]}" if len(phone_number) >= 4 else "****"
    
    logger.info(
        "Authentication attempt",
        extra={
            "event": "AUTHENTICATION_ATTEMPT",
            "phoneNumber": masked_phone,
            "result": result,
            "requestId": request_id,
            **(details or {})
        }
    )


def log_operation(
    logger: Logger,
    operation: str,
    agent_id: str,
    result: str,
    duration_ms: int = None,
    details: dict = None
):
    """
    Log operation with structured format.
    
    Args:
        logger: Logger instance
        operation: Operation type (PROMPT_UPDATE, BACKUP, RESTORE, TEST)
        agent_id: AI Agent ID
        result: Operation result (SUCCESS, FAILURE)
        duration_ms: Operation duration in milliseconds
        details: Additional details to log
    """
    log_data = {
        "event": operation,
        "agentId": agent_id,
        "result": result,
        **(details or {})
    }
    
    if duration_ms is not None:
        log_data["durationMs"] = duration_ms
    
    if result == "SUCCESS":
        logger.info(f"{operation} completed", extra=log_data)
    else:
        logger.error(f"{operation} failed", extra=log_data)


def log_error_with_context(
    logger: Logger,
    error: Exception,
    operation: str,
    context: dict = None
):
    """
    Log error with full technical details and stack trace.
    
    This function ensures comprehensive error logging with:
    - ERROR log level
    - Full stack trace (exc_info=True)
    - Structured context information
    - Error type and message
    
    Args:
        logger: Logger instance
        error: Exception that occurred
        operation: Operation being performed
        context: Additional context for debugging
    """
    logger.error(
        f"{operation} failed: {str(error)}",
        extra={
            "event": "ERROR",
            "operation": operation,
            "errorType": type(error).__name__,
            "errorMessage": str(error),
            "context": context or {}
        },
        exc_info=True  # Include full stack trace
    )


def log_warning_with_context(
    logger: Logger,
    message: str,
    operation: str,
    context: dict = None
):
    """
    Log warning with context for recoverable issues.
    
    Args:
        logger: Logger instance
        message: Warning message
        operation: Operation being performed
        context: Additional context
    """
    logger.warning(
        message,
        extra={
            "event": "WARNING",
            "operation": operation,
            "context": context or {}
        }
    )
