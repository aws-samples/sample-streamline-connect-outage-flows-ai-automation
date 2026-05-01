# Architecture Documentation: Supervisor AI Agent for Amazon Connect Outage Management

[← Back to Documentation Index](../README.md) | [Getting Started](../getting-started/project-setup.md) | [Deployment](../deployment/cdk-deployment.md) | [Operations](../operations/operations-runbook.md)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [System Architecture](#system-architecture)
4. [Component Architecture](#component-architecture)
5. [Data Flow Diagrams](#data-flow-diagrams)
6. [Security Architecture](#security-architecture)
7. [Error Handling Patterns](#error-handling-patterns)
8. [Scalability and Performance](#scalability-and-performance)
9. [Deployment Architecture](#deployment-architecture)
10. [Integration Points](#integration-points)

---

## System Overview

The Supervisor AI Agent for Amazon Connect Outage Management is a serverless, event-driven system that enables operations managers to update AI agent prompts during service outages through natural language phone conversations.

### Key Characteristics

- **Serverless**: Zero idle costs, automatic scaling
- **Event-Driven**: Triggered by phone calls and Lambda invocations
- **Multi-Layer Security**: Phone allowlist + PIN authentication
- **Dual Operational Modes**: Full outage updates and intent-level management
- **Automated Testing**: Validates all updates before confirmation
- **Comprehensive Audit**: All operations logged to S3 and CloudWatch

### Business Context

**Problem**: During service outages, updating AI agent prompts manually takes 15-20 minutes, requiring AWS Console navigation during high-stress situations.

**Solution**: Phone-based natural language interface reduces response time to under 2 minutes with automated backup, testing, and deployment.

**Impact**: 90% reduction in outage response time, 100% backup success rate, comprehensive audit trail.

---

## Architecture Principles

### 1. Serverless-First

All compute uses AWS Lambda with managed services (Connect, Lex, Q Connect, S3, Secrets Manager, CloudWatch) for:
- Zero idle costs (pay only for actual usage)
- Automatic scaling (no capacity planning)
- High availability (multi-AZ by default)
- Reduced operational overhead (no server management)

### 2. Defense in Depth

Multiple security layers protect the system:
- **Layer 1**: Phone number allowlist (network-level)
- **Layer 2**: PIN authentication (credential-level)
- **Layer 3**: IAM roles with least privilege (resource-level)
- **Layer 4**: Encryption at rest and in transit (data-level)
- **Layer 5**: Comprehensive audit logging (detection-level)

### 3. Fail-Safe Operations

System designed to fail safely:
- Always backup before changes
- Automated testing before confirmation
- Automatic rollback on critical test failures
- Graceful degradation for non-critical failures
- Manual override capabilities for emergencies

### 4. Immutable Infrastructure

Infrastructure as code with versioned resources:
- CDK for repeatable deployments
- AI Prompt versions (immutable, versioned)
- S3 versioning for backups and configurations
- CloudFormation change sets for safe updates

### 5. Observable by Design

Comprehensive observability built-in:
- Structured JSON logging to CloudWatch
- Custom metrics for key operations
- Audit logs to S3 for compliance
- CloudWatch alarms for proactive monitoring
- Distributed tracing for troubleshooting

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        External Layer                            │
│  ┌──────────────────┐                                           │
│  │ Operations       │  Phone Call                               │
│  │ Manager          │────────────┐                              │
│  └──────────────────┘            │                              │
└──────────────────────────────────┼──────────────────────────────┘
                                   │
┌──────────────────────────────────┼──────────────────────────────┐
│                    Voice Interface Layer                         │
│                                   ▼                              │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ Amazon Connect Contact Flow                            │    │
│  │ - Phone number validation                              │    │
│  │ - Call recording                                       │    │
│  │ - Contact Lens analytics                               │    │
│  └───────┬────────────────────────────────────┬───────────┘    │
│          │                                     │                │
│          ▼                                     ▼                │
│  ┌──────────────┐                    ┌──────────────────┐     │
│  │ Amazon Lex   │                    │ Conversational   │     │
│  │ PIN Bot      │                    │ AI Bot (Lex V2)  │     │
│  │              │                    │ QInConnectIntent  │     │
│  └──────┬───────┘                    └────────┬─────────┘     │
└─────────┼──────────────────────────────────────┼───────────────┘
          │                                      │
┌─────────┼──────────────────────────────────────┼───────────────┐
│         │           AI Agent Layer             │               │
│         │                                      ▼               │
│         │                            ┌──────────────────┐     │
│         │                            │ Amazon Q Connect  │     │
│         │                            │ Orchestration AI  │     │
│         │                            │ Agent (MCP Tools) │     │
│         │                            └────────┬─────────┘     │
│         │                                     │                │
│         │              ┌──────────────────────┼──────────┐    │
│         │              │   Flow Module Tools (MCP)       │    │
│         │              │  ┌─────────┐ ┌─────────┐       │    │
│         │              │  │list_    │ │get_agent│       │    │
│         │              │  │agents   │ │_config  │ ...×8 │    │
│         │              │  └─────────┘ └─────────┘       │    │
│         │              └──────────────────────┬──────────┘    │
└─────────┼──────────────────────────────────────┼───────────────┘
          │                                      │
┌─────────┼──────────────────────────────────────┼───────────────┐
│         │         Business Logic Layer         │               │
│         ▼                                      ▼               │
│  ┌──────────────┐                    ┌──────────────────┐    │
│  │ Auth Lambda  │                    │ Agent Manager    │    │
│  │              │                    │ Lambda           │    │
│  └──────────────┘                    └────────┬─────────┘    │
│                                               │               │
│                                    ┌──────────┼──────────┐   │
│                                    ▼          ▼          ▼   │
│                            ┌────────┐  ┌────────┐  ┌────────┐│
│                            │Backup  │  │Restore │  │Tester  ││
│                            │Lambda  │  │Lambda  │  │Lambda  ││
│                            └────────┘  └────────┘  └────────┘│
└────────────────────────────────┬───────────────────────────────┘
                                 │
┌────────────────────────────────┼───────────────────────────────┐
│              Data & Services Layer                              │
│                                 ▼                               │
│  ┌──────────┐  ┌────────────┐  ┌──────────────┐  ┌─────────┐│
│  │ Amazon   │  │   AWS      │  │   Amazon     │  │ Amazon  ││
│  │ S3       │  │  Secrets   │  │  CloudWatch  │  │ Q in    ││
│  │          │  │  Manager   │  │              │  │ Connect ││
│  │ Backups  │  │            │  │ Logs/Metrics │  │ APIs    ││
│  │ Intents  │  │            │  │              │  │         ││
│  │ Audit    │  │            │  │              │  │         ││
│  └──────────┘  └────────────┘  └──────────────┘  └─────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

**External Layer**:
- Operations managers with authorized phone numbers
- Initiates phone calls to supervisor hotline

**Voice Interface Layer**:
- Amazon Connect: Call routing and orchestration
- Amazon Lex PIN Bot: PIN collection and validation
- Conversational AI Bot: Routes voice to Q Connect AI agent via `AMAZON.QInConnectIntent`

**AI Agent Layer**:
- Amazon Q Connect Orchestration AI Agent: Multi-turn conversation with autonomous tool invocation
- Flow Module Tools (MCP): 8 tool modules that invoke Lambda functions mid-conversation without ending the call
- Return to Control: `Complete` tool signals conversation end, returns control to contact flow

**Business Logic Layer**:
- Authentication Lambda: Phone and PIN validation
- Agent Manager Lambda: Orchestrates all agent operations (list, get config, intents, disable/enable, update prompt)
- Backup Lambda: Creates backups before changes
- Restore Lambda: Restores from backups
- Tester Lambda: Validates updates with automated tests

**Data & Services Layer**:
- Amazon S3: Persistent storage for backups, intents, audit logs
- AWS Secrets Manager: Secure PIN storage
- Amazon CloudWatch: Logging and monitoring
- Amazon Q in Connect APIs: AI agent management

---

## Component Architecture

### Authentication Lambda

**Purpose**: Validates caller identity through phone allowlist and PIN verification

**Architecture**:
```
┌─────────────────────────────────────────────────────┐
│           Authentication Lambda                      │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │ Handler (handler.py)                         │  │
│  │ - Phone validation                           │  │
│  │ - PIN validation (Lex fulfillment)          │  │
│  │ - Retry tracking                             │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                    │
│  ┌──────────────▼───────────────────────────────┐  │
│  │ Shared Utilities                             │  │
│  │ - AWS clients (Secrets Manager)             │  │
│  │ - Logging (structured JSON)                 │  │
│  │ - Error handling                             │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
   ┌──────────┐        ┌──────────────┐
   │ Secrets  │        │  CloudWatch  │
   │ Manager  │        │  Logs        │
   └──────────┘        └──────────────┘
```

**Key Design Decisions**:
- Uses Lambda extension for Secrets Manager (caching, reduced latency)
- Stateless design (retry count in Lex session attributes)
- Structured logging for audit trail
- Fail-closed security (deny by default)

### Agent Manager Lambda

**Purpose**: Orchestrates all AI agent management operations

**Architecture**:
```
┌──────────────────────────────────────────────────────────────┐
│              Agent Manager Lambda                             │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Handler (handler.py)                                   │ │
│  │ - Operation routing                                    │ │
│  │ - Request validation                                   │ │
│  │ - Response formatting                                  │ │
│  └──────────────┬─────────────────────────────────────────┘ │
│                 │                                             │
│  ┌──────────────▼─────────────────────────────────────────┐ │
│  │ Operations                                             │ │
│  │ - list_agents                                          │ │
│  │ - get_agent                                            │ │
│  │ - list_intents                                         │ │
│  │ - disable_intent / enable_intent                       │ │
│  │ - restore_all_intents                                  │ │
│  │ - update_agent (full outage)                           │ │
│  └──────────────┬─────────────────────────────────────────┘ │
│                 │                                             │
│  ┌──────────────▼─────────────────────────────────────────┐ │
│  │ Prompt Generator                                       │ │
│  │ - Analyze current prompt                               │ │
│  │ - Generate outage instructions                         │ │
│  │ - Generate intent disable/enable instructions          │ │
│  │ - Maintain agent personality                           │ │
│  └──────────────┬─────────────────────────────────────────┘ │
│                 │                                             │
│  ┌──────────────▼─────────────────────────────────────────┐ │
│  │ Intent Manager                                         │ │
│  │ - Load Intent_Configuration from S3                    │ │
│  │ - Update intent status                                 │ │
│  │ - Store Intent_Configuration to S3                     │ │
│  └──────────────┬─────────────────────────────────────────┘ │
│                 │                                             │
│  ┌──────────────▼─────────────────────────────────────────┐ │
│  │ Workflow Orchestrator                                  │ │
│  │ - Coordinate backup (invoke Backup Lambda)             │ │
│  │ - Create AI Prompt version                             │ │
│  │ - Update AI Agent configuration                        │ │
│  │ - Coordinate testing (invoke Tester Lambda)            │ │
│  │ - Handle rollback on failures                          │ │
│  └──────────────┬─────────────────────────────────────────┘ │
│                 │                                             │
│  ┌──────────────▼─────────────────────────────────────────┐ │
│  │ Shared Utilities                                       │ │
│  │ - AWS clients (Q Connect, Lambda, S3)                  │ │
│  │ - Retry logic with exponential backoff                 │ │
│  │ - Error translation                                    │ │
│  │ - Audit logging                                        │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**Key Design Decisions**:
- Operation-based routing for extensibility
- Separate prompt generation logic for testability
- Intent management as abstraction layer over AI Prompts
- Workflow orchestration with automatic rollback
- Retry logic for transient API failures

### Backup Lambda

**Purpose**: Creates immutable backups before any changes

**Architecture**:
```
┌─────────────────────────────────────────────────────┐
│              Backup Lambda                           │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │ Handler (handler.py)                         │  │
│  │ - Receive agent configuration                │  │
│  │ - Build backup object                        │  │
│  │ - Generate S3 key                            │  │
│  │ - Store to S3                                │  │
│  │ - Verify storage                             │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                    │
│  ┌──────────────▼───────────────────────────────┐  │
│  │ Backup Object Builder                        │  │
│  │ - Timestamp                                  │  │
│  │ - Agent metadata                             │  │
│  │ - Full AI Agent configuration                │  │
│  │ - Current AI Prompt ID and text              │  │
│  │ - Intent_Configuration (if exists)           │  │
│  │ - Caller information                         │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                    │
│  ┌──────────────▼───────────────────────────────┐  │
│  │ S3 Storage                                   │  │
│  │ - Key: backups/{agent-id}/{timestamp}.json  │  │
│  │ - Encryption: SSE-KMS (customer-managed key)    │  │
│  │ - Versioning: Enabled                        │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Key Design Decisions**:
- Immutable backups (never modified after creation)
- Timestamped keys for chronological ordering
- Complete configuration capture (not just prompt text)
- Verification before returning success
- S3 versioning as additional safety layer

### Restore Lambda

**Purpose**: Restores AI agents from S3 backups

**Architecture**:
```
┌─────────────────────────────────────────────────────┐
│              Restore Lambda                          │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │ Handler (handler.py)                         │  │
│  │ - List backups for agent                     │  │
│  │ - Identify most recent backup                │  │
│  │ - Retrieve backup object                     │  │
│  │ - Extract configuration                      │  │
│  │ - Coordinate restoration                     │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                    │
│  ┌──────────────▼───────────────────────────────┐  │
│  │ Backup Selector                              │  │
│  │ - List S3 objects with prefix                │  │
│  │ - Sort by timestamp descending               │  │
│  │ - Select most recent                         │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                    │
│  ┌──────────────▼───────────────────────────────┐  │
│  │ Restoration Orchestrator                     │  │
│  │ - Parse backup JSON                          │  │
│  │ - Extract original prompt text               │  │
│  │ - Invoke Agent Manager for update            │  │
│  │ - Invoke Tester for validation               │  │
│  │ - Calculate outage duration                  │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Key Design Decisions**:
- Automatic selection of most recent backup
- Delegates to Agent Manager for actual update
- Calculates outage duration for reporting
- Validates restoration with automated tests

### Tester Lambda

**Purpose**: Validates AI agent updates through automated testing

**Architecture**:
```
┌─────────────────────────────────────────────────────┐
│              Tester Lambda                           │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │ Handler (handler.py)                         │  │
│  │ - Load test configuration                    │  │
│  │ - Execute test queries                       │  │
│  │ - Evaluate responses                         │  │
│  │ - Generate test report                       │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                    │
│  ┌──────────────▼───────────────────────────────┐  │
│  │ Test Configuration Loader                    │  │
│  │ - Load from environment variable             │  │
│  │ - Load from S3 (per-agent or global)        │  │
│  │ - Validate structure                         │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                    │
│  ┌──────────────▼───────────────────────────────┐  │
│  │ Test Executor                                │  │
│  │ - Create Q Connect session                   │  │
│  │ - Execute each test query                    │  │
│  │ - Collect responses                          │  │
│  │ - Handle timeouts and errors                 │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                    │
│  ┌──────────────▼───────────────────────────────┐  │
│  │ Response Evaluator                           │  │
│  │ - SHOULD_EXPLAIN_UNAVAILABLE                 │  │
│  │ - SHOULD_HANDLE_NORMALLY                     │  │
│  │ - SHOULD_OFFER_ALTERNATIVE                   │  │
│  │ - Keyword matching                           │  │
│  │ - Critical failure detection                 │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                    │
│  ┌──────────────▼───────────────────────────────┐  │
│  │ Test Report Generator                        │  │
│  │ - Total tests, passed, failed                │  │
│  │ - Critical failures                          │  │
│  │ - Sample responses                           │  │
│  │ - Per-intent results (for intent tests)     │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Key Design Decisions**:
- Configurable test queries (environment or S3)
- Keyword-based evaluation (simple, reliable)
- Critical failure detection triggers rollback
- Intent-specific testing for intent management
- Sample responses included in report

---

## Data Flow Diagrams

### Full Outage Update Workflow

```
Operations Manager          Contact Flow          Auth Lambda          Supervisor AI Agent          Agent Manager          Backup Lambda          Tester Lambda          Production Agent
       │                         │                      │                         │                         │                      │                      │                      │
       │──Call Hotline──────────>│                      │                         │                         │                      │                      │                      │
       │                         │                      │                         │                         │                      │                      │                      │
       │                         │──Validate Phone─────>│                         │                         │                      │                      │                      │
       │                         │<─Authorized──────────│                         │                         │                      │                      │                      │
       │                         │                      │                         │                         │                      │                      │                      │
       │<──Prompt for PIN────────│                      │                         │                         │                      │                      │                      │
       │──Enter PIN─────────────>│                      │                         │                         │                      │                      │                      │
       │                         │──Validate PIN───────>│                         │                         │                      │                      │                      │
       │                         │<─Authenticated───────│                         │                         │                      │                      │                      │
       │                         │                      │                         │                         │                      │                      │                      │
       │<──Connected to AI───────│                      │                         │                         │                      │                      │                      │
       │<──Greeting──────────────┼──────────────────────┼─────────────────────────│                         │                      │                      │                      │
       │──Describe Outage───────>│──────────────────────┼─────────────────────────>│                         │                      │                      │                      │
       │<──Confirm Understanding─┼──────────────────────┼─────────────────────────│                         │                      │                      │                      │
       │──Confirm Update────────>│──────────────────────┼─────────────────────────>│──update_agent──────────>│                      │                      │                      │
       │                         │                      │                         │                         │──backup_agent───────>│                      │                      │
       │                         │                      │                         │                         │<─Backup Success──────│                      │                      │
       │                         │                      │                         │                         │                      │                      │                      │
       │                         │                      │                         │                         │──Generate Prompt─────│                      │                      │
       │                         │                      │                         │                         │──Create AI Prompt────│                      │                      │
       │                         │                      │                         │                         │──Update AI Agent─────│                      │                      │
       │                         │                      │                         │                         │──Set PUBLISHED───────│                      │                      │
       │                         │                      │                         │                         │                      │                      │                      │
       │                         │                      │                         │                         │──test_agent─────────┼─────────────────────>│                      │
       │                         │                      │                         │                         │                      │──Execute Tests──────>│                      │
       │                         │                      │                         │                         │                      │<─Agent Responses─────│                      │
       │                         │                      │                         │                         │<─Test Results────────┼──────────────────────│                      │
       │                         │                      │                         │                         │                      │                      │                      │
       │                         │                      │                         │<─Update Success─────────│                      │                      │                      │
       │<──Confirmation + Results┼──────────────────────┼─────────────────────────│                         │                      │                      │                      │
       │                         │                      │                         │                         │                      │                      │                      │
```

### Intent-Level Management Workflow

```
Operations Manager     Supervisor AI Agent     Agent Manager     S3 (Intent Config)     Backup Lambda     Tester Lambda     Production Agent
       │                      │                      │                    │                    │                 │                   │
       │──"Disable PIN"──────>│                      │                    │                    │                 │                   │
       │                      │──disable_intent─────>│                    │                    │                 │                   │
       │                      │                      │──Load Config──────>│                    │                 │                   │
       │                      │                      │<─Current Config────│                    │                 │                   │
       │                      │                      │                    │                    │                 │                   │
       │                      │                      │──backup_agent──────┼────────────────────>│                 │                   │
       │                      │                      │<─Backup Success────┼────────────────────│                 │                   │
       │                      │                      │                    │                    │                 │                   │
       │                      │                      │──Update Config─────│                    │                 │                   │
       │                      │                      │──Generate Prompt───│                    │                 │                   │
       │                      │                      │──Create AI Prompt──│                    │                 │                   │
       │                      │                      │──Update AI Agent───│                    │                 │                   │
       │                      │                      │                    │                    │                 │                   │
       │                      │                      │──test_agent────────┼────────────────────┼─────────────────>│                   │
       │                      │                      │                    │                    │                 │──Test Disabled───>│
       │                      │                      │                    │                    │                 │──Test Enabled────>│
       │                      │                      │                    │                    │                 │<─Responses────────│
       │                      │                      │<─Test Results──────┼────────────────────┼─────────────────│                   │
       │                      │                      │                    │                    │                 │                   │
       │                      │                      │──Store Config─────>│                    │                 │                   │
       │                      │<─Success + Results───│                    │                    │                 │                   │
       │<─Confirmation────────│                      │                    │                    │                 │                   │
       │                      │                      │                    │                    │                 │                   │
```

### Restore Workflow

```
Operations Manager     Supervisor AI Agent     Restore Lambda     S3 (Backups)     Agent Manager     Tester Lambda     Production Agent
       │                      │                      │                  │                  │                 │                   │
       │──"Restore"──────────>│                      │                  │                  │                 │                   │
       │                      │──restore_agent──────>│                  │                  │                 │                   │
       │                      │                      │──List Backups───>│                  │                 │                   │
       │                      │                      │<─Backup List─────│                  │                 │                   │
       │                      │                      │──Get Latest──────>│                  │                 │                   │
       │                      │                      │<─Backup Object───│                  │                 │                   │
       │                      │                      │                  │                  │                 │                   │
       │                      │                      │──Extract Prompt──│                  │                 │                   │
       │                      │                      │──update_agent────┼──────────────────>│                 │                   │
       │                      │                      │                  │                  │──Create Prompt──│                   │
       │                      │                      │                  │                  │──Update Agent───│                   │
       │                      │                      │                  │                  │──Set PUBLISHED──│                   │
       │                      │                      │                  │                  │                 │                   │
       │                      │                      │──test_agent──────┼──────────────────┼─────────────────>│                   │
       │                      │                      │                  │                  │                 │──Execute Tests───>│
       │                      │                      │                  │                  │                 │<─Responses────────│
       │                      │                      │<─Test Results────┼──────────────────┼─────────────────│                   │
       │                      │                      │                  │                  │                 │                   │
       │                      │<─Success + Duration──│                  │                  │                 │                   │
       │<─Confirmation────────│                      │                  │                  │                 │                   │
       │                      │                      │                  │                  │                 │                   │
```

---

## Security Architecture

### Authentication Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Authentication Layers                     │
│                                                              │
│  Layer 1: Phone Number Validation                           │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Contact Flow extracts caller phone number          │    │
│  │ Invokes Auth Lambda with phone number              │    │
│  │ Auth Lambda checks against allowlist                │    │
│  │ Deny if not in allowlist (fail-closed)             │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  Layer 2: PIN Verification                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Lex Bot prompts for 6-digit PIN                    │    │
│  │ Invokes Auth Lambda with PIN                       │    │
│  │ Auth Lambda retrieves PIN from Secrets Manager     │    │
│  │ Compares provided PIN with stored PIN              │    │
│  │ Tracks retry attempts (max 3)                      │    │
│  │ Deny after 3 failed attempts                       │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  Layer 3: IAM Permissions                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Each Lambda has dedicated IAM role                  │    │
│  │ Least privilege permissions                         │    │
│  │ Resource-specific ARNs (no wildcards)              │    │
│  │ Deny by default, explicit allow only               │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  Layer 4: Data Encryption                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ At Rest: S3 (SSE-KMS, customer-managed key), Secrets Manager (KMS)       │    │
│  │ In Transit: TLS 1.2+ for all AWS API calls        │    │
│  │ No plaintext sensitive data in logs                │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  Layer 5: Audit Logging                                     │
│  ┌────────────────────────────────────────────────────┐    │
│  │ All authentication attempts logged                  │    │
│  │ All operations logged with caller identity          │    │
│  │ Immutable audit trail in S3                        │    │
│  │ CloudWatch for real-time monitoring                │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### IAM Role Architecture

**Principle**: Each Lambda function has a dedicated IAM role with least privilege permissions.

```
┌─────────────────────────────────────────────────────────────┐
│                    IAM Role Structure                        │
│                                                              │
│  Authentication Lambda Role                                 │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Permissions:                                        │    │
│  │ - secretsmanager:GetSecretValue (specific secret)  │    │
│  │ - logs:CreateLogGroup, PutLogEvents                │    │
│  │ - cloudwatch:PutMetricData                         │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Agent Manager Lambda Role                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Permissions:                                        │    │
│  │ - qconnect:ListAIAgents, GetAIAgent                │    │
│  │ - qconnect:GetAIPrompt, CreateAIPromptVersion      │    │
│  │ - qconnect:UpdateAIAgent                           │    │
│  │ - lambda:InvokeFunction (Backup, Tester)           │    │
│  │ - s3:GetObject, PutObject (intent configs)         │    │
│  │ - logs:CreateLogGroup, PutLogEvents                │    │
│  │ - cloudwatch:PutMetricData                         │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Backup Lambda Role                                         │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Permissions:                                        │    │
│  │ - s3:PutObject (backups prefix)                    │    │
│  │ - logs:CreateLogGroup, PutLogEvents                │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Restore Lambda Role                                        │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Permissions:                                        │    │
│  │ - s3:ListBucket, GetObject (backups prefix)        │    │
│  │ - lambda:InvokeFunction (Agent Manager, Tester)    │    │
│  │ - logs:CreateLogGroup, PutLogEvents                │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Tester Lambda Role                                         │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Permissions:                                        │    │
│  │ - qconnect:CreateSession, SendMessage              │    │
│  │ - logs:CreateLogGroup, PutLogEvents                │    │
│  │ - cloudwatch:PutMetricData                         │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Data Protection

**Encryption at Rest**:
- S3: SSE-KMS (customer-managed key) for all objects
- Secrets Manager: AWS KMS encryption
- CloudWatch Logs: Encrypted by default

**Encryption in Transit**:
- All AWS API calls use HTTPS with TLS 1.2+
- No plaintext transmission of sensitive data
- Phone calls encrypted by Amazon Connect

**Data Classification**:
- **Highly Sensitive**: Supervisor PIN (Secrets Manager only)
- **Sensitive**: Phone numbers (last 4 digits in logs), agent configurations
- **Internal**: Audit logs, test results, metrics
- **Public**: None (all data is internal or sensitive)

---

## Error Handling Patterns

### Error Handling Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                  Error Handling Layers                       │
│                                                              │
│  Layer 1: Input Validation                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │ - Validate all inputs before processing            │    │
│  │ - Return clear error messages for invalid inputs   │    │
│  │ - Fail fast on validation errors                   │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  Layer 2: Retry Logic                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │ - Exponential backoff for transient errors         │    │
│  │ - Max 3 retries for API calls                      │    │
│  │ - Jitter to prevent thundering herd                │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  Layer 3: Error Translation                                 │
│  ┌────────────────────────────────────────────────────┐    │
│  │ - Translate technical errors to user-friendly      │    │
│  │ - Remove sensitive details from user messages      │    │
│  │ - Provide actionable guidance                      │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  Layer 4: Graceful Degradation                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ - Continue operation if non-critical fails          │    │
│  │ - CloudWatch logging failure → log to stderr       │    │
│  │ - S3 audit log failure → log to CloudWatch         │    │
│  │ - Metrics failure → log warning, continue          │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  Layer 5: Comprehensive Logging                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │ - Log all errors with full technical details       │    │
│  │ - Include stack traces for debugging               │    │
│  │ - Structured JSON for analysis                     │    │
│  │ - Correlation IDs for distributed tracing          │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Error Categories and Handling

**Transient Errors** (Retry):
- API throttling (429)
- Service unavailable (503)
- Network timeouts
- Temporary service issues

**Permanent Errors** (Fail):
- Invalid credentials (401, 403)
- Resource not found (404)
- Invalid input (400)
- Quota exceeded (permanent)

**Critical Errors** (Rollback):
- Test failures after update
- Backup creation failure
- Data corruption detected

### Rollback Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    Rollback Decision Tree                    │
│                                                              │
│  Update Operation                                           │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────┐                                          │
│  │ Backup       │                                          │
│  │ Created?     │──No──> Abort Update                      │
│  └──────┬───────┘                                          │
│         │ Yes                                               │
│         ▼                                                    │
│  ┌──────────────┐                                          │
│  │ Prompt       │                                          │
│  │ Generated?   │──No──> Abort Update                      │
│  └──────┬───────┘                                          │
│         │ Yes                                               │
│         ▼                                                    │
│  ┌──────────────┐                                          │
│  │ AI Agent     │                                          │
│  │ Updated?     │──No──> Retry (3x) ──> Abort             │
│  └──────┬───────┘                                          │
│         │ Yes                                               │
│         ▼                                                    │
│  ┌──────────────┐                                          │
│  │ Tests        │                                          │
│  │ Passed?      │──No──> Critical? ──Yes──> Rollback      │
│  └──────┬───────┘              │                           │
│         │ Yes                  │ No                        │
│         ▼                      ▼                           │
│  ┌──────────────┐      ┌──────────────┐                  │
│  │ Success      │      │ Warn + Proceed│                  │
│  └──────────────┘      └──────────────┘                  │
│                                                              │
│  Rollback Process:                                          │
│  1. Retrieve backup from S3                                │
│  2. Extract original prompt                                │
│  3. Create new AI Prompt version with original text        │
│  4. Update AI Agent to reference restored prompt           │
│  5. Set visibility status to PUBLISHED                     │
│  6. Verify with tests                                      │
│  7. Report rollback to operations manager                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Scalability and Performance

### Performance Targets

| Metric | Target | Actual (Typical) |
|--------|--------|------------------|
| Complete Workflow Duration | <2 minutes (95th percentile) | 45-90 seconds |
| AI Agent Update Effect | <5 seconds | 2-3 seconds |
| Voice Conversation Latency | <3 seconds per exchange | 1-2 seconds |
| Test Execution | <10 seconds for 8+ queries | 5-8 seconds |
| Backup Creation | <5 seconds | 2-3 seconds |
| Restore Operation | <60 seconds | 30-45 seconds |

### Scalability Characteristics

**Horizontal Scaling**:
- Lambda: Automatic scaling up to account concurrency limit
- S3: Unlimited storage, automatic scaling
- CloudWatch: Automatic scaling for logs and metrics
- Amazon Connect: Scales to thousands of concurrent calls

**Vertical Scaling**:
- Lambda memory: Configurable (256MB - 512MB)
- Lambda timeout: Configurable (30s - 120s)
- No vertical scaling needed for managed services

**Concurrency Limits**:
- Supervisor calls: 5 concurrent (design target)
- Production agent conversations: Thousands (no impact from supervisor system)
- Lambda concurrent executions: 1000 (default account limit)
- S3 requests: 5,500 GET/HEAD per second per prefix

### Performance Optimizations

**Lambda Cold Start Mitigation**:
- Minimal dependencies in Lambda packages
- Lambda layers for shared dependencies
- Connection pooling for AWS SDK clients
- Lazy initialization of resources

**API Call Optimization**:
- Batch operations where possible
- Caching of frequently accessed data
- Parallel execution of independent operations
- Retry with exponential backoff

**Test Execution Optimization**:
- Parallel test query execution (where safe)
- Configurable test suite size
- Early termination on critical failures
- Reuse of Q Connect sessions

---

## Deployment Architecture

### CDK Stack Structure

```
┌─────────────────────────────────────────────────────────────┐
│              SupervisorAIAgentStack                          │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Parameters (CDK Context)                           │    │
│  │ - connectInstanceId                                │    │
│  │ - qConnectAssistantId                              │    │
│  │ - supervisorPhoneAllowlist                         │    │
│  │ - supervisorPin                                    │    │
│  │ - notificationEmail                                │    │
│  │ - productionAgentIds                               │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ S3 Bucket                                          │    │
│  │ - Versioning enabled                               │    │
│  │ - SSE-KMS encryption (customer-managed key)                │    │
│  │ - Lifecycle policies                               │    │
│  │ - Bucket policy (Lambda roles only)               │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Secrets Manager Secret                             │    │
│  │ - KMS encryption                                   │    │
│  │ - Resource policy (Auth Lambda only)              │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ IAM Roles (5 roles, one per Lambda)               │    │
│  │ - Least privilege permissions                      │    │
│  │ - Resource-specific ARNs                           │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Lambda Functions (5 functions)                     │    │
│  │ - Python 3.12 runtime                              │    │
│  │ - Appropriate memory and timeout                   │    │
│  │ - Environment variables                            │    │
│  │ - Lambda extension layer (Auth only)              │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ CloudWatch Log Groups (5 groups)                   │    │
│  │ - 90-day retention                                 │    │
│  │ - Encryption enabled                               │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ CloudWatch Alarms                                  │    │
│  │ - Authentication failures                          │    │
│  │ - Update failures                                  │    │
│  │ - Test failures                                    │    │
│  │ - Lambda errors                                    │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ SNS Topic (Alarm notifications)                    │    │
│  │ - Email subscription                               │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Stack Outputs                                      │    │
│  │ - Lambda ARNs (5)                                  │    │
│  │ - S3 bucket name                                   │    │
│  │ - Secret ARN                                       │    │
│  │ - Connect instance ARN                             │    │
│  │ - Q Connect assistant ID                           │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Deployment Process

```
Developer Workstation          AWS CloudFormation          AWS Services
       │                              │                         │
       │──cdk synth──────────────────>│                         │
       │                              │                         │
       │<─CloudFormation Template─────│                         │
       │                              │                         │
       │──cdk deploy─────────────────>│                         │
       │                              │                         │
       │                              │──Create S3 Bucket──────>│
       │                              │<─Bucket Created─────────│
       │                              │                         │
       │                              │──Create Secret─────────>│
       │                              │<─Secret Created─────────│
       │                              │                         │
       │                              │──Create IAM Roles──────>│
       │                              │<─Roles Created──────────│
       │                              │                         │
       │                              │──Create Lambdas────────>│
       │                              │<─Lambdas Created────────│
       │                              │                         │
       │                              │──Create Log Groups─────>│
       │                              │<─Log Groups Created─────│
       │                              │                         │
       │                              │──Create Alarms─────────>│
       │                              │<─Alarms Created─────────│
       │                              │                         │
       │                              │──Create SNS Topic──────>│
       │                              │<─Topic Created──────────│
       │                              │                         │
       │<─Stack Outputs───────────────│                         │
       │                              │                         │
```

### Manual Setup After CDK

After CDK deployment, manual configuration required for:

1. **Amazon Lex PIN Bot**
   - Create bot with AuthenticateUser intent
   - Configure PIN slot (6 digits)
   - Set Lambda fulfillment to Auth Lambda ARN
   - Configure retry logic (max 3 attempts)

2. **Amazon Connect Contact Flow**
   - Create contact flow with blocks:
     - Set Recording Behavior
     - Invoke Lambda (phone validation)
     - Get Customer Input (Lex PIN bot)
     - Check Contact Attributes (PIN result)
     - Get Customer Input (Conversational AI bot with `AMAZON.QInConnectIntent`)
     - Check Contact Attributes (Lex session attr `Tool` = `Complete`)
     - Play Prompt (thank you)
     - Disconnect
     - Connect to Supervisor AI Agent
   - Reference Lambda ARNs and Lex bot from CDK outputs

3. **Supervisor AI Agent**
   - Create AI Prompt with system prompt
   - Create AI Agent with tool integrations
   - Configure tools with Lambda ARNs
   - Set visibility status to PUBLISHED

---

## Integration Points

### Amazon Connect Integration

**Contact Flow → Auth Lambda**:
- Event: Contact Flow invocation
- Payload: `{"Details": {"ContactData": {"CustomerEndpoint": {"Address": "+1234567890"}}}}`
- Response: `{"authenticated": true/false, "phoneNumber": "+1234567890"}`

**Contact Flow → Lex PIN Bot**:
- Event: Get Customer Input block
- Payload: Voice or DTMF input
- Response: Lex fulfillment result (Fulfilled/Failed)

**Contact Flow → Conversational AI Bot → Supervisor AI Agent**:
- Event: Get Customer Input block with Conversational AI bot (`AMAZON.QInConnectIntent`)
- The bot routes voice to the Q Connect Orchestration AI Agent
- AI agent invokes MCP tools (flow module tools → Lambda) mid-conversation
- When AI agent invokes `Complete` (Return to Control), control returns to contact flow
- Contact flow checks Lex session attribute `Tool` = `Complete` → disconnect

### Amazon Lex Integration

**Lex Bot → Auth Lambda**:
- Event: Lex fulfillment request
- Payload: `{"sessionState": {"intent": {"slots": {"PIN": {"value": "123456"}}}}, "sessionAttributes": {"retryCount": "0"}}`
- Response: Lex fulfillment response with Fulfilled/Failed state

### Amazon Q in Connect Integration

**Supervisor AI Agent → Agent Manager Lambda**:
- Tool: `list_agents`, `get_agent_config`, `list_agent_intents`, `disable_intent`, `enable_intent`, `restore_all_intents`, `update_agent_prompt`
- Payload: Tool-specific parameters
- Response: Tool-specific results

**Supervisor AI Agent → Restore Lambda**:
- Tool: `restore_agent_prompt`
- Payload: `{"agentId": "...", "callerPhoneNumber": "..."}`
- Response: Restoration results

**Agent Manager → Q Connect APIs**:
- APIs: `ListAIAgents`, `GetAIAgent`, `GetAIPrompt`, `CreateAIPromptVersion`, `UpdateAIAgent`
- Authentication: IAM role
- Region: us-east-1

**Tester → Q Connect APIs**:
- APIs: `CreateSession`, `SendMessage`
- Authentication: IAM role
- Region: us-east-1

### S3 Integration

**Backup Lambda → S3**:
- Operation: PutObject
- Key: `backups/{agent-id}/{timestamp}-{agent-name}.json`
- Encryption: SSE-KMS (customer-managed key)
- Versioning: Enabled

**Agent Manager → S3**:
- Operations: GetObject, PutObject
- Key: `intent-configs/{agent-id}/current.json`
- Encryption: SSE-KMS (customer-managed key)
- Versioning: Enabled

**Restore Lambda → S3**:
- Operations: ListBucket, GetObject
- Prefix: `backups/{agent-id}/`
- Encryption: SSE-KMS (customer-managed key)

**All Lambdas → S3**:
- Operation: PutObject
- Key: `audit-logs/{year}/{month}/{day}/{operation}-{timestamp}.json`
- Encryption: SSE-KMS (customer-managed key)

### Secrets Manager Integration

**Auth Lambda → Secrets Manager**:
- Operation: GetSecretValue
- Secret: `supervisor-ai-agent-pin`
- Method: Lambda extension (caching)
- Encryption: KMS

### DynamoDB Integration

**Auth Lambda → DynamoDB**:
- Table: `supervisor-ai-agent-pin-attempts`
- Operations: GetItem, PutItem, UpdateItem, DeleteItem
- Purpose: PIN brute-force rate limiting and server-side auth tokens
- TTL: Automatic cleanup of expired records

### KMS Integration

**S3 Bucket**:
- Encryption: SSE-KMS with customer-managed key (`supervisor-ai-agent-backup`)
- Key rotation: Enabled (annual)

**SNS Topic**:
- Encryption: SSE-KMS (same key)

### VPC Configuration

**All Lambda Functions**:
- Deployed in private isolated subnets (2 AZs)
- No internet access (no NAT gateway)
- VPC Gateway Endpoints: S3, DynamoDB
- VPC Interface Endpoints: Secrets Manager, CloudWatch Logs, Lambda
- Security group: Outbound HTTPS (443) to VPC CIDR only

### Inter-Lambda Request Signing

**Agent Manager → Backup/Restore/Tester**:
- Signing: HMAC-SHA256 with shared secret from Secrets Manager
- Verification: Timestamp + signature validated on receipt
- Max age: 5 minutes

### CloudWatch Integration

**All Lambdas → CloudWatch Logs**:
- Log Group: `/aws/lambda/{function-name}`
- Format: Structured JSON
- Retention: 90 days

**All Lambdas → CloudWatch Metrics**:
- Namespace: `SupervisorAIAgent`
- Metrics: AuthenticationAttempts, PromptUpdates, TestExecutions, WorkflowDuration
- Dimensions: PhoneNumber, AgentId, Result, Operation

---

## Appendix

### Technology Versions

- **AWS CDK**: 2.x
- **Node.js**: 20.x or later
- **TypeScript**: 5.x
- **Python**: 3.12
- **boto3**: Latest (AWS SDK for Python)
- **AWS Lambda Powertools**: Latest

### AWS Service Limits

| Service | Limit | Impact |
|---------|-------|--------|
| Lambda concurrent executions | 1000 (default) | Supports 5+ concurrent supervisor calls |
| S3 requests per prefix | 5,500 GET/HEAD per second | No impact (low request rate) |
| Secrets Manager API calls | 5,000 per second | No impact (cached via Lambda extension) |
| CloudWatch Logs ingestion | 5 MB/s per log stream | No impact (low log volume) |
| Amazon Connect concurrent calls | Instance-specific | No impact on production calls |

### Cost Breakdown

**Monthly Cost Estimate** (10 outage updates/month):

| Service | Usage | Cost |
|---------|-------|------|
| Lambda | 50 invocations, 512MB, 30s avg | $0.50 |
| S3 | 10GB storage, 1,000 requests | $0.30 |
| Secrets Manager | 1 secret | $0.40 |
| CloudWatch Logs | 5GB ingestion, 90-day retention | $2.50 |
| CloudWatch Alarms | 5 alarms | $0.50 |
| SNS | 100 notifications | $0.01 |
| DynamoDB | On-demand, minimal usage | <$1 |
| KMS | 1 customer-managed key | <$1 |
| VPC Endpoints | 2 gateway + 3 interface endpoints | ~$7-14 |
| **Total** | | **~$15-20/month** |

**Note**: Amazon Connect and Amazon Q in Connect have separate pricing.

### Document Version

**Version**: 1.0  
**Last Updated**: 2025-03-01  
**Next Review**: 2025-06-01  
**Authors**: AWS ProServe Amazon Connect CoE

