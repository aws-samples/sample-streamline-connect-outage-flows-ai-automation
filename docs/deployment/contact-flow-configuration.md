# Amazon Connect Contact Flow Configuration Guide

## Overview

The Amazon Connect Contact Flow is automatically deployed via CDK as part of the Supervisor AI Agent infrastructure. This guide explains the flow logic, how it works, and how to customize it if needed.

## Contact Flow Architecture

The Supervisor Contact Flow orchestrates the complete authentication and routing workflow:

```
Incoming Call
    ↓
Set Recording Behavior (Enable)
    ↓
Extract Caller Phone Number
    ↓
Invoke Lambda (Phone Validation)
    ↓
Check Phone Validation Result
    ├─ Unauthorized → Play Message → Disconnect
    └─ Authorized → Continue
        ↓
    Get Customer Input (Lex PIN Bot)
        ↓
    Check PIN Validation Result
        ├─ Failed → Play Message → Disconnect
        └─ Success → Continue
            ↓
        Connect to Amazon Q (Supervisor AI Agent)
            ↓
        Play Thank You Message
            ↓
        Disconnect
```

## Flow Blocks

### Block 1: Set Recording Behavior

**Type**: Update Contact Recording Behavior  
**Purpose**: Enable call recording for compliance and audit

**Configuration**:
- Recording Behavior: Enable
- Recording Participant: Both (customer and agent)

**Why**: All supervisor sessions must be recorded for audit and compliance purposes.

---

### Block 2: Set Contact Attributes

**Type**: Update Contact Attributes  
**Purpose**: Extract caller phone number from contact data

**Configuration**:
- Attribute Key: `CallerPhoneNumber`
- Attribute Value: `$.CustomerEndpoint.Address`

**Why**: The phone number is needed for allowlist validation and audit logging.

---

### Block 3: Invoke Lambda (Phone Validation)

**Type**: Invoke AWS Lambda Function  
**Purpose**: Validate caller phone number against allowlist

**Configuration**:
- Lambda Function: Authentication Lambda ARN (from CDK output)
- Invocation Timeout: 8 seconds
- Invocation Attributes:
  - `operation`: `validate_phone`
  - `phoneNumber`: `$.Attributes.CallerPhoneNumber`
- Response Validation: JSON

**Lambda Response**:
```json
{
  "authenticated": true,
  "phoneNumber": "+1-555-0100",
  "timestamp": "2025-02-11T10:30:00Z"
}
```

**Error Handling**: On Lambda error, route to Disconnect block

---

### Block 4: Check Contact Attributes (Phone Result)

**Type**: Check Contact Attributes  
**Purpose**: Branch based on phone validation result

**Configuration**:
- Comparison Value: `$.External.authenticated`
- Condition: Equals `true`
  - If True → Continue to Lex Bot
  - If False → Play Unauthorized Message

**Why**: Only authorized phone numbers should proceed to PIN authentication.

---

### Block 5: Play Prompt - Unauthorized

**Type**: Play Prompt  
**Purpose**: Inform caller they are not authorized

**Configuration**:
- Text: "Your phone number is not authorized to access this system. Goodbye."
- Next Action: Disconnect

---

### Block 6: Get Customer Input (Lex Bot)

**Type**: Get Customer Input  
**Purpose**: Collect and validate 6-digit PIN via Lex bot

**Configuration**:
- Lex Bot: SupervisorPinBot
- Lex V2 Bot Alias ARN: (from CDK output)
- Initial Prompt: "Please enter your 6-digit PIN for authentication."
- Session Attributes: None (bot manages session)

**Lex Integration**:
- Bot collects PIN via voice or DTMF
- Bot invokes Authentication Lambda for validation
- Bot returns intent name and result

**Error Handling**: On Lex error, route to Disconnect block

---

### Block 7: Check Contact Attributes (PIN Result)

**Type**: Check Contact Attributes  
**Purpose**: Branch based on PIN validation result

**Configuration**:
- Comparison Value: `$.Lex.IntentName`
- Condition: Equals `AuthenticateUser`
  - If True → Continue to Supervisor AI Agent
  - If False → Play Authentication Failed Message

**Why**: Only successful PIN authentication should grant access to the Supervisor AI Agent.

---

### Block 8: Play Prompt - Authentication Failed

**Type**: Play Prompt  
**Purpose**: Inform caller authentication failed

**Configuration**:
- Text: "Authentication failed. Goodbye."
- Next Action: Disconnect

---

### Block 9: Connect to Amazon Q (Supervisor AI Agent)

**Type**: Connect to Amazon Q in Connect  
**Purpose**: Connect authenticated caller to Supervisor AI Agent

**Configuration**:
- Q Connect Assistant ID: (from CDK parameter)
- AI Agent ID: (to be added after agent creation)
- Contact Attributes:
  - `CallerPhoneNumber`: `$.Attributes.CallerPhoneNumber`

**Why**: The Supervisor AI Agent conducts the natural language conversation for outage management.

**Note**: The AI Agent ID must be added manually after creating the Supervisor AI Agent (Task 19.3).

**Error Handling**: On Q Connect error, route to Disconnect block

---

### Block 10: Play Prompt - Thank You

**Type**: Play Prompt  
**Purpose**: Thank caller before disconnecting

**Configuration**:
- Text: "Thank you for using the supervisor hotline. Goodbye."
- Next Action: Disconnect

---

### Block 11: Disconnect

**Type**: Disconnect / Hang Up  
**Purpose**: End the call

**Configuration**: None

---

## CDK-Deployed Configuration

The Contact Flow is automatically created with the following settings:

### Basic Settings

- **Flow Name**: `SupervisorAIAgentFlow`
- **Description**: Contact flow for Supervisor AI Agent with phone and PIN authentication
- **Type**: `CONTACT_FLOW`
- **State**: `ACTIVE`
- **Instance ARN**: From CDK parameter `ConnectInstanceId`

### Lambda Permissions

The CDK stack automatically grants Amazon Connect permission to invoke the Authentication Lambda:

```typescript
authLambda.addPermission('AllowConnectInvoke', {
  principal: new iam.ServicePrincipal('connect.amazonaws.com'),
  action: 'lambda:InvokeFunction',
  sourceArn: `arn:aws:connect:${region}:${account}:instance/${instanceId}`,
});
```

## Post-Deployment Configuration

### Step 1: Add AI Agent ID to Contact Flow

After creating the Supervisor AI Agent (Task 19.3), update the Contact Flow:

1. Navigate to Amazon Connect console
2. Select your instance
3. Go to **Routing** → **Contact Flows**
4. Find `SupervisorAIAgentFlow`
5. Click **Edit**
6. Find the **Connect to Amazon Q** block (Block 9)
7. Add the AI Agent ID from CDK outputs
8. Click **Save** and **Publish**

**AI Agent ID Location**:
```bash
aws cloudformation describe-stacks \
  --stack-name SupervisorAIAgentStack \
  --query 'Stacks[0].Outputs[?OutputKey==`SupervisorAIAgentId`].OutputValue' \
  --output text \
  --profile your-aws-profile \
  --region us-east-1
```

### Step 2: Associate Flow with Phone Number

1. In Amazon Connect console, go to **Routing** → **Phone Numbers**
2. Select the supervisor hotline phone number
3. In **Contact Flow / IVR**, select `SupervisorAIAgentFlow`
4. Click **Save**

## Customization Options

### Changing Recording Behavior

To disable recording or record only customer:

```json
{
  "Identifier": "1",
  "Type": "UpdateContactRecordingBehavior",
  "Parameters": {
    "RecordingBehaviorOption": "Disable",  // or "Enable"
    "RecordingParticipantOption": "Customer"  // or "Agent" or "Both"
  }
}
```

### Adjusting Lambda Timeout

To allow more time for phone validation:

```json
{
  "Parameters": {
    "InvocationTimeLimitSeconds": "15"  // Up to 20 seconds
  }
}
```

### Customizing Prompts

To change the unauthorized message:

```json
{
  "Parameters": {
    "Text": "Access denied. Your phone number is not on the authorized list. Please contact your administrator."
  }
}
```

### Adding Error Handling

To add custom error handling for Lambda failures:

```json
{
  "Transitions": {
    "NextAction": "4",
    "Errors": [
      {
        "ErrorType": "NoMatchingError",
        "NextAction": "12"  // Custom error handler block
      }
    ]
  }
}
```

### Adding Contact Lens Analytics

To enable Contact Lens for sentiment analysis and transcription:

1. In Amazon Connect console, enable Contact Lens for your instance
2. Contact Lens will automatically analyze recorded calls
3. View analytics in **Analytics and optimization** → **Contact Lens**

## Flow JSON Template

The complete flow JSON is available in the CDK stack. To export it:

```bash
aws connect describe-contact-flow \
  --instance-id <INSTANCE_ID> \
  --contact-flow-id <FLOW_ID> \
  --profile your-aws-profile \
  --region us-east-1 \
  --query 'ContactFlow.Content' \
  --output text > contact-flow.json
```

## Testing the Contact Flow

### Test in Connect Console

1. Navigate to Amazon Connect console
2. Select your instance
3. Go to **Routing** → **Contact Flows**
4. Find `SupervisorAIAgentFlow`
5. Click **Test**
6. Simulate different scenarios:
   - Authorized phone number
   - Unauthorized phone number
   - Correct PIN
   - Incorrect PIN

### Test via Phone

1. Call the supervisor hotline number
2. Verify recording announcement (if configured)
3. Enter PIN when prompted
4. Verify connection to Supervisor AI Agent
5. Complete a test conversation
6. Verify call recording in Amazon Connect

### Monitor Flow Execution

View flow execution logs in CloudWatch:

```bash
aws logs tail /aws/connect/<INSTANCE_ID> --follow \
  --profile your-aws-profile \
  --region us-east-1
```

## Troubleshooting

### Issue: Flow doesn't invoke Lambda

**Symptoms**: Phone validation doesn't occur, flow disconnects immediately

**Solution**:
1. Verify Lambda permissions are configured correctly
2. Check Lambda ARN in flow configuration
3. Review CloudWatch Logs for Lambda invocation errors

```bash
# Check Lambda permissions
aws lambda get-policy \
  --function-name supervisor-ai-agent-auth \
  --profile your-aws-profile \
  --region us-east-1

# Check flow configuration
aws connect describe-contact-flow \
  --instance-id <INSTANCE_ID> \
  --contact-flow-id <FLOW_ID> \
  --profile your-aws-profile \
  --region us-east-1
```

---

### Issue: Lex bot doesn't respond

**Symptoms**: Flow hangs after phone validation, no PIN prompt

**Solution**:
1. Verify Lex bot alias ARN is correct in flow
2. Check that Lex bot is published and active
3. Verify Lex bot has Lambda fulfillment configured

```bash
# Check Lex bot status
aws lexv2-models describe-bot \
  --bot-id <BOT_ID> \
  --profile your-aws-profile \
  --region us-east-1
```

---

### Issue: Amazon Q connection fails

**Symptoms**: Flow disconnects after PIN authentication

**Solution**:
1. Verify AI Agent ID is added to flow (Block 9)
2. Check that Supervisor AI Agent is published
3. Verify Q Connect assistant ID is correct

```bash
# Check AI Agent status
aws qconnect get-ai-agent \
  --assistant-id <ASSISTANT_ID> \
  --ai-agent-id <AGENT_ID> \
  --profile your-aws-profile \
  --region us-east-1
```

---

### Issue: Recording not working

**Symptoms**: Calls not recorded, no recordings in S3

**Solution**:
1. Verify recording is enabled in flow (Block 1)
2. Check that recording storage is configured in Connect instance
3. Verify S3 bucket permissions for recording storage

---

### Issue: Contact attributes not set

**Symptoms**: Lambda receives empty phone number, audit logs missing caller info

**Solution**:
1. Verify Block 2 is configured correctly
2. Check that `$.CustomerEndpoint.Address` is available
3. Review flow execution logs for attribute errors

## Security Considerations

### Call Recording

- All supervisor calls are recorded for audit and compliance
- Recordings are encrypted at rest in S3
- Recordings are retained according to instance configuration
- Access to recordings is controlled via IAM policies

### Authentication Flow

- Two-factor authentication: phone allowlist + PIN
- Phone validation occurs before PIN prompt
- Failed authentication attempts are logged
- Calls are terminated after 3 failed PIN attempts

### Contact Attributes

- Caller phone number is extracted and logged
- Phone number is passed to Lambda for validation
- Phone number is passed to Supervisor AI Agent for audit
- No sensitive data (PINs) is stored in contact attributes

### Lambda Integration

- Lambda functions are invoked with least privilege permissions
- Lambda invocations are logged to CloudWatch
- Lambda errors are handled gracefully
- Lambda timeouts prevent flow hangs

## CDK Stack Outputs

After deploying the CDK stack, retrieve the flow information:

```bash
aws cloudformation describe-stacks \
  --stack-name SupervisorAIAgentStack \
  --query 'Stacks[0].Outputs[?OutputKey==`SupervisorContactFlowId`]' \
  --profile your-aws-profile \
  --region us-east-1
```

**Output**:
- `SupervisorContactFlowId`: Contact Flow ARN for phone number association

## Related Documentation

- [Lex PIN Bot Configuration](./lex-pin-bot-configuration.md)
- [Supervisor AI Agent Setup](./supervisor-ai-agent-setup.md)
- [Authentication Lambda Implementation](../../lambda/auth/README.md)
- [Amazon Connect Administrator Guide](https://docs.aws.amazon.com/connect/latest/adminguide/)

## Support

For issues with the Contact Flow:
1. Test flow in Connect console before testing via phone
2. Check CloudWatch Logs for flow execution details
3. Review Lambda logs for authentication errors
4. Verify all ARNs and IDs are correct in flow configuration
5. Contact AWS Support for Connect-specific issues
