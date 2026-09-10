"""AWS SDK client factory with connection pooling and configuration.

Optimizations:
- Connection pooling with increased pool size for concurrent operations
- Adaptive retry mode for better handling of transient failures
- Client reuse across invocations (Lambda container reuse)
- Lazy client initialization to reduce cold start time
"""

import os
import boto3
from botocore.config import Config
from typing import Optional


# Optimized Boto3 configuration with enhanced connection pooling
# Increased max_pool_connections from 50 to 100 for better parallelization
BOTO3_CONFIG = Config(
    retries={
        'max_attempts': 3,
        'mode': 'adaptive'  # Adaptive mode adjusts retry behavior based on response
    },
    max_pool_connections=100,  # Increased for parallel operations
    connect_timeout=5,
    read_timeout=60,
    tcp_keepalive=True  # Keep connections alive for reuse
)


class AWSClients:
    """Factory for AWS SDK clients with connection pooling."""
    
    _s3_client = None
    _secrets_manager_client = None
    _lambda_client = None
    _cloudwatch_client = None
    _q_connect_client = None
    _dynamodb_resource = None
    
    @classmethod
    def _get_region(cls, region: Optional[str] = None) -> Optional[str]:
        """Get region from parameter or environment variable."""
        return region or os.environ.get('AWS_REGION')
    
    @classmethod
    def get_s3_client(cls, region: Optional[str] = None):
        """Get or create S3 client with connection pooling."""
        if cls._s3_client is None:
            cls._s3_client = boto3.client('s3', config=BOTO3_CONFIG, region_name=cls._get_region(region))
        return cls._s3_client
    
    @classmethod
    def get_secrets_manager_client(cls, region: Optional[str] = None):
        """Get or create Secrets Manager client with connection pooling."""
        if cls._secrets_manager_client is None:
            cls._secrets_manager_client = boto3.client(
                'secretsmanager', 
                config=BOTO3_CONFIG, 
                region_name=cls._get_region(region)
            )
        return cls._secrets_manager_client
    
    @classmethod
    def get_lambda_client(cls, region: Optional[str] = None):
        """Get or create Lambda client with connection pooling."""
        if cls._lambda_client is None:
            cls._lambda_client = boto3.client('lambda', config=BOTO3_CONFIG, region_name=cls._get_region(region))
        return cls._lambda_client
    
    @classmethod
    def get_cloudwatch_client(cls, region: Optional[str] = None):
        """Get or create CloudWatch client with connection pooling."""
        if cls._cloudwatch_client is None:
            cls._cloudwatch_client = boto3.client(
                'cloudwatch', 
                config=BOTO3_CONFIG, 
                region_name=cls._get_region(region)
            )
        return cls._cloudwatch_client
    
    @classmethod
    def get_q_connect_client(cls, region: Optional[str] = None):
        """Get or create Amazon Q in Connect client with connection pooling."""
        if cls._q_connect_client is None:
            cls._q_connect_client = boto3.client(
                'qconnect', 
                config=BOTO3_CONFIG, 
                region_name=cls._get_region(region)
            )
        return cls._q_connect_client
    
    @classmethod
    def get_dynamodb_resource(cls, region: Optional[str] = None):
        """Get or create DynamoDB resource with connection pooling."""
        if cls._dynamodb_resource is None:
            cls._dynamodb_resource = boto3.resource(
                'dynamodb',
                config=BOTO3_CONFIG,
                region_name=cls._get_region(region)
            )
        return cls._dynamodb_resource
    
    @classmethod
    def prewarm_clients(cls, client_types: list[str], region: Optional[str] = None) -> None:
        """
        Pre-warm specified clients during Lambda initialization.
        
        This reduces latency for the first API call by initializing clients
        during the Lambda INIT phase rather than during the first invocation.
        
        Args:
            client_types: List of client types to pre-warm
                         (e.g., ['s3', 'lambda', 'qconnect'])
            region: AWS region (optional)
        
        Example:
            # In Lambda handler initialization
            AWSClients.prewarm_clients(['s3', 'qconnect', 'lambda'])
        """
        client_map = {
            's3': cls.get_s3_client,
            'secrets_manager': cls.get_secrets_manager_client,
            'lambda': cls.get_lambda_client,
            'cloudwatch': cls.get_cloudwatch_client,
            'qconnect': cls.get_q_connect_client,
            'dynamodb': cls.get_dynamodb_resource
        }
        
        for client_type in client_types:
            if client_type in client_map:
                client_map[client_type](region)
