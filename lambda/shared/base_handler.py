"""Base Lambda handler class with common functionality.

Performance optimizations:
- Lazy imports for faster cold starts
- Client pre-warming support
- Efficient error handling
"""

import json
import time
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

# Import only essential modules at module level
# Other imports are lazy-loaded when needed
from aws_lambda_powertools.utilities.typing import LambdaContext


class BaseLambdaHandler(ABC):
    """
    Base class for Lambda handlers with common functionality.
    
    Provides:
    - Structured logging
    - Error handling
    - Metrics publishing
    - AWS client management
    - Request/response handling
    
    Performance optimizations:
    - Lazy imports to reduce cold start time
    - Client pre-warming for frequently used services
    - Efficient error handling with minimal overhead
    """
    
    def __init__(self, service_name: str, prewarm_clients: Optional[list[str]] = None):
        """
        Initialize base handler.
        
        Args:
            service_name: Name of the Lambda function/service
            prewarm_clients: List of AWS clients to pre-warm during initialization
                           (e.g., ['s3', 'qconnect', 'lambda'])
        """
        self.service_name = service_name
        
        # Lazy import logging and tracing modules
        from .logging_config import get_logger
        from aws_lambda_powertools import Tracer, Metrics
        from .aws_clients import AWSClients
        
        self.logger = get_logger(service_name)
        self.tracer = Tracer(service=service_name)
        self.metrics = Metrics(namespace="SupervisorAIAgent", service=service_name)
        self.aws_clients = AWSClients
        
        # Pre-warm specified clients to reduce first-call latency
        if prewarm_clients:
            self.logger.debug(
                "Pre-warming AWS clients",
                extra={"clients": prewarm_clients}
            )
            self.aws_clients.prewarm_clients(prewarm_clients)
    
    @abstractmethod
    def process_event(self, event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        """
        Process Lambda event (must be implemented by subclasses).
        
        Args:
            event: Lambda event
            context: Lambda context
            
        Returns:
            Response dictionary
        """
        pass
    
    def handler(self, event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        """
        Main Lambda handler with error handling, metrics, and graceful degradation.
        
        Args:
            event: Lambda event
            context: Lambda context
            
        Returns:
            Response dictionary
        """
        # Lazy import error handling and graceful degradation modules
        from .error_handling import handle_error
        from .graceful_degradation import (
            safe_cloudwatch_log,
            safe_audit_log,
            safe_publish_metric,
            maintain_conversation_context,
            is_recoverable_error
        )
        
        start_time = time.time()
        
        # Log incoming request with graceful degradation
        safe_cloudwatch_log(
            self.logger,
            self.logger.info,
            "Processing request",
            extra={
                "requestId": context.aws_request_id,
                "functionName": context.function_name,
                "eventType": event.get('operation') or event.get('Details', {}).get('ContactData', {}).get('Attributes', {}).get('operation')
            }
        )
        
        try:
            # Process event
            response = self.process_event(event, context)
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log success with graceful degradation
            safe_cloudwatch_log(
                self.logger,
                self.logger.info,
                "Request completed successfully",
                extra={
                    "requestId": context.aws_request_id,
                    "durationMs": duration_ms
                }
            )
            
            # Publish success metrics with graceful degradation
            safe_publish_metric(
                self.metrics,
                "RequestSuccess",
                1,
                unit="Count",
                fallback_logger=self.logger
            )
            safe_publish_metric(
                self.metrics,
                "RequestDuration",
                duration_ms,
                unit="Milliseconds",
                fallback_logger=self.logger
            )
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Handle error with logging
            error_response = handle_error(
                error=e,
                logger=self.logger,
                operation=self.service_name,
                context={
                    "requestId": context.aws_request_id,
                    "functionName": context.function_name,
                    "durationMs": duration_ms
                }
            )
            
            # Add recoverable flag to response if applicable
            if is_recoverable_error(e):
                error_response['recoverable'] = True
                error_response['context'] = maintain_conversation_context(
                    e,
                    self.service_name,
                    event.copy(),
                    self.logger
                )
            
            # Write audit log for failure with graceful degradation
            if hasattr(self, 'audit_logger'):
                agent_id = event.get('agentId', 'unknown')
                caller_phone = event.get('metadata', {}).get('callerPhoneNumber') or event.get('callerPhoneNumber', 'unknown')
                
                safe_audit_log(
                    self.audit_logger,
                    operation=self.service_name.upper().replace('-', '_'),
                    agent_id=agent_id,
                    caller_phone_number=caller_phone,
                    result="FAILURE",
                    details={
                        "requestId": context.aws_request_id,
                        "durationMs": duration_ms
                    },
                    error_message=str(e),
                    fallback_logger=self.logger
                )
            
            # Publish failure metrics with graceful degradation
            safe_publish_metric(
                self.metrics,
                "RequestFailure",
                1,
                unit="Count",
                fallback_logger=self.logger
            )
            safe_publish_metric(
                self.metrics,
                "RequestDuration",
                duration_ms,
                unit="Milliseconds",
                fallback_logger=self.logger
            )
            
            return error_response
        
        finally:
            # Flush metrics with error handling
            try:
                self.metrics.flush_metrics()
            except Exception as metrics_error:
                # Log warning but don't fail the request
                safe_cloudwatch_log(
                    self.logger,
                    self.logger.warning,
                    "Failed to flush metrics",
                    extra={"error": str(metrics_error)}
                )
    
    def get_required_env_var(self, var_name: str) -> str:
        """
        Get required environment variable with validation.
        
        Args:
            var_name: Environment variable name
            
        Returns:
            Environment variable value
            
        Raises:
            ValueError: If environment variable is not set
        """
        import os
        value = os.environ.get(var_name)
        if not value:
            raise ValueError(f"Required environment variable {var_name} is not set")
        return value
    
    def parse_json_event(self, event: Dict[str, Any], key: str = 'body') -> Dict[str, Any]:
        """
        Parse JSON from event body or return event directly.
        
        Args:
            event: Lambda event
            key: Key containing JSON string (default: 'body')
            
        Returns:
            Parsed event dictionary
        """
        if key in event and isinstance(event[key], str):
            try:
                return json.loads(event[key])
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON from {key}", extra={"error": str(e)})
                raise ValueError(f"Invalid JSON in {key}")
        return event
    
    def create_response(
        self,
        status_code: int = 200,
        body: Dict[str, Any] = None,
        headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Create API Gateway response.
        
        Args:
            status_code: HTTP status code
            body: Response body
            headers: Response headers
            
        Returns:
            API Gateway response dictionary
        """
        response = {
            'statusCode': status_code,
            'headers': headers or {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }
        
        if body is not None:
            response['body'] = json.dumps(body)
        
        return response
