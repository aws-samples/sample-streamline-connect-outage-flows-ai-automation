# Tester Lambda - Test Query Configuration

## Overview

The Tester Lambda validates updated AI agents by executing test queries and evaluating responses. The test query configuration system supports multiple sources with a fallback hierarchy, allowing flexible configuration management.

## Configuration Hierarchy

The system loads test configurations in the following order (first found wins):

1. **Per-Agent Configuration (S3)**: `s3://{BACKUP_BUCKET}/test-configs/{agent-id}/test_queries.json`
2. **Global Configuration (S3)**: `s3://{BACKUP_BUCKET}/test-configs/global/test_queries.json`
3. **Environment Variable**: `TEST_QUERIES_CONFIG` (JSON string)
4. **Default Configuration File**: `lambda/tester/test_queries_config.json`

## Configuration Structure

### Complete Configuration Example

```json
{
  "version": "1.0",
  "description": "Test query configuration for AI agent validation",
  "testQueries": [
    {
      "query": "I need to make a payment",
      "expectedBehavior": "SHOULD_EXPLAIN_UNAVAILABLE",
      "keywords": ["unavailable", "currently", "apologize", "temporarily"],
      "critical": true,
      "category": "payment",
      "description": "Test that payment requests are properly rejected during outage"
    }
  ],
  "intentTestQueries": {
    "check_balance": {
      "testQuery": "What's my account balance?",
      "expectedBehaviorWhenEnabled": "SHOULD_HANDLE_NORMALLY",
      "expectedBehaviorWhenDisabled": "SHOULD_EXPLAIN_UNAVAILABLE",
      "keywords": ["balance", "account"]
    }
  },
  "behaviorCategories": {
    "SHOULD_EXPLAIN_UNAVAILABLE": {
      "description": "Agent should explain that the service is temporarily unavailable",
      "requiredKeywords": ["unavailable", "temporarily", "currently"],
      "minimumMatches": 1
    },
    "SHOULD_HANDLE_NORMALLY": {
      "description": "Agent should handle the request normally",
      "forbiddenKeywords": ["unavailable", "currently unavailable"],
      "requiresResponse": true
    },
    "SHOULD_OFFER_ALTERNATIVE": {
      "description": "Agent should suggest alternative services",
      "requiredKeywords": ["available", "can", "help", "alternative"],
      "minimumMatches": 1
    }
  }
}
```

### Field Descriptions

#### testQueries (Array)

Each test query object contains:

- `query` (string, required): The test query text to send to the agent
- `expectedBehavior` (string, required): Expected behavior category
  - `SHOULD_EXPLAIN_UNAVAILABLE`: Agent should explain service is unavailable
  - `SHOULD_HANDLE_NORMALLY`: Agent should handle request normally
  - `SHOULD_OFFER_ALTERNATIVE`: Agent should suggest alternatives
- `keywords` (array, required): Keywords to look for in the response
- `critical` (boolean, optional): Whether failure triggers automatic rollback (default: false)
- `category` (string, optional): Category for grouping (e.g., "payment", "inquiry")
- `description` (string, optional): Human-readable description of the test
- `intentName` (string, optional): Intent being tested (for intent-specific tests)

#### intentTestQueries (Object)

Maps intent names to test configurations:

- Key: Intent name (e.g., "check_balance")
- Value: Object containing:
  - `testQuery`: Query text for testing this intent
  - `expectedBehaviorWhenEnabled`: Expected behavior when intent is enabled
  - `expectedBehaviorWhenDisabled`: Expected behavior when intent is disabled
  - `keywords`: Keywords to validate in responses

#### behaviorCategories (Object)

Defines evaluation criteria for each behavior category:

- `description`: Human-readable description
- `requiredKeywords`: Keywords that must appear in response
- `forbiddenKeywords`: Keywords that must NOT appear in response
- `minimumMatches`: Minimum number of required keywords to match
- `requiresResponse`: Whether a non-empty response is required

## Usage Examples

### 1. Using Default Configuration

No configuration needed - the system automatically uses the default configuration file.

```python
# Lambda automatically loads default configuration
# No environment variables or S3 setup required
```

### 2. Using Environment Variable

Set the `TEST_QUERIES_CONFIG` environment variable with JSON configuration:

```bash
export TEST_QUERIES_CONFIG='{
  "version": "1.0",
  "testQueries": [
    {
      "query": "Can I make a payment?",
      "expectedBehavior": "SHOULD_EXPLAIN_UNAVAILABLE",
      "keywords": ["unavailable", "apologize"],
      "critical": true
    }
  ]
}'
```

### 3. Using Global S3 Configuration

Upload configuration to S3:

```bash
aws s3 cp test_queries.json s3://{BACKUP_BUCKET}/test-configs/global/test_queries.json
```

### 4. Using Per-Agent S3 Configuration

Upload agent-specific configuration:

```bash
aws s3 cp agent_test_queries.json s3://{BACKUP_BUCKET}/test-configs/{agent-id}/test_queries.json
```

## Configuration Management

### Saving Configuration to S3

```python
from tester.config_loader import ConfigLoader, TestQueryConfig

config_loader = ConfigLoader()

# Create configuration
config = TestQueryConfig(
    version="1.0",
    description="Custom test configuration",
    test_queries=[...],
    intent_test_queries={...},
    behavior_categories={...}
)

# Save as global configuration
config_loader.save_config_to_s3(config, agent_id=None)

# Save as per-agent configuration
config_loader.save_config_to_s3(config, agent_id="agent-uuid")
```

### Loading Configuration

```python
from tester.config_loader import ConfigLoader

config_loader = ConfigLoader()

# Load global configuration
config = config_loader.load_config()

# Load per-agent configuration (with fallback to global)
config = config_loader.load_config(agent_id="agent-uuid")
```

## Test Execution

### Invoking Tester Lambda

```python
import boto3

lambda_client = boto3.client('lambda')

# Test with default configuration
response = lambda_client.invoke(
    FunctionName='supervisor-ai-agent-tester',
    InvocationType='RequestResponse',
    Payload=json.dumps({
        'agentId': 'agent-uuid',
        'testScenario': 'outage-update',
        'outageInfo': {
            'affectedServices': ['payment', 'transfer'],
            'availableServices': ['balance', 'history']
        }
    })
)

# Test with intent-specific configuration
response = lambda_client.invoke(
    FunctionName='supervisor-ai-agent-tester',
    InvocationType='RequestResponse',
    Payload=json.dumps({
        'agentId': 'agent-uuid',
        'testScenario': 'intent-test',
        'intentTestConfig': {
            'disabledIntents': [
                {'name': 'change_pin', 'testQuery': 'I want to change my PIN'}
            ],
            'enabledIntents': [
                {'name': 'check_balance', 'testQuery': 'What is my balance?'}
            ]
        }
    })
)
```

## Validation

The configuration loader validates:

1. Required fields are present (`testQueries`, `query`, `expectedBehavior`, `keywords`)
2. `expectedBehavior` values are valid (one of the three supported categories)
3. `keywords` is an array
4. `critical` is a boolean (if present)
5. Behavior categories use valid names

Invalid configurations raise `ValueError` with descriptive error messages.

## Best Practices

1. **Start with Default**: Use the default configuration as a template
2. **Test Incrementally**: Add test queries gradually and validate each addition
3. **Use Categories**: Group related tests using the `category` field
4. **Mark Critical Tests**: Set `critical: true` for tests that should trigger rollback
5. **Per-Agent Configs**: Use per-agent configurations for specialized agents
6. **Version Control**: Include `version` field and increment when making changes
7. **Document Tests**: Use `description` field to explain test purpose
8. **Keyword Selection**: Choose keywords that reliably indicate expected behavior
9. **Test Coverage**: Include tests for unavailable, available, and alternative scenarios
10. **S3 Versioning**: Enable S3 versioning to track configuration changes

## Troubleshooting

### Configuration Not Loading

Check the following:

1. Verify `BACKUP_BUCKET` environment variable is set
2. Check S3 bucket permissions for Lambda execution role
3. Validate JSON syntax in configuration file
4. Review CloudWatch logs for parsing errors

### Tests Failing Unexpectedly

1. Review `evaluation_details` in test results
2. Check `matchedKeywords` to see which keywords were found
3. Verify agent responses contain expected keywords
4. Adjust keywords or add alternatives if needed

### Configuration Validation Errors

1. Check error message for specific field causing issue
2. Verify all required fields are present
3. Ensure `expectedBehavior` uses valid values
4. Validate JSON structure matches schema

## Related Files

- `lambda/tester/handler.py`: Main Tester Lambda handler
- `lambda/tester/config_loader.py`: Configuration loading logic
- `lambda/tester/test_queries_config.json`: Default configuration file
- `lambda/tests/test_tester_config.py`: Configuration tests
