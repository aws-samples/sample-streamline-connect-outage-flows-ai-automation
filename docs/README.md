# Supervisor AI Agent Documentation

Welcome to the Supervisor AI Agent for Amazon Connect Outage Management documentation. This guide provides comprehensive information about the system architecture, deployment, operations, and development.

---

## Documentation Structure

### 🚀 Getting Started

Start here if you're new to the project or setting up the system for the first time.

- **[Project Setup Guide](getting-started/project-setup.md)** - Prerequisites, installation, and initial configuration
- **[Configuration Guide](getting-started/configuration.md)** - Environment variables, AWS credentials, and system parameters

### 🏗️ Architecture

Understand the system design, components, and how they interact.

- **[System Architecture](architecture/system-architecture.md)** - Complete system design, components, data flows, and design decisions
- **[Supervisor AI Agent System Prompt](architecture/supervisor-ai-agent-system-prompt.md)** - AI agent configuration and conversation design

### 📦 Deployment

Deploy the system to your AWS environment using AWS CDK.

- **[CDK Deployment Guide](deployment/cdk-deployment.md)** - Step-by-step deployment instructions
- **[CDK Parameters](deployment/cdk-parameters.md)** - Configuration parameters for CDK deployment
- **[CDK Stack Outputs](deployment/cdk-stack-outputs.md)** - Understanding and using CDK outputs
- **[CDK Integration Guide](deployment/cdk-integration-guide.md)** - Integrating CDK outputs with manual resources

#### Manual Setup Guides

- **[Supervisor AI Agent Setup](deployment/supervisor-ai-agent-setup.md)** - Configuring the Supervisor AI Agent in Amazon Q in Connect (only manual post-deploy step)
- **[Customer Contact Flow Setup](deployment/customer-contact-flow-setup.md)** - Setting up the customer-facing contact flow and Production AI Agent
- **[Contact Flow Configuration](deployment/contact-flow-configuration.md)** - Understanding the CDK-deployed contact flow
- **[Intent Management Workflows](deployment/intent-management-workflows.md)** - Setting up intent-level management capabilities

#### Testing

- **[Post-Deploy Testing Guide](deployment/post-deploy-testing.md)** - Step-by-step verification after deployment

### 🔧 Operations

Day-to-day operations, monitoring, and troubleshooting.

- **[Operations Runbook](operations/operations-runbook.md)** - Complete operational guide including:
  - Using the supervisor hotline
  - Managing full outages
  - Managing intent-level outages
  - Monitoring system health
  - Troubleshooting common issues
  - Incident response procedures

### 💻 Development

Contributing to the project and understanding the codebase.

- **[Git Workflow](development/git-workflow.md)** - Branching strategy, commit guidelines, and pull request process
- **[Sanitization Summary](development/sanitization-summary.md)** - Data sanitization and security practices

### 📚 API Reference

Technical reference for Lambda functions and their interfaces.

- **[Lambda Functions API](api/lambda-functions.md)** - Complete API reference for all Lambda functions:
  - Authentication Lambda
  - Agent Manager Lambda
  - Backup Lambda
  - Restore Lambda
  - Tester Lambda

### 📋 Specifications

Detailed requirements, design documents, and implementation tasks.

Located in `.kiro/specs/supervisor-ai-agent-outage-management/`:

- **[Requirements Document](../.kiro/specs/supervisor-ai-agent-outage-management/requirements.md)** - Complete functional and non-functional requirements
- **[Design Document](../.kiro/specs/supervisor-ai-agent-outage-management/design.md)** - Detailed system design and architecture decisions
- **[Implementation Tasks](../.kiro/specs/supervisor-ai-agent-outage-management/tasks.md)** - Task breakdown and implementation progress

---

## Quick Links

### For New Users

1. Start with [Project Setup Guide](getting-started/project-setup.md)
2. Review [System Architecture](architecture/system-architecture.md)
3. Follow [CDK Deployment Guide](deployment/cdk-deployment.md)
4. Complete manual setup guides in the [Deployment](#deployment) section
5. Read [Operations Runbook](operations/operations-runbook.md)

### For Operators

- **Using the System**: [Operations Runbook](operations/operations-runbook.md)
- **Troubleshooting**: [Operations Runbook - Troubleshooting Section](operations/operations-runbook.md#troubleshooting)
- **Monitoring**: [Operations Runbook - Monitoring Section](operations/operations-runbook.md#monitoring)

### For Developers

- **Contributing**: [Git Workflow](development/git-workflow.md)
- **API Reference**: [Lambda Functions API](api/lambda-functions.md)
- **Architecture**: [System Architecture](architecture/system-architecture.md)
- **Requirements**: [Requirements Document](../.kiro/specs/supervisor-ai-agent-outage-management/requirements.md)

### For Administrators

- **Deployment**: [CDK Deployment Guide](deployment/cdk-deployment.md)
- **Configuration**: [Configuration Guide](getting-started/configuration.md)
- **Security**: [Sanitization Summary](development/sanitization-summary.md)

---

## Recommended Reading Order

### First-Time Setup

1. [Project Setup Guide](getting-started/project-setup.md)
2. [Configuration Guide](getting-started/configuration.md)
3. [System Architecture](architecture/system-architecture.md)
4. [CDK Deployment Guide](deployment/cdk-deployment.md)
5. Manual setup guides (in order):
   - [Contact Flow Configuration](deployment/contact-flow-configuration.md)
   - [Supervisor AI Agent Setup](deployment/supervisor-ai-agent-setup.md)
   - [Customer Contact Flow Setup](deployment/customer-contact-flow-setup.md)
   - [Intent Management Workflows](deployment/intent-management-workflows.md)
6. [Operations Runbook](operations/operations-runbook.md)

### Understanding the System

1. [System Architecture](architecture/system-architecture.md)
2. [Supervisor AI Agent System Prompt](architecture/supervisor-ai-agent-system-prompt.md)
3. [Lambda Functions API](api/lambda-functions.md)
4. [Requirements Document](../.kiro/specs/supervisor-ai-agent-outage-management/requirements.md)
5. [Design Document](../.kiro/specs/supervisor-ai-agent-outage-management/design.md)

### Day-to-Day Operations

1. [Operations Runbook](operations/operations-runbook.md) - Your primary reference
2. [Lambda Functions API](api/lambda-functions.md) - For understanding system behavior
3. [System Architecture](architecture/system-architecture.md) - For troubleshooting

---

## System Overview

The Supervisor AI Agent for Amazon Connect Outage Management is a phone-based conversational interface that enables operations managers to update Amazon Connect AI agent prompts during service outages. The system reduces outage response time from 15-20 minutes to under 2 minutes.

### Key Features

- **Multi-layer Authentication**: Phone allowlist + PIN verification
- **Natural Language Interface**: Describe outages conversationally
- **Two Operational Modes**:
  - **Full Outage Mode**: Update entire agent behavior for service-wide outages
  - **Intent-Level Mode**: Selectively disable/enable specific capabilities
- **Automated Backup**: Always backs up before changes
- **Comprehensive Testing**: Validates updates before confirmation
- **Automatic Rollback**: Restores previous state if critical tests fail
- **Complete Audit Trail**: All actions logged for compliance

### Technology Stack

- **Voice Interface**: Amazon Connect, Amazon Lex V2, Amazon Q in Connect
- **Compute**: AWS Lambda (Python 3.12)
- **Storage**: Amazon S3 (backups, audit logs, intent configurations)
- **Secrets**: AWS Secrets Manager
- **Monitoring**: Amazon CloudWatch
- **Infrastructure**: AWS CDK (TypeScript)

---

## Support and Feedback

For questions, issues, or feedback:

1. Review the [Operations Runbook](operations/operations-runbook.md) for troubleshooting
2. Check the [Lambda Functions API](api/lambda-functions.md) for technical details
3. Consult the [System Architecture](architecture/system-architecture.md) for design decisions

---

## Navigation Tips

- Each document includes a "Back to Documentation Index" link at the top
- Use your browser's back button to return to previous pages
- Bookmark this page for quick access to all documentation
- Use Ctrl+F (Cmd+F on Mac) to search within documents

---

**Last Updated**: April 19, 2026

[Main Project README](../README.md)
