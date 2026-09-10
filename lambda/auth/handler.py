"""Authentication Lambda handler for phone and PIN validation."""

import os
import json
import uuid
import time
from typing import Dict, Any
from aws_lambda_powertools.utilities.typing import LambdaContext

import sys
from pathlib import Path
# Add parent directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.base_handler import BaseLambdaHandler
from shared.logging_config import log_authentication_attempt
from shared.aws_clients import AWSClients
from shared.metrics_publisher import MetricsPublisher
from .phone_validator import (
    parse_allowlist,
    validate_phone_number,
    create_phone_validation_response
)
from .pin_validator import validate_pin
from .rate_limiter import check_lockout, record_failed_attempt, clear_attempts


class AuthenticationHandler(BaseLambdaHandler):
    """Handler for authentication operations (phone and PIN validation)."""
    
    def __init__(self):
        super().__init__(service_name="supervisor-ai-agent-auth")
        
        # Load secret ARN for PIN validation and phone allowlist
        self.secret_arn = os.environ.get('SECRET_ARN', '')
        
        # Load phone allowlist from Secrets Manager (same secret as PIN)
        self.phone_allowlist = self._load_allowlist_from_secret()
    
    def _load_allowlist_from_secret(self):
        """Load phone allowlist from Secrets Manager secret."""
        if not self.secret_arn:
            self.logger.warning("SECRET_ARN not configured, allowlist empty")
            return []
        try:
            secrets_client = AWSClients.get_secrets_manager_client()
            response = secrets_client.get_secret_value(SecretId=self.secret_arn)
            secret_data = json.loads(response['SecretString'])
            allowlist = secret_data.get('allowlist', [])
            if isinstance(allowlist, str):
                allowlist = parse_allowlist(allowlist)
            self.logger.info("Loaded phone allowlist from Secrets Manager", extra={"count": len(allowlist)})
            return allowlist
        except Exception as e:
            self.logger.error("Failed to load allowlist from Secrets Manager", extra={"error": str(e)})
            return []
    
    def process_event(self, event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        """
        Process authentication event.
        
        Supports:
        - Phone validation from Contact Flow (has Details.ContactData)
        - Direct PIN validation from MCP tool (has operation=validate_pin)
        """
        if self._is_phone_validation_event(event):
            return self._handle_phone_validation(event, context)
        elif self._is_direct_pin_event(event):
            return self._handle_direct_pin_validation(event, context)
        else:
            self.logger.error("Unknown event type", extra={"event": event})
            raise ValueError("Unknown authentication event type")
    
    def _is_phone_validation_event(self, event: Dict[str, Any]) -> bool:
        """Check if event is a phone validation request from Contact Flow."""
        # Flow module MCP tool calls also have Details.ContactData but include operation in Parameters
        if self._is_direct_pin_event(event):
            return False
        return 'Details' in event and 'ContactData' in event['Details']
    
    def _is_direct_pin_event(self, event: Dict[str, Any]) -> bool:
        """Check if event is a PIN validation from MCP tool (direct or via flow module)."""
        if event.get('operation') == 'validate_pin':
            return True
        # Flow module format: operation is under Details.Parameters
        params = event.get('Details', {}).get('Parameters', {})
        return params.get('operation') == 'validate_pin'
    
    def _handle_phone_validation(
        self,
        event: Dict[str, Any],
        context: LambdaContext
    ) -> Dict[str, Any]:
        """Handle phone number validation from Contact Flow."""
        contact_data = event.get('Details', {}).get('ContactData', {})
        customer_endpoint = contact_data.get('CustomerEndpoint', {})
        caller_number = customer_endpoint.get('Address', '')
        
        self.logger.info(
            "Processing phone validation",
            extra={
                "requestId": context.aws_request_id,
                "contactId": contact_data.get('ContactId')
            }
        )
        
        is_authenticated = validate_phone_number(
            caller_number=caller_number,
            allowlist=self.phone_allowlist,
            logger=self.logger
        )
        
        log_authentication_attempt(
            logger=self.logger,
            phone_number=caller_number,
            result="SUCCESS" if is_authenticated else "FAILURE",
            request_id=context.aws_request_id,
            details={"authenticationType": "PHONE"}
        )
        
        MetricsPublisher.publish_authentication_attempt(
            metrics=self.metrics,
            phone_number=caller_number,
            result="SUCCESS" if is_authenticated else "FAILURE"
        )
        
        return create_phone_validation_response(
            authenticated=is_authenticated,
            phone_number=caller_number
        )
    
    def _handle_direct_pin_validation(
        self,
        event: Dict[str, Any],
        context: LambdaContext
    ) -> Dict[str, Any]:
        """Handle direct PIN validation from AI agent MCP tool."""
        # Extract PIN from either top-level or Details.Parameters (flow module format)
        params = event.get('Details', {}).get('Parameters', event)
        provided_pin = str(params.get('pin', ''))
        phone_number = params.get('phoneNumber', 'MCP_TOOL')
        
        self.logger.info(
            "Processing direct PIN validation",
            extra={"requestId": context.aws_request_id}
        )
        
        # Check rate limiting lockout
        is_locked, lock_message = check_lockout(phone_number, logger=self.logger)
        if is_locked:
            MetricsPublisher.publish_authentication_attempt(
                metrics=self.metrics,
                phone_number=phone_number,
                result="LOCKED_OUT"
            )
            return {
                "authenticated": "false",
                "message": lock_message
            }
        
        is_valid = validate_pin(
            provided_pin=provided_pin,
            secret_arn=self.secret_arn,
            logger=self.logger
        )
        
        # Record attempt result for rate limiting
        auth_token = None
        if is_valid:
            clear_attempts(phone_number, logger=self.logger)
            # Generate server-side auth token
            auth_token = str(uuid.uuid4())
            try:
                table_name = os.environ.get('PIN_ATTEMPTS_TABLE', 'supervisor-ai-agent-pin-attempts')
                dynamodb = AWSClients.get_dynamodb_resource()
                table = dynamodb.Table(table_name)
                table.put_item(Item={
                    'phone_number': f'auth_token#{auth_token}',
                    'ttl_expiry': int(time.time()) + 900,  # 15 min TTL
                    'created_at': int(time.time()),
                    'caller_phone': phone_number,
                })
            except Exception as e:
                self.logger.error('Failed to store auth token', extra={'error': str(e)})
                auth_token = None
        else:
            locked_out = record_failed_attempt(phone_number, logger=self.logger)
            if locked_out:
                self.metrics.add_metric(name="PinLockout", unit="Count", value=1)
        
        log_authentication_attempt(
            logger=self.logger,
            phone_number=phone_number,
            result="SUCCESS" if is_valid else "FAILURE",
            request_id=context.aws_request_id,
            details={"authenticationType": "PIN_DIRECT"}
        )
        
        MetricsPublisher.publish_authentication_attempt(
            metrics=self.metrics,
            phone_number=phone_number,
            result="SUCCESS" if is_valid else "FAILURE"
        )
        
        response = {
            "authenticated": str(is_valid).lower(),
            "message": "Authentication successful." if is_valid else "Invalid PIN."
        }
        if is_valid and auth_token:
            response['authToken'] = auth_token
        return response


# Lambda handler function (lazy init for test compatibility)
_handler_instance = None


def _get_handler():
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = AuthenticationHandler()
    return _handler_instance


def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler entry point."""
    return _get_handler().handler(event, context)
