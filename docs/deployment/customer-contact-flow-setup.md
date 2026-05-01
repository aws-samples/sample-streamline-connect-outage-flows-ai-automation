# Customer Contact Flow Setup Guide

[← Back to Documentation Index](../README.md) | [Supervisor AI Agent Setup](./supervisor-ai-agent-setup.md) | [CDK Deployment](./cdk-deployment.md)

---

## Overview

This guide covers the manual setup steps for the customer-facing contact flow. The customer flow routes callers directly to the Production AI Agent — no authentication required. Together with the supervisor flow, it demonstrates the complete outage management loop:

1. **Before outage**: Customer calls → Production AI Agent handles all requests normally
2. **Supervisor updates**: Supervisor calls → updates prompt or disables intents
3. **During outage**: Customer calls → Production AI Agent reflects outage messaging
4. **After recovery**: Supervisor restores → Customer calls → normal behavior restored

### Architecture Summary

```
Phone Call → Customer Contact Flow → Set Recording (Contact Lens)
  → Connect assistant (Q in Connect session)
  → Conversational AI Bot (AMAZON.QInConnectIntent)
  → Production AI Agent (ORCHESTRATION)
  → Complete (Return to Control) → "Thank you" → Disconnect
```

## Prerequisites

1. **CDK Stack Deployed** — Customer contact flow created with placeholder block
2. **Amazon Connect Instance** with Amazon Q in Connect enabled
3. **Q Connect Assistant ID** from CDK outputs or existing setup

## Step 1: Create Production AI Agent (Orchestration)

The production agent must be `ORCHESTRATION` type — a conversational agent whose behavior is controlled by its AI Prompt and tools. The supervisor system updates this prompt to reflect outages.

### 1.1 Create the Agent

1. Open Connect admin website → **AI agent designer** → **AI agents**
2. Click **Create AI agent**
3. Select type: **Orchestration**
4. For **Copy from existing**, select: **SelfServiceOrchestrator**
5. Name: `ProductionBankingAgent`

### 1.2 Attach AI Prompt

Create and attach an AI Prompt describing the banking agent personality and capabilities. The prompt must be in YAML format:

```yaml
system: |
  You are a friendly and professional banking customer service agent. You help customers with checking account balances, transferring funds between accounts, changing their PIN, and general account inquiries. Be conversational, concise, and helpful. If a customer request is outside your capabilities, politely let them know and suggest they contact a branch or human agent. When the customer indicates they are done (e.g. "that's all", "thank you", "goodbye"), use the Complete tool to end the conversation gracefully.
messages:
  - "{{$.conversationHistory}}"
  - role: assistant
    content: <message>
```

### 1.3 Verify Tools

> **Note:** The agent should have **Complete** and **Escalate** Return to Control tools from the SelfServiceOrchestrator template. Do NOT remove Complete.

### 1.4 Publish

Click **Publish** to make the agent active.

### 1.5 Set as Default Self-Service Agent

1. Go to **AI agent designer** → **AI Agents** → **Default AI Agent Configurations**
2. Set **Self Service** to the **Supervisor AI Agent** (e.g., `SupervisorOutageAgent`)

> **Note:** Both flows share one AI agent. The agent uses a `FlowType` contact attribute (set by CDK in each contact flow) to switch between customer banking persona and supervisor outage management persona. See [Supervisor AI Agent Setup](./supervisor-ai-agent-setup.md) for the dual-persona prompt configuration.

### 1.6 Verify via CLI

```bash
aws qconnect list-ai-agents \
  --assistant-id <ASSISTANT_ID> \
  --origin CUSTOMER \
  --query 'aiAgentSummaries[?type==`ORCHESTRATION`].{name:name,id:aiAgentId,status:status}'
```

## Step 2: Create Customer Conversational AI Bot

This must be done via the Amazon Connect admin console — no API available.

### 2.1 Create the Bot

1. Open Connect admin website → **Routing** → **Flows** → **Conversational AI** tab
2. Click **Create Conversational AI bot**
3. Name: `CustomerConversationalAIBot`
4. Click **Save**

### 2.2 Enable the Connect AI Agents Intent

1. Open the bot you just created
2. Go to the **Configuration** tab
3. Toggle on **Connect AI agents intent** (`AMAZON.QInConnectIntent`)
4. In the dialog, select the Q Connect assistant ARN from the dropdown
5. Click **Confirm**
6. Click **Build** and wait for the build to complete

### 2.3 Create Alias

1. In the bot settings, go to **Aliases**
2. Create alias named `live`
3. Enable **Use in flow and flow modules**

### 2.4 Verify Lex Bot SLR Permissions

```bash
aws iam list-role-policies \
  --role-name AWSServiceRoleForLexV2Bots_AmazonConnect_<ACCOUNT_ID>
```

If `QInConnectAssistantPolicy` is missing: open **Lex console** (not Connect admin) → open the bot → edit `QInConnectIntent` → re-save → rebuild.

> **⚠️ Lex Bot SLR Permission Note**: If the Conversational AI bot was created via the Amazon Connect admin website, the Lex service-linked role (SLR) may **not** automatically receive the `QInConnectAssistantPolicy` needed for the `AMAZON.QInConnectIntent` to invoke Q in Connect. **Symptoms**: the bot builds successfully but the AI agent never responds during calls. **Fix**: Open the **Amazon Lex console** (not Connect admin) → open `CustomerConversationalAIBot` → navigate to the `QInConnectIntent` → make a minor edit (e.g., add/remove a space in a sample utterance) → **Save intent** → **Build** the bot.

## Step 3: Update Customer Contact Flow

The CDK deploys the customer contact flow with a placeholder message block. You need to replace it with the bot routing.

### 3.1 Open the Flow

Go to **Routing** → **Flows** → open `CustomerContactFlow`

### 3.2 Remove Placeholder

Delete the placeholder block that says "Customer flow setup in progress. Please add the Conversational AI bot block in the Connect console."

### 3.3 Update Recording Block

Open the existing **Set recording and analytics behavior** block → enable **Contact Lens real-time analytics** (required for Q in Connect voice).

### 3.4 Add Connect Assistant Block

1. Found under the **Integrate** category in the flow designer
2. Select your Q in Connect assistant from the dropdown
3. This creates the Q in Connect session for the contact

### 3.5 Verify FlowType Attribute (CDK-deployed)

The CDK stack deploys a `Set contact attributes` block that sets `FlowType=CUSTOMER`. This tells the AI agent to use its customer banking persona.

1. Verify the block exists in the flow after `action-recording`
2. If missing (e.g., flow was manually recreated), add a **Set contact attributes** block:
   - Destination: **User defined**
   - Key: `FlowType`, Value: `CUSTOMER`

> **How it works**: Both flows share one AI agent (SupervisorOutageAgent). The agent's prompt checks the `FlowType` attribute — `CUSTOMER` triggers the banking persona, `SUPERVISOR` triggers the outage management persona.

### 3.6 Add Get Customer Input Block

1. Prompt (text-to-speech): "Welcome to our customer service line. How can I help you today?"
2. Tab: **Amazon Lex**
3. Select bot: `CustomerConversationalAIBot`
4. Select alias: `live`

### 3.7 Add Check Contact Attributes Block

- Namespace: **Lex session attributes**
- Attribute: `Tool`
- Condition: Equals `Complete`

### 3.8 Add Play Prompt Block

- Text-to-speech: "Thank you for calling. Goodbye."

### 3.9 Wire the Blocks

```
Logging → Recording (Contact Lens real-time)
  → Set FlowType=CUSTOMER → Connect assistant
  → Get Customer Input (Lex bot)
  → Check Tool=Complete → "Thank you" → Disconnect

Error paths:
  Connect assistant error → Disconnect
  Get Customer Input error → Disconnect
  Check attributes no match → Disconnect
```

### 3.10 Save and Publish

Click **Save** then **Publish**.

## Step 4: Claim and Associate Phone Number

### 4.1 Search Available Numbers

```bash
aws connect search-available-phone-numbers \
  --target-arn arn:aws:connect:<REGION>:<ACCOUNT_ID>:instance/<INSTANCE_ID> \
  --phone-number-country-code US \
  --phone-number-type TOLL_FREE \
  --max-results 3
```

### 4.2 Claim a Number

```bash
aws connect claim-phone-number \
  --target-arn arn:aws:connect:<REGION>:<ACCOUNT_ID>:instance/<INSTANCE_ID> \
  --phone-number "<PHONE_NUMBER>" \
  --phone-number-description "Customer contact center line"
```

### 4.3 Associate with Customer Contact Flow

```bash
aws connect associate-phone-number-contact-flow \
  --instance-id <INSTANCE_ID> \
  --contact-flow-id <CUSTOMER_FLOW_ID> \
  --phone-number-id <PHONE_NUMBER_ID>
```

### 4.4 Verify

```bash
aws connect list-phone-numbers-v2 \
  --instance-id <INSTANCE_ID> \
  --query 'ListPhoneNumbersSummaryList[].{Phone:PhoneNumber,Target:TargetArn}'
```

## Step 5: Verify End-to-End

### Normal Operations Test

1. Call the customer phone number from any phone
2. Verify welcome message: "Welcome to our customer service line. How can I help you today?"
3. Say: "What's my account balance?" → verify conversational response
4. Say: "I want to change my PIN" → verify conversational response
5. Say: "That's all, thank you" → verify "Thank you for calling. Goodbye." and disconnect

### Supervisor Outage Loop Test

1. **Before outage**: Call customer number → verify normal responses
2. **Supervisor disables intent**: Call supervisor hotline → disable "change card PIN" → confirm
3. **During outage**: Call customer number → ask about PIN change → verify "temporarily unavailable" response
4. **Other intents still work**: Ask about balance → verify normal response
5. **Supervisor restores**: Call supervisor hotline → restore all capabilities → confirm
6. **After recovery**: Call customer number → ask about PIN change → verify normal response

### Monitor Logs

```bash
aws logs tail /aws/lambda/supervisor-ai-agent-manager --follow
```

## Troubleshooting

| Issue | Solution |
|---|---|
| AI agent not responding | Verify Contact Lens real-time analytics is enabled in the recording block |
| Bot builds but no AI response | Check Lex SLR permissions (see Step 2.4 note above) |
| "Connect assistant" block missing | Look under the **Integrate** category in the flow designer |
| Supervisor changes not reflected | Changes apply to new calls only — hang up and call again |
| Welcome message but then silence | Verify bot alias `live` is enabled for flow and flow modules |

## Relationship to Supervisor Flow

| Aspect | Supervisor Flow | Customer Flow |
|---|---|---|
| Phone number | Supervisor hotline | Customer contact center |
| Authentication | Phone allowlist + PIN | None |
| AI Agent | SupervisorOutageAgent (orchestration) | ProductionBankingAgent (orchestration) |
| Tools | 9 MCP + 1 RTC | 2 RTC (Complete, Escalate) |
| Purpose | Update prompts/intents | Serve customers |
| Contact Lens | Required | Required |
| Connect assistant | Required | Required |

## Related Documentation

- [Supervisor AI Agent Setup](./supervisor-ai-agent-setup.md)
- [System Architecture](../architecture/system-architecture.md)
- [CDK Deployment](./cdk-deployment.md)
- [Post-Deploy Testing](./post-deploy-testing.md)
- [Operations Runbook](../operations/operations-runbook.md)
