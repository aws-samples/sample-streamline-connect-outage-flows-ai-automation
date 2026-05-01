"""Graceful degradation utilities for handling non-critical failures."""

import sys
import json
from typing import Callable, Any, Optional
from aws_lambda_powertools import Logger


def safe_cloudwatch_log(
    logger: Logger,
    log_function: Callable,
    message: str,
    extra: dict = None,
    exc_info: bool = False
):
    """
    Safely log to CloudWatch with fallback to stderr.
    
    If CloudWatch logging fails, logs to stderr to ensure the message is captured.
    
    Args:
        logger: Logger instance
        log_function: Logger method to call (logger.info, logger.error, etc.)
        message: Log message
        extra: Extra structured data
        exc_info: Whether to include exception info
    """
    try:
        if exc_info:
            log_function(message, extra=extra or {}, exc_info=True)
        else:
            log_function(message, extra=extra or {})
    except Exception as log_error:
        # Fallback to stderr if CloudWatch logging fails
        try:
            fallback_message = {
                "level": "ERROR",
                "message": "CloudWatch logging failed, using stderr fallback",
                "originalMessage": message,
                "originalExtra": extra or {},
                "loggingError": str(log_error)
            }
            print(json.dumps(fallback_message), file=sys.stderr)
        except Exception:
            # Last resort: plain text to stderr
            print(f"CRITICAL: Logging system failure. Original message: {message}", file=sys.stderr)


def safe_audit_log(
    audit_logger: Any,
    operation: str,
    agent_id: str,
    caller_phone_number: str,
    result: str,
    details: dict = None,
    error_message: str = None,
    fallback_logger: Logger = None
):
    """
    Safely write audit log to S3 with fallback to CloudWatch.
    
    If S3 audit logging fails, logs to CloudWatch to ensure audit trail is maintained.
    
    Args:
        audit_logger: Audit logger instance
        operation: Operation type
        agent_id: AI Agent ID
        caller_phone_number: Caller phone number
        result: Operation result
        details: Additional details
        error_message: Error message if operation failed
        fallback_logger: CloudWatch logger for fallback
    """
    try:
        audit_logger.log_operation(
            operation=operation,
            agent_id=agent_id,
            caller_phone_number=caller_phone_number,
            result=result,
            details=details or {},
            error_message=error_message
        )
    except Exception as audit_error:
        # Fallback to CloudWatch if S3 audit logging fails
        if fallback_logger:
            fallback_logger.warning(
                "S3 audit logging failed, logged to CloudWatch instead",
                extra={
                    "event": "AUDIT_LOG_FALLBACK",
                    "operation": operation,
                    "agentId": agent_id,
                    "callerPhoneNumber": caller_phone_number[-4:] if caller_phone_number else "unknown",
                    "result": result,
                    "details": details or {},
                    "errorMessage": error_message,
                    "auditError": str(audit_error)
                }
            )
        else:
            # Last resort: stderr
            print(
                json.dumps({
                    "level": "WARNING",
                    "message": "Audit logging failed",
                    "operation": operation,
                    "agentId": agent_id,
                    "result": result,
                    "auditError": str(audit_error)
                }),
                file=sys.stderr
            )


def safe_publish_metric(
    metrics: Any,
    metric_name: str,
    value: float,
    unit: str = None,
    dimensions: dict = None,
    fallback_logger: Logger = None
):
    """
    Safely publish metric to CloudWatch with fallback logging.
    
    If metrics publishing fails, logs a warning but continues operation.
    
    Args:
        metrics: Metrics instance
        metric_name: Name of the metric
        value: Metric value
        unit: Metric unit (Count, Milliseconds, etc.)
        dimensions: Metric dimensions
        fallback_logger: CloudWatch logger for fallback
    """
    try:
        if unit:
            metrics.add_metric(name=metric_name, unit=unit, value=value)
        else:
            metrics.add_metric(name=metric_name, value=value)
        
        # Add dimensions if provided
        if dimensions:
            for key, val in dimensions.items():
                metrics.add_dimension(name=key, value=val)
    except Exception as metric_error:
        # Log warning but don't fail the operation
        if fallback_logger:
            fallback_logger.warning(
                "Metrics publishing failed",
                extra={
                    "event": "METRICS_FAILURE",
                    "metricName": metric_name,
                    "metricValue": value,
                    "metricUnit": unit,
                    "dimensions": dimensions or {},
                    "metricError": str(metric_error)
                }
            )


def maintain_conversation_context(
    error: Exception,
    operation: str,
    context: dict,
    logger: Logger
) -> dict:
    """
    Maintain conversation context after recoverable errors.
    
    Preserves conversation state and allows retry without losing context.
    
    Args:
        error: Exception that occurred
        operation: Operation being performed
        context: Current conversation context
        logger: Logger instance
        
    Returns:
        Updated context with error information for retry
    """
    logger.warning(
        f"Recoverable error in {operation}, maintaining context for retry",
        extra={
            "event": "RECOVERABLE_ERROR",
            "operation": operation,
            "errorType": type(error).__name__,
            "errorMessage": str(error),
            "contextPreserved": True
        }
    )
    
    # Add error information to context for retry
    context['lastError'] = {
        'operation': operation,
        'errorType': type(error).__name__,
        'errorMessage': str(error),
        'retryable': True
    }
    
    return context


def is_recoverable_error(error: Exception) -> bool:
    """
    Determine if an error is recoverable.
    
    Recoverable errors include:
    - Throttling exceptions
    - Temporary service unavailability
    - Network timeouts
    - Transient AWS service errors
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is recoverable, False otherwise
    """
    from botocore.exceptions import ClientError
    
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        recoverable_codes = [
            'ThrottlingException',
            'TooManyRequestsException',
            'ServiceUnavailable',
            'InternalServerError',
            'RequestTimeout',
            'SlowDown'
        ]
        return error_code in recoverable_codes
    
    # Network and timeout errors are generally recoverable
    error_name = type(error).__name__
    recoverable_types = [
        'Timeout',
        'ConnectionError',
        'ReadTimeout',
        'ConnectTimeout'
    ]
    
    return any(recoverable in error_name for recoverable in recoverable_types)


def handle_non_critical_failure(
    error: Exception,
    component: str,
    logger: Logger,
    continue_operation: bool = True
) -> bool:
    """
    Handle non-critical component failure with graceful degradation.
    
    Logs the failure and determines whether to continue operation.
    
    Args:
        error: Exception that occurred
        component: Component that failed
        logger: Logger instance
        continue_operation: Whether to continue despite failure
        
    Returns:
        True if operation should continue, False if it should abort
    """
    logger.warning(
        f"Non-critical component failure: {component}",
        extra={
            "event": "NON_CRITICAL_FAILURE",
            "component": component,
            "errorType": type(error).__name__,
            "errorMessage": str(error),
            "continueOperation": continue_operation
        }
    )
    
    return continue_operation
