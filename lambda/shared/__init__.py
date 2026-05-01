# Shared utilities for Lambda functions

from .aws_clients import AWSClients, BOTO3_CONFIG
from .logging_config import get_logger, log_authentication_attempt, log_operation
from .retry_logic import (
    exponential_backoff,
    retry_with_backoff,
    is_retryable_error,
    RetryableError
)
from .error_handling import (
    SupervisorError,
    AuthenticationError,
    AgentNotFoundError,
    BackupError,
    RestoreError,
    TestError,
    PromptUpdateError,
    translate_aws_error,
    handle_error,
    create_success_response,
    create_error_response
)
from .base_handler import BaseLambdaHandler
from .audit_logging import AuditLogger
from .metrics_publisher import MetricsPublisher

__all__ = [
    # AWS Clients
    'AWSClients',
    'BOTO3_CONFIG',
    
    # Logging
    'get_logger',
    'log_authentication_attempt',
    'log_operation',
    
    # Retry Logic
    'exponential_backoff',
    'retry_with_backoff',
    'is_retryable_error',
    'RetryableError',
    
    # Error Handling
    'SupervisorError',
    'AuthenticationError',
    'AgentNotFoundError',
    'BackupError',
    'RestoreError',
    'TestError',
    'PromptUpdateError',
    'translate_aws_error',
    'handle_error',
    'create_success_response',
    'create_error_response',
    
    # Base Handler
    'BaseLambdaHandler',
    
    # Audit Logging
    'AuditLogger',
    
    # Metrics Publishing
    'MetricsPublisher',
]
