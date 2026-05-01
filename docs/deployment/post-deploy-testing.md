# End-to-End Testing Guide

[← Back to Documentation Index](../README.md) | [Setup Guide](./supervisor-ai-agent-setup.md) | [Troubleshooting](../operations/troubleshooting.md) | [Operations Runbook](../operations/operations-runbook.md)

---

## Test Environment

| Resource | Value |
|---|---|
| Supervisor Hotline | `<SUPERVISOR_PHONE_NUMBER>` |
| Allowlisted Phone | `<ALLOWLISTED_PHONE>` |
| Supervisor PIN | `<SUPERVISOR_PIN>` |
| Connect Instance | `<CONNECT_INSTANCE_ID>` |
| Supervisor AI Agent | `<SUPERVISOR_AI_AGENT_ID>` |
| Q Connect Assistant | `<ASSISTANT_ID>` |
| Supervisor Contact Flow | `<SUPERVISOR_CONTACT_FLOW_ID>` |
| Supervisor Conv AI Bot | `<SUPERVISOR_BOT_NAME>` |
| Customer Hotline | `<CUSTOMER_PHONE_NUMBER>` |
| Customer Contact Flow | `<CUSTOMER_CONTACT_FLOW_ID>` |
| Production Agent | `<PRODUCTION_AGENT_ID>` (SELF_SERVICE) |
| Customer Conv AI Bot | `<CUSTOMER_BOT_NAME>` |

---

## Adding Supervisor Phone Numbers

The phone allowlist is stored in Secrets Manager (not as a Lambda environment variable). Update it directly:

```bash
aws secretsmanager put-secret-value \
  --secret-id supervisor-ai-agent-pin \
  --secret-string '{"pin":"<SUPERVISOR_PIN>","allowlist":["+1AAAAAAAAAA","+1BBBBBBBBBB"]}' \
  --profile your-aws-profile --region us-east-1
```

No CDK redeployment needed. Changes take effect on the next Lambda cold start.

### Phone Number Format

- Must be E.164 format: `+<country code><number>` (e.g., `+12025551234`)
- No spaces, dashes, or parentheses
- US numbers: `+1` followed by 10 digits

---

## Pre-Test Verification

Run these before calling:

```bash
# 1. AI agent is ACTIVE with 10 tools (9 MCP + 1 RTC)
aws qconnect get-ai-agent \
  --assistant-id <ASSISTANT_ID> \
  --ai-agent-id <AI_AGENT_ID> \
  --query '{status:aiAgent.status,tools:length(aiAgent.configuration.orchestrationAIAgentConfiguration.toolConfigurations)}'
# Expected: {"status": "ACTIVE", "tools": 10}

# 2. Contact flow is active
aws connect describe-contact-flow \
  --instance-id <CONNECT_INSTANCE_ID> \
  --contact-flow-id <CONTACT_FLOW_ID> \
  --query 'ContactFlow.{State:State,Status:Status}'
# Expected: {"State": "ACTIVE", "Status": "PUBLISHED"}

# 3. Security profile has 9 tool modules
aws connect list-security-profile-flow-modules \
  --instance-id <CONNECT_INSTANCE_ID> \
  --security-profile-id <SECURITY_PROFILE_ID> \
  --query 'length(AllowedFlowModules)'
# Expected: 9

# 4. Verify your phone number is in the allowlist (stored in Secrets Manager)
aws secretsmanager get-secret-value \
  --secret-id supervisor-ai-agent-pin \
  --query 'SecretString' --output text
# Expected: JSON with "allowlist" array containing your phone number

# 5. Verify Lex bot SLR has Q in Connect permissions
aws iam list-role-policies \
  --role-name <LEX_BOT_SLR_ROLE_NAME>
# Expected: should include QInConnectAssistantPolicy

# 6. Open log tail in separate terminal
aws logs tail /aws/lambda/supervisor-ai-agent-manager --follow
```

## Test 1: Authentication — Phone Allowlist

**Action:** Call `<SUPERVISOR_PHONE_NUMBER>` from a NON-allowlisted phone number.

**Expected:** "Your phone number is not authorized to access this system. Goodbye." → Call disconnects.

**Pass criteria:** Call rejected, no PIN prompt.

## Test 2: Authentication — PIN Validation

**Action:** Call `<SUPERVISOR_PHONE_NUMBER>` from `<ALLOWLISTED_PHONE>`. Enter wrong PIN 3 times.

**Expected:** PIN rejected each time, call terminates after 3 failures.

**Pass criteria:** No access to AI agent after 3 wrong PINs.

## Test 3: Authentication — Successful Login

**Action:** Call `<SUPERVISOR_PHONE_NUMBER>` from `<ALLOWLISTED_PHONE>`. Enter PIN `<SUPERVISOR_PIN>`.

**Expected:** PIN accepted, connected to Supervisor AI Agent. Agent greets you conversationally.

**Pass criteria:** AI agent responds with greeting, ready for conversation.

## Test 4: MCP Tool — List Agents

**Action:** After authentication, say: "What agents are available?"

**Expected:**
- AI agent invokes `list_agents` MCP tool (check CloudWatch logs)
- AI agent responds with list of production agents
- Call does NOT end — conversation continues

**Pass criteria:** Tool invoked, results returned, conversation continues.

**CloudWatch verification:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/supervisor-ai-agent-manager \
  --filter-pattern '"list_agents"' \
  --start-time $(date -v-5M +%s000) \
  --query 'events[*].message' --output text | head -20
```

## Test 5: MCP Tool — List Agent Intents

**Action:** Say: "What capabilities does that agent have?"

**Expected:** AI agent invokes `list_agent_intents`, returns list of intents with enabled/disabled status.

**Pass criteria:** Intent list returned, conversation continues.

## Test 6: MCP Tool — Disable Intent

**Action:** Say: "Disable the change card PIN feature."

**Expected:**
- AI agent asks for confirmation
- After confirming, invokes `disable_intent` MCP tool
- Reports success with test results
- Conversation continues

**Pass criteria:** Intent disabled, backup created, test results reported.

## Test 7: MCP Tool — Enable Intent

**Action:** Say: "Enable the change card PIN feature."

**Expected:** AI agent confirms, invokes `enable_intent`, reports success.

**Pass criteria:** Intent re-enabled, test results reported.

## Test 8: MCP Tool — Update Agent Prompt (Full Outage)

**Action:** Say: "Payment processing is down. Account lookups and transfers are still working. Estimated recovery in 2 hours."

**Expected:**
- AI agent extracts outage info and explains planned changes
- Asks for confirmation
- After confirming, invokes `update_agent_prompt`
- Reports success with backup location and test results

**Pass criteria:** Prompt updated, backup created, tests passed.

## Test 9: MCP Tool — Restore Agent Prompt

**Action:** Say: "Restore the agent to its original prompt."

**Expected:** AI agent confirms, invokes `restore_agent_prompt`, reports success.

**Pass criteria:** Original prompt restored, tests passed.

## Test 10: Conversation Completion

**Action:** Say: "That's all, thank you."

**Expected:**
- AI agent invokes `Complete` Return to Control tool
- Contact flow plays "Thank you for using the Supervisor AI Agent. Goodbye."
- Call disconnects gracefully

**Pass criteria:** Call ends cleanly with thank you message.

## Test Results Template

| Test | Description | Result | Notes |
|---|---|---|---|
| 1 | Phone allowlist rejection | ☐ Pass ☐ Fail | |
| 2 | Wrong PIN 3x termination | ☐ Pass ☐ Fail | |
| 3 | Successful authentication | ☐ Pass ☐ Fail | |
| 4 | list_agents MCP tool | ☐ Pass ☐ Fail | |
| 5 | list_agent_intents MCP tool | ☐ Pass ☐ Fail | |
| 6 | disable_intent MCP tool | ☐ Pass ☐ Fail | |
| 7 | enable_intent MCP tool | ☐ Pass ☐ Fail | |
| 8 | update_agent_prompt MCP tool | ☐ Pass ☐ Fail | |
| 9 | restore_agent_prompt MCP tool | ☐ Pass ☐ Fail | |
| 10 | Complete → disconnect | ☐ Pass ☐ Fail | |

## Troubleshooting During Testing

| Symptom | Check |
|---|---|
| No ring / busy signal | Phone number associated with contact flow? `aws connect list-phone-numbers-v2` |
| Welcome message then disconnect | Missing "Connect assistant" block in flow, or Lex bot SLR missing Q in Connect permissions. See [Troubleshooting Guide](../operations/troubleshooting.md). |
| PIN prompt never appears | AI agent not set as default self-service, or `validate_pin` tool not in security profile |
| Silence after PIN accepted | Contact Lens real-time not enabled in Set recording block |
| Tool not invoked | Check CloudWatch logs for Lambda. Check security profile has all 9 tool modules. |
| Call drops mid-conversation | MCP tool timeout (30s limit). Check Lambda duration in CloudWatch. |
| "Complete" doesn't end call | Contact flow checking `$.Lex.SessionAttributes.Tool` = `Complete`? |

For detailed troubleshooting steps, see the [Troubleshooting Guide](../operations/troubleshooting.md).

---

## Customer Flow Tests

### Test 11: Customer Flow — Normal Operations

**Action:** Call `<CUSTOMER_PHONE_NUMBER>` from any phone.

**Expected:** "Welcome to our customer service line. How can I help you today?" → AI agent responds conversationally.

**Pass criteria:** Welcome message plays, AI agent engages.

### Test 12: Customer Flow — Banking Queries

**Action:** After connecting, say: "What's my account balance?"

**Expected:** AI agent responds conversationally about balance inquiries.

**Pass criteria:** Normal conversational response, no outage messaging.

### Test 13: Customer Flow — PIN Change (Normal)

**Action:** Say: "I want to change my PIN"

**Expected:** AI agent responds normally about PIN change capability.

**Pass criteria:** Normal response, no "unavailable" messaging.

### Test 14: Customer Flow — Conversation End

**Action:** Say: "That's all, thank you"

**Expected:** "Thank you for calling. Goodbye." → Call disconnects.

**Pass criteria:** Graceful disconnect.

### Test 15: Supervisor Outage Loop — Disable Intent

**Action:**
1. Call `<SUPERVISOR_PHONE_NUMBER>` from `<ALLOWLISTED_PHONE>`
2. Enter PIN `<SUPERVISOR_PIN>`
3. Say: "Disable the change card PIN feature for the production agent"
4. Confirm

**Expected:** Supervisor AI agent confirms intent disabled, reports test results.

**Pass criteria:** Intent disabled successfully.

### Test 16: Customer Flow — Disabled Intent Reflected

**Action:** Call `<CUSTOMER_PHONE_NUMBER>`, say: "I want to change my PIN"

**Expected:** AI agent says the PIN change capability is "temporarily unavailable" or similar.

**Pass criteria:** Outage messaging reflected in customer experience.

### Test 17: Customer Flow — Other Intents Still Work

**Action:** Say: "What's my account balance?"

**Expected:** Normal conversational response (not affected by PIN disable).

**Pass criteria:** Unrelated capabilities still work normally.

### Test 18: Supervisor Outage Loop — Restore

**Action:**
1. Call `<SUPERVISOR_PHONE_NUMBER>` from `<ALLOWLISTED_PHONE>`
2. Enter PIN `<SUPERVISOR_PIN>`
3. Say: "Restore all capabilities for the production agent"
4. Confirm

**Expected:** Supervisor AI agent confirms all capabilities restored.

**Pass criteria:** Restoration successful.

### Test 19: Customer Flow — Normal After Restore

**Action:** Call `<CUSTOMER_PHONE_NUMBER>`, say: "I want to change my PIN"

**Expected:** Normal conversational response (PIN change available again).

**Pass criteria:** Customer experience back to normal.

## Customer Flow Test Results

| Test | Description | Result | Notes |
|---|---|---|---|
| 11 | Customer flow welcome message | ☐ Pass ☐ Fail | |
| 12 | Banking query (balance) | ☐ Pass ☐ Fail | |
| 13 | PIN change (normal) | ☐ Pass ☐ Fail | |
| 14 | Conversation end / disconnect | ☐ Pass ☐ Fail | |
| 15 | Supervisor disables PIN intent | ☐ Pass ☐ Fail | |
| 16 | Customer sees disabled intent | ☐ Pass ☐ Fail | |
| 17 | Other intents still work | ☐ Pass ☐ Fail | |
| 18 | Supervisor restores all | ☐ Pass ☐ Fail | |
| 19 | Customer back to normal | ☐ Pass ☐ Fail | |

## Troubleshooting Customer Flow

| Symptom | Check |
|---|---|
| Welcome message then disconnect | Missing Connect assistant block, or Lex bot SLR missing Q in Connect permissions |
| AI agent not responding | Verify Contact Lens real-time analytics enabled in recording block |
| Supervisor changes not reflected | Changes apply to new calls only — hang up and call again |
| Tool check not working | Customer flow uses `Tool=Complete` check (same as supervisor flow) since the production agent is ORCHESTRATION type |

For detailed troubleshooting, see the [Troubleshooting Guide](../operations/troubleshooting.md).
