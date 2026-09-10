# Troubleshooting Guide

[← Back to README](../../README.md) | [Operations Runbook](./operations-runbook.md)

## Deployment Issues

### Stack DELETE_FAILED — Contact Flow Referenced by Phone Number

- **Symptom**: CDK stack delete fails with `Contact flow Id is referenced in the following resources`
- **Cause**: Phone number is still associated with the contact flow
- **Fix**: Disassociate the phone number first, then retry delete:

```bash
aws connect disassociate-phone-number-contact-flow \
  --instance-id <ID> \
  --phone-number-id <ID>
```

### Stack Deploy — Module Not Found

- **Symptom**: `Cannot find module '../lib/supervisor-ai-agent-stack'`
- **Cause**: TypeScript not compiled
- **Fix**: Run `npm run build` in the `cdk/` directory before `cdk deploy`

## Contact Flow Issues

### Call Disconnects After Welcome Message — Missing Q in Connect Session

- **Symptom**: Caller hears welcome prompt then gets disconnected
- **Error in logs**: `Amazon Lex needs active session for Q In Connect. Please provide valid session attribute x-amz-lex:q-in-connect:session-arn`
- **Cause**: Missing "Connect assistant" block in the contact flow before the Get Customer Input block
- **Fix**: Add a "Connect assistant" block (under the Integrate category) before the Get Customer Input block. Configure it with the Q in Connect assistant ARN. Also ensure the Set recording block has Contact Lens real-time analytics enabled.

### Call Disconnects After Welcome Message — Lex Bot Cannot Access Q in Connect

- **Symptom**: Caller hears welcome prompt then gets disconnected
- **Error in logs**: `Invalid Bot Configuration: Amazon Lex could not access your Q In Connect Assistant`
- **Cause**: The Lex bot's Service Linked Role (SLR) is missing Q in Connect permissions (QInConnectAssistantPolicy)
- **Fix**: Go to the Amazon Lex console (not Connect admin), open the bot, navigate to the QInConnectIntent, re-save and rebuild. This triggers Lex to update the SLR with the required `wisdom:CreateSession`, `wisdom:GetAssistant`, `wisdom:SendMessage`, `wisdom:GetNextMessage` permissions.

### Phone Number Not Associated with Contact Flow

- **Symptom**: Call immediately disconnects or gets busy signal
- **Cause**: Phone number not associated with the contact flow (e.g., after stack redeployment)
- **Fix**:

```bash
aws connect associate-phone-number-contact-flow \
  --instance-id <ID> \
  --contact-flow-id <ID> \
  --phone-number-id <ID>
```

### 'Connect assistant' Block Not Visible in Flow Designer

- **Symptom**: Cannot find the Amazon Q in Connect block in the flow designer
- **Cause**: The block is named "Connect assistant" (not "Amazon Q in Connect") and is under the Integrate category
- **Fix**: Look under Integrate in the block palette. If still not visible, ensure Contact Lens is enabled on the instance and Q in Connect assistant is associated with the instance.

## AI Agent Issues

### MCP Tool Does Not Allow Overriding Input Schema

- **Symptom**: `ValidationException: MCP tool 'X' does not allow overriding input schema`
- **Cause**: MCP tools get their description and inputSchema from the flow module definition, not the agent config
- **Fix**: Remove `description` and `inputSchema` fields from MCP tool entries in the agent config JSON. Only `RETURN_TO_CONTROL` tools (like Complete) allow inputSchema in the agent config.

### validate_pin Tool Not Invoked

- **Symptom**: AI agent doesn't ask for PIN after connecting
- **Cause**: `validate_pin` tool not added to the AI agent, or not in the security profile
- **Fix**: Ensure the tool module is in the security profile AND added to the AI agent's tool configurations. Also verify the AI agent is set as the default self-service agent.

## Monitoring

### Where to Find Logs

| Component | Log Group |
|-----------|-----------|
| Contact flow | `/aws/connect/<instance-name>` |
| Auth Lambda | `/aws/lambda/supervisor-ai-agent-auth` |
| Agent Manager Lambda | `/aws/lambda/supervisor-ai-agent-manager` |
| Restore Lambda | `/aws/lambda/supervisor-ai-agent-restore` |

### Useful Log Queries

```bash
# Recent contact flow errors
aws logs filter-log-events \
  --log-group-name /aws/connect/<instance-name> \
  --filter-pattern 'Error' \
  --start-time $(date -v-30M +%s000)

# Recent auth Lambda invocations
aws logs filter-log-events \
  --log-group-name /aws/lambda/supervisor-ai-agent-auth \
  --filter-pattern 'validate_pin' \
  --start-time $(date -v-30M +%s000)
```
