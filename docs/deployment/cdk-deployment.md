# CDK Deployment Guide

[← Back to Documentation Index](../README.md) | [Getting Started](../getting-started/project-setup.md) | [Architecture](../architecture/system-architecture.md) | [Operations](../operations/operations-runbook.md)

---

## Overview

This guide provides comprehensive instructions for deploying the Supervisor AI Agent for Amazon Connect Outage Management using AWS CDK.

## Prerequisites

### Required Software

1. **Node.js 18.x or higher**
   - Download from: https://nodejs.org/
   - Verify: `node --version`

2. **npm (comes with Node.js)**
   - Verify: `npm --version`

3. **AWS CLI v2**
   - Download from: https://aws.amazon.com/cli/
   - Verify: `aws --version`

4. **Python 3.12**
   - Download from: https://www.python.org/
   - Verify: `python3.12 --version`

5. **AWS CDK Toolkit**
   - Install: `npm install -g aws-cdk`
   - Verify: `cdk --version`

### AWS Configuration

1. **AWS Account Access**
   - You need an AWS account with appropriate permissions
   - Administrator access is recommended for initial deployment

2. **AWS Credentials**
   - Configure AWS CLI with your credentials:
     ```bash
     aws configure --profile your-aws-profile
     ```
   - Enter your AWS Access Key ID, Secret Access Key, and default region (us-east-1)

3. **AWS Profile and Region**
   - Default profile: `your-aws-profile`
   - Default region: `us-east-1`
   - Set environment variables:
     ```bash
     export AWS_PROFILE=your-aws-profile
     export AWS_REGION=us-east-1
     ```

### Amazon Connect Prerequisites

Before deploying the CDK stack, you must have:

1. **Amazon Connect Instance**
   - An existing Amazon Connect instance with Amazon Q in Connect enabled
   - Note the instance ID (format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
   - Find it in: AWS Console → Amazon Connect → Instance alias → Overview
   - [Create an Amazon Connect instance](https://docs.aws.amazon.com/connect/latest/adminguide/amazon-connect-instances.html)

2. **Amazon Q in Connect Assistant**
   - An existing Amazon Q in Connect assistant associated with your Connect instance
   - Note the assistant ID (format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
   - Find it in: AWS Console → Amazon Connect → Instance → Amazon Q
   - [Enable Amazon Q in Connect for your instance](https://docs.aws.amazon.com/connect/latest/adminguide/enable-q.html)

3. **Production AI Agent IDs** (Optional)
   - IDs of production AI agents you want to manage
   - Find them in: AWS Console → Amazon Connect → Instance → Amazon Q → AI Agents
   - [Create AI Agents in Amazon Q in Connect](https://docs.aws.amazon.com/connect/latest/adminguide/create-ai-agent-versions.html)

## CDK Bootstrap

CDK requires a one-time bootstrap process per AWS account and region:

```bash
cd cdk
cdk bootstrap aws://ACCOUNT-ID/us-east-1 --profile your-aws-profile
```

Replace `ACCOUNT-ID` with your AWS account ID (get it with `aws sts get-caller-identity --profile your-aws-profile --query Account --output text`).

## Deployment Methods

### Method 1: Automated Deployment Script (Recommended)

The deployment script performs pre-deployment validation and guides you through the process:

```bash
# From project root
./cdk/scripts/deploy.sh
```

**Script Features:**
- Validates all prerequisites (Node.js, AWS CLI, Python, credentials)
- Checks CDK bootstrap status
- Installs dependencies if needed
- Builds and synthesizes the CDK stack
- Provides deployment command for manual execution

**Script Options:**
```bash
./cdk/scripts/deploy.sh --help

Options:
  --profile PROFILE       AWS profile to use (default: your-aws-profile)
  --region REGION         AWS region to deploy to (default: us-east-1)
  --skip-validation       Skip pre-deployment validation checks
  --outputs-only          Show stack outputs only (no deployment)
  --help                  Show this help message
```

**Examples:**
```bash
# Deploy with default settings
./cdk/scripts/deploy.sh

# Deploy with custom profile and region
./cdk/scripts/deploy.sh --profile my-profile --region us-west-2

# Skip validation (if you've already validated)
./cdk/scripts/deploy.sh --skip-validation

# View stack outputs after deployment
./cdk/scripts/deploy.sh --outputs-only
```

### Method 2: Manual Deployment

If you prefer manual control:

1. **Install CDK Dependencies**
   ```bash
   cd cdk
   npm install
   ```

2. **Build CDK Project**
   ```bash
   npm run build
   ```

3. **Configure Parameters**
   
   Edit `cdk/cdk.context.json` to add your configuration:
   ```json
   {
     "connectInstanceId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
     "qConnectAssistantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
     "SupervisorPinSecretArn": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:supervisor-ai-agent-pin-XXXXXX",
     "notificationEmail": "ops-team@example.com"
   }
   ```

   Or pass parameters via command line (see below).
   
   **Note:** CDK automatically bundles Python dependencies from each Lambda's `requirements.txt` using Docker. No manual dependency installation required.

4. **Synthesize Stack**
   ```bash
   cdk synth --profile your-aws-profile --region us-east-1
   ```

5. **Deploy Stack**
   ```bash
   cdk deploy --profile your-aws-profile --region us-east-1
   ```

## CDK Parameters

The stack accepts the following parameters:

### Required Parameters

| Parameter | Description | Format | Example |
|-----------|-------------|--------|---------|
| `connectInstanceId` | Amazon Connect instance ID | UUID | `12345678-1234-1234-1234-123456789012` |
| `qConnectAssistantId` | Amazon Q in Connect assistant ID | UUID | `87YOUR_PIN-4321-4321-4321-210987YOUR_PIN` |

### Optional Parameters

| Parameter | Description | Format | Default | Example |
|-----------|-------------|--------|---------|---------|
| `SupervisorPinSecretArn` | ARN of pre-created Secrets Manager secret | ARN string | (required) | `arn:aws:secretsmanager:...` |
| `notificationEmail` | Email for CloudWatch alarm notifications | Email address | Empty | `ops-team@example.com` |
| `productionAgentIds` | Comma-separated list of production agent IDs | UUIDs | Empty | `agent-id-1,agent-id-2` |

### Passing Parameters

**Via cdk.context.json** (recommended for persistent configuration):
```json
{
  "connectInstanceId": "your-instance-id",
  "qConnectAssistantId": "your-assistant-id",
  "SupervisorPinSecretArn": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:supervisor-ai-agent-pin-XXXXXX",
  "notificationEmail": "ops@example.com"
}
```

**Via command line** (for one-time or testing):
```bash
cdk deploy \
  -c connectInstanceId=your-instance-id \
  -c qConnectAssistantId=your-assistant-id \
  -c SupervisorPinSecretArn="arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:supervisor-ai-agent-pin-XXXXXX" \
  -c notificationEmail="ops@example.com" \
  --profile your-aws-profile \
  --region us-east-1
```

**Via environment variables**:
```bash
export CDK_CONNECT_INSTANCE_ID="your-instance-id"
export CDK_QCONNECT_ASSISTANT_ID="your-assistant-id"
export CDK_SUPERVISOR_PIN_SECRET_ARN="arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:supervisor-ai-agent-pin-XXXXXX"
export CDK_NOTIFICATION_EMAIL="ops@example.com"

cdk deploy --profile your-aws-profile --region us-east-1
```

## Deployment Process

### Step 1: Pre-Deployment Validation

The deployment script validates:
- ✅ Node.js version (18.x or higher)
- ✅ npm installation
- ✅ AWS CLI installation (v2 recommended)
- ✅ AWS credentials and authentication
- ✅ Python 3.12 installation
- ✅ Python virtual environment
- ✅ CDK bootstrap status
- ✅ CDK dependencies
- ✅ Required parameters

### Step 2: Build and Synthesis

The script:
1. Installs npm dependencies if needed
2. Compiles TypeScript to JavaScript
3. Synthesizes CloudFormation template
4. Validates template structure

### Step 3: Deployment

The deployment creates:
- **5 Lambda Functions**: Authentication, Agent Manager, Backup, Restore, Tester
- **1 S3 Bucket**: For backups, intent configurations, and audit logs
- **1 Secrets Manager Secret**: For supervisor PIN
- **5 IAM Roles**: One for each Lambda function with least privilege permissions
- **5 CloudWatch Log Groups**: For Lambda function logs
- **CloudWatch Alarms**: For monitoring authentication failures, update failures, and errors
- **1 SNS Topic**: For alarm notifications

**Deployment Time**: Approximately 3-5 minutes

### Step 4: Post-Deployment

After deployment completes:
1. Review stack outputs (see below)
2. Note Lambda ARNs, S3 bucket name, and Secret ARN
3. Proceed to manual resource setup (see Manual Setup section)

## Stack Outputs

After successful deployment, the stack provides outputs for integration:

```bash
# View outputs
aws cloudformation describe-stacks \
  --stack-name SupervisorAIAgentStack \
  --profile your-aws-profile \
  --region us-east-1 \
  --query 'Stacks[0].Outputs'

# Or use the deployment script
./cdk/scripts/deploy.sh --outputs-only
```

### Output Reference

| Output Key | Description | Used In |
|------------|-------------|---------|
| `AuthenticationLambdaArn` | ARN of Authentication Lambda | Contact Flow, Lex Bot |
| `AgentManagerLambdaArn` | ARN of Agent Manager Lambda | Supervisor AI Agent tools |
| `BackupLambdaArn` | ARN of Backup Lambda | Agent Manager invocation |
| `RestoreLambdaArn` | ARN of Restore Lambda | Supervisor AI Agent tools |
| `TesterLambdaArn` | ARN of Tester Lambda | Agent Manager invocation |
| `BackupBucketName` | Name of S3 backup bucket | Lambda environment variables |
| `SupervisorPinSecretArn` | ARN of Secrets Manager secret | Authentication Lambda |
| `ConnectInstanceArn` | ARN of Connect instance | Lambda permissions |
| `QConnectAssistantId` | Amazon Q assistant ID | Lambda environment variables |

### Example Output

```json
[
  {
    "OutputKey": "AuthenticationLambdaArn",
    "OutputValue": "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:supervisor-ai-agent-auth"
  },
  {
    "OutputKey": "AgentManagerLambdaArn",
    "OutputValue": "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:supervisor-ai-agent-manager"
  },
  {
    "OutputKey": "BackupBucketName",
    "OutputValue": "supervisor-ai-agent-backups-ACCOUNT_ID-REGION"
  },
  {
    "OutputKey": "SupervisorPinSecretArn",
    "OutputValue": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:supervisor-ai-agent-pin-AbCdEf"
  }
]
```

## Manual Setup After CDK Deployment

After CDK deployment completes, you must manually configure the conversational resources:

### 1. Amazon Lex PIN Bot

Follow the guide: `docs/manual-setup/lex-pin-bot-configuration.md`

**Key Integration Points:**
- Lambda fulfillment: Use `AuthenticationLambdaArn` from stack outputs
- Bot configuration: 6-digit PIN slot, 3 retry attempts

### 2. Amazon Connect Contact Flow

Follow the guide: `docs/manual-setup/contact-flow-configuration.md`

**Key Integration Points:**
- Phone validation Lambda: Use `AuthenticationLambdaArn` from stack outputs
- Lex bot: Reference the PIN bot created in step 1
- Supervisor AI Agent: Reference the agent created in step 3

### 3. Supervisor AI Agent

Follow the guide: `docs/manual-setup/supervisor-ai-agent-setup.md`

**Key Integration Points:**
- Tool Lambda ARNs: Use `AgentManagerLambdaArn` and `RestoreLambdaArn` from stack outputs
- System prompt: Use the template provided in the guide
- Tool definitions: Configure with Lambda ARNs

### 4. Intent Management (Optional)

Follow the guide: `docs/manual-setup/intent-management-workflows.md`

**Key Integration Points:**
- Intent configuration storage: Uses S3 bucket from stack outputs
- Intent management tools: Already configured in Agent Manager Lambda

## Updating the Stack

To update the stack after making changes:

```bash
# Build changes
cd cdk
npm run build

# Review changes
cdk diff --profile your-aws-profile --region us-east-1

# Deploy updates
cdk deploy --profile your-aws-profile --region us-east-1
```

**Note**: Updates to Lambda functions, IAM roles, and S3 bucket are safe. Updates to Secrets Manager may require manual intervention.

## Destroying the Stack

To remove all resources:

```bash
cd cdk
cdk destroy --profile your-aws-profile --region us-east-1
```

**Warning**: This will delete:
- All Lambda functions
- S3 bucket (if empty)
- Secrets Manager secret (with recovery window)
- IAM roles and policies
- CloudWatch log groups and alarms

**Data Retention**:
- S3 bucket must be empty before deletion (backups and audit logs will be retained)
- Secrets Manager secret has a 30-day recovery window
- CloudWatch logs are deleted immediately

## Troubleshooting

### Common Issues

**Issue**: `CDK is not bootstrapped`
```
Solution: Run bootstrap command:
cd cdk
cdk bootstrap aws://ACCOUNT-ID/us-east-1 --profile your-aws-profile
```

**Issue**: `Unable to resolve AWS account to use`
```
Solution: Set AWS credentials:
export AWS_PROFILE=your-aws-profile
export AWS_REGION=us-east-1
```

**Issue**: `npm ERR! code ENOENT`
```
Solution: Install dependencies:
cd cdk
npm install
```

**Issue**: `Python 3.12 not found`
```
Solution: Install Python 3.12 from https://www.python.org/
```

**Issue**: `Stack already exists`
```
Solution: Update existing stack:
cdk deploy --profile your-aws-profile --region us-east-1
```

**Issue**: `Insufficient permissions`
```
Solution: Ensure your AWS credentials have administrator access or required permissions:
- cloudformation:*
- lambda:*
- s3:*
- secretsmanager:*
- iam:*
- logs:*
- sns:*
```

### Validation Failures

If the deployment script reports validation failures:

1. **Node.js version too old**: Upgrade to Node.js 18.x or higher
2. **AWS CLI not found**: Install AWS CLI v2
3. **AWS credentials invalid**: Run `aws configure --profile your-aws-profile`
4. **Python 3.12 not found**: Install Python 3.12
5. **CDK not bootstrapped**: Run bootstrap command (see above)

### Deployment Failures

If deployment fails:

1. **Check CloudFormation Events**:
   ```bash
   aws cloudformation describe-stack-events \
     --stack-name SupervisorAIAgentStack \
     --profile your-aws-profile \
     --region us-east-1 \
     --max-items 20
   ```

2. **Review Error Messages**: Look for specific resource failures
3. **Check IAM Permissions**: Ensure your credentials have required permissions
4. **Verify Parameters**: Ensure all required parameters are provided
5. **Check Service Quotas**: Verify you haven't exceeded Lambda, S3, or other service limits

### Getting Help

- **AWS Support**: Contact AWS Support for account or service issues
- **CDK Documentation**: https://docs.aws.amazon.com/cdk/
- **Project Documentation**: See `docs/` directory for detailed guides

## Security Considerations

### Credentials and Secrets

- **Supervisor PIN**: Stored in AWS Secrets Manager with KMS encryption
- **AWS Credentials**: Never commit credentials to version control
- **IAM Roles**: Use least privilege permissions for all Lambda functions

### Network Security

- **Lambda Functions**: Run in AWS-managed VPC with no public internet access
- **S3 Bucket**: Private with bucket policy restricting access to Lambda roles
- **Secrets Manager**: Access restricted to Authentication Lambda role only

### Data Protection

- **Encryption at Rest**: S3 (SSE-S3), Secrets Manager (KMS)
- **Encryption in Transit**: TLS 1.2+ for all AWS API calls
- **Audit Logs**: All operations logged to S3 and CloudWatch

### Access Control

- **Phone Allowlist**: Only authorized phone numbers can access the system
- **PIN Authentication**: Second factor authentication required
- **IAM Policies**: Resource-specific ARNs, no wildcard permissions

## Cost Estimation

Estimated monthly costs (based on moderate usage):

| Service | Usage | Estimated Cost |
|---------|-------|----------------|
| Lambda | 1,000 invocations/month, 512MB, 30s avg | $0.50 |
| S3 | 10GB storage, 1,000 requests | $0.30 |
| Secrets Manager | 1 secret | $0.40 |
| CloudWatch Logs | 5GB ingestion, 30-day retention | $2.50 |
| CloudWatch Alarms | 5 alarms | $0.50 |
| SNS | 100 notifications | $0.01 |
| **Total** | | **~$4.21/month** |

**Note**: Costs vary based on usage patterns. Amazon Connect and Amazon Q in Connect have separate pricing.

## Next Steps

After successful deployment:

1. ✅ Review stack outputs and note integration values
2. ✅ Configure Amazon Lex PIN Bot (see `docs/manual-setup/lex-pin-bot-configuration.md`)
3. ✅ Configure Amazon Connect Contact Flow (see `docs/manual-setup/contact-flow-configuration.md`)
4. ✅ Configure Supervisor AI Agent (see `docs/manual-setup/supervisor-ai-agent-setup.md`)
5. ✅ Test the complete workflow with a test call
6. ✅ Configure intent management (optional, see `docs/manual-setup/intent-management-workflows.md`)
7. ✅ Set up monitoring and alerting
8. ✅ Train operations team on system usage

## Additional Resources

- **CDK Configuration Guide**: `docs/manual-setup/supervisor-ai-agent-cdk-configuration.md`
- **Contact Flow Setup**: `docs/manual-setup/contact-flow-configuration.md`
- **Lex Bot Setup**: `docs/manual-setup/lex-pin-bot-configuration.md`
- **Supervisor AI Agent Setup**: `docs/manual-setup/supervisor-ai-agent-setup.md`
- **Intent Management**: `docs/manual-setup/intent-management-workflows.md`
- **System Prompt**: `docs/supervisor-ai-agent-system-prompt.md`
- **Project Setup**: `PROJECT_SETUP.md`
