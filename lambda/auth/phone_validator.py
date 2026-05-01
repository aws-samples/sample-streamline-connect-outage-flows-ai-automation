"""Phone number validation for Amazon Connect Contact Flow."""

import os
from typing import Dict, Any, List
from datetime import datetime
from aws_lambda_powertools import Logger


def parse_allowlist(allowlist_str: str) -> List[str]:
    """
    Parse phone allowlist from comma-separated string.
    
    Args:
        allowlist_str: Comma-separated list of E.164 phone numbers
        
    Returns:
        List of phone numbers
    """
    if not allowlist_str:
        return []
    
    # Split by comma and strip whitespace
    phones = [phone.strip() for phone in allowlist_str.split(',')]
    
    # Filter out empty strings
    return [phone for phone in phones if phone]


def validate_phone_number(
    caller_number: str,
    allowlist: List[str],
    logger: Logger = None
) -> bool:
    """
    Validate caller phone number against allowlist.
    
    Args:
        caller_number: Caller phone number in E.164 format
        allowlist: List of allowed phone numbers
        logger: Logger instance for logging
        
    Returns:
        True if phone number is in allowlist, False otherwise
    """
    if not caller_number:
        if logger:
            logger.warning("Empty caller phone number provided")
        return False
    
    if not allowlist:
        if logger:
            logger.warning("Empty phone allowlist configured")
        return False
    
    # Normalize phone numbers for comparison (remove spaces, dashes)
    normalized_caller = caller_number.replace(' ', '').replace('-', '')
    normalized_allowlist = [phone.replace(' ', '').replace('-', '') for phone in allowlist]
    
    is_allowed = normalized_caller in normalized_allowlist
    
    if logger:
        # Mask phone number for privacy (show last 4 digits only)
        masked_phone = f"***{caller_number[-4:]}" if len(caller_number) >= 4 else "****"
        logger.info(
            f"Phone validation: {masked_phone}",
            extra={
                "phoneNumber": masked_phone,
                "result": "ALLOWED" if is_allowed else "DENIED"
            }
        )
    
    return is_allowed


def create_phone_validation_response(
    authenticated: bool,
    phone_number: str
) -> Dict[str, Any]:
    """
    Create phone validation response for Contact Flow.
    
    Args:
        authenticated: Whether phone number is authenticated
        phone_number: Caller phone number
        
    Returns:
        Response dictionary for Contact Flow
    """
    from datetime import datetime, timezone
    return {
        "authenticated": str(authenticated).lower(),
        "phoneNumber": phone_number,
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    }
