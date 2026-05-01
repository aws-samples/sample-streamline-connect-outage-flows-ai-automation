# CDK Integration Guide

## Overview

This guide provides step-by-step instructions for integrating CDK-deployed resources with the manually configured Amazon Q in Connect Supervisor AI Agent.

## Prerequisites

Before starting integration, ensure:

1. ✅ CDK stack deployed successfully
2. ✅ Stack outputs retrieved and documented
3. ✅ AWS Console access to Amazon Connect
4. ✅ Appropriate IAM permissions for resource configuration

## Integration Workflow

```
CDK Deployment (Contact Flow + Lambdas + S3 + Secrets)
      ↓
Retrieve Stack Outputs
      ↓
Configure Supervisor AI Agent (Amazon Q in Connect)
      ↓
Update Contact Flow with AI Agent ID
      ↓
Test Full Workflow
```

## Step 1: Retrieve Stack Outputs

### Using AWS CLI

```bash
# Save all outputs to file
aws cloudformation describe-stacks \
  --stack-name SupervisorAIAgentStack \
  --profile your-aws-profile \
  --region us-east-1 \
  --query 'Stacks[0].Outputs' \
  --output json > integration-outputs.json

# Display outputs in readable format
cat integration-outputs.json | jq -r '.[] | "\(.OutputKey)=\(.OutputValue)"'
```

### Create Integration Checklist

Create a checklist with your specific values:

```bash
# Extract specific outputs
AUTH_LAMBDA_ARN=$(cat integration-outputs.json | jq -r '.[] | select(.OutputKey=="AuthenticationLambdaArn") | .OutputValue')
AGENT_MANAGER_ARN=$(cat integration-outputs.json | jq -r '.[] | select(.OutputKey=="AgentManagerLambdaArn") | .OutputValue')
RESTORE_LAMBDA_ARN=$(cat integration-outputs.json | jq -r '.[] | select(.OutputKey=="RestoreLambdaArn") | .OutputValue')
QCONNECT_ASSISTANT_ID=$(cat integration-outputs.json | jq -r '.[] | select(.OutputKey=="QConnectAssistantId") | .OutputValue')

# Print checklist
echo "Integration Checklist:"
echo "====================="
echo "1. Authentication Lambda ARN: $AUTH_LAMBDA_ARN"
echo "2. Agent Manager Lambda ARN: $AGENT_MANAGER_ARN"
echo "3. Restore Lambda ARN: $RESTORE_LAMBDA_ARN"
echo "4. Q Connect Assistant ID: $QCONNECT_ASSISTANT_ID"
```

## Step 2: Configure Supervisor AI Agent

### 4.1 Create AI Agent

1. Navigate to Amazon Connect console
2. Select your instance
3. Go to "Amazon Q" → "AI Agents"
4. Click "Create AI agent"
5. Configure:
   - **Name**: `SupervisorAIAgent`
   - **Description**: `AI agent for managing production agent prompts during outages`
   - **Type**: Orchestration

### 4.2 Configure AI Prompt

1. In AI Agent configuration, go to "AI Prompt"
2. Click "Create new prompt"
3. **Prompt name**: `SupervisorAIAgentPrompt`
4. **Prompt text**: Copy from `docs/supervisor-ai-agent-system-prompt.md`

**Key sections to include**:
- Greeting and role explanation
- Outage information extraction
- Change explanation and confirmation
- Tool usage instructions
- Error handling

### 4.3 Configure Tools (Action Groups)

**Tool 1: list_agents**

```json
{
  "name": "list_agents",
  "description": "List all production AI agents in the Amazon Connect instance",
  "parameters": {
    "filters": {
      "type": "object",
      "description": "Optional filters for agent list (e.g., origin: CUSTOMER)",
      "required": false
    }
  },
  "lambdaArn": "<AgentManagerLambdaArn from stack outputs>"
}
```

**Tool 2: get_agent_config**

```json
{
  "name": "get_agent_config",
  "description": "Get the current configuration of a specific AI agent",
  "parameters": {
    "agentId": {
      "type": "string",
      "description": "ID of the AI agent to retrieve",
      "required": true
    }
  },
  "lambdaArn": "<AgentManagerLambdaArn from stack outputs>"
}
```

**Tool 3: list_agent_intents**

```json
{
  "name": "list_agent_intents",
  "description": "List all intents (capabilities) of an AI agent with their enabled/disabled status",
  "parameters": {
    "agentId": {
      "type": "string",
      "description": "ID of the AI agent",
      "required": true
    }
  },
  "lambdaArn": "<AgentManagerLambdaArn from stack outputs>"
}
```

**Tool 4: disable_intent**

```json
{
  "name": "disable_intent",
  "description": "Disable a specific intent (capability) of an AI agent",
  "parameters": {
    "agentId": {
      "type": "string",
      "description": "ID of the AI agent",
      "required": true
    },
    "intentName": {
      "type": "string",
      "description": "Name of the intent to disable",
      "required": true
    },
    "callerPhoneNumber": {
      "type": "string",
      "description": "Phone number of the caller requesting the change",
      "required": true
    }
  },
  "lambdaArn": "<AgentManagerLambdaArn from stack outputs>"
}
```

**Tool 5: enable_intent**

```json
{
  "name": "enable_intent",
  "description": "Enable a previously disabled intent (capability) of an AI agent",
  "parameters": {
    "agentId": {
      "type": "string",
      "description": "ID of the AI agent",
      "required": true
    },
    "intentName": {
      "type": "string",
      "description": "Name of the intent to enable",
      "required": true
    },
    "callerPhoneNumber": {
      "type": "string",
      "description": "Phone number of the caller requesting the change",
      "required": true
    }
  },
  "lambdaArn": "<AgentManagerLambdaArn from stack outputs>"
}
```

**Tool 6: restore_all_intents**

```json
{
  "name": "restore_all_intents",
  "description": "Restore all intents to normal operation (enable all disabled intents)",
  "parameters": {
    "agentId": {
      "type": "string",
      "description": "ID of the AI agent",
      "required": true
    },
    "callerPhoneNumber": {
      "type": "string",
      "description": "Phone number of the caller requesting the restore",
      "required": true
    }
  },
  "lambdaArn": "<AgentManagerLambdaArn from stack outputs>"
}
```

**Tool 7: update_agent_prompt**

```json
{
  "name": "update_agent_prompt",
  "description": "Update AI agent prompt with outage information (for full service outages)",
  "parameters": {
    "agentId": {
      "type": "string",
      "description": "ID of the AI agent to update",
      "required": true
    },
    "outageInfo": {
      "type": "object",
      "description": "Outage information including affected services, available services, and estimated recovery time",
      "required": true,
      "properties": {
        "affectedServices": {
          "type": "array",
          "description": "List of services that are unavailable"
        },
        "availableServices": {
          "type": "array",
          "description": "List of services that remain available"
        },
        "estimatedRecoveryTime": {
          "type": "string",
          "description": "Estimated time for service recovery"
        }
      }
    },
    "callerPhoneNumber": {
      "type": "string",
      "description": "Phone number of the caller requesting the update",
      "required": true
    }
  },
  "lambdaArn": "<AgentManagerLambdaArn from stack outputs>"
}
```

**Tool 8: restore_agent_prompt**

```json
{
  "name": "restore_agent_prompt",
  "description": "Restore AI agent prompt to normal operation from backup",
  "parameters": {
    "agentId": {
      "type": "string",
      "description": "ID of the AI agent to restore",
      "required": true
    },
    "callerPhoneNumber": {
      "type": "string",
      "description": "Phone number of the caller requesting the restore",
      "required": true
    }
  },
  "lambdaArn": "<RestoreLambdaArn from stack outputs>"
}
```

### 4.4 Configure Guardrails (Optional)

1. In AI Agent configuration, go to "Guardrails"
2. Configure content filters:
   - Hate speech: High
   - Insults: High
   - Sexual content: High
   - Violence: High
3. Configure denied topics:
   - Unauthorized access attempts
   - Social engineering
4. Configure word filters (optional)

### 4.5 Publish AI Agent

1. Review all configurations
2. Click "Save"
3. Click "Publish"
4. **Visibility status**: Set to `PUBLISHED`
5. Note the **AI Agent ID** (needed for Contact Flow)

## Step 3: Update Contact Flow with AI Agent

1. Return to the CDK-deployed Contact Flow in Amazon Connect console
2. Edit the Conversational AI block to select the newly created `SupervisorAIAgent`
3. Save and publish the Contact Flow

## Step 4: End-to-End Testing

### 4.1 Test Phone Authentication

1. Call the supervisor hotline phone number
2. Verify:
   - ✅ Call is answered
   - ✅ Recording starts
   - ✅ Phone number validation occurs
   - ✅ If authorized: proceeds to PIN prompt
   - ✅ If unauthorized: receives rejection message

### 4.2 Test PIN Authentication

1. When prompted, enter the 6-digit PIN
2. Verify:
   - ✅ PIN prompt is presented by the Supervisor AI Agent
   - ✅ PIN is validated via Authentication Lambda
   - ✅ If correct: proceeds to Supervisor AI Agent conversation
   - ✅ If incorrect: allows retry (up to 3 attempts)
   - ✅ After 3 failures: call terminates

### 4.3 Test Supervisor AI Agent Conversation

1. After authentication, test natural language:
   - "List all production agents"
   - "Show me the configuration for [agent name]"
   - "What capabilities does [agent name] have?"

2. Verify:
   - ✅ Agent responds naturally
   - ✅ Tools are invoked correctly
   - ✅ Responses include relevant information

### 4.4 Test Intent Management Workflow

1. Say: "Disable the change PIN feature for [agent name]"
2. Verify:
   - ✅ Agent confirms intent name and current status
   - ✅ Agent explains what will happen
   - ✅ Agent asks for confirmation
   - ✅ After confirmation: backup is created
   - ✅ Prompt is updated
   - ✅ Testing is performed
   - ✅ Results are reported

3. Say: "Enable the change PIN feature for [agent name]"
4. Verify similar workflow

5. Say: "Restore all capabilities for [agent name]"
6. Verify restoration workflow

### 4.5 Test Full Outage Workflow

1. Say: "The payment system is down. Customers can still check balances and view transactions. We expect recovery in 2 hours."

2. Verify:
   - ✅ Agent extracts outage information
   - ✅ Agent summarizes understanding
   - ✅ Agent explains planned changes
   - ✅ Agent asks for confirmation
   - ✅ After confirmation: backup is created
   - ✅ Prompt is updated
   - ✅ Testing is performed
   - ✅ Results are reported with examples

3. Say: "Restore normal operations for [agent name]"
4. Verify restoration workflow

## Step 5: Monitoring and Validation

### 5.1 Check CloudWatch Logs

```bash
# View Authentication Lambda logs
aws logs tail /aws/lambda/supervisor-ai-agent-auth \
  --follow \
  --profile your-aws-profile \
  --region us-east-1

# View Agent Manager Lambda logs
aws logs tail /aws/lambda/supervisor-ai-agent-manager \
  --follow \
  --profile your-aws-profile \
  --region us-east-1
```

### 5.2 Check S3 Backups

```bash
# List backups
aws s3 ls s3://supervisor-ai-agent-backups-ACCOUNT_ID-REGION/backups/ \
  --recursive \
  --profile your-aws-profile \
  --region us-east-1

# Download and inspect a backup
aws s3 cp s3://supervisor-ai-agent-backups-ACCOUNT_ID-REGION/backups/{agent-id}/{backup-file}.json . \
  --profile your-aws-profile \
  --region us-east-1

cat {backup-file}.json | jq .
```

### 5.3 Check Audit Logs

```bash
# List audit logs
aws s3 ls s3://supervisor-ai-agent-backups-ACCOUNT_ID-REGION/audit-logs/ \
  --recursive \
  --profile your-aws-profile \
  --region us-east-1

# View recent audit log
aws s3 cp s3://supervisor-ai-agent-backups-ACCOUNT_ID-REGION/audit-logs/2025/03/01/{log-file}.json - \
  --profile your-aws-profile \
  --region us-east-1 | jq .
```

### 5.4 Subscribe to Alarms

```bash
# Subscribe email to alarm topic
aws sns subscribe \
  --topic-arn arn:aws:sns:REGION:ACCOUNT_ID:supervisor-ai-agent-alarms \
  --protocol email \
  --notification-endpoint ops-team@example.com \
  --profile your-aws-profile \
  --region us-east-1

# Confirm subscription via email link
```

## Troubleshooting Integration Issues

### Issue: Lambda Not Invoked

**Symptoms**: Contact Flow shows Lambda error

**Solutions**:
1. Verify Lambda ARN is correct in Contact Flow
2. Check Lambda function exists and is active
3. Verify Contact Flow has permission to invoke Lambda
4. Check Lambda timeout settings (increase if needed)
5. Review Lambda CloudWatch logs for errors

### Issue: AI Agent Not Responding

**Symptoms**: Call reaches AI Agent but no response

**Solutions**:
1. Verify AI Agent is published
2. Check AI Agent visibility status is PUBLISHED
3. Verify tool Lambda ARNs are correct
4. Check Lambda execution roles have Q Connect permissions
5. Review AI Agent conversation logs in Connect

### Issue: Tools Not Working

**Symptoms**: AI Agent responds but tools fail

**Solutions**:
1. Verify tool definitions match Lambda function signatures
2. Check Lambda ARNs in tool configurations
3. Verify Lambda execution roles have required permissions
4. Test Lambda functions directly with sample payloads
5. Review Lambda CloudWatch logs for errors

### Issue: Backups Not Created

**Symptoms**: Updates succeed but no backups in S3

**Solutions**:
1. Verify S3 bucket exists and is accessible
2. Check Backup Lambda execution role has S3 permissions
3. Review Backup Lambda CloudWatch logs
4. Test Backup Lambda directly
5. Verify S3 bucket name in Lambda environment variables

## Post-Integration Checklist

- [ ] CDK stack deployed successfully (Contact Flow + Lambdas + S3 + Secrets)
- [ ] All stack outputs retrieved and documented
- [ ] Supervisor AI Agent created and published in Amazon Q in Connect
- [ ] All tools configured with correct Lambda ARNs
- [ ] Contact Flow updated with AI Agent ID
- [ ] Phone number assigned to Contact Flow
- [ ] End-to-end phone authentication tested
- [ ] PIN authentication tested via Supervisor AI Agent
- [ ] Intent management workflow tested
- [ ] Full outage workflow tested
- [ ] CloudWatch logs verified
- [ ] S3 backups verified
- [ ] Audit logs verified
- [ ] Email subscribed to alarm topic
- [ ] Operations team trained on system usage
- [ ] Documentation updated with specific ARNs and IDs

## Additional Resources

- **Deployment Guide**: `cdk/DEPLOYMENT.md`
- **Stack Outputs Reference**: `cdk/STACK_OUTPUTS.md`
- **Parameters Reference**: `cdk/PARAMETERS.md`
- **Contact Flow Configuration**: `docs/deployment/contact-flow-configuration.md`
- **Supervisor AI Agent Setup**: `docs/deployment/supervisor-ai-agent-setup.md`
- **Intent Management Workflows**: `docs/deployment/intent-management-workflows.md`
- **System Prompt**: `docs/architecture/supervisor-ai-agent-system-prompt.md`
