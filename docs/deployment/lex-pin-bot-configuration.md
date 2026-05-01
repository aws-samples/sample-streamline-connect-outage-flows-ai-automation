# Amazon Lex V2 PIN Bot Configuration Guide

## Overview

The Amazon Lex V2 PIN Bot is automatically deployed via CDK as part of the Supervisor AI Agent infrastructure. This guide explains the bot configuration, how it works, and how to customize it if needed.

## Bot Architecture

The PIN Bot is a simple conversational bot with two intents:

1. **AuthenticateUser Intent**: Collects and validates the 6-digit PIN
2. **FallbackIntent**: Handles unrecognized input (required by Lex V2)

### Authentication Flow

```
User Call → Contact Flow → Lex PIN Bot
                              ↓
                    Prompt for 6-digit PIN
                              ↓
                    User enters PIN (voice or DTMF)
                              ↓
                    Invoke Authentication Lambda
                              ↓
                    Return success/failure to Contact Flow
```

## CDK-Deployed Configuration

The PIN Bot is automatically created with the following configuration:

### Basic Settings

- **Bot Name**: `SupervisorPinBot`
- **Description**: PIN authentication bot for supervisor access
- **Locale**: `en_US` (English - United States)
- **Voice**: Joanna (Amazon Polly voice)
- **Session Timeout**: 5 minutes (300 seconds)
- **NLU Confidence Threshold**: 0.40

### IAM Role

The bot uses a dedicated IAM role (`LexBotRole`) with permissions to:
- Invoke the Authentication Lambda function
- Access CloudWatch Logs for bot conversation logs

### Bot Alias

- **Alias Name**: `Production`
- **Version**: `DRAFT` (automatically updated with bot changes)
- **Lambda Integration**: Connected to Authentication Lambda via code hook

## Intent Configuration

### AuthenticateUser Intent

**Purpose**: Collect and validate the 6-digit PIN

**Sample Utterances**:
- "My PIN is {PIN}"
- "{PIN}"
- "The PIN is {PIN}"

**Slots**:
- **Slot Name**: `PIN`
- **Slot Type**: `AMAZON.Number`
- **Constraint**: Required
- **Prompt**: "Please enter your 6-digit PIN."
- **Max Retries**: 3

**Fulfillment**:
- **Code Hook**: Enabled
- **Lambda Function**: Authentication Lambda
- **Interface Version**: 1.0

**Retry Logic**:
The bot allows up to 3 attempts to enter the PIN. After 3 failed attempts, the Authentication Lambda terminates the call.

### FallbackIntent

**Purpose**: Handle unrecognized input

**Response**: "I'm sorry, I didn't understand that. Please enter your 6-digit PIN."

This intent is required by Amazon Lex V2 and ensures the bot can gracefully handle unexpected input.

## Lambda Integration

### Authentication Lambda Fulfillment

The bot invokes the Authentication Lambda function for PIN validation:

**Request Format** (Lex Event):
```json
{
  "sessionId": "session-uuid",
  "inputTranscript": "123456",
  "interpretations": [
    {
      "intent": {
        "name": "AuthenticateUser",
        "slots": {
          "PIN": {
            "value": {
              "interpretedValue": "123456"
            }
          }
        }
      }
    }
  ],
  "sessionState": {
    "intent": {
      "name": "AuthenticateUser",
      "state": "InProgress"
    }
  }
}
```

**Response Format** (Lex Response):
```json
{
  "sessionState": {
    "dialogAction": {
      "type": "Close"
    },
    "intent": {
      "name": "AuthenticateUser",
      "state": "Fulfilled"  // or "Failed"
    }
  },
  "messages": [
    {
      "contentType": "PlainText",
      "content": "Authentication successful. Connecting you to the supervisor agent."
    }
  ]
}
```

### Lambda Permissions

The CDK stack automatically grants the Lex bot permission to invoke the Authentication Lambda:

```typescript
authLambda.addPermission('AllowLexInvoke', {
  principal: new iam.ServicePrincipal('lexv2.amazonaws.com'),
  action: 'lambda:InvokeFunction',
  sourceArn: `arn:aws:lex:${region}:${account}:bot-alias/${botId}/*`,
});
```

## Customization Options

### Changing the Voice

To use a different Amazon Polly voice, modify the `voiceSettings` in the CDK stack:

```typescript
voiceSettings: {
  voiceId: 'Matthew',  // Male voice
  // Other options: Joanna, Kendra, Kimberly, Salli, Joey, Justin, Matthew
},
```

### Adjusting Session Timeout

To change how long the bot waits for user input:

```typescript
idleSessionTtlInSeconds: 600,  // 10 minutes instead of 5
```

### Modifying Prompts

To change the PIN prompt message, update the `promptSpecification`:

```typescript
promptSpecification: {
  messageGroupsList: [
    {
      message: {
        plainTextMessage: {
          value: 'For security, please enter your six digit PIN code.',
        },
      },
    },
  ],
  maxRetries: 3,
},
```

### Adding SSML for Better Voice Experience

For more natural-sounding prompts, use SSML:

```typescript
message: {
  ssmlMessage: {
    value: '<speak>Please enter your <emphasis level="strong">six digit</emphasis> PIN.</speak>',
  },
},
```

### Changing Retry Limit

To allow more or fewer PIN attempts:

```typescript
maxRetries: 5,  // Allow 5 attempts instead of 3
```

**Note**: The Authentication Lambda also enforces a 3-attempt limit. If you change the bot's retry limit, update the Lambda function accordingly.

## Testing the PIN Bot

### Test in Lex Console

1. Navigate to Amazon Lex V2 console
2. Select `SupervisorPinBot`
3. Click **Test** to open the test interface
4. Try these test scenarios:

**Successful Authentication**:
```
Bot: "Please enter your 6-digit PIN."
You: "123456"
Bot: "Authentication successful. Connecting you to the supervisor agent."
```

**Invalid PIN Format**:
```
Bot: "Please enter your 6-digit PIN."
You: "abc"
Bot: "I'm sorry, I didn't understand that. Please enter your 6-digit PIN."
```

**Failed Authentication**:
```
Bot: "Please enter your 6-digit PIN."
You: "999999"
Bot: "Incorrect PIN. Please try again."
```

### Test via Phone

1. Call the supervisor hotline number
2. Complete phone number authentication
3. When prompted, enter your 6-digit PIN
4. Verify authentication succeeds or fails appropriately

### Monitor Bot Conversations

View bot conversation logs in CloudWatch:

```bash
aws logs tail /aws/lex/SupervisorPinBot --follow \
  --profile your-aws-profile \
  --region us-east-1
```

## Troubleshooting

### Issue: Bot doesn't invoke Lambda

**Symptoms**: PIN validation doesn't occur, bot doesn't respond after PIN entry

**Solution**:
1. Verify Lambda permissions are configured correctly
2. Check that the bot alias has the code hook configured
3. Review CloudWatch Logs for Lambda invocation errors

```bash
# Check Lambda permissions
aws lambda get-policy \
  --function-name supervisor-ai-agent-auth \
  --profile your-aws-profile \
  --region us-east-1

# Check bot alias configuration
aws lexv2-models describe-bot-alias \
  --bot-id <BOT_ID> \
  --bot-alias-id <ALIAS_ID> \
  --profile your-aws-profile \
  --region us-east-1
```

---

### Issue: Bot doesn't recognize PIN input

**Symptoms**: Bot keeps asking for PIN even after user provides it

**Solution**:
1. Verify the `PIN` slot is configured with `AMAZON.Number` type
2. Check that slot constraint is set to `Required`
3. Ensure sample utterances include `{PIN}` placeholder

---

### Issue: Authentication always fails

**Symptoms**: All PIN attempts fail even with correct PIN

**Solution**:
1. Verify the supervisor PIN is correctly stored in Secrets Manager
2. Check Authentication Lambda logs for errors
3. Verify Lambda has permission to read from Secrets Manager

```bash
# Check secret value
aws secretsmanager get-secret-value \
  --secret-id supervisor-ai-agent-pin \
  --profile your-aws-profile \
  --region us-east-1

# Check Lambda logs
aws logs tail /aws/lambda/supervisor-ai-agent-auth --follow \
  --profile your-aws-profile \
  --region us-east-1
```

---

### Issue: Bot times out during PIN entry

**Symptoms**: Bot disconnects before user can enter PIN

**Solution**:
1. Increase `idleSessionTtlInSeconds` in bot configuration
2. Verify Contact Flow timeout settings
3. Check for network latency issues

## Security Considerations

### PIN Storage

- The supervisor PIN is stored in AWS Secrets Manager with KMS encryption
- The PIN is never logged or exposed in bot conversation logs
- Lambda retrieves the PIN at runtime using the Secrets Lambda Extension

### Retry Limits

- The bot allows 3 retry attempts for PIN entry
- The Authentication Lambda enforces an additional 3-attempt limit
- After 3 failed attempts, the call is terminated

### Audit Logging

- All authentication attempts are logged to CloudWatch with:
  - Timestamp
  - Phone number (last 4 digits only)
  - Result (success/failure)
  - Request ID for tracing

### Data Privacy

- Bot conversations are encrypted in transit (TLS)
- Conversation logs are encrypted at rest in CloudWatch
- No sensitive data (full phone numbers, PINs) is stored in logs

## CDK Stack Outputs

After deploying the CDK stack, retrieve the bot information:

```bash
aws cloudformation describe-stacks \
  --stack-name SupervisorAIAgentStack \
  --query 'Stacks[0].Outputs[?OutputKey==`PinBotId` || OutputKey==`PinBotAliasId` || OutputKey==`PinBotAliasArn`]' \
  --profile your-aws-profile \
  --region us-east-1
```

**Outputs**:
- `PinBotId`: Bot ID for use in Contact Flow
- `PinBotAliasId`: Alias ID for production use
- `PinBotAliasArn`: Full ARN for IAM policies and integrations

## Integration with Contact Flow

The PIN Bot is integrated into the Contact Flow via the **Get Customer Input** block:

1. After phone number validation succeeds
2. Contact Flow invokes the PIN Bot
3. Bot collects and validates PIN
4. Bot returns result to Contact Flow
5. Contact Flow checks authentication result
6. If successful, connects to Supervisor AI Agent
7. If failed, terminates call

For complete Contact Flow configuration, see [Contact Flow Setup Guide](./contact-flow-setup.md).

## Related Documentation

- [Authentication Lambda Implementation](../../lambda/auth/README.md)
- [Contact Flow Setup Guide](./contact-flow-setup.md)
- [Supervisor AI Agent Setup](./supervisor-ai-agent-setup.md)
- [Amazon Lex V2 Developer Guide](https://docs.aws.amazon.com/lexv2/latest/dg/)

## Support

For issues with the PIN Bot:
1. Check CloudWatch Logs for bot conversations
2. Review Authentication Lambda logs
3. Verify IAM permissions and Lambda integration
4. Test bot in Lex console before testing via phone
5. Contact AWS Support for Lex-specific issues
