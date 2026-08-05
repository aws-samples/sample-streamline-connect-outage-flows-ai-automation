"""PIN brute-force rate limiting using DynamoDB."""
import os
import time
from typing import Tuple
from aws_lambda_powertools import Logger

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.aws_clients import AWSClients

MAX_ATTEMPTS = 3
LOCKOUT_SECONDS = 1800  # 30 minutes
TTL_SECONDS = 3600  # 1 hour auto-cleanup


def _get_table():
    table_name = os.environ.get('PIN_ATTEMPTS_TABLE', 'supervisor-ai-agent-pin-attempts')
    dynamodb = AWSClients.get_dynamodb_resource()
    return dynamodb.Table(table_name)


def check_lockout(phone_number: str, logger: Logger = None) -> Tuple[bool, str]:
    """Check if phone number is locked out. Returns (is_locked, message)."""
    try:
        table = _get_table()
        response = table.get_item(Key={'phone_number': phone_number})
        item = response.get('Item')
        if not item:
            return False, ''
        locked_until = float(item.get('locked_until', 0))
        if locked_until > time.time():
            remaining = int(locked_until - time.time()) // 60
            if logger:
                logger.warning('Phone number locked out', extra={'phone_number': phone_number[-4:], 'remaining_minutes': remaining})
            return True, f'Too many failed attempts. Try again in {remaining} minutes.'
        return False, ''
    except Exception as e:
        if logger:
            logger.error('Failed to check lockout — failing closed for security', extra={'error': str(e)})
        return True, 'Authentication service temporarily unavailable. Please try again later.'  # Fail closed for auth


def record_failed_attempt(phone_number: str, logger: Logger = None) -> bool:
    """Record a failed PIN attempt. Returns True if now locked out."""
    try:
        table = _get_table()
        now = time.time()
        response = table.update_item(
            Key={'phone_number': phone_number},
            UpdateExpression='SET attempt_count = if_not_exists(attempt_count, :zero) + :one, last_attempt = :now, ttl_expiry = :ttl',
            ExpressionAttributeValues={':zero': 0, ':one': 1, ':now': int(now), ':ttl': int(now + TTL_SECONDS)},
            ReturnValues='ALL_NEW'
        )
        count = response['Attributes'].get('attempt_count', 0)
        if count >= MAX_ATTEMPTS:
            table.update_item(
                Key={'phone_number': phone_number},
                UpdateExpression='SET locked_until = :lock',
                ExpressionAttributeValues={':lock': int(now + LOCKOUT_SECONDS)}
            )
            if logger:
                logger.warning('Phone number locked out after max attempts', extra={'phone_number': phone_number[-4:], 'attempts': count})
            return True
        return False
    except Exception as e:
        if logger:
            logger.error('Failed to record attempt', extra={'error': str(e)})
        return False


def clear_attempts(phone_number: str, logger: Logger = None):
    """Clear attempt counter on successful PIN validation."""
    try:
        table = _get_table()
        table.delete_item(Key={'phone_number': phone_number})
    except Exception as e:
        if logger:
            logger.error('Failed to clear attempts', extra={'error': str(e)})
