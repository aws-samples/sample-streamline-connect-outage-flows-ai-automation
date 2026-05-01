# Supervisor AI Agent CDK Configuration Guide

## Overview

The Amazon Q in Connect Supervisor AI Agent is automatically deployed via CDK as part of the Supervisor AI Agent infrastructure. This guide explains the agent configuration, how it works, and how to customize it if needed.

## Architecture

The Supervisor AI Agent consists of two main components:

1. **AI Prompt**: Contains the system instructions that define agent behavior
2. **AI Agent**: Orchestration agent with tool integrations for backend operations

```
Supervisor AI Agent
    ├── AI Prompt (System Instructions)
    │   ├── Conversational style and tone
    │   ├── Operational modes (Full Outage / Intent-Level)
    │   ├── Information extraction logic
    │   ├── Confirmation requirements
    │   └── Result reporting templates
    │
    └── AI Agent (Orchestration)
        ├── Tool Integration: list_agents
        ├── Tool Integration: get_agent_config
        ├── Tool Integration: list_agent_intents
        ├── Tool Integration: disable_intent
        ├── Tool Integration: enable_intent
        ├── Tool Integration: restore_all_intents
        ├── Tool Integration: update_agent_prompt
        └── Tool Integration: restore_agent_prompt
```

## CDK-Deployed Configuration

### AI Prompt Configuration

**Resource Type**: `CfnAIPrompt`  
**Name**: `SupervisorAIAgentPrompt`  
**Type**: `TEXT`  
**API Format**: `ANTHROPIC_CLAUDE_MESSAGES`  
**Model**: `anthropic.claude-3-sonnet-20240229-v1:0`

The AI Prompt contains a condensed version of the complete system prompt (see [Complete System Prompt](../supervisor-ai-agent-system-prompt.md) for full details).

**Key Capabilities**:
- Greet authenticated operations managers professionally
- Extract outage information through natural conversation
- Support two operational modes (Full Outage and Intent-Level)
- Explain planned changes before execution
- Request explicit confirmation before updates
- Report comprehensive results with test validation

### AI Agent Configuration

**Resource Type**: `CfnAIAgent`  
**Name**: `SupervisorAIAgent`  
**Type**: `ORCHESTRATION`  
**Locale**: `en_US`

The AI Agent is configured with 8 Lambda tool integrations for backend operations.

## Tool Integrations

### Tool 1: list_agents

**Lambda**: Agent Manager Lambda  
**Purpose**: List all production AI agents

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "filters": {
      "type": "object",
      "properties": {
        "origin": {
          "type": "string",
          "enum": ["CUSTOMER"]
        }
      }
    }
  }
}
```

**Usage**: When operations manager asks "which agents are available?"

---

### Tool 2: get_agent_config

**Lambda**: Agent Manager Lambda  
**Purpose**: Retrieve detailed agent configuration

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "agentId": {
      "type": "string"
    }
  },
  "required": ["agentId"]
}
```

**Usage**: To understand current agent setup before updates

---

### Tool 3: list_agent_intents

**Lambda**: Agent Manager Lambda  
**Purpose**: List agent capabilities with enabled/disabled status

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "agentId": {
      "type": "string"
    }
  },
  "required": ["agentId"]
}
```

**Usage**: When operations manager asks "what can the agent do?"

---

### Tool 4: disable_intent

**Lambda**: Agent Manager Lambda  
**Purpose**: Disable a specific capability

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "agentId": {"type": "string"},
    "intentName": {"type": "string"},
    "callerPhoneNumber": {"type": "string"}
  },
  "required": ["agentId", "intentName", "callerPhoneNumber"]
}
```

**Usage**: After confirmation to disable a specific intent

---

### Tool 5: enable_intent

**Lambda**: Agent Manager Lambda  
**Purpose**: Enable a specific capability

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "agentId": {"type": "string"},
    "intentName": {"type": "string"},
    "callerPhoneNumber": {"type": "string"}
  },
  "required": ["agentId", "intentName", "callerPhoneNumber"]
}
```

**Usage**: After confirmation to enable a specific intent

---

### Tool 6: restore_all_intents

**Lambda**: Agent Manager Lambda  
**Purpose**: Restore all capabilities to normal operation

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "agentId": {"type": "string"},
    "callerPhoneNumber": {"type": "string"}
  },
  "required": ["agentId", "callerPhoneNumber"]
}
```

**Usage**: After confirmation to restore all intents

---

### Tool 7: update_agent_prompt

**Lambda**: Agent Manager Lambda  
**Purpose**: Update agent prompt with outage information

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "agentId": {"type": "string"},
    "outageInfo": {
      "type": "object",
      "properties": {
        "affectedServices": {"type": "array", "items": {"type": "string"}},
        "availableServices": {"type": "array", "items": {"type": "string"}},
        "estimatedRecoveryTime": {"type": "string"}
      },
      "required": ["affectedServices", "availableServices"]
    },
    "callerPhoneNumber": {"type": "string"}
  },
  "required": ["agentId", "outageInfo", "callerPhoneNumber"]
}
```

**Usage**: After confirmation to update agent for full outage

---

### Tool 8: restore_agent_prompt

**Lambda**: Restore Lambda  
**Purpose**: Restore agent's original prompt from backup

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "agentId": {"type": "string"},
    "callerPhoneNumber": {"type": "string"}
  },
  "required": ["agentId", "callerPhoneNumber"]
}
```

**Usage**: After confirmation to restore normal operations

---

## Lambda Permissions

The CDK stack automatically grants Amazon Q in Connect permission to invoke the Lambda functions:

```typescript
// Agent Manager Lambda
agentManagerLambda.addPermission('AllowQConnectInvoke', {
  principal: new iam.ServicePrincipal('wisdom.amazonaws.com'),
  action: 'lambda:InvokeFunction',
  sourceArn: `arn:aws:wisdom:${region}:${account}:assistant/${assistantId}`,
});

// Restore Lambda
restoreLambda.addPermission('AllowQConnectInvoke', {
  principal: new iam.ServicePrincipal('wisdom.amazonaws.com'),
  action: 'lambda:InvokeFunction',
  sourceArn: `arn:aws:wisdom:${region}:${account}:assistant/${assistantId}`,
});
```

## Post-Deployment Steps

### Step 1: Verify AI Agent Creation

After CDK deployment, verify the agent was created successfully:

```bash
aws qconnect get-ai-agent \
  --assistant-id <ASSISTANT_ID> \
  --ai-agent-id <AGENT_ID> \
  --profile your-aws-profile \
  --region us-east-1
```

### Step 2: Publish the AI Agent

The AI Agent is created in `DRAFT` status. To make it active, publish it:

```bash
aws qconnect update-ai-agent \
  --assistant-id <ASSISTANT_ID> \
  --ai-agent-id <AGENT_ID> \
  --visibility-status PUBLISHED \
  --profile your-aws-profile \
  --region us-east-1
```

**Note**: This step may need to be done via the Amazon Q in Connect console if the CLI command is not available.

### Step 3: Update Contact Flow

Add the AI Agent ID to the Contact Flow (Block 9):

1. Navigate to Amazon Connect console
2. Go to **Routing** → **Contact Flows**
3. Find `SupervisorAIAgentFlow`
4. Edit Block 9 (Connect to Amazon Q)
5. Add the AI Agent ID from CDK outputs
6. Save and Publish

### Step 4: Test the Agent

Test the complete workflow:

1. Call the supervisor hotline
2. Complete phone and PIN authentication
3. Interact with the Supervisor AI Agent
4. Verify tool invocations work correctly

## Customization Options

### Changing the AI Model

To use a different Claude model:

```typescript
modelId: 'anthropic.claude-3-haiku-20240307-v1:0',  // Faster, less expensive
// or
modelId: 'anthropic.claude-3-opus-20240229-v1:0',   // More capable, more expensive
```

### Modifying the System Prompt

To customize the agent's behavior, update the `supervisorSystemPrompt` variable in the CDK stack:

```typescript
const supervisorSystemPrompt = `Your custom system prompt here...`;
```

**Important**: Keep the core structure (greeting, operational modes, confirmation requirements, tool usage) to ensure proper functionality.

### Adding Custom Tools

To add additional tool integrations:

```typescript
{
  lambdaToolConfiguration: {
    lambdaArn: customLambda.functionArn,
    name: 'custom_tool',
    description: 'Description of custom tool',
    inputSchema: {
      type: 'object',
      properties: {
        // Define parameters
      },
      required: ['param1'],
    },
  },
}
```

### Changing the Locale

To support a different language:

```typescript
locale: 'es_ES',  // Spanish
// or
locale: 'fr_FR',  // French
```

**Note**: You'll also need to translate the system prompt to the target language.

## Monitoring and Troubleshooting

### CloudWatch Logs

Monitor AI Agent conversations and tool invocations:

```bash
# Agent Manager Lambda logs
aws logs tail /aws/lambda/supervisor-ai-agent-manager --follow \
  --profile your-aws-profile \
  --region us-east-1

# Restore Lambda logs
aws logs tail /aws/lambda/supervisor-ai-agent-restore --follow \
  --profile your-aws-profile \
  --region us-east-1
```

### Common Issues

**Issue**: Agent doesn't invoke tools

**Symptoms**: Agent responds but doesn't execute backend operations

**Solution**:
1. Verify Lambda permissions are configured correctly
2. Check that tool names match exactly in agent configuration
3. Review Lambda logs for invocation errors

```bash
# Check Lambda permissions
aws lambda get-policy \
  --function-name supervisor-ai-agent-manager \
  --profile your-aws-profile \
  --region us-east-1
```

---

**Issue**: Agent gives generic responses

**Symptoms**: Agent doesn't follow system prompt instructions

**Solution**:
1. Verify AI Prompt is correctly associated with AI Agent
2. Check that AI Agent is published (not in DRAFT status)
3. Review system prompt for clarity and completeness

---

**Issue**: Tool invocations fail

**Symptoms**: Agent reports errors when trying to execute operations

**Solution**:
1. Check Lambda function logs for errors
2. Verify Lambda has required IAM permissions
3. Verify input parameters match tool schema

---

**Issue**: Agent not available in Contact Flow

**Symptoms**: Can't select agent in Connect to Amazon Q block

**Solution**:
1. Verify AI Agent is published (visibility status = PUBLISHED)
2. Check that AI Agent is associated with correct assistant
3. Verify assistant ID matches in Contact Flow and AI Agent

## Security Considerations

### Tool Invocation Security

- Lambda functions are invoked with least privilege permissions
- Caller phone number is passed to all tools for audit logging
- All operations are logged to CloudWatch and S3
- Tool invocations are rate-limited by Amazon Q in Connect

### System Prompt Security

- System prompt does not contain sensitive information
- No credentials or API keys in prompt
- Prompt instructs agent to handle errors gracefully
- Prompt requires explicit confirmation before destructive operations

### AI Agent Access Control

- Agent is only accessible through authenticated Contact Flow
- Phone and PIN authentication required before agent access
- All conversations are recorded for audit
- Agent cannot be accessed directly via API

## CDK Stack Outputs

After deploying the CDK stack, retrieve the agent information:

```bash
aws cloudformation describe-stacks \
  --stack-name SupervisorAIAgentStack \
  --query 'Stacks[0].Outputs[?contains(OutputKey, `SupervisorAI`)]' \
  --profile your-aws-profile \
  --region us-east-1
```

**Outputs**:
- `SupervisorAIPromptId`: AI Prompt ID
- `SupervisorAIPromptArn`: AI Prompt ARN
- `SupervisorAIAgentId`: AI Agent ID (use in Contact Flow)
- `SupervisorAIAgentArn`: AI Agent ARN

## Complete System Prompt

The CDK stack includes a condensed version of the system prompt for deployment. For the complete, detailed system prompt with all examples and templates, see:

[Complete Supervisor AI Agent System Prompt](../supervisor-ai-agent-system-prompt.md)

This document includes:
- Detailed conversational examples
- Complete explanation templates
- Error handling scenarios
- Multi-agent operation workflows
- Intent management workflows
- Service restoration workflows

## Related Documentation

- [Complete System Prompt](../supervisor-ai-agent-system-prompt.md)
- [Supervisor AI Agent Setup Guide](./supervisor-ai-agent-setup.md)
- [Contact Flow Configuration](./contact-flow-configuration.md)
- [Intent Management Workflows](./intent-management-workflows.md)
- [Amazon Q in Connect Developer Guide](https://docs.aws.amazon.com/connect/latest/adminguide/amazon-q-connect.html)

## Support

For issues with the Supervisor AI Agent:
1. Test agent in Q Connect console before testing via phone
2. Check CloudWatch Logs for tool invocation details
3. Review Lambda logs for backend operation errors
4. Verify all ARNs and IDs are correct in agent configuration
5. Ensure AI Agent is published (not in DRAFT status)
6. Contact AWS Support for Q Connect-specific issues
