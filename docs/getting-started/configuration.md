# Configuration Guide

[← Back to Documentation Index](../README.md) | [Project Setup](project-setup.md) | [Deployment](../deployment/cdk-deployment.md) | [Operations](../operations/operations-runbook.md)

---

This document describes the required environment variables and configuration parameters for the Supervisor AI Agent system. **Do not commit actual values to version control.**

## Required Environment Variables

### AWS Configuration

Set these environment variables before running AWS CLI or CDK commands:

```bash
export AWS_PROFILE=your-aws-profile    # Your AWS CLI profile name
export AWS_REGION=us-east-1            # Your target AWS region
```

### Python Virtual Environment

Always activate the Python virtual environment before running Python commands:

```bash
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate     # On Windows
```

## Pre-Deployment: Create Supervisor Secret

Before deploying the CDK stack, create a Secrets Manager secret containing the supervisor PIN and phone allowlist:

```bash
aws secretsmanager create-secret \
  --name supervisor-ai-agent-pin \
  --secret-string '{"pin":"YOUR_6_DIGIT_PIN","allowlist":["+1234567890","+0987YOUR_PIN"]}' \
  --profile your-aws-profile --region us-east-1
```

The secret JSON must contain:
- `pin` (string): 6-digit supervisor PIN
- `allowlist` (array): Authorized phone numbers in E.164 format

Note the secret ARN from the output — you'll need it as the `SupervisorPinSecretArn` CDK parameter.

## CDK Deployment Parameters

### Required Parameters

These parameters must be provided during CDK deployment:

| Parameter | Description | Format | Example |
|-----------|-------------|--------|---------|
| `connectInstanceId` | Amazon Connect instance ID | UUID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `qConnectAssistantId` | Amazon Q in Connect assistant ID | UUID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |

### Optional Parameters

| Parameter | Description | Format | Example |
|-----------|-------------|--------|---------|
| `SupervisorPinSecretArn` | ARN of pre-created Secrets Manager secret containing PIN and phone allowlist | ARN string | `arn:aws:secretsmanager:us-east-1:123456789012:secret:supervisor-ai-agent-pin-AbCdEf` |
| `notificationEmail` | CloudWatch alarm email | Email address | `ops-team@example.com` |
| `productionAgentIds` | Production agent IDs | UUIDs, comma-separated | `agent-id-1,agent-id-2` |

### How to Provide Parameters

**Method 1: Context parameters (recommended)**

```bash
cd cdk
cdk deploy \
  -c connectInstanceId=your-instance-id \
  -c qConnectAssistantId=your-assistant-id \
  -c SupervisorPinSecretArn="arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:supervisor-ai-agent-pin-XXXXXX" \
  -c notificationEmail="your-email@example.com" \
  --profile your-aws-profile \
  --region us-east-1
```

**Method 2: Environment variables**

```bash
export CDK_CONNECT_INSTANCE_ID="your-instance-id"
export CDK_QCONNECT_ASSISTANT_ID="your-assistant-id"
export CDK_SUPERVISOR_PIN_SECRET_ARN="arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:supervisor-ai-agent-pin-XXXXXX"
export CDK_NOTIFICATION_EMAIL="your-email@example.com"

cd cdk
cdk deploy --profile your-aws-profile --region us-east-1
```

**Method 3: cdk.json (not recommended for sensitive data)**

Create a `cdk.json.local` file (excluded from git):

```json
{
  "context": {
    "connectInstanceId": "your-instance-id",
    "qConnectAssistantId": "your-assistant-id",
    "SupervisorPinSecretArn": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:supervisor-ai-agent-pin-XXXXXX",
    "notificationEmail": "your-email@example.com"
  }
}
```

## Finding Your Configuration Values

### Amazon Connect Instance ID

```bash
aws connect list-instances \
  --profile your-aws-profile \
  --region us-east-1 \
  --query 'InstanceSummaryList[*].[Id,InstanceAlias]' \
  --output table
```

### Amazon Q in Connect Assistant ID

```bash
# First, get your Connect instance ARN
INSTANCE_ARN=$(aws connect list-instances \
  --profile your-aws-profile \
  --region us-east-1 \
  --query 'InstanceSummaryList[0].Arn' \
  --output text)

# Then list assistants
aws wisdom list-assistants \
  --profile your-aws-profile \
  --region us-east-1 \
  --query 'assistantSummaries[*].[assistantId,name]' \
  --output table
```

### Phone Numbers

Phone numbers must be in E.164 format:
- US: `+1-555-0100`
- UK: `+44-20-7123-4567`
- Multiple: `+1-555-0100,+1-555-0101,+1-555-0102`

## Security Best Practices

1. **Never commit sensitive values** to version control
2. **Use AWS Secrets Manager** for production credentials
3. **Rotate PINs regularly** (at least quarterly)
4. **Limit phone allowlist** to only authorized personnel
5. **Use least-privilege AWS credentials** for deployment
6. **Enable MFA** on AWS accounts with deployment access
7. **Review CloudWatch logs** regularly for unauthorized access attempts

## Post-Deployment Configuration

After CDK deployment completes, you'll need to manually configure:

1. **Amazon Connect Contact Flow** - See `docs/manual-setup/contact-flow-configuration.md`
2. **Supervisor AI Agent** - See `docs/manual-setup/supervisor-ai-agent-setup.md`

## Updating Configuration

### Updating Phone Allowlist

The phone allowlist is stored in Secrets Manager (not as a CDK parameter). Update it directly:

```bash
aws secretsmanager put-secret-value \
  --secret-id supervisor-ai-agent-pin \
  --secret-string '{"pin":"CURRENT_PIN","allowlist":["+1-555-0100","+1-555-0101","+1-555-0102"]}' \
  --profile your-aws-profile \
  --region us-east-1
```

No CDK redeployment needed. Changes take effect on the next Lambda cold start.

### Updating PIN

Update the PIN directly in Secrets Manager (no CDK redeployment needed):

```bash
aws secretsmanager put-secret-value \
  --secret-id supervisor-ai-agent-pin \
  --secret-string '{"pin":"NEW_6_DIGIT_PIN","allowlist":["+1-555-0100"]}' \
  --profile your-aws-profile \
  --region us-east-1
```

**Important**: Include the full secret JSON with both `pin` and `allowlist` fields.

### Updating Notification Email

```bash
# Get SNS topic ARN from stack outputs
TOPIC_ARN=$(aws cloudformation describe-stacks \
  --stack-name SupervisorAIAgentStack \
  --profile your-aws-profile \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`AlarmTopicArn`].OutputValue' \
  --output text)

# Subscribe new email
aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol email \
  --notification-endpoint new-email@example.com \
  --profile your-aws-profile \
  --region us-east-1
```

## Troubleshooting

### Missing Configuration Parameters

If you see errors about missing parameters during deployment:

1. Verify all required parameters are provided
2. Check parameter format (UUIDs, E.164 phone numbers, etc.)
3. Ensure environment variables are exported in current shell session

### Invalid Phone Number Format

Phone numbers must:
- Start with `+` (plus sign)
- Include country code
- Contain only digits after country code
- Be in E.164 format

### AWS Profile Not Found

If you see "Profile not found" errors:

1. Verify profile exists: `aws configure list-profiles`
2. Check `~/.aws/credentials` and `~/.aws/config` files
3. Configure profile if needed: `aws configure --profile your-aws-profile`

## Additional Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [Amazon Connect Documentation](https://docs.aws.amazon.com/connect/)
- [Amazon Q in Connect Documentation](https://docs.aws.amazon.com/connect/latest/adminguide/amazon-q-connect.html)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
