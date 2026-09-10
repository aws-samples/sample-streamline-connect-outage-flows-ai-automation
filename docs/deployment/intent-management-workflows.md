# Intent Management Workflows

## Overview

This document describes how to use the Supervisor AI Agent to manage specific capabilities (intents) of production AI agents. Intent management allows operations managers to selectively enable or disable individual agent capabilities without affecting other functionality.

## When to Use Intent Management

Use intent-level management when:
- A specific feature has a bug that needs to be temporarily disabled
- Compliance requires disabling certain capabilities
- Targeted service degradation affects only specific functionality
- You need to control individual capabilities independently

Use full outage mode when:
- Complete services are unavailable
- Multiple capabilities are affected simultaneously
- Broad service disruptions impact most functionality

## Prerequisites

Before using intent management:
1. Authenticate successfully through the supervisor hotline (phone number validation + PIN)
2. Know which production AI agent you want to manage
3. Understand which capability (intent) needs to be managed

## Workflow 1: List Agent Capabilities

### Purpose
Discover what capabilities a production AI agent currently handles and their enabled/disabled status.

### When to Use
- Before disabling or enabling intents (to see what's available)
- To check current status of capabilities
- To understand what the agent can do

### Conversation Flow

**Step 1: Request capability list**

Operations Manager says:
- "What can the agent do?"
- "List the capabilities"
- "Show me the intents"
- "What features does the voice agent handle?"

**Step 2: Agent retrieves and presents capabilities**

The Supervisor AI Agent will:
1. Call the `list_agent_intents` tool
2. Present capabilities in natural language

Example response:
```
"The Production Voice Agent currently handles these capabilities:
- Check Balance: View account balance - Currently enabled
- Transfer Funds: Transfer money between accounts - Currently enabled
- Change PIN: Change card PIN - Currently enabled
- Report Lost Card: Report a lost or stolen card - Currently enabled
- Payment History: View recent transactions - Currently enabled

Which capability would you like to manage?"
```

### Example Conversation

```
Operations Manager: "What capabilities does the voice agent have?"

Supervisor AI Agent: "Let me check that for you."

[Agent retrieves capabilities]

Supervisor AI Agent: "The Production Voice Agent currently handles these capabilities:
- Check Balance: View account balance - Currently enabled
- Transfer Funds: Transfer money between accounts - Currently enabled  
- Change PIN: Change card PIN - Currently enabled
- Report Lost Card: Report a lost or stolen card - Currently enabled
- Payment History: View recent transactions - Currently enabled

Which capability would you like to manage?"
```

## Workflow 2: Disable Specific Intent

### Purpose
Temporarily disable a specific capability while keeping all other capabilities operational.

### When to Use
- A specific feature has a bug
- Compliance requires disabling a capability
- Backend service for one feature is unavailable
- Need to prevent customers from using a specific function

### Conversation Flow

**Step 1: Request intent disable**

Operations Manager says:
- "Disable the change PIN feature"
- "Turn off balance transfers"
- "Stop handling payment history requests"
- "I need to disable [capability name]"

**Step 2: Agent confirms intent and status**

The Supervisor AI Agent will:
1. Confirm the intent name
2. Verify current status (should be enabled)
3. Describe what the intent does

Example:
```
"I understand you want to disable the Change PIN capability. 
This capability is currently enabled and handles card PIN changes. 
Is that correct?"
```

**Step 3: Operations Manager confirms**

Say "Yes" or "That's correct"

**Step 4: Agent explains impact**

The Supervisor AI Agent will explain:
- What happens when the intent is disabled
- How customers will be informed
- That other capabilities remain operational

Example:
```
"When I disable this capability:
- Customers requesting PIN changes will be told it's temporarily unavailable
- Alternative options will be suggested where available
- All other capabilities will continue working normally

Should I proceed with disabling Change PIN?"
```

**Step 5: Operations Manager confirms execution**

Say "Yes", "Go ahead", or "Proceed"

**Step 6: Agent executes and reports results**

The Supervisor AI Agent will:
1. Create a backup of current configuration
2. Update the agent prompt to handle the disabled intent
3. Test the updated agent
4. Report results

Example:
```
"I've successfully disabled the Change PIN capability. Here's what I verified:
- The capability is now marked as unavailable
- I tested with sample queries and confirmed customers are told it's temporarily unavailable
- Other capabilities like Check Balance and Transfer Funds are still working normally
- A backup was created at s3://bucket/backups/agent-id/timestamp.json in case you need to restore it"
```

### What Happens Behind the Scenes

1. **Backup Creation**: Current agent configuration and intent configuration are backed up to S3
2. **Intent Configuration Update**: The intent is marked as disabled in the Intent_Configuration stored in S3
3. **Prompt Generation**: A new AI Prompt is generated that:
   - Recognizes requests for the disabled intent
   - Explains the capability is temporarily unavailable
   - Suggests alternatives where available
   - Maintains normal handling for all other intents
4. **Agent Update**: The AI Agent configuration is updated to reference the new AI Prompt
5. **Testing**: Automated tests verify:
   - Disabled intent requests are properly rejected
   - Enabled intents continue working normally
6. **Audit Logging**: The operation is logged with timestamp, agent ID, intent name, and caller information

### Example Conversation

```
Operations Manager: "We need to disable the change PIN feature. There's a bug in the backend system."

Supervisor AI Agent: "I understand you want to disable the Change PIN capability. This capability is currently enabled and handles card PIN changes. Is that correct?"

Operations Manager: "Yes, that's right."

Supervisor AI Agent: "When I disable this capability:
- Customers requesting PIN changes will be told it's temporarily unavailable
- Alternative options will be suggested where available
- All other capabilities will continue working normally

Should I proceed with disabling Change PIN?"

Operations Manager: "Yes, please do that."

Supervisor AI Agent: [Executes disable operation]

"I've successfully disabled the Change PIN capability. Here's what I verified:
- The capability is now marked as unavailable
- I tested with sample queries and confirmed customers are told it's temporarily unavailable
- Other capabilities like Check Balance and Transfer Funds are still working normally
- A backup was created in case you need to restore it

Is there anything else you need help with?"
```

## Workflow 3: Enable Specific Intent

### Purpose
Re-enable a previously disabled capability to restore specific functionality.

### When to Use
- Bug fix has been deployed
- Compliance issue resolved
- Backend service restored
- Ready to restore specific capability

### Conversation Flow

**Step 1: Request intent enable**

Operations Manager says:
- "Enable the change PIN feature"
- "Turn on balance transfers"
- "Restore payment history"
- "I need to enable [capability name]"

**Step 2: Agent confirms intent and status**

The Supervisor AI Agent will:
1. Confirm the intent name
2. Verify current status (should be disabled)

Example:
```
"I understand you want to enable the Change PIN capability. 
This capability is currently disabled. 
Is that correct?"
```

**Step 3: Operations Manager confirms**

Say "Yes" or "That's correct"

**Step 4: Agent explains impact**

The Supervisor AI Agent will explain what happens when the intent is enabled:

Example:
```
"When I enable this capability:
- Customers will be able to request PIN changes normally
- The agent will handle these requests as it did before

Should I proceed with enabling Change PIN?"
```

**Step 5: Operations Manager confirms execution**

Say "Yes", "Go ahead", or "Proceed"

**Step 6: Agent executes and reports results**

The Supervisor AI Agent will:
1. Create a backup of current configuration
2. Update the agent prompt to handle the enabled intent normally
3. Test the updated agent
4. Report results

Example:
```
"I've successfully enabled the Change PIN capability. Here's what I verified:
- The capability is now available again
- I tested with sample queries and confirmed it's working normally
- A backup was created in case you need to make changes"
```

### What Happens Behind the Scenes

1. **Backup Creation**: Current agent configuration and intent configuration are backed up to S3
2. **Intent Configuration Update**: The intent is marked as enabled in the Intent_Configuration
3. **Prompt Generation**: A new AI Prompt is generated that handles the intent normally
4. **Agent Update**: The AI Agent configuration is updated to reference the new AI Prompt
5. **Testing**: Automated tests verify the enabled intent works correctly
6. **Audit Logging**: The operation is logged with timestamp, agent ID, intent name, and caller information

### Example Conversation

```
Operations Manager: "The PIN change bug is fixed. Can you enable that feature again?"

Supervisor AI Agent: "I understand you want to enable the Change PIN capability. This capability is currently disabled. Is that correct?"

Operations Manager: "Yes."

Supervisor AI Agent: "When I enable this capability:
- Customers will be able to request PIN changes normally
- The agent will handle these requests as it did before

Should I proceed with enabling Change PIN?"

Operations Manager: "Yes, go ahead."

Supervisor AI Agent: [Executes enable operation]

"I've successfully enabled the Change PIN capability. Here's what I verified:
- The capability is now available again
- I tested with sample queries and confirmed it's working normally
- A backup was created in case you need to make changes

Is there anything else you need help with?"
```

## Workflow 4: Restore All Intents

### Purpose
Restore all capabilities to normal operation, enabling any previously disabled intents.

### When to Use
- All issues resolved, ready to return to full service
- Multiple intents were disabled and all need to be restored
- Want to quickly return to normal operations

### Conversation Flow

**Step 1: Request restore all**

Operations Manager says:
- "Restore everything"
- "Enable all capabilities"
- "Back to normal"
- "Restore all intents"

**Step 2: Agent confirms operation**

The Supervisor AI Agent will confirm the scope:

Example:
```
"I understand you want to restore all capabilities to normal operation. 
This will enable any capabilities that were previously disabled. 
Should I proceed?"
```

**Step 3: Operations Manager confirms**

Say "Yes", "Go ahead", or "Proceed"

**Step 4: Agent executes and reports results**

The Supervisor AI Agent will:
1. Retrieve the most recent backup before any intent modifications
2. Restore the original AI Prompt
3. Update Intent_Configuration to enable all intents
4. Test the restored agent
5. Calculate partial outage duration
6. Report results

Example:
```
"I've successfully restored all capabilities to normal operation. Here's what I verified:
- All 5 capabilities are now enabled
- I tested sample queries across different capabilities and confirmed they're working normally
- The partial outage lasted 2 hours and 15 minutes
- A backup was created at s3://bucket/backups/agent-id/timestamp.json"
```

### What Happens Behind the Scenes

1. **Backup Retrieval**: System finds the most recent backup before any intent modifications
2. **Intent Configuration Update**: All intents are marked as enabled in Intent_Configuration
3. **Prompt Restoration**: The original AI Prompt text is restored from backup
4. **Agent Update**: The AI Agent configuration is updated to reference the restored AI Prompt
5. **Testing**: Automated tests verify all intents work normally
6. **Duration Calculation**: System calculates how long the partial outage lasted
7. **Audit Logging**: The operation is logged with timestamp, agent ID, and caller information

### Example Conversation

```
Operations Manager: "All the issues are fixed. Can you restore everything to normal?"

Supervisor AI Agent: "I understand you want to restore all capabilities to normal operation. This will enable any capabilities that were previously disabled. Should I proceed?"

Operations Manager: "Yes."

Supervisor AI Agent: [Executes restore all operation]

"I've successfully restored all capabilities to normal operation. Here's what I verified:
- All 5 capabilities are now enabled
- I tested sample queries across different capabilities and confirmed they're working normally
- The partial outage lasted 2 hours and 15 minutes
- A backup was created

Is there anything else you need help with?"
```

## Combining Workflows

You can use multiple workflows in the same call:

### Example: List, Disable, and Enable

```
Operations Manager: "What can the voice agent do?"

Supervisor AI Agent: [Lists all capabilities]

Operations Manager: "Disable the transfer funds feature."

Supervisor AI Agent: [Confirms and disables]

Operations Manager: "Actually, can you also disable payment history?"

Supervisor AI Agent: [Confirms and disables]

Operations Manager: "Now enable transfer funds back."

Supervisor AI Agent: [Confirms and enables]
```

## Best Practices

### 1. List Capabilities First
Before disabling or enabling intents, list the capabilities to:
- See what's available
- Verify intent names
- Check current status

### 2. Confirm Intent Names
Use the exact intent name from the capability list to avoid errors.

### 3. Test After Changes
The system automatically tests changes, but you should also:
- Monitor customer interactions
- Check CloudWatch logs
- Verify expected behavior

### 4. Document Changes
Keep track of:
- Which intents were disabled
- Why they were disabled
- When they were disabled
- When they were re-enabled

### 5. Use Restore All for Multiple Intents
If multiple intents were disabled and all need to be restored, use "restore all" instead of enabling each one individually.

### 6. Monitor Backup Locations
The agent reports backup locations. Keep track of these for audit purposes.

## Troubleshooting

### Intent Not Found

**Problem**: Agent says "I couldn't find a capability named '[intent name]'"

**Solution**: 
1. List all capabilities to see available intent names
2. Use the exact name from the list
3. Check for typos or case sensitivity

### Intent Already Disabled/Enabled

**Problem**: Trying to disable an already disabled intent (or enable an already enabled intent)

**Solution**:
1. List capabilities to check current status
2. Proceed with the opposite operation if needed

### Test Failures

**Problem**: Agent reports test failures after disabling/enabling

**Solution**:
1. Review the test failure details
2. Decide whether to proceed or rollback
3. For critical failures, the system automatically rolls back

### Multiple Intents Need Management

**Problem**: Need to disable/enable many intents

**Solution**:
1. For disabling multiple: Disable each one individually
2. For enabling multiple: Use "restore all" if all need to be enabled
3. For mixed operations: Handle each intent individually

## Audit and Compliance

All intent management operations are logged with:
- Timestamp
- Agent ID
- Intent name
- Operation (disable/enable/restore_all)
- Caller phone number
- Before and after Intent_Configuration
- Test results

Audit logs are stored in:
- Amazon S3: `s3://bucket/audit-logs/YYYY/MM/DD/intent-{operation}-{timestamp}.json`
- Amazon CloudWatch: `/aws/lambda/supervisor-ai-agent-manager`

## Related Documentation

- [Supervisor AI Agent Setup Guide](./supervisor-ai-agent-setup.md) - Complete setup instructions
- [Full Outage Management](./full-outage-workflows.md) - Managing complete service outages
- [System Prompt](../supervisor-ai-agent-system-prompt.md) - Complete system prompt with intent management

## Summary

Intent management provides granular control over production AI agent capabilities:

1. **List Capabilities**: Discover what the agent can do
2. **Disable Intent**: Turn off specific capabilities temporarily
3. **Enable Intent**: Restore specific capabilities
4. **Restore All**: Return all capabilities to normal operation

All operations include automatic backup, testing, and audit logging for safety and compliance.
