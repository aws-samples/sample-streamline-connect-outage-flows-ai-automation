# CDK Parameters Reference

## Overview

This document provides a comprehensive reference for all CDK stack parameters, their formats, validation rules, and how to pass them during deployment.

## Parameter Definitions

### Required Parameters

#### connectInstanceId

**Description**: Amazon Connect instance ID where the Supervisor AI Agent will be deployed.

**Format**: UUID (36 characters)
- Pattern: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- Example: `12345678-1234-1234-1234-123456789012`

**How to Find**:
1. Open AWS Console → Amazon Connect
2. Click on your instance alias
3. Go to Overview tab
4. Copy the Instance ID (not the Instance ARN)

**Validation**:
- Must be a valid UUID format
- Instance must exist in the deployment region
- Instance must have Amazon Q in Connect enabled

**Required**: Yes

#### qConnectAssistantId

**Description**: Amazon Q in Connect assistant ID associated with your Connect instance.

**Format**: UUID (36 characters)
- Pattern: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- Example: `87YOUR_PIN-4321-4321-4321-210987YOUR_PIN`

**How to Find**:
1. Open AWS Console → Amazon Connect
2. Click on your instance alias
3. Go to Amazon Q tab
4. Copy the Assistant ID

**Validation**:
- Must be a valid UUID format
- Assistant must exist and be associated with the Connect instance
- Assistant must be in ACTIVE state

**Required**: Yes

#### SupervisorPinSecretArn

**Description**: ARN of a pre-created Secrets Manager secret containing the supervisor PIN and phone allowlist.

**Format**: ARN string
- Pattern: `arn:aws:secretsmanager:REGION:ACCOUNT:secret:NAME-XXXXXX`
- Example: `arn:aws:secretsmanager:us-east-1:123456789012:secret:supervisor-ai-agent-pin-AbCdEf`

**Secret JSON Format**:
```json
{
  "pin": "YOUR_PIN",
  "allowlist": ["+1234567890", "+0987YOUR_PIN"]
}
```

**Pre-creation**:
```bash
aws secretsmanager create-secret \
  --name supervisor-ai-agent-pin \
  --secret-string '{"pin":"YOUR_PIN","allowlist":["+1234567890"]}' \
  --profile your-aws-profile --region us-east-1
```

**Validation**:
- Must be a valid Secrets Manager ARN
- Secret must exist before CDK deployment
- Secret must contain `pin` (6-digit string) and `allowlist` (array of E.164 numbers)

**Required**: Yes

### Optional Parameters

#### notificationEmail

**Description**: Email address for CloudWatch alarm notifications.

**Format**: Valid email address
- Pattern: `user@domain.com`
- Example: `ops-team@example.com`

**Validation**:
- Must be a valid email format
- Domain must have valid MX records (for delivery)

**Default**: Empty (no email notifications)

**Note**: After deployment, you must confirm the SNS subscription via email link.

#### productionAgentIds

**Description**: Comma-separated list of production AI agent IDs to manage.

**Format**: UUIDs, comma-separated
- Pattern: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx,xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- Example: `agent-id-1,agent-id-2,agent-id-3`

**How to Find**:
1. Open AWS Console → Amazon Connect
2. Click on your instance alias
3. Go to Amazon Q → AI Agents
4. Copy the Agent IDs

**Validation**:
- Each ID must be a valid UUID format
- Agents must exist in the specified assistant
- Agents must be in ACTIVE state

**Default**: Empty (all agents in assistant are manageable)

**Note**: This parameter is informational and used for documentation. The system can manage any agent in the assistant regardless of this list.

## Parameter Passing Methods

### Method 1: cdk.context.json (Recommended)

**Best for**: Persistent configuration, team collaboration, version control

**Location**: `cdk/cdk.context.json`

**Format**:
```json
{
  "connectInstanceId": "12345678-1234-1234-1234-123456789012",
  "qConnectAssistantId": "87YOUR_PIN-4321-4321-4321-210987YOUR_PIN",
  "SupervisorPinSecretArn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:supervisor-ai-agent-pin-AbCdEf",
  "notificationEmail": "ops-team@example.com",
  "productionAgentIds": "agent-id-1,agent-id-2"
}
```

**Advantages**:
- ✅ Persistent across deployments
- ✅ Version controlled (can be committed to git)
- ✅ Easy to share with team
- ✅ No need to remember parameters

**Disadvantages**:
- ⚠️ Sensitive data (secret ARN) in version control (use .gitignore or environment variables for sensitive values)

**Deployment**:
```bash
cd cdk
cdk deploy --profile your-aws-profile --region us-east-1
```

### Method 2: Command Line Arguments

**Best for**: One-time deployments, testing, overriding context values

**Format**:
```bash
cd cdk
cdk deploy \
  -c connectInstanceId=12345678-1234-1234-1234-123456789012 \
  -c qConnectAssistantId=87YOUR_PIN-4321-4321-4321-210987YOUR_PIN \
  -c SupervisorPinSecretArn="arn:aws:secretsmanager:us-east-1:123456789012:secret:supervisor-ai-agent-pin-AbCdEf" \
  -c notificationEmail="ops-team@example.com" \
  -c productionAgentIds="agent-id-1,agent-id-2" \
  --profile your-aws-profile \
  --region us-east-1
```

**Advantages**:
- ✅ No file modification needed
- ✅ Overrides context values
- ✅ Good for testing different configurations

**Disadvantages**:
- ❌ Must remember all parameters
- ❌ Long command line
- ❌ Not persistent

**Note**: Command line parameters override cdk.context.json values.

### Method 3: Environment Variables

**Best for**: CI/CD pipelines, keeping secrets out of version control

**Format**:
```bash
# Set environment variables
export CDK_CONNECT_INSTANCE_ID="12345678-1234-1234-1234-123456789012"
export CDK_QCONNECT_ASSISTANT_ID="87YOUR_PIN-4321-4321-4321-210987YOUR_PIN"
export CDK_SUPERVISOR_PIN_SECRET_ARN="arn:aws:secretsmanager:us-east-1:123456789012:secret:supervisor-ai-agent-pin-AbCdEf"
export CDK_NOTIFICATION_EMAIL="ops-team@example.com"
export CDK_PRODUCTION_AGENT_IDS="agent-id-1,agent-id-2"

# Deploy
cd cdk
cdk deploy --profile your-aws-profile --region us-east-1
```

**Advantages**:
- ✅ Keeps secrets out of version control
- ✅ Good for CI/CD pipelines
- ✅ Can be set in shell profile

**Disadvantages**:
- ❌ Requires code modification to read environment variables
- ❌ Not persistent across sessions (unless in shell profile)

**Note**: This method requires modifying `cdk/bin/cdk.ts` to read environment variables.

### Method 4: AWS Systems Manager Parameter Store

**Best for**: Production deployments, centralized configuration management

**Setup**:
```bash
# Store parameters in Parameter Store
aws ssm put-parameter \
  --name /supervisor-ai-agent/connectInstanceId \
  --value "12345678-1234-1234-1234-123456789012" \
  --type String \
  --profile your-aws-profile \
  --region us-east-1

aws ssm put-parameter \
  --name /supervisor-ai-agent/qConnectAssistantId \
  --value "87YOUR_PIN-4321-4321-4321-210987YOUR_PIN" \
  --type String \
  --profile your-aws-profile \
  --region us-east-1

aws ssm put-parameter \
  --name /supervisor-ai-agent/supervisorPin \
  --value "987654" \
  --type SecureString \
  --profile your-aws-profile \
  --region us-east-1
```

**Advantages**:
- ✅ Centralized configuration
- ✅ Secure storage (SecureString for sensitive data)
- ✅ Access control via IAM
- ✅ Audit trail

**Disadvantages**:
- ❌ Requires code modification to read from Parameter Store
- ❌ Additional AWS service dependency

**Note**: This method requires modifying `cdk/bin/cdk.ts` to read from Parameter Store.

## Parameter Validation

### Pre-Deployment Validation

The deployment script (`cdk/scripts/deploy.sh`) validates parameters before deployment:

```bash
./cdk/scripts/deploy.sh
```

**Validation Checks**:
- ✅ Required parameters are present
- ✅ UUID format validation
- ✅ E.164 phone number format
- ✅ PIN format (6 digits)
- ✅ Email format
- ⚠️ Warning if parameters are missing (can still deploy)

### Runtime Validation

The CDK stack validates parameters during synthesis:

```bash
cd cdk
cdk synth --profile your-aws-profile --region us-east-1
```

**Validation Checks**:
- ✅ Required parameters must be provided
- ✅ Format validation (UUID, E.164, etc.)
- ❌ Deployment fails if validation fails

## Parameter Examples

### Minimal Configuration (Required Only)

```json
{
  "connectInstanceId": "12345678-1234-1234-1234-123456789012",
  "qConnectAssistantId": "87YOUR_PIN-4321-4321-4321-210987YOUR_PIN",
  "SupervisorPinSecretArn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:supervisor-ai-agent-pin-AbCdEf"
}
```

**Result**:
- PIN and phone allowlist managed via Secrets Manager
- No email notifications
- All agents in assistant are manageable

### Development Configuration

```json
{
  "connectInstanceId": "12345678-1234-1234-1234-123456789012",
  "qConnectAssistantId": "87YOUR_PIN-4321-4321-4321-210987YOUR_PIN",
  "SupervisorPinSecretArn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:supervisor-ai-agent-pin-AbCdEf",
  "notificationEmail": "dev-team@example.com"
}
```

**Result**:
- PIN and phone allowlist managed via Secrets Manager
- Email notifications to dev team

### Production Configuration

```json
{
  "connectInstanceId": "12345678-1234-1234-1234-123456789012",
  "qConnectAssistantId": "87YOUR_PIN-4321-4321-4321-210987YOUR_PIN",
  "SupervisorPinSecretArn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:supervisor-ai-agent-pin-AbCdEf",
  "notificationEmail": "ops-team@example.com,oncall@example.com",
  "productionAgentIds": "prod-agent-1,prod-agent-2,prod-agent-3"
}
```

**Result**:
- PIN and phone allowlist managed via Secrets Manager
- Multiple email recipients
- Documented production agents

## Security Best Practices

### Phone Allowlist

**Recommendations**:
- ✅ Always configure allowlist for production (stored in Secrets Manager)
- ✅ Use corporate phone numbers only
- ✅ Limit to operations team members
- ✅ Review and update regularly via `aws secretsmanager put-secret-value`
- ❌ Don't use personal phone numbers
- ❌ Don't share allowlist publicly

### Supervisor PIN

**Recommendations**:
- ✅ Use strong, random 6-digit PIN
- ✅ Change default PIN immediately
- ✅ Rotate PIN regularly (quarterly) via `aws secretsmanager put-secret-value`
- ✅ PIN is stored in Secrets Manager (managed via `SupervisorPinSecretArn`)
- ❌ Don't use common PINs (000000, 123456, 111111)
- ❌ Don't share PIN via email or chat
- ❌ Don't reuse PINs across environments

**PIN Rotation**:
```bash
# Update PIN in Secrets Manager (include full secret JSON)
aws secretsmanager put-secret-value \
  --secret-id supervisor-ai-agent-pin \
  --secret-string '{"pin":"NEW_6_DIGIT_PIN","allowlist":["+1-555-0100"]}' \
  --profile your-aws-profile \
  --region us-east-1
```

### Notification Email

**Recommendations**:
- ✅ Use team distribution list
- ✅ Include on-call rotation
- ✅ Test email delivery
- ✅ Confirm SNS subscription
- ❌ Don't use personal email only
- ❌ Don't ignore alarm emails

## Troubleshooting

### Parameter Not Found

**Issue**: CDK reports parameter not found

**Solutions**:
1. Check parameter name spelling in cdk.context.json
2. Verify parameter is passed via command line
3. Check environment variable names
4. Ensure cdk.context.json is in correct location

### Invalid Parameter Format

**Issue**: CDK validation fails with format error

**Solutions**:
1. Verify UUID format (36 characters with dashes)
2. Check E.164 phone format (starts with +)
3. Verify PIN is exactly 6 digits
4. Check email format

### Connect Instance Not Found

**Issue**: Deployment fails with instance not found

**Solutions**:
1. Verify instance ID is correct
2. Check instance exists in deployment region
3. Verify IAM permissions to access Connect
4. Ensure instance is in ACTIVE state

### Assistant Not Found

**Issue**: Deployment fails with assistant not found

**Solutions**:
1. Verify assistant ID is correct
2. Check assistant is associated with Connect instance
3. Verify Amazon Q in Connect is enabled
4. Ensure assistant is in ACTIVE state

### Phone Number Validation Fails

**Issue**: Phone numbers rejected during validation

**Solutions**:
1. Ensure E.164 format (+country code + number)
2. Remove spaces, dashes, parentheses
3. Verify country code is correct
4. Check for typos

### PIN Validation Fails

**Issue**: PIN rejected during validation

**Solutions**:
1. Ensure PIN is exactly 6 digits
2. Remove any non-numeric characters
3. Check for leading/trailing spaces
4. Verify PIN is a string, not a number (in JSON)

## Parameter Update Procedures

### Updating Phone Allowlist

The phone allowlist is stored in Secrets Manager. Update it directly (no CDK redeployment needed):

```bash
aws secretsmanager put-secret-value \
  --secret-id supervisor-ai-agent-pin \
  --secret-string '{"pin":"CURRENT_PIN","allowlist":["+1-555-0102","+1-555-0103","+1-555-0105"]}' \
  --profile your-aws-profile \
  --region us-east-1
```

**Important**: Include the full secret JSON with both `pin` and `allowlist` fields.

### Updating PIN

The PIN is stored in Secrets Manager. Update it directly (no CDK redeployment needed):

```bash
aws secretsmanager put-secret-value \
  --secret-id supervisor-ai-agent-pin \
  --secret-string '{"pin":"NEW_6_DIGIT_PIN","allowlist":["+1-555-0100"]}' \
  --profile your-aws-profile \
  --region us-east-1
```

**Important**: Include the full secret JSON with both `pin` and `allowlist` fields.

```bash
# Verify update
aws secretsmanager get-secret-value \
  --secret-id supervisor-ai-agent-pin \
  --profile your-aws-profile \
  --region us-east-1 \
  --query SecretString \
  --output text
```

### Adding Notification Email

```bash
# Method 1: Update cdk.context.json and redeploy
# Edit cdk/cdk.context.json and change notificationEmail

# Method 2: Subscribe directly to SNS topic
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:supervisor-ai-agent-alarms \
  --protocol email \
  --notification-endpoint new-email@example.com \
  --profile your-aws-profile \
  --region us-east-1

# Confirm subscription via email
```

## Additional Resources

- **Deployment Guide**: `cdk/DEPLOYMENT.md`
- **Stack Outputs**: `cdk/STACK_OUTPUTS.md`
- **CDK Configuration**: `docs/manual-setup/supervisor-ai-agent-cdk-configuration.md`
- **Security Best Practices**: AWS Well-Architected Framework
