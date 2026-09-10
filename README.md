# Supervisor AI Agent for Amazon Connect Outage Management

A serverless, phone-based system that enables operations managers to update Amazon Connect AI agent prompts during service outages through natural language conversation. Reduces outage response time from 15-20 minutes to under 2 minutes.

## Overview

During service outages, customer-facing AI agents need immediate updates to inform customers about unavailable services and guide them to alternatives. This system provides a secure, voice-based interface for operations managers to update AI agent prompts in real-time without manual AWS Console navigation.

The system supports two operational modes:
- **Full Outage Mode**: Update entire agent prompts for complete service outages
- **Intent-Level Mode**: Selectively disable/enable specific capabilities (e.g., "disable change card PIN") while keeping other services operational

### Key Features

- **Phone-Based Interface**: Natural language conversation via Amazon Connect
- **Multi-Layer Authentication**: Phone allowlist + PIN verification
- **Dual Operational Modes**: Full outage updates or granular intent-level management
- **Intent Discovery**: List and manage specific agent capabilities
- **Selective Disable/Enable**: Control individual intents without affecting others
- **Automated Backup**: Always backs up prompts and intent configurations before changes
- **Automated Testing**: Validates updates before deployment
- **Immediate Deployment**: Updates take effect within 5 seconds
- **Automatic Rollback**: Restores previous prompt if tests fail
- **Comprehensive Audit Trail**: All operations logged to S3 and CloudWatch

### Business Impact

- **Response Time**: Reduced from 15-20 minutes to under 2 minutes (90% improvement)
- **Reliability**: 100% backup success rate with automated rollback
- **Security**: Multi-layer authentication with comprehensive audit logging
- **Cost**: Serverless architecture with pay-per-use pricing (~$15-20/month for typical usage, primarily VPC endpoint costs)

## Architecture

### System Components

```
┌─────────────────────┐
│ Operations Manager  │
│   (Phone Call)      │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│  Supervisor AI Agent Outage Management System            │
│                                                          │
│  ┌──────────────┐  ┌──────────────────────────────┐     │
│  │   Amazon     │  │  Amazon Q in Connect         │     │
│  │   Connect    │──│  Supervisor AI Agent          │     │
│  │ Contact Flow │  │  (PIN Auth + Outage Mgmt)     │     │
│  └──────────────┘  └──────────┬───────────────────┘     │
│                                │                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  VPC (Private Isolated Subnets)                  │    │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │    │
│  │  │  Auth  │ │ Agent  │ │ Backup │ │Restore │   │    │
│  │  │+Rate   │ │Manager │ │        │ │        │   │    │
│  │  │Limiter │ │+Prompt │ │        │ │        │   │    │
│  │  │        │ │Valid.  │ │        │ │ Tester │   │    │
│  │  └────────┘ └────────┘ └────────┘ └────────┘   │    │
│  │  VPC Endpoints: S3, Secrets Mgr, DynamoDB, Logs │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Amazon   │ │  AWS     │ │ Amazon   │ │ Amazon   │  │
│  │   S3     │ │ Secrets  │ │DynamoDB  │ │CloudWatch│  │
│  │(SSE-KMS) │ │ Manager  │ │PIN Rate  │ │Logs 90d  │  │
│  │ Backups  │ │PIN+Allow │ │Limiting  │ │ Metrics  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌──────────┐ ┌──────────┐                              │
│  │ AWS KMS  │ │ Amazon   │                              │
│  │Customer  │ │  SNS     │                              │
│  │Managed   │ │(Encrypted)│                              │
│  └──────────┘ └──────────┘                              │
└─────────────────────┬────────────────────────────────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │ Production AI Agents│
           │ (Voice/Chat/Email)  │
           └─────────────────────┘
```

### Technology Stack

- **Voice Interface**: Amazon Connect, Amazon Q in Connect
- **Compute**: AWS Lambda (Python 3.12)
- **Storage**: Amazon S3 (backups and audit logs)
- **Secrets**: AWS Secrets Manager
- **Monitoring**: Amazon CloudWatch
- **Infrastructure**: AWS CDK (TypeScript)
- **Network**: Amazon VPC (private isolated subnets, VPC endpoints)
- **Rate Limiting**: Amazon DynamoDB (PIN attempt tracking, auth tokens)
- **Encryption**: AWS KMS (customer-managed keys for S3 and SNS)

### Lambda Functions

1. **Authentication Lambda**: Validates phone numbers and PINs
2. **Agent Manager Lambda**: Orchestrates agent discovery, intent management, prompt generation, and updates
3. **Backup Lambda**: Backs up prompts and intent configurations to S3 before changes
4. **Restore Lambda**: Restores prompts and intent configurations from S3 backups
5. **Tester Lambda**: Validates updated agents through automated testing (including intent-specific tests)

## Project Structure

```
supervisor-ai-agent/
├── cdk/                           # CDK TypeScript infrastructure code
│   ├── bin/
│   │   └── supervisor-ai-agent.ts
│   ├── lib/
│   │   └── supervisor-ai-agent-stack.ts
│   ├── cdk.json
│   └── package.json
├── lambda/                        # Python Lambda functions
│   ├── auth/
│   │   ├── handler.py
│   │   ├── rate_limiter.py
│   │   └── requirements.txt
│   ├── agent_manager/
│   │   ├── handler.py
│   │   ├── prompt_validator.py
│   │   └── requirements.txt
│   ├── backup/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── restore/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── tester/
│   │   ├── handler.py
│   │   └── requirements.txt
│   └── shared/                    # Shared utilities
│       ├── aws_clients.py
│       ├── logging_config.py
│       ├── retry_logic.py
│       └── error_handling.py
│       ├── request_signing.py
├── docs/                          # Documentation
│   ├── deployment/                # Deployment and setup guides
│   ├── architecture/              # System design docs
│   ├── operations/                # Runbooks and monitoring
│   ├── getting-started/           # Setup and configuration
│   └── api/                       # Lambda API reference
├── tests/                         # Unit and property-based tests
│   ├── unit/
│   └── property/
├── .kiro/                         # Kiro spec and steering files
│   ├── specs/
│   │   └── supervisor-ai-agent-outage-management/
│   │       ├── requirements.md
│   │       ├── design.md
│   │       └── tasks.md
│   └── steering/
│       └── supervisor-ai-agent-implementation.md
└── README.md
```

## Prerequisites

### Required Tools

- **AWS CLI**: Version 2.x or later
- **AWS CDK**: Version 2.x or later
- **Node.js**: Version 20.x or later (for CDK)
- **Python**: Version 3.12 (for Lambda functions)
- **Git**: For version control

### AWS Account Requirements

- **AWS Account**: With appropriate permissions
- **AWS Profile**: Configured in `~/.aws/credentials` (e.g., `your-aws-profile`)
- **AWS Region**: `us-east-1` (or your preferred region)
- **Amazon Connect Instance**: Existing instance with Amazon Q in Connect enabled ([setup guide](https://docs.aws.amazon.com/connect/latest/adminguide/amazon-connect-instances.html))
- **Amazon Q in Connect Assistant**: Existing assistant for production AI agents ([enable Q in Connect](https://docs.aws.amazon.com/connect/latest/adminguide/enable-q.html))

### AWS Permissions

The deployment user/role needs permissions for:
- Lambda (create, update, invoke)
- S3 (create bucket, put/get objects)
- Secrets Manager (create secret, get secret value)
- IAM (create roles, attach policies)
- CloudWatch (create log groups, put metrics)
- CDK (CloudFormation stack operations)
- DynamoDB (create table, read/write items)
- KMS (create key, encrypt/decrypt)
- EC2 (create VPC, subnets, security groups, VPC endpoints)

## Installation

> **Security Note**: This repository has been sanitized to remove personal information and sensitive data. Before deployment, you must configure your own AWS credentials, phone numbers, and other parameters. See [CONFIGURATION.md](CONFIGURATION.md) for detailed setup instructions. Never commit sensitive values to version control.

### 1. Clone the Repository

```bash
git clone https://code.aws.dev/proserve/amazon-connect-coe/apgs/streamline-connect-outage-flows-ai-automation.git
cd streamline-connect-outage-flows-ai-automation
```

### 2. Set AWS Credentials

```bash
export AWS_PROFILE=your-aws-profile
export AWS_REGION=us-east-1
```

### 3. Install CDK Dependencies

```bash
cd cdk
npm install
```

### 4. Install Python Dependencies (for local testing)

```bash
cd ../lambda
pip install -r requirements.txt
cd ..
```

**Note:** CDK automatically bundles Python dependencies for Lambda deployment using Docker. Local installation is only needed for running tests.

### 5. Bootstrap CDK (First Time Only)

```bash
cd cdk
cdk bootstrap --profile your-aws-profile --region us-east-1
```

## Deployment

### 1. Configure Parameters

Edit deployment parameters:
- Connect instance ID
- Amazon Q in Connect assistant ID  
- Production agent IDs
- Notification email
- **SupervisorPinSecretArn**: ARN of a pre-created Secrets Manager secret (see below)

**Pre-deployment: Create the supervisor secret**

```bash
aws secretsmanager create-secret \
  --name supervisor-ai-agent-pin \
  --secret-string '{"pin":"YOUR_6_DIGIT_PIN","allowlist":["+1234567890"]}' \
  --profile your-aws-profile --region us-east-1
```

The secret must contain:
- `pin`: 6-digit supervisor PIN
- `allowlist`: JSON array of authorized phone numbers in E.164 format

> **Note**: `supervisorPin` and `supervisorPhoneAllowlist` CDK parameters have been removed. PIN and phone allowlist are now managed entirely through Secrets Manager.

### 2. Deploy CDK Stack

```bash
cd cdk
npm install
cdk bootstrap --profile your-aws-profile --region us-east-1
cdk deploy --profile your-aws-profile --region us-east-1 \
  --parameters ConnectInstanceId=YOUR_CONNECT_INSTANCE_ID \
  --parameters QConnectAssistantId=YOUR_ASSISTANT_ID \
  --parameters ProductionAgentIds=YOUR_PRODUCTION_AGENT_ID \
  --parameters SupervisorPinSecretArn=YOUR_SECRET_ARN \
  --parameters NotificationEmail=your-email@example.com
```

**How to find parameter values:**

```bash
# Connect Instance ID
aws connect list-instances --query 'InstanceSummaryList[*].[Id,InstanceAlias]' --output table

# Q Connect Assistant ID
aws qconnect list-assistants --query 'assistantSummaries[*].[assistantId,name]' --output table

# Secret ARN (from Step 1 output)
aws secretsmanager describe-secret --secret-id supervisor-ai-agent-pin --query 'ARN' --output text
```

**Note**: Deployment takes 2-5 minutes. The command will output Lambda ARNs, S3 bucket name, and Secret ARN needed for manual setup.

### 3. Post-Deploy Manual Setup

After CDK deployment, the Contact Flow is created automatically. The only manual step is configuring the Supervisor AI Agent:

1. **Amazon Q in Connect Supervisor AI Agent**: Follow [Supervisor AI Agent Setup Guide](docs/deployment/supervisor-ai-agent-setup.md)

Use the Lambda ARNs and other outputs from CDK deployment in the manual setup.

### 4. Verify Deployment

After completing all setup, verify the system works end-to-end:

Follow the [Post-Deploy Testing Guide](docs/deployment/post-deploy-testing.md) for step-by-step verification.

## Usage

### Full Outage Mode: Updating AI Agent Prompts

Use this mode when entire services or multiple capabilities are unavailable.

1. **Call the supervisor hotline** from an authorized phone number
2. **Enter your 6-digit PIN** when prompted
3. **Describe the outage** in natural language:
   - "Payment processing is down, estimated recovery in 2 hours"
   - "Email service is unavailable, phone and chat are working"
4. **Review the proposed changes** explained by the Supervisor AI Agent
5. **Confirm the update** when ready
6. **Receive confirmation** with test results

### Intent-Level Mode: Managing Specific Capabilities

Use this mode to selectively disable/enable specific agent capabilities.

#### Listing Agent Capabilities

1. **Call the supervisor hotline** from an authorized phone number
2. **Enter your 6-digit PIN** when prompted
3. **Request capability list**: "What capabilities does the agent have?"
4. **Review the list** of available intents (e.g., check balance, transfer funds, change PIN)

#### Disabling a Specific Capability

1. **Call the supervisor hotline** from an authorized phone number
2. **Enter your 6-digit PIN** when prompted
3. **Request to disable**: "Disable the change card PIN feature"
4. **Review the proposed changes** explained by the Supervisor AI Agent
5. **Confirm the update** when ready
6. **Receive confirmation** with test results showing:
   - Disabled intent properly rejected
   - Other intents still working normally

#### Enabling a Previously Disabled Capability

1. **Call the supervisor hotline** from an authorized phone number
2. **Enter your 6-digit PIN** when prompted
3. **Request to enable**: "Enable the change card PIN feature"
4. **Review the proposed changes** explained by the Supervisor AI Agent
5. **Confirm the update** when ready
6. **Receive confirmation** with test results

### Restoring Normal Operations

#### Full Restoration (All Intents)

1. **Call the supervisor hotline** from an authorized phone number
2. **Enter your 6-digit PIN** when prompted
3. **Request restoration**: "Restore all capabilities to normal" or "Restore the original prompts"
4. **Confirm the restoration** when ready
5. **Receive confirmation** with outage duration

### Example Scenarios

**Scenario 1: Payment System Outage (Full Outage Mode)**
- Supervisor: "Payment processing is down, but account inquiries and transfers are still working"
- System: Updates agent to acknowledge payment outage, highlight available services
- Result: All customers receive consistent outage messaging

**Scenario 2: PIN Change Feature Bug (Intent-Level Mode)**
- Supervisor: "Disable the change card PIN capability"
- System: Updates agent to reject PIN change requests, keeps all other services operational
- Result: Only PIN changes are unavailable, other banking services work normally

**Scenario 3: Partial Service Recovery (Intent-Level Mode)**
- Supervisor: "Enable the change card PIN feature"
- System: Restores PIN change capability while keeping other services unchanged
- Result: PIN changes work again, seamless restoration

## Testing

### Run Unit Tests

```bash
cd tests
pytest unit/ -v
```

### Run Property-Based Tests

```bash
pytest property/ -v --hypothesis-show-statistics
```

### Run All Tests

```bash
pytest -v
```

## Monitoring

### CloudWatch Dashboards

Access CloudWatch dashboards for:
- Authentication attempts and failures
- Prompt update operations
- Test execution results
- Lambda function performance

### CloudWatch Alarms

Configured alarms for:
- High authentication failure rate (>10 failures in 5 minutes)
- Phone spoofing detection (>5 phone validation failures in 5 minutes)
- PIN lockout events (brute-force attempts)
- Unusual authenticated sessions (>3 sessions in 1 hour)
- Prompt update failures (>0 failures)
- Critical test failures (>0 failures)
- Lambda errors (>5% error rate)
- Lambda throttling

### Audit Logs

All operations are logged to:
- **CloudWatch Logs**: Real-time operational logs (90-day retention)
- **S3 Audit Logs**: Long-term audit trail (90-day retention)
  - Prompt updates (full outage mode)
  - Intent disable/enable operations
  - Restore operations
  - All with before/after configurations

## Security

### Authentication

- **Phone Allowlist**: Stored in Secrets Manager (not Lambda environment variables)
- **PIN Verification**: 6-digit PIN validated server-side against Secrets Manager
- **Server-Side Rate Limiting**: DynamoDB tracks PIN attempts per phone number
- **Brute-Force Protection**: Lockout after 3 failed attempts (30-minute cooldown)
- **Auth Tokens**: Successful PIN validation generates a server-side token (15-minute TTL) verified before all mutating operations
- **Prompt Injection Protection**: Server-side PIN enforcement independent of AI agent

### Encryption

- **At Rest**: S3 (SSE-KMS with customer-managed key), Secrets Manager (KMS), DynamoDB (AWS-managed encryption), SNS (KMS)
- **In Transit**: TLS 1.2+ for all AWS API calls
- **Inter-Lambda**: HMAC-SHA256 request signing for all inter-Lambda invocations

### IAM Roles

- **Least Privilege**: Each Lambda function has minimal required permissions
- **Resource-Specific**: IAM policies use specific resource ARNs

### Audit Trail

- All authentication attempts logged
- All prompt updates logged with before/after content
- All intent management operations logged (disable/enable/restore)
- All restore operations logged
- Intent configurations versioned in S3
- Caller phone number recorded for all operations

### Network Isolation

- **VPC**: Auth and Backup Lambdas deployed in private isolated subnets (no internet access). Agent Manager, Restore, and Tester Lambdas run outside VPC (Q Connect has no VPC endpoint).
- **VPC Endpoints**: S3, DynamoDB (gateway); Secrets Manager, CloudWatch Logs, Lambda (interface)
- **Security Groups**: Outbound restricted to VPC endpoints only (port 443)

### Future Security Recommendations

The following enhancements are recommended for production hardening:

- **ANI Validation**: Integrate Amazon Connect's carrier-level Automatic Number Identification (ANI) verification to strengthen phone-based authentication beyond caller ID matching
- **Per-Operator PINs**: Assign unique PINs to each supervisor for individual audit trails and independent revocation
- **TOTP Authentication**: Replace static PINs with time-based one-time passwords (TOTP) to eliminate PIN reuse and long-term compromise risks

See [Security Fixes Status Report](docs/security-fixes-status.md) for details.

## Troubleshooting

### Common Issues

**Authentication Failures**:
- Verify phone number is in E.164 format in allowlist
- Check PIN is correct in Secrets Manager
- Review CloudWatch logs for Authentication Lambda

**Prompt Update Failures**:
- Check Amazon Q in Connect API permissions
- Verify agent ID is correct
- Review CloudWatch logs for Agent Manager Lambda

**Test Failures**:
- Review test query configuration
- Check test results in CloudWatch logs
- Verify agent responses match expected behavior

### Support

For issues or questions:
1. Check CloudWatch logs for error details
2. Review audit logs in S3 for operation history
3. Contact the development team with log excerpts

## Development

### Implementation Guidelines

Before implementing, review `.kiro/steering/supervisor-ai-agent-implementation.md` for:
- AWS configuration (profile, region)
- AWS knowledge validation using MCP tools
- Terminal command timeout handling
- CDK development guidelines
- Testing strategy
- Security requirements

### Spec-Driven Development

This project follows spec-driven development methodology:
- **Requirements**: `.kiro/specs/supervisor-ai-agent-outage-management/requirements.md`
- **Design**: `.kiro/specs/supervisor-ai-agent-outage-management/design.md`
- **Tasks**: `.kiro/specs/supervisor-ai-agent-outage-management/tasks.md`

### Contributing

1. Review the spec files in `.kiro/specs/supervisor-ai-agent-outage-management/`
2. Follow the implementation guidelines in `.kiro/steering/`
3. Write tests for all new functionality (unit + property-based)
4. Ensure all tests pass before submitting changes
5. Update documentation as needed

## Performance

### Target Metrics

- **Workflow Duration**: <2 minutes (95th percentile)
- **Prompt Update Effect**: <5 seconds
- **Voice Conversation Latency**: <3 seconds per exchange
- **Test Execution**: <10 seconds for 8+ test queries

### Scalability

- **Concurrent Supervisor Calls**: Up to 5
- **Production AI Agents**: Up to 10 per Connect instance
- **Customer Conversations**: Thousands concurrent (no impact)

## Cost Optimization

### Serverless Architecture

- **Zero Idle Costs**: Pay only for actual usage
- **Lambda**: Charged per invocation and duration
- **S3**: Lifecycle policies transition old backups to lower-cost storage
- **Secrets Manager**: Single secret with minimal cost

> **Note**: VPC interface endpoints incur ~$7-14/month regardless of usage. This is the primary fixed cost.

### Estimated Monthly Cost

For typical usage (10 outage updates per month):
- Lambda: <$1
- S3: <$1
- Secrets Manager: <$1
- DynamoDB: <$1
- KMS: <$1
- CloudWatch: <$2
- VPC Endpoints: ~$7-14 (interface endpoints)
- **Total**: ~$15-20/month

## Cleanup

To avoid ongoing charges, remove all resources when you're done:

### 1. Destroy CDK Stack

```bash
cd cdk
cdk destroy --profile your-aws-profile --region us-east-1
```

This removes: Lambda functions, S3 bucket (if empty), DynamoDB table, VPC, VPC endpoints, KMS key, SNS topic, CloudWatch alarms, IAM roles.

### 2. Manual Cleanup (not managed by CDK)

```bash
# Delete Secrets Manager secrets
aws secretsmanager delete-secret --secret-id supervisor-ai-agent-pin --force-delete-without-recovery
aws secretsmanager delete-secret --secret-id supervisor-ai-agent-signing-key --force-delete-without-recovery

# Release phone numbers
aws connect release-phone-number --phone-number-id <PHONE_NUMBER_ID>

# Delete Conversational AI bots (via Connect admin console)
# Delete AI Agent and AI Prompt (via Connect admin console)
```

### 3. Verify

```bash
aws cloudformation describe-stacks --stack-name SupervisorAIAgentStack 2>&1 | grep -q "does not exist" && echo "Stack deleted"
```

> **Warning**: The S3 backup bucket has `removalPolicy: RETAIN` and won't be deleted by `cdk destroy`. Delete manually if no longer needed: `aws s3 rb s3://supervisor-ai-agent-backups-ACCOUNT_ID-REGION --force`

## Roadmap

### Phase 1 (Current)
- ✅ Core functionality (authentication, backup, update, restore, testing)
- ✅ Full outage mode (complete prompt updates)
- ✅ Intent-level mode (selective capability management)
- ✅ Intent discovery and status tracking
- ✅ CDK infrastructure deployment
- ✅ Manual setup documentation

### Phase 2 (Future)
- [ ] Multi-region support
- [ ] Scheduled prompt updates
- [ ] Advanced testing scenarios
- [ ] Integration with incident management systems
- [ ] Intent dependency management (disable dependent intents automatically)

### Phase 3 (Future)
- [ ] Web-based management console
- [ ] Prompt version history and comparison
- [ ] Intent usage analytics
- [ ] A/B testing for prompt variations
- [ ] Analytics dashboard for prompt effectiveness

## Documentation

Comprehensive documentation is available in the `docs/` directory, organized by topic:

### 📚 [Complete Documentation Index](docs/README.md)

Visit the [Documentation Index](docs/README.md) for a complete guide to all available documentation.

### Quick Links

#### Getting Started
- [Project Setup Guide](docs/getting-started/project-setup.md) - Prerequisites, installation, and initial configuration
- [Configuration Guide](docs/getting-started/configuration.md) - Environment variables and system parameters

#### Architecture
- [System Architecture](docs/architecture/system-architecture.md) - Complete system design and components
- [Supervisor AI Agent System Prompt](docs/architecture/supervisor-ai-agent-system-prompt.md) - AI agent configuration

#### Deployment
- [CDK Deployment Guide](docs/deployment/cdk-deployment.md) - Step-by-step deployment instructions
- [CDK Integration Guide](docs/deployment/cdk-integration-guide.md) - Integrating CDK outputs with manual resources
- [Manual Setup Guides](docs/deployment/) - Connect and Q Connect configuration

#### Operations
- [Operations Runbook](docs/operations/operations-runbook.md) - Day-to-day operations, monitoring, and troubleshooting
- [Troubleshooting Guide](docs/operations/troubleshooting.md) - Common issues and solutions from deployment and testing

#### Development
- [Git Workflow](docs/development/git-workflow.md) - Branching strategy and commit guidelines
- [Sanitization Summary](docs/development/sanitization-summary.md) - Data sanitization practices

#### API Reference
- [Lambda Functions API](docs/api/lambda-functions.md) - Complete API reference for all Lambda functions

### Documentation Structure

```
docs/
├── README.md                          # Documentation index
├── getting-started/                   # Installation and setup
│   ├── project-setup.md
│   └── configuration.md
├── architecture/                      # System design
│   ├── system-architecture.md
│   └── supervisor-ai-agent-system-prompt.md
├── deployment/                        # Deployment guides
│   ├── cdk-deployment.md
│   ├── cdk-integration-guide.md
│   ├── cdk-parameters.md
│   ├── cdk-stack-outputs.md
│   └── [manual setup guides]
├── operations/                        # Operations and monitoring
│   └── operations-runbook.md
├── development/                       # Contributing and development
│   ├── git-workflow.md
│   └── sanitization-summary.md
└── api/                              # API reference
    └── lambda-functions.md
```

## License

Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

## Authors

AWS ProServe Amazon Connect Center of Excellence (CoE)

## Acknowledgments

- Amazon Connect team for voice infrastructure
- Amazon Q in Connect team for AI agent capabilities
- AWS Lambda team for serverless compute
- AWS CDK team for infrastructure as code

## Project Status

**Status**: Active Development

This project is under active development. The core functionality is complete and ready for deployment. Future enhancements are planned based on customer feedback and evolving requirements.
