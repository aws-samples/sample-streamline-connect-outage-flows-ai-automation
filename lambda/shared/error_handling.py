"""Error handling utilities for Lambda functions."""

from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger


class SupervisorError(Exception):
    """Base exception for Supervisor AI Agent errors."""
    
    def __init__(self, message: str, user_message: str = None, guidance: str = None, details: dict = None):
        """
        Initialize error with technical and user-friendly messages.
        
        Args:
            message: Technical error message for logging
            user_message: User-friendly error message
            guidance: Specific guidance for resolution
            details: Additional error details
        """
        super().__init__(message)
        self.user_message = user_message or message
        self.guidance = guidance or "Please try again or contact support."
        self.details = details or {}
        if guidance:
            self.details['guidance'] = guidance


class AuthenticationError(SupervisorError):
    """Authentication-related errors."""
    
    def __init__(self, message: str, user_message: str = None, guidance: str = None):
        if not guidance:
            guidance = "Verify your phone number is authorized and your PIN is correct. Contact your administrator if you need access."
        super().__init__(message, user_message, guidance)


class AgentNotFoundError(SupervisorError):
    """AI Agent not found errors."""
    
    def __init__(self, agent_id: str, message: str = None):
        technical_message = message or f"AI Agent not found: {agent_id}"
        user_message = "The requested AI agent was not found."
        guidance = "Use the list agents operation to see available agents. Verify the agent ID is correct."
        super().__init__(technical_message, user_message, guidance, {'agentId': agent_id})


class BackupError(SupervisorError):
    """Backup operation errors."""
    
    def __init__(self, message: str, user_message: str = None, guidance: str = None):
        if not guidance:
            guidance = "The backup operation failed. The update has been aborted to prevent data loss. Please try again."
        super().__init__(message, user_message, guidance)


class RestoreError(SupervisorError):
    """Restore operation errors."""
    
    def __init__(self, message: str, user_message: str = None, guidance: str = None):
        if not guidance:
            guidance = "The restore operation failed. Verify backups exist for this agent. Contact support if the issue persists."
        super().__init__(message, user_message, guidance)


class TestError(SupervisorError):
    """Testing operation errors."""
    
    def __init__(self, message: str, user_message: str = None, guidance: str = None, critical: bool = False):
        if not guidance:
            if critical:
                guidance = "Critical tests failed. The update has been rolled back automatically. Review the test results and try again."
            else:
                guidance = "Some tests failed but the update was applied. Monitor the agent behavior and restore if needed."
        super().__init__(message, user_message, guidance, {'critical': critical})


class PromptUpdateError(SupervisorError):
    """Prompt update operation errors."""
    
    def __init__(self, message: str, user_message: str = None, guidance: str = None):
        if not guidance:
            guidance = "The prompt update failed. No changes were made to the agent. Please try again."
        super().__init__(message, user_message, guidance)


class IntentNotFoundError(SupervisorError):
    """Intent not found errors."""
    
    def __init__(self, intent_name: str, available_intents: list = None):
        technical_message = f"Intent not found: {intent_name}"
        user_message = f"The intent '{intent_name}' was not found in the agent configuration."
        
        if available_intents:
            intent_list = ", ".join(available_intents)
            guidance = f"Available intents are: {intent_list}. Please specify one of these intents."
        else:
            guidance = "Use the list intents operation to see available intents for this agent."
        
        super().__init__(
            technical_message, 
            user_message, 
            guidance, 
            {'intentName': intent_name, 'availableIntents': available_intents}
        )


class IntentConfigurationError(SupervisorError):
    """Intent configuration errors."""
    
    def __init__(self, message: str, user_message: str = None, guidance: str = None):
        if not guidance:
            guidance = "The intent configuration operation failed. Please try again or contact support."
        super().__init__(message, user_message, guidance)


def translate_aws_error(error: ClientError, logger: Logger = None) -> Dict[str, str]:
    """
    Translate AWS API error to user-friendly message with resolution guidance.
    
    Args:
        error: Boto3 ClientError
        logger: Logger instance for technical logging
        
    Returns:
        Dictionary with 'message' and 'guidance' keys
    """
    error_code = error.response.get('Error', {}).get('Code', 'Unknown')
    error_message = error.response.get('Error', {}).get('Message', 'Unknown error')
    operation = getattr(error, 'operation_name', 'Unknown')
    
    # Log technical details
    if logger:
        logger.error(
            "AWS API error",
            extra={
                "errorCode": error_code,
                "errorMessage": error_message,
                "operation": operation,
                "httpStatusCode": error.response.get('ResponseMetadata', {}).get('HTTPStatusCode')
            }
        )
    
    # Map error codes to user-friendly messages with resolution guidance
    error_translations = {
        # Amazon Q in Connect errors
        'AccessDeniedException': {
            'message': "Access denied to AI agent service.",
            'guidance': "Verify that IAM permissions are configured correctly for the Lambda function. Contact your administrator if the issue persists."
        },
        'ResourceNotFoundException': {
            'message': "The requested AI agent or resource was not found.",
            'guidance': "Verify the agent ID is correct. Use the list agents operation to see available agents."
        },
        'ThrottlingException': {
            'message': "Request rate limit exceeded.",
            'guidance': "The system is experiencing high load. Please wait 30 seconds and try again."
        },
        'ValidationException': {
            'message': "Invalid request parameters provided.",
            'guidance': "Check that all required information is provided correctly. If describing an outage, include affected services and available services."
        },
        'ConflictException': {
            'message': "Resource conflict detected.",
            'guidance': "Another update may be in progress. Wait a moment and try again."
        },
        'ServiceQuotaExceededException': {
            'message': "Service quota exceeded.",
            'guidance': "Contact AWS support to request a quota increase for Amazon Q in Connect."
        },
        'InternalServerError': {
            'message': "AWS service encountered an error.",
            'guidance': "This is a temporary issue. Please try again in a few moments."
        },
        
        # S3 errors
        'NoSuchKey': {
            'message': "The requested backup file was not found.",
            'guidance': "Verify the agent has been backed up previously. Check the backup bucket for available backups."
        },
        'NoSuchBucket': {
            'message': "The backup storage bucket was not found.",
            'guidance': "Verify the CDK stack was deployed correctly. Contact your administrator to check S3 bucket configuration."
        },
        
        # Secrets Manager errors
        'ResourceNotFoundException': {
            'message': "The authentication secret was not found.",
            'guidance': "Verify the CDK stack was deployed correctly. Contact your administrator to check Secrets Manager configuration."
        },
        'DecryptionFailure': {
            'message': "Failed to decrypt authentication credentials.",
            'guidance': "Verify KMS key permissions are configured correctly. Contact your administrator."
        },
        
        # Lambda errors
        'InvalidParameterValue': {
            'message': "Invalid parameter value provided.",
            'guidance': "Check that all inputs are in the correct format. Phone numbers should be in E.164 format (+1234567890)."
        },
        'ResourceInUseException': {
            'message': "The resource is currently being updated.",
            'guidance': "Another operation is in progress. Please wait for it to complete and try again."
        },
        'TooManyRequestsException': {
            'message': "Too many concurrent requests.",
            'guidance': "The system is at capacity. Please wait a moment and try again."
        },
        
        # Lex errors
        'BadRequestException': {
            'message': "Invalid request to authentication service.",
            'guidance': "Ensure you entered a 6-digit PIN. Try again or contact support if the issue persists."
        },
        'NotFoundException': {
            'message': "Authentication service configuration not found.",
            'guidance': "Verify the Lex bot is configured correctly. Contact your administrator."
        },
        
        # Connect errors
        'InvalidRequestException': {
            'message': "Invalid request to contact center service.",
            'guidance': "Verify the contact flow is configured correctly. Contact your administrator."
        },
        'ResourceNotFoundException': {
            'message': "Contact center resource not found.",
            'guidance': "Verify the Amazon Connect instance and contact flow are configured correctly."
        }
    }
    
    # Get translation or use default
    translation = error_translations.get(
        error_code,
        {
            'message': "An error occurred while processing your request.",
            'guidance': "Please try again. If the issue persists, contact your administrator with the request ID."
        }
    )
    
    return translation


def handle_error(
    error: Exception,
    logger: Logger,
    operation: str,
    context: dict = None
) -> Dict[str, Any]:
    """
    Handle error with comprehensive logging and user-friendly response.
    
    Args:
        error: Exception that occurred
        logger: Logger instance
        operation: Operation being performed
        context: Additional context for logging
        
    Returns:
        Error response dictionary with message and guidance
    """
    # Log full technical details with stack trace
    logger.error(
        f"{operation} failed",
        extra={
            "operation": operation,
            "error": str(error),
            "errorType": type(error).__name__,
            "context": context or {},
        },
        exc_info=True  # Include stack trace
    )
    
    # Determine user-friendly message and guidance
    if isinstance(error, SupervisorError):
        user_message = error.user_message
        guidance = error.details.get('guidance', 'Please try again or contact support.')
    elif isinstance(error, ClientError):
        translation = translate_aws_error(error, logger)
        user_message = translation['message']
        guidance = translation['guidance']
    else:
        user_message = "An unexpected error occurred."
        guidance = "Please try again. If the issue persists, contact support with the request ID."
    
    return {
        'success': False,
        'error': user_message,
        'guidance': guidance,
        'errorType': type(error).__name__
    }


def create_success_response(data: dict = None) -> Dict[str, Any]:
    """
    Create standardized success response.
    
    Args:
        data: Response data
        
    Returns:
        Success response dictionary
    """
    response = {'success': True}
    if data:
        response.update(data)
    return response


def create_error_response(
    message: str,
    guidance: str = None,
    error_type: str = None,
    details: dict = None
) -> Dict[str, Any]:
    """
    Create standardized error response with guidance.
    
    Args:
        message: User-friendly error message
        guidance: Specific guidance for resolution
        error_type: Error type/code
        details: Additional error details
        
    Returns:
        Error response dictionary
    """
    response = {
        'success': False,
        'error': message
    }
    
    if guidance:
        response['guidance'] = guidance
    
    if error_type:
        response['errorType'] = error_type
    
    if details:
        response['details'] = details
    
    return response
