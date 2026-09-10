"""Retry logic with exponential backoff for AWS API calls."""

import time
import random
from typing import Callable, TypeVar, Any
from functools import wraps
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger


T = TypeVar('T')


class RetryableError(Exception):
    """Exception indicating an operation should be retried."""
    pass


def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error is retryable.
    
    Args:
        error: Exception to check
        
    Returns:
        True if error should be retried, False otherwise
    """
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        
        # Retryable AWS error codes
        retryable_codes = [
            'ThrottlingException',
            'TooManyRequestsException',
            'RequestLimitExceeded',
            'ServiceUnavailable',
            'InternalServerError',
            'InternalError',
            'RequestTimeout',
            'RequestTimeoutException',
            'PriorRequestNotComplete',
            'ConnectionError',
            'ProvisionedThroughputExceededException'
        ]
        
        return error_code in retryable_codes
    
    return False


def exponential_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True
):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles each retry)
        max_delay: Maximum delay in seconds
        jitter: Add random jitter to prevent thundering herd
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            logger = kwargs.get('logger')
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    is_last_attempt = attempt == max_attempts
                    
                    if not is_retryable_error(e) or is_last_attempt:
                        if logger:
                            logger.error(
                                f"Operation failed after {attempt} attempts",
                                extra={
                                    "function": func.__name__,
                                    "attempt": attempt,
                                    "error": str(e),
                                    "errorType": type(e).__name__
                                }
                            )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random())  # nosec B311 - jitter for load distribution, not security
                    
                    if logger:
                        logger.warning(
                            f"Retrying after error (attempt {attempt}/{max_attempts})",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt,
                                "delaySeconds": delay,
                                "error": str(e),
                                "errorType": type(e).__name__
                            }
                        )
                    
                    time.sleep(delay)
            
            # Should never reach here, but for type safety
            raise RuntimeError(f"Retry logic failed after {max_attempts} attempts")
        
        return wrapper
    return decorator


def retry_with_backoff(
    func: Callable[..., T],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    logger: Logger = None,
    *args,
    **kwargs
) -> T:
    """
    Retry a function with exponential backoff (non-decorator version).
    
    Args:
        func: Function to retry
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        logger: Logger instance for logging retry attempts
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func
        
    Returns:
        Result of successful function call
        
    Raises:
        Last exception if all retries fail
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            is_last_attempt = attempt == max_attempts
            
            if not is_retryable_error(e) or is_last_attempt:
                if logger:
                    logger.error(
                        f"Operation failed after {attempt} attempts",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt,
                            "error": str(e),
                            "errorType": type(e).__name__
                        }
                    )
                raise
            
            # Calculate delay with exponential backoff
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            delay = delay * (0.5 + random.random())  # nosec B311 - jitter for load distribution, not security
            
            if logger:
                logger.warning(
                    f"Retrying after error (attempt {attempt}/{max_attempts})",
                    extra={
                        "function": func.__name__,
                        "attempt": attempt,
                        "delaySeconds": delay,
                        "error": str(e),
                        "errorType": type(e).__name__
                    }
                )
            
            time.sleep(delay)
    
    raise RuntimeError(f"Retry logic failed after {max_attempts} attempts")
