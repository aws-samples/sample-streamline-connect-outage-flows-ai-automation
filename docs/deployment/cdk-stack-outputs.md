# CDK Stack Outputs Reference

## Overview

This document provides a comprehensive reference for all CDK stack outputs, their purposes, and how to use them in manual resource configuration.

## Retrieving Stack Outputs

### Using AWS CLI

```bash
# Get all outputs in table format
aws cloudformation describe-stacks \
  --stack-name SupervisorAIAgentStack \
  --profile your-aws-profile \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table

# Get all outputs in JSON format
aws cloudformation describe-stacks \
  --stack-name SupervisorAIAgentStack \
  --profile your-aws-profile \
  --region us-east-1 \
  --query 'Stacks[0].Outputs' \
  --output json

# Get specific output value
aws cloudformation describe-stacks \
  --stack-name SupervisorAIAgentStack \
  --profile your-aws-profile \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`AuthenticationLambdaArn`].OutputValue' \
  --output text
```

### Using Deployment Script

```bash
# View outputs using the deployment script
./cdk/scripts/deploy.sh --outputs-only
```

### Using CDK CLI

```bash
# View outputs after deployment
cd cdk
cdk deploy --profile your-aws-profile --region us-east-1 --outputs-file outputs.json
cat outputs.json
```

## Output Definitions

### Lambda Function ARNs

#### AuthenticationLambdaArn

**Description**: ARN of the Authentication Lambda function that validates phone numbers and PINs.

**Format**: `arn:aws:lambda:us-east-1:ACCOUNT_ID:function:supervisor-ai-agent-auth`

**Used In**:
- Amazon Connect Contact Flow (phone number validation)
- Supervisor AI Agent MCP tool (PIN validation via `authenticate_pin` tool)

**Configuration Steps**:
1. **Contact Flow - Phone Validation Block**:
   - Block type: Invoke AWS Lambda function
   - Function ARN: Use this output value
   - Timeout: 8 seconds
   - Input: Contact attributes (CustomerEndpoint.Address)

2. **Supervisor AI Agent - PIN Validation Tool**:
   - Tool: `authenticate_pin` (MCP tool)
   - Lambda function: Use this output value
   - Note: PIN validation is handled by the AI agent via MCP tool (no separate Lex bot needed)

**Example Usage**:
```json
// Contact Flow JSON snippet
{
  "Type": "InvokeLambdaFunction",
  "Parameters": {
    "LambdaFunctionARN": "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:supervisor-ai-agent-auth",
    "InvocationTimeLimitSeconds": "8"
  }
}
```

#### AgentManagerLambdaArn

**Description**: ARN of the Agent Manager Lambda function that orchestrates AI agent operations.

**Format**: `arn:aws:lambda:us-east-1:ACCOUNT_ID:function:supervisor-ai-agent-manager`

**Used In**:
- Supervisor AI Agent tool definitions (list_agents, get_agent_config, update_agent_prompt, list_agent_intents, disable_intent, enable_intent, restore_all_intents)

**Configuration Steps**:
1. **Supervisor AI Agent - Tool Configuration**:
   - Tool type: Action group
   - Lambda function: Use this output value
   - Tool definitions: See `docs/manual-setup/supervisor-ai-agent-setup.md`

**Tool Operations**:
- `list_agents`: List all production AI agents
- `get_agent_config`: Get agent configuration
- `list_agent_intents`: List agent intents with status
- `disable_intent`: Disable specific intent
- `enable_intent`: Enable specific intent
- `restore_all_intents`: Restore all intents to normal
- `update_agent_prompt`: Update agent prompt for full outage

**Example Tool Definition**:
```json
{
  "name": "list_agents",
  "description": "List all production AI agents in the Amazon Connect instance",
  "parameters": {
    "filters": {
      "type": "object",
      "description": "Optional filters for agent list"
    }
  },
  "lambdaArn": "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:supervisor-ai-agent-manager"
}
```

#### BackupLambdaArn

**Description**: ARN of the Backup Lambda function that backs up AI agent configurations.

**Format**: `arn:aws:lambda:us-east-1:ACCOUNT_ID:function:supervisor-ai-agent-backup`

**Used In**:
- Agent Manager Lambda (invoked automatically before updates)
- Not directly configured in manual resources

**Purpose**:
- Automatically invoked by Agent Manager before prompt updates
- Creates timestamped backups in S3
- Stores full agent configuration and intent state

**Note**: This Lambda is invoked programmatically by Agent Manager Lambda and does not require manual configuration.

#### RestoreLambdaArn

**Description**: ARN of the Restore Lambda function that restores AI agent configurations from backups.

**Format**: `arn:aws:lambda:us-east-1:ACCOUNT_ID:function:supervisor-ai-agent-restore`

**Used In**:
- Supervisor AI Agent tool definitions (restore_agent_prompt)

**Configuration Steps**:
1. **Supervisor AI Agent - Tool Configuration**:
   - Tool name: restore_agent_prompt
   - Tool type: Action group
   - Lambda function: Use this output value

**Example Tool Definition**:
```json
{
  "name": "restore_agent_prompt",
  "description": "Restore AI agent prompt from backup when services recover",
  "parameters": {
    "agentId": {
      "type": "string",
      "description": "ID of the AI agent to restore",
      "required": true
    },
    "callerPhoneNumber": {
      "type": "string",
      "description": "Phone number of the caller requesting restore",
      "required": true
    }
  },
  "lambdaArn": "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:supervisor-ai-agent-restore"
}
```

#### TesterLambdaArn

**Description**: ARN of the Tester Lambda function that validates updated AI agents.

**Format**: `arn:aws:lambda:us-east-1:ACCOUNT_ID:function:supervisor-ai-agent-tester`

**Used In**:
- Agent Manager Lambda (invoked automatically after updates)
- Restore Lambda (invoked automatically after restoration)
- Not directly configured in manual resources

**Purpose**:
- Automatically invoked after prompt updates
- Executes test queries against updated agents
- Validates correct behavior before confirmation

**Note**: This Lambda is invoked programmatically and does not require manual configuration.

### Storage Resources

#### BackupBucketName

**Description**: Name of the S3 bucket for backups, intent configurations, and audit logs.

**Format**: `supervisor-ai-agent-backups-ACCOUNT_ID-REGION`

**Used In**:
- Lambda environment variables (automatically configured by CDK)
- Manual verification and troubleshooting

**Bucket Structure**:
```
s3://supervisor-ai-agent-backups-ACCOUNT_ID-REGION/
├── backups/
│   ├── {agent-id-1}/
│   │   ├── 2025-03-01T10-30-00-Production-Voice-Agent.json
│   │   └── 2025-03-01T14-15-00-Production-Voice-Agent.json
│   └── {agent-id-2}/
│       └── 2025-03-01T11-00-00-Production-Chat-Agent.json
├── intent-configs/
│   ├── {agent-id-1}/
│   │   └── current.json
│   └── {agent-id-2}/
│       └── current.json
└── audit-logs/
    └── 2025/
        └── 03/
            └── 01/
                ├── prompt-update-10-30-00.json
                ├── intent-disable-11-00-00.json
                └── prompt-restore-14-15-00.json
```

**Accessing Backups**:
```bash
# List all backups for an agent
aws s3 ls s3://supervisor-ai-agent-backups-ACCOUNT_ID-REGION/backups/{agent-id}/ \
  --profile your-aws-profile \
  --region us-east-1

# Download a specific backup
aws s3 cp s3://supervisor-ai-agent-backups-ACCOUNT_ID-REGION/backups/{agent-id}/{timestamp}-{agent-name}.json . \
  --profile your-aws-profile \
  --region us-east-1

# List intent configurations
aws s3 ls s3://supervisor-ai-agent-backups-ACCOUNT_ID-REGION/intent-configs/ \
  --profile your-aws-profile \
  --region us-east-1 \
  --recursive

# View audit logs
aws s3 ls s3://supervisor-ai-agent-backups-ACCOUNT_ID-REGION/audit-logs/2025/03/01/ \
  --profile your-aws-profile \
  --region us-east-1
```

**Lifecycle Policies**:
- Backups transition to STANDARD_IA after 30 days
- Backups transition to GLACIER after 90 days
- Backups expire after 365 days
- Audit logs retained for 365 days

### Security Resources

#### SupervisorPinSecretArn

**Description**: ARN of the AWS Secrets Manager secret containing the supervisor PIN.

**Format**: `arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:supervisor-ai-agent-pin-AbCdEf`

**Used In**:
- Authentication Lambda environment variables (automatically configured by CDK)
- PIN rotation procedures

**Secret Structure**:
```json
{
  "pin": "YOUR_PIN",
  "allowlist": ["+1234567890", "+0987YOUR_PIN"]
}
```

**Retrieving PIN Value**:
```bash
# Get secret value
aws secretsmanager get-secret-value \
  --secret-id arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:supervisor-ai-agent-pin-AbCdEf \
  --profile your-aws-profile \
  --region us-east-1 \
  --query SecretString \
  --output text | jq -r '.pin'
```

**Updating PIN**:
```bash
# Update PIN value
aws secretsmanager update-secret \
  --secret-id arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:supervisor-ai-agent-pin-AbCdEf \
  --secret-string '{"pin":"YOUR_PIN"}' \
  --profile your-aws-profile \
  --region us-east-1
```

**Security Notes**:
- PIN is encrypted at rest using AWS KMS
- Access restricted to Authentication Lambda execution role
- Supports automatic rotation (configure separately)
- 30-day recovery window if deleted

### Amazon Connect Resources

#### ConnectInstanceArn

**Description**: ARN of the Amazon Connect instance (passed as parameter, echoed as output).

**Format**: `arn:aws:connect:us-east-1:ACCOUNT_ID:instance/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

**Used In**:
- Lambda IAM policies (for Amazon Q in Connect API permissions)
- Reference for manual resource configuration

**Purpose**:
- Validates the Connect instance exists
- Used in IAM policies to scope permissions
- Reference for Contact Flow and AI Agent configuration

#### QConnectAssistantId

**Description**: ID of the Amazon Q in Connect assistant (passed as parameter, echoed as output).

**Format**: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

**Used In**:
- Lambda environment variables (automatically configured by CDK)
- Reference for AI Agent configuration

**Purpose**:
- Identifies the Amazon Q assistant for API calls
- Used by Agent Manager and Tester Lambdas
- Reference for Supervisor AI Agent creation

### Monitoring Resources

#### AlarmTopicArn

**Description**: ARN of the SNS topic for CloudWatch alarm notifications.

**Format**: `arn:aws:sns:us-east-1:ACCOUNT_ID:supervisor-ai-agent-alarms`

**Used In**:
- CloudWatch alarms (automatically configured by CDK)
- Email subscription for notifications

**Subscribing to Alarms**:
```bash
# Subscribe email to alarm topic
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:supervisor-ai-agent-alarms \
  --protocol email \
  --notification-endpoint ops-team@example.com \
  --profile your-aws-profile \
  --region us-east-1

# Confirm subscription via email link
```

**Alarm Types**:
- High authentication failure rate (>10 failures in 5 minutes)
- Prompt update failures (>0 failures)
- Critical test failures (>0 failures)
- Lambda errors (>5% error rate)
- Lambda throttling
- Phone spoofing detection (>5 phone failures in 5 minutes)
- PIN lockout events
- Unusual authenticated sessions (>3 in 1 hour)

### Additional Resources (Created by Security Hardening)

The following resources are created by the CDK stack but do not have explicit CfnOutputs. They can be found in the CloudFormation resources:

- **DynamoDB Table**: `supervisor-ai-agent-pin-attempts` — PIN rate limiting and auth tokens
- **KMS Key**: `supervisor-ai-agent-backup` — Customer-managed encryption key for S3 and SNS
- **VPC**: Private isolated subnets with VPC endpoints for S3, DynamoDB, Secrets Manager, CloudWatch Logs, Lambda
- **Signing Key Secret**: `supervisor-ai-agent-signing-key` — HMAC key for inter-Lambda request signing

## Integration Guide

### Step-by-Step Integration

#### 1. Retrieve All Outputs

```bash
# Save outputs to file
aws cloudformation describe-stacks \
  --stack-name SupervisorAIAgentStack \
  --profile your-aws-profile \
  --region us-east-1 \
  --query 'Stacks[0].Outputs' \
  --output json > stack-outputs.json

# View outputs
cat stack-outputs.json | jq -r '.[] | "\(.OutputKey): \(.OutputValue)"'
```

#### 2. ~~Configure Amazon Lex PIN Bot~~ (No Longer Required)

**Note**: PIN validation is now handled by the Supervisor AI Agent via MCP tool (`authenticate_pin`). No separate Lex bot is needed.

**Required Outputs**:
- `AuthenticationLambdaArn`

**How It Works**:
1. The Supervisor AI Agent calls the `authenticate_pin` MCP tool
2. The tool invokes the Authentication Lambda with the PIN
3. The Lambda validates against Secrets Manager and returns the result

#### 3. Configure Amazon Connect Contact Flow

**Required Outputs**:
- `AuthenticationLambdaArn`
- Supervisor AI Agent ID (from step 4)

**Steps**:
1. Create contact flow (see `docs/manual-setup/contact-flow-configuration.md`)
2. Add phone validation block with `AuthenticationLambdaArn`
3. PIN authentication is handled by the Supervisor AI Agent via MCP tool (no separate Lex bot block needed)
4. Add Connect assistant block for Supervisor AI Agent
5. Publish contact flow

#### 4. Configure Supervisor AI Agent

**Required Outputs**:
- `AgentManagerLambdaArn`
- `RestoreLambdaArn`
- `QConnectAssistantId`

**Steps**:
1. Create AI Agent (see `docs/manual-setup/supervisor-ai-agent-setup.md`)
2. Configure system prompt
3. Add tool definitions using Lambda ARNs
4. Publish AI Agent

#### 5. Test Integration

**Required Outputs**:
- All Lambda ARNs
- Contact flow phone number

**Steps**:
1. Call supervisor hotline
2. Verify phone validation works
3. Enter PIN and verify authentication
4. Test natural language conversation
5. Test agent listing and configuration retrieval
6. Test prompt update workflow

## Output Usage Matrix

| Output | Contact Flow | Supervisor AI Agent | Manual Verification |
|--------|--------------|---------------------|---------------------|
| AuthenticationLambdaArn | ✅ Phone validation | ✅ PIN validation (MCP tool) | ✅ Test invocation |
| AgentManagerLambdaArn | ❌ | ✅ Tool definitions | ✅ Test invocation |
| BackupLambdaArn | ❌ | ❌ | ✅ Test invocation |
| RestoreLambdaArn | ❌ | ✅ Tool definitions | ✅ Test invocation |
| TesterLambdaArn | ❌ | ❌ | ✅ Test invocation |
| BackupBucketName | ❌ | ❌ | ✅ Browse backups |
| SupervisorPinSecretArn | ❌ | ❌ | ❌ | ✅ View/update PIN |
| ConnectInstanceArn | ❌ | ❌ | ❌ | ✅ Reference |
| QConnectAssistantId | ❌ | ❌ | ✅ Agent creation | ✅ Reference |
| AlarmTopicArn | ❌ | ❌ | ❌ | ✅ Subscribe email |

## Testing Outputs

### Test Lambda Functions

```bash
# Test Authentication Lambda (phone validation)
aws lambda invoke \
  --function-name supervisor-ai-agent-auth \
  --payload '{"Details":{"ContactData":{"CustomerEndpoint":{"Address":"+1-555-0100"}}}}' \
  --profile your-aws-profile \
  --region us-east-1 \
  response.json

cat response.json

# Test Agent Manager Lambda (list agents)
aws lambda invoke \
  --function-name supervisor-ai-agent-manager \
  --payload '{"operation":"list_agents"}' \
  --profile your-aws-profile \
  --region us-east-1 \
  response.json

cat response.json
```

### Verify S3 Bucket

```bash
# List bucket contents
aws s3 ls s3://supervisor-ai-agent-backups-ACCOUNT_ID-REGION/ \
  --profile your-aws-profile \
  --region us-east-1 \
  --recursive

# Check bucket versioning
aws s3api get-bucket-versioning \
  --bucket supervisor-ai-agent-backups-ACCOUNT_ID-REGION \
  --profile your-aws-profile \
  --region us-east-1

# Check bucket encryption
aws s3api get-bucket-encryption \
  --bucket supervisor-ai-agent-backups-ACCOUNT_ID-REGION \
  --profile your-aws-profile \
  --region us-east-1
```

### Verify Secrets Manager

```bash
# Get secret metadata
aws secretsmanager describe-secret \
  --secret-id supervisor-ai-agent-pin \
  --profile your-aws-profile \
  --region us-east-1

# Get secret value (requires permissions)
aws secretsmanager get-secret-value \
  --secret-id supervisor-ai-agent-pin \
  --profile your-aws-profile \
  --region us-east-1 \
  --query SecretString \
  --output text
```

### Verify CloudWatch Resources

```bash
# List log groups
aws logs describe-log-groups \
  --log-group-name-prefix /aws/lambda/supervisor-ai-agent \
  --profile your-aws-profile \
  --region us-east-1

# List alarms
aws cloudwatch describe-alarms \
  --alarm-name-prefix supervisor-ai-agent \
  --profile your-aws-profile \
  --region us-east-1
```

## Troubleshooting

### Output Not Found

**Issue**: Output key not present in stack outputs

**Solutions**:
1. Verify stack deployment completed successfully
2. Check CloudFormation stack status
3. Review stack events for errors
4. Redeploy stack if necessary

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name SupervisorAIAgentStack \
  --profile your-aws-profile \
  --region us-east-1 \
  --query 'Stacks[0].StackStatus'
```

### Invalid ARN Format

**Issue**: ARN format doesn't match expected pattern

**Solutions**:
1. Verify you're using the correct AWS account and region
2. Check for typos when copying ARNs
3. Ensure stack deployed to correct region

### Lambda Function Not Found

**Issue**: Lambda ARN exists but function not accessible

**Solutions**:
1. Verify Lambda function exists in correct region
2. Check IAM permissions for accessing Lambda
3. Verify function wasn't manually deleted

```bash
# List Lambda functions
aws lambda list-functions \
  --profile your-aws-profile \
  --region us-east-1 \
  --query 'Functions[?starts_with(FunctionName, `supervisor-ai-agent`)].FunctionName'
```

### S3 Bucket Access Denied

**Issue**: Cannot access S3 bucket using output name

**Solutions**:
1. Verify bucket exists in correct region
2. Check IAM permissions for S3 access
3. Verify bucket policy allows your access

```bash
# Check bucket exists
aws s3api head-bucket \
  --bucket supervisor-ai-agent-backups-ACCOUNT_ID-REGION \
  --profile your-aws-profile \
  --region us-east-1
```

## Additional Resources

- **Deployment Guide**: `cdk/DEPLOYMENT.md`
- **CDK Configuration**: `docs/manual-setup/supervisor-ai-agent-cdk-configuration.md`
- **Contact Flow Setup**: `docs/manual-setup/contact-flow-configuration.md`
- **Supervisor AI Agent Setup**: `docs/manual-setup/supervisor-ai-agent-setup.md`
- **Intent Management**: `docs/manual-setup/intent-management-workflows.md`
