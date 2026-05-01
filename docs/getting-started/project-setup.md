# Supervisor AI Agent for Amazon Connect Outage Management - Setup Guide

[← Back to Documentation Index](../README.md) | [Configuration](configuration.md) | [Architecture](../architecture/system-architecture.md) | [Deployment](../deployment/cdk-deployment.md)

---

## Overview

This project implements a phone-based conversational interface that enables operations managers to update Amazon Connect AI agent prompts during service outages through natural language conversation.

## Architecture

- **Voice Interface**: Amazon Connect, Amazon Lex V2, Amazon Q in Connect
- **Compute**: AWS Lambda (Python 3.13)
- **Storage**: Amazon S3 (backups, intent configs, audit logs)
- **Secrets**: AWS Secrets Manager
- **Monitoring**: Amazon CloudWatch
- **Infrastructure**: AWS CDK (TypeScript)

## Prerequisites

### Required Software

- **Python 3.13** (or 3.12+)
- **Node.js 20.x** (for AWS CDK)
- **AWS CLI** configured with appropriate credentials
- **AWS CDK CLI**: `npm install -g aws-cdk`

### AWS Configuration

This project uses:
- **AWS Profile**: Configured in `~/.aws/credentials` (e.g., `your-aws-profile`)
- **AWS Region**: `us-east-1` (or your preferred region)

Set environment variables:
```bash
export AWS_PROFILE=your-aws-profile
export AWS_REGION=us-east-1
```

## Project Structure

```
.
├── cdk/                          # AWS CDK infrastructure code (TypeScript)
│   ├── bin/
│   │   └── cdk.ts               # CDK app entry point
│   ├── lib/
│   │   └── supervisor-ai-agent-stack.ts  # Main stack definition
│   ├── cdk.json                 # CDK configuration
│   └── package.json             # Node.js dependencies
├── lambda/                       # Python Lambda functions
│   ├── auth/                    # Authentication Lambda
│   ├── agent_manager/           # Agent Manager Lambda
│   ├── backup/                  # Backup Lambda
│   ├── restore/                 # Restore Lambda
│   ├── tester/                  # Tester Lambda
│   ├── shared/                  # Shared utilities
│   └── requirements.txt         # Python dependencies
├── docs/                        # Documentation
│   └── manual-setup/            # Manual resource setup guides
└── venv/                        # Python virtual environment
```

## Setup Instructions

### 1. Python Virtual Environment

The virtual environment is already created. Activate it:

```bash
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate     # On Windows
```

Verify activation:
```bash
which python  # Should point to venv/bin/python
python --version  # Should show Python 3.13.x
```

### 2. Install Python Dependencies (for local testing)

```bash
pip install -r lambda/requirements.txt
```

**Note:** These dependencies are only needed for local testing. CDK automatically bundles dependencies for Lambda deployment using Docker.

### 3. Install CDK Dependencies

```bash
cd cdk
npm install
cd ..
```

### 4. Bootstrap CDK (First Time Only)

If you haven't used CDK in this AWS account/region before:

```bash
cdk bootstrap --profile your-aws-profile --region us-east-1
```

### 5. Configure CDK Parameters

The stack accepts the following parameters (will be prompted during deployment):

- **ConnectInstanceId**: Your Amazon Connect instance ID
- **QConnectAssistantId**: Your Amazon Q in Connect assistant ID
- **ProductionAgentIds**: Comma-separated list of production AI agent IDs
- **SupervisorPhoneAllowlist**: Comma-separated list of authorized phone numbers (E.164 format)
- **SupervisorPin**: Six-digit PIN for authentication
- **NotificationEmail**: Email for CloudWatch alarm notifications

## Development Workflow

### Running Tests

```bash
# Activate virtual environment first
source venv/bin/activate

# Run all tests
pytest lambda/tests/ -v

# Run property-based tests with statistics
pytest lambda/tests/ -v -k "property" --hypothesis-show-statistics

# Run with coverage
pytest lambda/tests/ --cov=lambda --cov-report=html
```

### CDK Commands

```bash
# Synthesize CloudFormation template
cdk synth --profile your-aws-profile --region us-east-1

# View differences
cdk diff --profile your-aws-profile --region us-east-1

# Deploy stack
cdk deploy --profile your-aws-profile --region us-east-1

# Destroy stack
cdk destroy --profile your-aws-profile --region us-east-1
```

### Linting and Type Checking

```bash
# Python type checking
mypy lambda/

# Python linting
pylint lambda/

# TypeScript linting
cd cdk && npm run lint
```

## Implementation Tasks

The implementation follows the task list in `.kiro/specs/supervisor-ai-agent-outage-management/tasks.md`:

1. ✅ Set up CDK project structure
2. Set up shared Python utilities
3. Implement Authentication Lambda
4. Implement Backup Lambda
5. Implement Tester Lambda
6. Implement Agent Manager Lambda
7. Implement Restore Lambda
8. Implement Supervisor AI Agent configuration
9. Implement Intent Management
10. Create CDK infrastructure stack
11. Create manual setup documentation
12. Testing and validation

## Manual Setup Required

The following AWS resources require manual configuration (documented in `docs/manual-setup/`):

1. **Amazon Lex V2 PIN Bot**: For PIN authentication
2. **Amazon Connect Contact Flow**: For call routing and authentication
3. **Amazon Q in Connect Supervisor AI Agent**: For natural language conversation

CDK outputs provide integration points (Lambda ARNs, S3 bucket names, etc.) for these manual resources.

## Security Considerations

- Supervisor PIN stored in AWS Secrets Manager with KMS encryption
- All S3 data encrypted at rest with SSE-S3
- IAM roles follow least privilege principle
- Phone number allowlist for first-factor authentication
- All API calls use TLS 1.2+
- Comprehensive audit logging to S3

## Monitoring

- CloudWatch Logs for all Lambda functions (30-day retention)
- CloudWatch Metrics for authentication, updates, tests
- CloudWatch Alarms for failures and performance issues
- SNS notifications for critical alerts

## Support

For issues or questions:
1. Check CloudWatch Logs for Lambda function errors
2. Review audit logs in S3 for operation history
3. Consult the design document: `.kiro/specs/supervisor-ai-agent-outage-management/design.md`
4. Review requirements: `.kiro/specs/supervisor-ai-agent-outage-management/requirements.md`

## License

[Add your license information here]
