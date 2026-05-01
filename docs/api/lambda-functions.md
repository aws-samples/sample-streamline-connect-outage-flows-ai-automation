# Lambda Functions API Reference

This document provides API reference documentation for all Lambda functions in the Supervisor AI Agent system.

[← Back to Documentation Index](../README.md)

---

## Table of Contents

- [Authentication Lambda](#authentication-lambda)
- [Agent Manager Lambda](#agent-manager-lambda)
- [Backup Lambda](#backup-lambda)
- [Restore Lambda](#restore-lambda)
- [Tester Lambda](#tester-lambda)

---

## Authentication Lambda

**Function Name**: `supervisor-ai-agent-auth`  
**Runtime**: Python 3.12  
**Memory**: 256 MB  
**Timeout**: 30 seconds

### Purpose

Validates caller phone numbers against an allowlist and verifies PINs against stored values in AWS Secrets Manager.

### Operations

#### Phone Number Validation

**Input Event** (from Amazon Connect Contact Flow):
```json
{
  "Details": {
    "ContactData": {
      "CustomerEndpoint": {
        "Address": "+1-555-0100"
      }
    }
  }
}
```

**Output**:
```json
{
  "authenticated": true,
  "phoneNumber": "+1-555-0100",
  "timestamp": "2025-03-01T10:30:00Z"
}
```

#### PIN Validation

**Input Event** (from Amazon Lex):
```json
{
  "sessionState": {
    "intent": {
      "slots": {
        "PIN": {
          "value": {
            "interpretedValue": "123456"
          }
        }
      }
    }
  }
}
```

**Output** (Lex Response):
```json
{
  "sessionState": {
    "dialogAction": {
      "type": "Close"
    },
    "intent": {
      "state": "Fulfilled"
    }
  }
}
```

#### Rate Limiting

The Auth Lambda enforces server-side PIN brute-force protection using DynamoDB:

- **Max attempts**: 3 failed PIN attempts per phone number
- **Lockout duration**: 30 minutes
- **TTL**: Records auto-expire after 1 hour

**Lockout Response**:
```json
{
  "authenticated": "false",
  "message": "Too many failed attempts. Try again in 25 minutes."
}
```

#### Auth Token Generation

On successful PIN validation, the Auth Lambda generates a server-side auth token:

**Successful Response** (with token):
```json
{
  "authenticated": "true",
  "message": "Authentication successful.",
  "authToken": "uuid-v4-token"
}
```

The token is stored in DynamoDB with a 15-minute TTL. All mutating operations on the Agent Manager Lambda require a valid `authToken`.

#### Phone Allowlist Source

The phone allowlist is loaded from Secrets Manager (same secret as PIN) at Lambda initialization, not from environment variables. Secret format:
```json
{"pin": "YOUR_PIN", "allowlist": ["+1234567890"]}
```

### Environment Variables

- `PHONE_ALLOWLIST`: Comma-separated list of E.164 phone numbers
- `SECRET_ARN`: ARN of Secrets Manager secret containing supervisor PIN
- `LOG_LEVEL`: Logging level (default: INFO)

### Error Handling

- Returns `authenticated: false` for unauthorized phone numbers
- Returns Lex `Failed` state for incorrect PINs
- Tracks retry attempts (max 3)
- Logs all authentication attempts to CloudWatch

### Auth Lambda Modules

- **handler.py**: Main handler with phone validation and PIN validation operations
- **phone_validator.py**: Phone number parsing and allowlist matching
- **pin_validator.py**: PIN comparison against Secrets Manager
- **rate_limiter.py**: DynamoDB-based brute-force protection (check_lockout, record_failed_attempt, clear_attempts)

---

## Agent Manager Lambda

**Function Name**: `supervisor-ai-agent-manager`  
**Runtime**: Python 3.12  
**Memory**: 512 MB  
**Timeout**: 120 seconds

### Purpose

Orchestrates AI agent management operations including listing agents, retrieving configurations, managing intents, generating AI Prompts, and coordinating backup/test workflows.

#### Authentication Verification

All mutating operations (`update_agent`, `update_agents`, `disable_intent`, `enable_intent`, `restore`) require a valid `authToken` in the event payload. The token is verified against DynamoDB before processing.

**Rejected Response** (missing/invalid token):
```json
{"success": false, "error": "Authentication required. Provide a valid authToken."}
```

#### Prompt Content Validation

Before deploying prompts to production agents, content is validated by `prompt_validator.py`:
- **Blocklist patterns**: Rejects injection attempts ("ignore previous instructions", "<script>", etc.)
- **Max length**: 10,000 characters
- **URL check**: Rejects prompts containing http:// or https:// URLs

### Operations

#### 1. List Agents

**Input**:
```json
{
  "operation": "list_agents",
  "filters": {
    "origin": "CUSTOMER"
  }
}
```

**Output**:
```json
{
  "agents": [
    {
      "agentId": "agent-uuid",
      "agentName": "Production Voice Agent",
      "type": "VOICE",
      "status": "ACTIVE",
      "description": "Customer-facing voice agent"
    }
  ]
}
```

#### 2. Get Agent Configuration

**Input**:
```json
{
  "operation": "get_agent",
  "agentId": "agent-uuid"
}
```

**Output**:
```json
{
  "agentId": "agent-uuid",
  "agentName": "Production Voice Agent",
  "configuration": {
    "orchestrationAIPromptId": "prompt-uuid:version",
    "locale": "en_US"
  },
  "currentPromptText": "System prompt text..."
}
```

#### 3. List Agent Intents

**Input**:
```json
{
  "operation": "list_intents",
  "agentId": "agent-uuid"
}
```

**Output**:
```json
{
  "agentId": "agent-uuid",
  "intents": [
    {
      "name": "check_balance",
      "description": "Check account balance",
      "enabled": true
    },
    {
      "name": "change_pin",
      "description": "Change card PIN",
      "enabled": false
    }
  ]
}
```

#### 4. Disable Intent

**Input**:
```json
{
  "operation": "disable_intent",
  "agentId": "agent-uuid",
  "intentName": "change_pin",
  "callerPhoneNumber": "+1-555-0100"
}
```

**Output**:
```json
{
  "success": true,
  "agentId": "agent-uuid",
  "intentName": "change_pin",
  "backupLocation": "s3://bucket/backups/...",
  "testResults": {
    "totalTests": 4,
    "passed": 4,
    "failed": 0
  }
}
```

#### 5. Enable Intent

**Input**:
```json
{
  "operation": "enable_intent",
  "agentId": "agent-uuid",
  "intentName": "change_pin",
  "callerPhoneNumber": "+1-555-0100"
}
```

**Output**:
```json
{
  "success": true,
  "agentId": "agent-uuid",
  "intentName": "change_pin",
  "backupLocation": "s3://bucket/backups/...",
  "testResults": {
    "totalTests": 2,
    "passed": 2,
    "failed": 0
  }
}
```

#### 6. Restore All Intents

**Input**:
```json
{
  "operation": "restore_all_intents",
  "agentId": "agent-uuid",
  "callerPhoneNumber": "+1-555-0100"
}
```

**Output**:
```json
{
  "success": true,
  "agentId": "agent-uuid",
  "restoredIntents": ["check_balance", "change_pin", "transfer_funds"],
  "testResults": {
    "totalTests": 6,
    "passed": 6,
    "failed": 0
  }
}
```

#### 7. Update Agent (Full Outage)

**Input**:
```json
{
  "operation": "update_agent",
  "agentId": "agent-uuid",
  "outageInfo": {
    "affectedServices": ["Payment Processing", "Bill Pay"],
    "availableServices": ["Account Balance", "Transaction History"],
    "estimatedRecoveryTime": "2 hours"
  },
  "callerPhoneNumber": "+1-555-0100"
}
```

**Output**:
```json
{
  "success": true,
  "agentId": "agent-uuid",
  "newPromptVersion": "prompt-uuid:2",
  "backupLocation": "s3://bucket/backups/...",
  "testResults": {
    "totalTests": 8,
    "passed": 8,
    "failed": 0,
    "criticalFailures": 0
  }
}
```

### Environment Variables

- `ASSISTANT_ID`: Amazon Q in Connect assistant ID
- `BACKUP_BUCKET`: S3 bucket name for backups
- `BACKUP_LAMBDA_ARN`: ARN of Backup Lambda function
- `TESTER_LAMBDA_ARN`: ARN of Tester Lambda function
- `CONNECT_INSTANCE_ARN`: Amazon Connect instance ARN
- `LOG_LEVEL`: Logging level (default: INFO)

### Error Handling

- Retries API calls with exponential backoff (up to 3 attempts)
- Aborts updates if backup fails
- Automatically rolls back if critical tests fail
- Returns detailed error messages for troubleshooting

### Agent Manager Lambda Modules

- **handler.py**: Main handler with all agent management operations
- **prompt_validator.py**: Prompt content validation (blocklist, length, URL checks)

---

## Backup Lambda

**Function Name**: `supervisor-ai-agent-backup`  
**Runtime**: Python 3.12  
**Memory**: 256 MB  
**Timeout**: 60 seconds

### Purpose

Backs up current AI agent configurations and prompts to S3 before modifications.

### Input

```json
{
  "agentId": "agent-uuid",
  "agentName": "Production Voice Agent",
  "assistantId": "assistant-uuid",
  "configuration": {
    "orchestrationAIAgentConfiguration": {
      "orchestrationAIPromptId": "prompt-uuid:version"
    }
  },
  "metadata": {
    "backupReason": "outage-update",
    "callerPhoneNumber": "+1-555-0100"
  }
}
```

### Output

```json
{
  "success": true,
  "backupLocation": "s3://bucket/backups/agent-uuid/2025-03-01T10-30-00-Production-Voice-Agent.json",
  "timestamp": "2025-03-01T10:30:00Z"
}
```

### Backup Object Structure

```json
{
  "agentId": "agent-uuid",
  "agentName": "Production Voice Agent",
  "assistantId": "assistant-uuid",
  "timestamp": "2025-03-01T10:30:00Z",
  "aiAgentConfiguration": {
    "orchestrationAIAgentConfiguration": {
      "orchestrationAIPromptId": "prompt-uuid:version",
      "locale": "en_US"
    }
  },
  "currentPromptId": "prompt-uuid:version",
  "currentPromptText": "Current AI Prompt text...",
  "visibilityStatus": "PUBLISHED",
  "intentConfiguration": {
    "intents": [
      {
        "name": "check_balance",
        "description": "Check account balance",
        "enabled": true
      }
    ]
  },
  "metadata": {
    "backupReason": "outage-update",
    "callerPhoneNumber": "+1-555-0100"
  }
}
```

### Environment Variables

- `BACKUP_BUCKET`: S3 bucket name for backups
- `LOG_LEVEL`: Logging level (default: INFO)

### S3 Key Pattern

`backups/{agent-id}/{timestamp}-{agent-name}.json`

Example: `backups/abc-123/2025-03-01T10-30-00-Production-Voice-Agent.json`

---

## Restore Lambda

**Function Name**: `supervisor-ai-agent-restore`  
**Runtime**: Python 3.12  
**Memory**: 256 MB  
**Timeout**: 90 seconds

### Purpose

Restores AI agent prompts from S3 backups when services recover.

### Input

```json
{
  "agentId": "agent-uuid",
  "callerPhoneNumber": "+1-555-0100"
}
```

### Output

```json
{
  "success": true,
  "agentId": "agent-uuid",
  "restoredFrom": "s3://bucket/backups/agent-uuid/2025-03-01T10-30-00-Production-Voice-Agent.json",
  "outageDuration": "47 minutes",
  "testResults": {
    "totalTests": 8,
    "passed": 8,
    "failed": 0
  }
}
```

### Environment Variables

- `BACKUP_BUCKET`: S3 bucket name for backups
- `AGENT_MANAGER_LAMBDA_ARN`: ARN of Agent Manager Lambda
- `TESTER_LAMBDA_ARN`: ARN of Tester Lambda
- `LOG_LEVEL`: Logging level (default: INFO)

### Restore Algorithm

1. List all backups for agent from S3 (prefix: `backups/{agentId}/`)
2. Sort backups by timestamp descending
3. Retrieve most recent backup object
4. Parse JSON and extract original AI Prompt text
5. Create new AI Prompt version with original text
6. Update AI Agent configuration to reference restored prompt
7. Set visibilityStatus to PUBLISHED
8. Test restored agent
9. Calculate outage duration

---

## Tester Lambda

**Function Name**: `supervisor-ai-agent-tester`  
**Runtime**: Python 3.12  
**Memory**: 512 MB  
**Timeout**: 90 seconds

### Purpose

Validates updated AI agents by executing test queries and evaluating responses.

### Input

```json
{
  "agentId": "agent-uuid",
  "testScenario": "outage-update",
  "outageInfo": {
    "affectedServices": ["Payment Processing"],
    "availableServices": ["Account Balance"]
  }
}
```

### Output

```json
{
  "success": true,
  "totalTests": 8,
  "passed": 7,
  "failed": 1,
  "criticalFailures": 0,
  "results": [
    {
      "query": "I need to make a payment",
      "expectedBehavior": "SHOULD_EXPLAIN_UNAVAILABLE",
      "actualResponse": "I apologize, but payment processing is currently unavailable...",
      "passed": true,
      "critical": true
    }
  ],
  "sampleResponses": [
    {
      "query": "What's my balance?",
      "response": "I can help you check your account balance..."
    }
  ]
}
```

### Test Query Configuration

```json
{
  "testQueries": [
    {
      "query": "I need to make a payment",
      "expectedBehavior": "SHOULD_EXPLAIN_UNAVAILABLE",
      "keywords": ["unavailable", "currently", "apologize"],
      "critical": true
    },
    {
      "query": "What's my order status?",
      "expectedBehavior": "SHOULD_HANDLE_NORMALLY",
      "keywords": ["order", "status", "check"],
      "critical": false
    }
  ]
}
```

### Expected Behaviors

- `SHOULD_EXPLAIN_UNAVAILABLE`: Check for keywords like "unavailable", "currently", "apologize"
- `SHOULD_HANDLE_NORMALLY`: Check for normal service keywords, no outage mentions
- `SHOULD_OFFER_ALTERNATIVE`: Check for alternative service suggestions

### Environment Variables

- `ASSISTANT_ID`: Amazon Q in Connect assistant ID
- `TEST_QUERIES_CONFIG`: JSON string with test queries
- `LOG_LEVEL`: Logging level (default: INFO)

### Critical Failures

Any critical test that fails triggers automatic rollback to the previous prompt version.

#### Enhanced Test Evaluation

- **Keyword threshold**: Critical tests require ≥2 keyword matches (not 1)
- **Negative keywords**: Tests fail if response contains forbidden terms (e.g., "ignore", "disregard", "system prompt")
- **Minimum response length**: Responses under 20 characters fail

---

## Common Patterns

### Error Response Format

All Lambda functions return errors in a consistent format:

```json
{
  "success": false,
  "error": {
    "code": "BACKUP_FAILED",
    "message": "Failed to store backup to S3",
    "details": "Access denied to bucket supervisor-ai-agent-backups"
  }
}
```

### Logging Format

All Lambda functions use structured JSON logging:

```json
{
  "timestamp": "2025-03-01T10:30:00.123Z",
  "level": "INFO",
  "requestId": "abc-123-def-456",
  "function": "supervisor-ai-agent-manager",
  "event": "PROMPT_UPDATE",
  "agentId": "agent-uuid",
  "callerPhoneNumber": "+1-555-0100",
  "duration": 1234,
  "status": "success",
  "message": "Agent prompt updated successfully"
}
```

### Retry Logic

All Lambda functions implement exponential backoff for AWS API calls:

- Initial retry delay: 1 second
- Maximum retries: 3
- Backoff multiplier: 2x
- Maximum delay: 8 seconds

---

## Shared Modules

- **aws_clients.py**: Centralized AWS SDK client management
- **logging_config.py**: Structured JSON logging configuration
- **retry_logic.py**: Exponential backoff with jitter for AWS API calls
- **error_handling.py**: User-friendly error translation
- **request_signing.py**: HMAC-SHA256 signing for inter-Lambda request authentication
- **audit_logging.py**: S3-based audit log writer
- **metrics_publisher.py**: CloudWatch custom metrics publisher

---

## Related Documentation

- [System Architecture](../architecture/system-architecture.md)
- [CDK Deployment Guide](../deployment/cdk-deployment.md)
- [Operations Runbook](../operations/operations-runbook.md)

[← Back to Documentation Index](../README.md)
