"""HMAC-SHA256 request signing for inter-Lambda communication."""
import hashlib
import hmac
import json
import time
import os
from typing import Dict, Any
from aws_lambda_powertools import Logger

from shared.aws_clients import AWSClients

_cached_key = None


def _get_signing_key(logger: Logger = None) -> str:
    global _cached_key
    if _cached_key:
        return _cached_key
    secret_arn = os.environ.get('SIGNING_KEY_SECRET_ARN', '')
    if not secret_arn:
        raise ValueError('SIGNING_KEY_SECRET_ARN not configured')
    client = AWSClients.get_secrets_manager_client()
    response = client.get_secret_value(SecretId=secret_arn)
    _cached_key = response['SecretString']
    return _cached_key


def sign_request(payload: dict, logger: Logger = None) -> dict:
    """Add x-signature and x-timestamp to payload."""
    key = _get_signing_key(logger)
    timestamp = str(int(time.time()))
    message = json.dumps(payload, sort_keys=True, default=str) + timestamp
    signature = hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
    payload['x-signature'] = signature
    payload['x-timestamp'] = timestamp
    return payload


def verify_request(payload: dict, max_age_seconds: int = 300, logger: Logger = None) -> bool:
    """Verify x-signature and x-timestamp in payload. Returns True if valid."""
    signature = payload.pop('x-signature', None)
    timestamp = payload.pop('x-timestamp', None)
    if not signature or not timestamp:
        if logger:
            logger.warning('Missing signature or timestamp in request')
        return False
    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > max_age_seconds:
            if logger:
                logger.warning('Request timestamp expired', extra={'age_seconds': abs(time.time() - ts)})
            return False
    except ValueError:
        return False
    key = _get_signing_key(logger)
    message = json.dumps(payload, sort_keys=True, default=str) + timestamp
    expected = hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
