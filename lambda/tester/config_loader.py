"""
Test query configuration loader.

This module handles loading test query configurations from multiple sources:
- Default configuration file (test_queries_config.json)
- Environment variable (TEST_QUERIES_CONFIG)
- S3 bucket (per-agent or global configurations)
"""

import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.aws_clients import AWSClients
from shared.retry_logic import exponential_backoff


@dataclass
class TestQueryConfig:
    """Test query configuration."""
    version: str
    description: str
    test_queries: List[Dict[str, Any]]
    intent_test_queries: Dict[str, Dict[str, Any]]
    behavior_categories: Dict[str, Dict[str, Any]]


class ConfigLoader:
    """Loads test query configurations from various sources."""
    
    def __init__(
        self,
        aws_clients: Optional[AWSClients] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize configuration loader.
        
        Args:
            aws_clients: AWS clients instance
            logger: Logger instance
        """
        self.aws_clients = aws_clients or AWSClients()
        self.logger = logger or logging.getLogger(__name__)
        self.backup_bucket = os.environ.get('BACKUP_BUCKET', '')
    
    def load_config(
        self,
        agent_id: Optional[str] = None
    ) -> TestQueryConfig:
        """
        Load test query configuration with fallback hierarchy:
        1. Per-agent configuration from S3 (if agent_id provided)
        2. Global configuration from S3
        3. Environment variable (TEST_QUERIES_CONFIG)
        4. Default configuration file
        
        Args:
            agent_id: Optional agent ID for per-agent configuration
            
        Returns:
            TestQueryConfig object
        """
        # Try per-agent configuration from S3
        if agent_id and self.backup_bucket:
            config_data = self._load_from_s3_per_agent(agent_id)
            if config_data:
                self.logger.info(
                    "Loaded per-agent test configuration from S3",
                    extra={"agentId": agent_id}
                )
                return self._parse_config(config_data)
        
        # Try global configuration from S3
        if self.backup_bucket:
            config_data = self._load_from_s3_global()
            if config_data:
                self.logger.info("Loaded global test configuration from S3")
                return self._parse_config(config_data)
        
        # Try environment variable
        config_data = self._load_from_env()
        if config_data:
            self.logger.info("Loaded test configuration from environment variable")
            return self._parse_config(config_data)
        
        # Fall back to default configuration file
        self.logger.info("Loading default test configuration from file")
        config_data = self._load_default_config()
        return self._parse_config(config_data)
    
    def _load_from_s3_per_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Load per-agent test configuration from S3.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Configuration dictionary or None if not found
        """
        try:
            s3_key = f"test-configs/{agent_id}/test_queries.json"
            return self._load_from_s3(s3_key)
        except Exception as e:
            self.logger.debug(
                "Per-agent test configuration not found in S3",
                extra={"agentId": agent_id, "error": str(e)}
            )
            return None
    
    def _load_from_s3_global(self) -> Optional[Dict[str, Any]]:
        """
        Load global test configuration from S3.
        
        Returns:
            Configuration dictionary or None if not found
        """
        try:
            s3_key = "test-configs/global/test_queries.json"
            return self._load_from_s3(s3_key)
        except Exception as e:
            self.logger.debug(
                "Global test configuration not found in S3",
                extra={"error": str(e)}
            )
            return None
    
    @exponential_backoff(max_attempts=3)
    def _load_from_s3(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """
        Load configuration from S3.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            Configuration dictionary or None if not found
        """
        if not self.backup_bucket:
            return None
        
        try:
            s3_client = self.aws_clients.get_s3_client()
            response = s3_client.get_object(
                Bucket=self.backup_bucket,
                Key=s3_key
            )
            
            config_json = response['Body'].read().decode('utf-8')
            return json.loads(config_json)
            
        except s3_client.exceptions.NoSuchKey:
            return None
        except Exception as e:
            self.logger.warning(
                "Failed to load test configuration from S3",
                extra={"bucket": self.backup_bucket, "key": s3_key, "error": str(e)}
            )
            return None
    
    def _load_from_env(self) -> Optional[Dict[str, Any]]:
        """
        Load configuration from environment variable.
        
        Returns:
            Configuration dictionary or None if not found
        """
        config_json = os.environ.get('TEST_QUERIES_CONFIG')
        if not config_json:
            return None
        
        try:
            return json.loads(config_json)
        except json.JSONDecodeError as e:
            self.logger.warning(
                "Failed to parse TEST_QUERIES_CONFIG from environment",
                extra={"error": str(e)}
            )
            return None
    
    def _load_default_config(self) -> Dict[str, Any]:
        """
        Load default configuration from file.
        
        Returns:
            Configuration dictionary
        """
        config_file = os.path.join(
            os.path.dirname(__file__),
            'test_queries_config.json'
        )
        
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(
                "Failed to load default test configuration",
                extra={"file": config_file, "error": str(e)}
            )
            # Return minimal fallback configuration
            return self._get_minimal_fallback_config()
    
    def _get_minimal_fallback_config(self) -> Dict[str, Any]:
        """
        Get minimal fallback configuration if all else fails.
        
        Returns:
            Minimal configuration dictionary
        """
        return {
            "version": "1.0",
            "description": "Minimal fallback configuration",
            "testQueries": [
                {
                    "query": "I need to make a payment",
                    "expectedBehavior": "SHOULD_EXPLAIN_UNAVAILABLE",
                    "keywords": ["unavailable", "currently", "apologize"],
                    "critical": True
                },
                {
                    "query": "What's my account balance?",
                    "expectedBehavior": "SHOULD_HANDLE_NORMALLY",
                    "keywords": ["balance", "account"],
                    "critical": False
                }
            ],
            "intentTestQueries": {},
            "behaviorCategories": {
                "SHOULD_EXPLAIN_UNAVAILABLE": {
                    "description": "Explain unavailability",
                    "requiredKeywords": ["unavailable"],
                    "minimumMatches": 1
                },
                "SHOULD_HANDLE_NORMALLY": {
                    "description": "Handle normally",
                    "forbiddenKeywords": ["unavailable"],
                    "requiresResponse": True
                },
                "SHOULD_OFFER_ALTERNATIVE": {
                    "description": "Offer alternatives",
                    "requiredKeywords": ["available", "help"],
                    "minimumMatches": 1
                }
            }
        }
    
    def _parse_config(self, config_data: Dict[str, Any]) -> TestQueryConfig:
        """
        Parse and validate configuration data.
        
        Args:
            config_data: Raw configuration dictionary
            
        Returns:
            TestQueryConfig object
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Validate required fields
        if 'testQueries' not in config_data:
            raise ValueError("Configuration missing 'testQueries' field")
        
        # Validate test queries structure
        test_queries = config_data['testQueries']
        if not isinstance(test_queries, list):
            raise ValueError("'testQueries' must be a list")
        
        for i, query in enumerate(test_queries):
            self._validate_test_query(query, i)
        
        # Validate behavior categories if present
        behavior_categories = config_data.get('behaviorCategories', {})
        if behavior_categories:
            self._validate_behavior_categories(behavior_categories)
        
        return TestQueryConfig(
            version=config_data.get('version', '1.0'),
            description=config_data.get('description', ''),
            test_queries=test_queries,
            intent_test_queries=config_data.get('intentTestQueries', {}),
            behavior_categories=behavior_categories
        )
    
    def _validate_test_query(self, query: Dict[str, Any], index: int):
        """
        Validate a single test query structure.
        
        Args:
            query: Test query dictionary
            index: Query index for error messages
            
        Raises:
            ValueError: If query structure is invalid
        """
        required_fields = ['query', 'expectedBehavior', 'keywords']
        for field in required_fields:
            if field not in query:
                raise ValueError(
                    f"Test query at index {index} missing required field '{field}'"
                )
        
        # Validate expectedBehavior
        valid_behaviors = [
            'SHOULD_EXPLAIN_UNAVAILABLE',
            'SHOULD_HANDLE_NORMALLY',
            'SHOULD_OFFER_ALTERNATIVE'
        ]
        if query['expectedBehavior'] not in valid_behaviors:
            raise ValueError(
                f"Test query at index {index} has invalid expectedBehavior. "
                f"Must be one of: {', '.join(valid_behaviors)}"
            )
        
        # Validate keywords is a list
        if not isinstance(query['keywords'], list):
            raise ValueError(
                f"Test query at index {index} 'keywords' must be a list"
            )
        
        # Validate critical is boolean if present
        if 'critical' in query and not isinstance(query['critical'], bool):
            raise ValueError(
                f"Test query at index {index} 'critical' must be a boolean"
            )
    
    def _validate_behavior_categories(self, categories: Dict[str, Dict[str, Any]]):
        """
        Validate behavior categories structure.
        
        Args:
            categories: Behavior categories dictionary
            
        Raises:
            ValueError: If categories structure is invalid
        """
        valid_category_names = [
            'SHOULD_EXPLAIN_UNAVAILABLE',
            'SHOULD_HANDLE_NORMALLY',
            'SHOULD_OFFER_ALTERNATIVE'
        ]
        
        for category_name, category_config in categories.items():
            if category_name not in valid_category_names:
                raise ValueError(
                    f"Invalid behavior category '{category_name}'. "
                    f"Must be one of: {', '.join(valid_category_names)}"
                )
            
            if not isinstance(category_config, dict):
                raise ValueError(
                    f"Behavior category '{category_name}' must be a dictionary"
                )
    
    def save_config_to_s3(
        self,
        config: TestQueryConfig,
        agent_id: Optional[str] = None
    ) -> bool:
        """
        Save test configuration to S3.
        
        Args:
            config: Test query configuration
            agent_id: Optional agent ID for per-agent configuration
            
        Returns:
            True if successful, False otherwise
        """
        if not self.backup_bucket:
            self.logger.warning("Cannot save config to S3: BACKUP_BUCKET not set")
            return False
        
        try:
            # Determine S3 key
            if agent_id:
                s3_key = f"test-configs/{agent_id}/test_queries.json"
            else:
                s3_key = "test-configs/global/test_queries.json"
            
            # Build configuration dictionary
            config_data = {
                "version": config.version,
                "description": config.description,
                "testQueries": config.test_queries,
                "intentTestQueries": config.intent_test_queries,
                "behaviorCategories": config.behavior_categories
            }
            
            # Save to S3
            s3_client = self.aws_clients.get_s3_client()
            s3_client.put_object(
                Bucket=self.backup_bucket,
                Key=s3_key,
                Body=json.dumps(config_data, indent=2),
                ContentType='application/json'
            )
            
            self.logger.info(
                "Saved test configuration to S3",
                extra={
                    "bucket": self.backup_bucket,
                    "key": s3_key,
                    "agentId": agent_id
                }
            )
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to save test configuration to S3",
                extra={"error": str(e), "agentId": agent_id}
            )
            return False
