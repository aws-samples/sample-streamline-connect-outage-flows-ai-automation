# Operations Runbook: Supervisor AI Agent for Amazon Connect Outage Management

[← Back to Documentation Index](../README.md) | [Architecture](../architecture/system-architecture.md) | [Deployment](../deployment/cdk-deployment.md) | [API Reference](../api/lambda-functions.md)

---

## Overview

This runbook provides operational procedures for using and maintaining the Supervisor AI Agent system. It covers daily operations, troubleshooting, monitoring, and emergency procedures.

## Table of Contents

1. [System Access](#system-access)
2. [Using the Supervisor Hotline](#using-the-supervisor-hotline)
3. [Handling Authentication Failures](#handling-authentication-failures)
4. [Verifying AI Agent Updates](#verifying-ai-agent-updates)
5. [Restoring AI Agents](#restoring-ai-agents)
6. [Monitoring System Health](#monitoring-system-health)
7. [AI Prompt Versioning and Visibility Status](#ai-prompt-versioning-and-visibility-status)
8. [Troubleshooting Common Issues](#troubleshooting-common-issues)
9. [Emergency Procedures](#emergency-procedures)
10. [Maintenance Tasks](#maintenance-tasks)

---

## System Access

### Prerequisites

- **Authorized Phone Number**: Your phone number must be in the supervisor allowlist
- **6-Digit PIN**: You must know the current supervisor PIN
- **Supervisor Hotline Number**: Contact your administrator for the hotline phone number

### Access Levels

**Operations Manager**: Can call the supervisor hotline to update AI agent prompts
**System Administrator**: Has AWS Console access to manage infrastructure and configurations
**DevOps Engineer**: Has CloudWatch access for monitoring and troubleshooting

---

## Using the Supervisor Hotline

### Full Outage Mode: Updating AI Agent Prompts

Use this mode when entire services or multiple capabilities are unavailable.

#### Step-by-Step Procedure

**Step 1: Initiate Call**
1. Call the supervisor hotline from your authorized phone number
2. Wait for the system to validate your phone number (automatic)
3. If validation fails, you'll hear "Unauthorized access" and the call will end

**Step 2: Enter PIN**
1. When prompted, enter your 6-digit PIN using the phone keypad
2. You have 3 attempts to enter the correct PIN
3. After 3 failed attempts, the call will terminate

**Step 3: Describe the Outage**
1. The Supervisor AI Agent will greet you and ask about the situation
2. Describe the outage in natural language, including:
   - Which services are unavailable
   - Which services are still working
   - Estimated recovery time (if known)

**Example:**
> "Payment processing is down. Account inquiries and transfers are still working. We expect recovery in about 2 hours."

**Step 4: Review Proposed Changes**
1. The Supervisor AI Agent will explain what changes it will make:
   - Current agent configuration
   - Services that will be marked unavailable
   - Services that will remain available
   - Estimated recovery timeframe
2. Listen carefully to ensure the changes are correct

**Step 5: Confirm or Cancel**
1. If the changes are correct, say "Yes" or "Confirm" to proceed
2. If the changes are incorrect, say "No" or "Cancel" to abort
3. You can also ask clarifying questions before confirming

**Step 6: Wait for Completion**
1. The system will:
   - Back up the current prompt
   - Generate the updated prompt
   - Deploy the update
   - Run automated tests
2. This typically takes 30-60 seconds

**Step 7: Receive Confirmation**
1. The Supervisor AI Agent will confirm:
   - Update completed successfully
   - Number of tests executed
   - Test results (passed/failed)
   - Sample responses from the updated agent
   - Backup location
2. Note the backup location for potential rollback

**Step 8: End Call**
1. Ask if you need any additional actions
2. End the call when finished

### Intent-Level Mode: Managing Specific Capabilities

Use this mode to selectively disable/enable specific agent capabilities.

#### Listing Agent Capabilities

**Step 1-2**: Same as Full Outage Mode (call and authenticate)

**Step 3: Request Capability List**
Say: "What capabilities does the agent have?" or "List the agent's intents"

**Step 4: Review the List**
The Supervisor AI Agent will list all available intents with their current status:
- Intent name (e.g., "check balance", "transfer funds", "change PIN")
- Description
- Current status (enabled or disabled)

#### Disabling a Specific Capability

**Step 1-2**: Same as Full Outage Mode (call and authenticate)

**Step 3: Request to Disable**
Say: "Disable the [intent name] feature" or "Turn off [capability]"

**Example:**
> "Disable the change card PIN feature"

**Step 4: Review Proposed Changes**
The Supervisor AI Agent will explain:
- Which intent will be disabled
- How the agent will handle requests for this capability
- That other intents will continue working normally

**Step 5: Confirm and Wait**
1. Confirm the change
2. Wait for backup, update, and testing (30-60 seconds)

**Step 6: Receive Confirmation**
The system will report:
- Intent successfully disabled
- Test results showing disabled intent is rejected
- Test results showing other intents still work
- Backup location

#### Enabling a Previously Disabled Capability

**Step 1-2**: Same as Full Outage Mode (call and authenticate)

**Step 3: Request to Enable**
Say: "Enable the [intent name] feature" or "Turn on [capability]"

**Example:**
> "Enable the change card PIN feature"

**Step 4-6**: Same as disabling (review, confirm, receive confirmation)

#### Restoring All Capabilities

**Step 1-2**: Same as Full Outage Mode (call and authenticate)

**Step 3: Request Full Restoration**
Say: "Restore all capabilities" or "Restore all intents to normal"

**Step 4: Confirm and Wait**
1. Confirm the restoration
2. Wait for the system to restore from backup (30-60 seconds)

**Step 5: Receive Confirmation**
The system will report:
- All intents restored to normal operation
- Test results confirming all intents work
- Duration of the partial outage
- Backup used for restoration

---

## Handling Authentication Failures

### Phone Number Not Authorized

**Symptom**: Call immediately ends with "Unauthorized access" message

**Cause**: Your phone number is not in the supervisor allowlist

**Resolution**:
1. Verify you're calling from an authorized phone number
2. Contact your system administrator to add your number to the allowlist

**Updating Phone Allowlist**:
```bash
aws secretsmanager put-secret-value \
  --secret-id supervisor-ai-agent-pin \
  --secret-string '{"pin":"CURRENT_PIN","allowlist":["+1-555-0100","+1-555-0101"]}' \
  --profile your-aws-profile --region us-east-1
```
No redeployment needed. Changes take effect on next Lambda cold start.

**Prevention**: Maintain an up-to-date list of authorized phone numbers

### Incorrect PIN

**Symptom**: "Incorrect PIN" message after entering PIN

**Cause**: Wrong PIN entered or PIN has been changed

**Resolution**:
1. Try again (you have 3 total attempts)
2. If you've forgotten the PIN, contact your system administrator
3. Administrator can retrieve the PIN from AWS Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id supervisor-ai-agent-pin \
     --profile your-aws-profile \
     --region us-east-1 \
     --query SecretString \
     --output text
   ```

**To Change PIN** (Administrator):
1. Update the secret in AWS Secrets Manager:
   ```bash
   aws secretsmanager update-secret \
     --secret-id supervisor-ai-agent-pin \
     --secret-string '{"pin":"NEW_PIN"}' \
     --profile your-aws-profile \
     --region us-east-1
   ```
2. Notify all authorized operations managers of the new PIN

**Prevention**: 
- Use a secure method to share the PIN with authorized personnel
- Change the PIN periodically (e.g., quarterly)
- Change the PIN immediately if compromised

### Maximum Retry Attempts Exceeded

**Symptom**: Call terminates after 3 failed PIN attempts

**Cause**: Incorrect PIN entered 3 times

**Resolution**:
1. Wait a few minutes and call again
2. Ensure you have the correct PIN before calling
3. Contact administrator if you don't know the current PIN

**Server-Side Rate Limiting**: If you enter the wrong PIN 3 times, your phone number is locked out for 30 minutes. This is enforced server-side (DynamoDB) and cannot be bypassed. Wait 30 minutes or contact a system administrator to clear the lockout.

**Prevention**: Verify PIN before calling during high-stress situations

---

## Verifying AI Agent Updates

### Immediate Verification (During Call)

The Supervisor AI Agent provides immediate verification:
1. **Test Results**: Number of tests passed/failed
2. **Sample Responses**: Examples of how the agent now responds
3. **Backup Confirmation**: Location of the backup for rollback

### Post-Call Verification (Recommended)

**Method 1: Test Call to Production Agent**
1. Call your production AI agent as a customer would
2. Ask about an unavailable service
3. Verify the agent explains the service is unavailable
4. Ask about an available service
5. Verify the agent handles it normally

**Method 2: CloudWatch Logs**
1. Open AWS Console → CloudWatch → Log Groups
2. Navigate to `/aws/lambda/supervisor-ai-agent-manager`
3. Find the most recent log stream
4. Look for log entries with `"event": "PROMPT_UPDATE"`
5. Verify `"status": "success"`

**Method 3: S3 Audit Logs**
1. Open AWS Console → S3
2. Navigate to the backup bucket (from CDK outputs)
3. Go to `audit-logs/{year}/{month}/{day}/`
4. Download the most recent `prompt-update-*.json` file
5. Review the `beforePromptContent` and `afterPromptContent` fields

**Method 4: Amazon Q in Connect Console**
1. Open AWS Console → Amazon Connect → Your Instance → Amazon Q
2. Navigate to AI Agents
3. Select your production agent
4. Review the current AI Prompt version
5. Verify the prompt text includes outage information or intent modifications

### Verification Checklist

After any update, verify:
- [ ] Automated tests passed (reported during call)
- [ ] Sample responses are appropriate (reported during call)
- [ ] Backup was created successfully (reported during call)
- [ ] Production agent responds correctly to test queries (manual test)
- [ ] CloudWatch logs show successful update (optional)
- [ ] S3 audit log contains update record (optional)

---

## Restoring AI Agents

### When to Restore

Restore AI agents when:
- Services have recovered from an outage
- An update was incorrect and needs to be rolled back
- Testing revealed issues with the updated prompt
- All disabled intents should be re-enabled

### Full Restoration Procedure

**Step 1-2**: Call and authenticate (same as updating)

**Step 3: Request Restoration**
Say: "Restore the original prompt" or "Restore [agent name] to normal operations"

**Step 4: Confirm**
The Supervisor AI Agent will:
- Identify the most recent backup
- Explain what will be restored
- Ask for confirmation

**Step 5: Wait for Completion**
The system will:
- Retrieve the backup from S3
- Restore the original prompt
- Test the restored agent
- Calculate outage duration

**Step 6: Receive Confirmation**
The system will report:
- Restoration completed successfully
- Test results
- Outage duration (time from backup to restoration)

### Manual Restoration (Emergency)

If the phone system is unavailable, administrators can restore manually:

**Step 1: List Backups**
```bash
aws s3 ls s3://BACKUP_BUCKET_NAME/backups/AGENT_ID/ \
  --profile your-aws-profile \
  --region us-east-1
```

**Step 2: Download Most Recent Backup**
```bash
aws s3 cp s3://BACKUP_BUCKET_NAME/backups/AGENT_ID/TIMESTAMP-AGENT_NAME.json backup.json \
  --profile your-aws-profile \
  --region us-east-1
```

**Step 3: Extract Prompt Text**
```bash
cat backup.json | jq -r '.currentPromptText' > original_prompt.txt
```

**Step 4: Create New AI Prompt Version**
Use the Amazon Q in Connect console or AWS CLI to create a new AI Prompt version with the original text.

**Step 5: Update AI Agent Configuration**
Update the AI Agent to reference the new AI Prompt version and set `visibilityStatus` to `PUBLISHED`.

**Note**: Manual restoration is complex and error-prone. Use the phone system whenever possible.

---

## Monitoring System Health

### CloudWatch Dashboards

**Access**: AWS Console → CloudWatch → Dashboards

**Key Metrics to Monitor**:
1. **Authentication Attempts**: Track successful and failed authentication
2. **Prompt Updates**: Monitor update frequency and success rate
3. **Test Executions**: Track test pass/fail rates
4. **Lambda Performance**: Monitor duration, errors, and throttling

### CloudWatch Alarms

**Configured Alarms**:

1. **High Authentication Failure Rate**
   - Threshold: >10 failures in 5 minutes
   - Action: SNS notification to operations team
   - Investigation: Check for unauthorized access attempts or PIN issues

2. **Prompt Update Failures**
   - Threshold: >0 failures
   - Action: SNS notification to operations team
   - Investigation: Check Lambda logs and API permissions

3. **Critical Test Failures**
   - Threshold: >0 failures
   - Action: SNS notification to operations team
   - Investigation: Automatic rollback triggered, verify agent behavior

4. **Lambda Errors**
   - Threshold: >5% error rate
   - Action: SNS notification to DevOps team
   - Investigation: Check Lambda logs for error details

#### Security Alarms

- **Phone Spoofing Detection**: Triggers when >5 phone validation failures occur in 5 minutes (possible caller ID spoofing)
- **PIN Lockout**: Triggers when a phone number is locked out due to failed PIN attempts (possible brute-force attack)
- **Unusual Sessions**: Triggers when >3 authenticated sessions occur in 1 hour (possible stolen credentials)

### Daily Health Checks

**Morning Check** (5 minutes):
1. Review CloudWatch alarms for any triggered alerts
2. Check Lambda error rates in CloudWatch metrics
3. Verify S3 backup bucket has recent backups (if updates occurred)
4. Review authentication logs for unusual activity

**Weekly Check** (15 minutes):
1. Review all audit logs in S3 for the past week
2. Verify backup retention policies are working
3. Check Lambda function performance trends
4. Review CloudWatch Logs Insights for patterns

### CloudWatch Logs Insights Queries

**Query 1: Recent Authentication Attempts**
```
fields @timestamp, phoneNumber, result, requestId
| filter event = "AUTHENTICATION_ATTEMPT"
| sort @timestamp desc
| limit 50
```

**Query 2: Prompt Updates in Last 24 Hours**
```
fields @timestamp, agentId, callerPhoneNumber, status
| filter event = "PROMPT_UPDATE"
| filter @timestamp > ago(24h)
| sort @timestamp desc
```

**Query 3: Failed Operations**
```
fields @timestamp, function, event, status, message
| filter status = "failure"
| sort @timestamp desc
| limit 20
```

**Query 4: Intent Management Operations**
```
fields @timestamp, operation, agentId, intentName, status
| filter operation in ["INTENT_DISABLE", "INTENT_ENABLE", "INTENT_RESTORE_ALL"]
| sort @timestamp desc
| limit 50
```

---

## AI Prompt Versioning and Visibility Status

### Understanding AI Prompt Versions

**AI Prompts are separate resources** from AI Agents:
- Each AI Prompt has a unique ID and can have multiple versions
- AI Agents reference specific AI Prompt versions
- Updates create new AI Prompt versions (immutable)
- Old versions remain available for rollback

### Visibility Status

**SAVED**: Draft configuration, not active for customer interactions
- Used for testing and development
- Not visible to customers
- Can be modified before publishing

**PUBLISHED**: Active configuration, serving customer interactions
- All updates set status to PUBLISHED automatically
- Takes effect immediately (within 5 seconds)
- Cannot be modified (must create new version)

### Version Management

**Viewing Current Version**:
1. AWS Console → Amazon Connect → Instance → Amazon Q
2. Select AI Agents → Choose your agent
3. View "AI Prompt" field showing current version (e.g., `prompt-id:5`)

**Version History**:
- All versions are retained in AWS
- Backups in S3 include the version number
- Rollback uses the version from the backup

**Best Practices**:
- Always backup before updates (automatic in this system)
- Document significant prompt changes in audit logs
- Test new versions before confirming updates
- Keep track of which version is in production

### Prompt Update Workflow

1. **Backup**: Current prompt and version saved to S3
2. **Generate**: New prompt text created based on outage info or intent changes
3. **Create Version**: New AI Prompt version created via CreateAIPromptVersion API
4. **Update Agent**: AI Agent configuration updated to reference new version
5. **Publish**: Visibility status set to PUBLISHED
6. **Test**: Automated tests validate the update
7. **Confirm**: Success reported to operations manager

---

## Troubleshooting Common Issues

### Issue: Call Drops During Update

**Symptoms**: Call disconnects while waiting for update to complete

**Possible Causes**:
- Network connectivity issue
- Lambda timeout (rare)
- Amazon Connect service issue

**Resolution**:
1. Wait 2-3 minutes for the update to complete
2. Call back and ask "What's the status of [agent name]?"
3. Verify the update completed by checking CloudWatch logs
4. If update failed, try again

**Prevention**: Ensure stable phone connection during calls

### Issue: Agent Not Responding Correctly After Update

**Symptoms**: Production agent gives incorrect responses after update

**Possible Causes**:
- Prompt generation error
- Test validation missed an issue
- Caching delay (rare)

**Resolution**:
1. Call supervisor hotline immediately
2. Request restoration: "Restore [agent name] to normal operations"
3. Verify restoration with test queries
4. Report the issue to development team with details

**Prevention**: Always verify updates with test queries after confirmation

### Issue: Backup Not Found During Restore

**Symptoms**: System reports "No backup found" when attempting restore

**Possible Causes**:
- S3 bucket permissions issue
- Backup was never created
- Incorrect agent ID

**Resolution**:
1. Verify agent ID is correct
2. Check S3 bucket manually for backups:
   ```bash
   aws s3 ls s3://BACKUP_BUCKET_NAME/backups/ \
     --recursive \
     --profile your-aws-profile \
     --region us-east-1
   ```
3. If backups exist, contact administrator to check Lambda permissions
4. If no backups exist, manual restoration required (see Manual Restoration section)

### Issue: Tests Failing After Update

**Symptoms**: System reports test failures and triggers automatic rollback

**Possible Causes**:
- Prompt generation created incorrect instructions
- Test queries don't match actual customer scenarios
- Agent configuration issue

**Resolution**:
1. System automatically rolls back to previous version
2. Review the test failure details reported during call
3. Try updating again with clearer outage description
4. If issue persists, contact development team

**Prevention**: Provide clear, specific outage information during updates

### Issue: Intent Not Disabling Correctly

**Symptoms**: After disabling an intent, the agent still handles requests for that capability

**Possible Causes**:
- Prompt generation didn't include disable instructions
- Intent name mismatch
- Caching delay

**Resolution**:
1. Wait 30 seconds and test again
2. If still not working, call supervisor hotline
3. Request to disable the intent again with exact intent name
4. Verify with test query

**Prevention**: Use exact intent names from the capability list

### Issue: Unable to List Agent Capabilities

**Symptoms**: System cannot retrieve intent list

**Possible Causes**:
- No Intent_Configuration exists yet
- S3 permissions issue
- Agent prompt doesn't have clear intent structure

**Resolution**:
1. Try again - system will analyze prompt and create Intent_Configuration
2. If fails repeatedly, check CloudWatch logs for errors
3. Contact administrator to verify S3 permissions
4. May require manual Intent_Configuration creation

---

## Emergency Procedures

### Complete System Outage

If the supervisor hotline is completely unavailable:

**Step 1: Verify Outage**
- Try calling from multiple authorized numbers
- Check AWS Service Health Dashboard for Connect issues
- Check CloudWatch alarms for system errors

**Step 2: Manual Prompt Update** (Administrator Only)
1. Access AWS Console → Amazon Connect → Instance → Amazon Q
2. Navigate to AI Agents → Select production agent
3. Create new AI Prompt version with outage information
4. Update AI Agent configuration to reference new prompt
5. Set visibility status to PUBLISHED
6. Document the manual change in audit logs

**Step 3: Notify Team**
- Inform operations team of manual update
- Document the outage and resolution
- Create incident report

**Step 4: Restore Supervisor Hotline**
- Check Lambda function health
- Review CloudWatch logs for errors
- Restart Lambda functions if needed (redeploy)
- Test with authorized phone number

### Unauthorized Access Detected

If you suspect unauthorized access attempts:

**Step 1: Immediate Actions**
1. Change supervisor PIN immediately:
   ```bash
   aws secretsmanager update-secret \
     --secret-id supervisor-ai-agent-pin \
     --secret-string '{"pin":"NEW_PIN"}' \
     --profile your-aws-profile \
     --region us-east-1
   ```
2. Review authentication logs for suspicious activity
3. Notify security team

**Step 2: Investigation**
1. Check CloudWatch logs for failed authentication attempts
2. Identify phone numbers attempting access
3. Review S3 audit logs for any successful unauthorized updates
4. Check if any unauthorized prompt changes were made

**Step 3: Remediation**
1. Update phone allowlist to remove compromised numbers
2. Update the allowlist in Secrets Manager
3. Restore any unauthorized prompt changes
4. Document the incident

**Step 4: Prevention**
1. Review and update access controls
2. Implement additional monitoring
3. Train team on security best practices
4. Consider implementing MFA for AWS Console access

### Critical Test Failures

If automated tests consistently fail after updates:

**Step 1: Automatic Rollback**
- System automatically rolls back to previous version
- No manual intervention needed for rollback

**Step 2: Investigation**
1. Review test failure details from call
2. Check CloudWatch logs for Tester Lambda
3. Verify test query configuration is appropriate
4. Test production agent manually

**Step 3: Resolution**
1. If test queries are incorrect, update test configuration
2. If prompt generation is incorrect, report to development team
3. Try update again with different outage description
4. Consider manual prompt update if urgent

### Data Loss or Corruption

If backups are lost or corrupted:

**Step 1: Assess Impact**
1. Check S3 bucket for any remaining backups
2. Verify S3 versioning is enabled
3. Check S3 version history for deleted objects

**Step 2: Recovery**
1. Restore from S3 version history if available
2. Check CloudWatch logs for prompt text (may be logged)
3. Reconstruct prompt from audit logs if needed
4. As last resort, manually recreate prompt based on documentation

**Step 3: Prevention**
1. Verify S3 versioning is enabled
2. Implement S3 bucket replication to another region
3. Regular backup verification tests
4. Document prompt configurations externally

---

## Maintenance Tasks

### Weekly Maintenance

**Task 1: Review Audit Logs** (15 minutes)
1. Download audit logs from S3 for the past week
2. Review all prompt updates and intent changes
3. Verify all changes were authorized
4. Document any anomalies

**Task 2: Backup Verification** (10 minutes)
1. List recent backups in S3
2. Download and verify 2-3 random backups
3. Ensure JSON structure is valid
4. Verify prompt text is complete

**Task 3: Test Supervisor Hotline** (5 minutes)
1. Call from authorized number
2. Authenticate with PIN
3. Request agent capability list
4. Verify system responds correctly
5. End call without making changes

### Monthly Maintenance

**Task 1: PIN Rotation** (10 minutes)
1. Generate new 6-digit PIN
2. Update in AWS Secrets Manager
3. Notify all authorized operations managers
4. Test authentication with new PIN
5. Document PIN change in security log

**Task 2: Access Review** (20 minutes)
1. Review phone allowlist for accuracy
2. Remove phone numbers for departed personnel
3. Add phone numbers for new operations managers
4. Update the allowlist in Secrets Manager if changes made
5. Test authentication for all authorized numbers

**Task 3: Performance Review** (30 minutes)
1. Review CloudWatch metrics for Lambda performance
2. Check average workflow duration (target: <2 minutes)
3. Review test execution times (target: <10 seconds)
4. Identify any performance degradation trends
5. Optimize if needed (increase Lambda memory, etc.)

**Task 4: Cost Review** (15 minutes)
1. Review AWS Cost Explorer for system costs
2. Verify costs are within expected range (~$5/month)
3. Check for any unexpected charges
4. Optimize S3 lifecycle policies if needed

### Quarterly Maintenance

**Task 1: Disaster Recovery Test** (60 minutes)
1. Simulate complete system outage
2. Practice manual prompt update procedure
3. Test backup restoration from S3
4. Verify all recovery procedures work
5. Document any issues or improvements needed

**Task 2: Security Audit** (90 minutes)
1. Review all IAM roles and permissions
2. Verify least privilege is maintained
3. Check for any security vulnerabilities
4. Review authentication logs for patterns
5. Update security documentation

**Task 3: Documentation Review** (45 minutes)
1. Review all operational documentation
2. Update procedures based on lessons learned
3. Add new troubleshooting scenarios
4. Verify contact information is current
5. Update training materials

**Task 4: Capacity Planning** (30 minutes)
1. Review usage trends
2. Forecast future capacity needs
3. Verify Lambda concurrency limits are adequate
4. Check S3 storage growth
5. Plan for scaling if needed

### Annual Maintenance

**Task 1: System Architecture Review** (2 hours)
1. Review overall system architecture
2. Identify improvement opportunities
3. Evaluate new AWS services or features
4. Plan major upgrades or enhancements
5. Update architecture documentation

**Task 2: Compliance Audit** (3 hours)
1. Review all audit logs for the year
2. Verify compliance with security policies
3. Generate compliance reports
4. Address any compliance gaps
5. Update compliance documentation

**Task 3: Training Refresh** (4 hours)
1. Conduct training session for all operations managers
2. Review system capabilities and procedures
3. Practice emergency scenarios
4. Update training materials
5. Certify all personnel

---

## Appendix

### Quick Reference Card

**Supervisor Hotline**: [Contact administrator for number]

**Authentication**:
- Phone must be in allowlist
- 6-digit PIN required
- 3 attempts maximum

**Common Commands**:
- "What capabilities does the agent have?" - List intents
- "Disable [intent name]" - Disable specific capability
- "Enable [intent name]" - Enable specific capability
- "Restore all capabilities" - Full restoration
- "[Service] is down" - Full outage update

**Emergency Contacts**:
- Operations Manager: [Contact info]
- System Administrator: [Contact info]
- DevOps Team: [Contact info]
- Security Team: [Contact info]

### AWS Resources Quick Reference

**Lambda Functions**:
- `supervisor-ai-agent-auth` - Authentication
- `supervisor-ai-agent-manager` - Agent management
- `supervisor-ai-agent-backup` - Backup operations
- `supervisor-ai-agent-restore` - Restore operations
- `supervisor-ai-agent-tester` - Testing

**S3 Bucket**: `supervisor-ai-agent-backups-{account-id}-{region}`
- Folder: `backups/{agent-id}/` - Prompt backups
- Folder: `intent-configs/{agent-id}/` - Intent configurations
- Folder: `audit-logs/{year}/{month}/{day}/` - Audit logs

**Secrets Manager**: `supervisor-ai-agent-pin`

**CloudWatch Log Groups**:
- `/aws/lambda/supervisor-ai-agent-auth`
- `/aws/lambda/supervisor-ai-agent-manager`
- `/aws/lambda/supervisor-ai-agent-backup`
- `/aws/lambda/supervisor-ai-agent-restore`
- `/aws/lambda/supervisor-ai-agent-tester`

### Useful AWS CLI Commands

**View Recent Logs**:
```bash
aws logs tail /aws/lambda/supervisor-ai-agent-manager \
  --follow \
  --profile your-aws-profile \
  --region us-east-1
```

**List Recent Backups**:
```bash
aws s3 ls s3://BACKUP_BUCKET_NAME/backups/AGENT_ID/ \
  --profile your-aws-profile \
  --region us-east-1
```

**Get Current PIN**:
```bash
aws secretsmanager get-secret-value \
  --secret-id supervisor-ai-agent-pin \
  --profile your-aws-profile \
  --region us-east-1 \
  --query SecretString \
  --output text
```

---

## Document Version

**Version**: 1.0  
**Last Updated**: 2025-03-01  
**Next Review**: 2025-06-01


### Enable AI Agent CloudWatch Logging

To debug AI agent behavior (which prompt is being used, what the agent sees, tool invocations), enable Q Connect assistant logging:

```bash
# Step 1: Create log group
aws logs create-log-group --log-group-name /aws/connect/ai-agent-logs

# Step 2: Create delivery source
aws logs put-delivery-source \
  --name supervisor-ai-agent-delivery-source \
  --log-type EVENT_LOGS \
  --resource-arn arn:aws:wisdom:us-east-1:ACCOUNT_ID:assistant/ASSISTANT_ID

# Step 3: Create delivery destination
aws logs put-delivery-destination \
  --name supervisor-ai-agent-delivery-dest \
  --output-format json \
  --delivery-destination-configuration '{"destinationResourceArn":"arn:aws:logs:us-east-1:ACCOUNT_ID:log-group:/aws/connect/ai-agent-logs:*"}'

# Step 4: Link source to destination
aws logs create-delivery \
  --delivery-source-name supervisor-ai-agent-delivery-source \
  --delivery-destination-arn arn:aws:logs:us-east-1:ACCOUNT_ID:delivery-destination:supervisor-ai-agent-delivery-dest
```

Logs include: `ai_agent_id`, `ai_agent_name`, `prompt` (full system prompt sent to LLM), `response`, `utterance`, `conversation_session_data`, `orchestration_id`. Useful for verifying which prompt version is active and debugging dual-persona routing.

Query example:
```bash
aws logs filter-log-events \
  --log-group-name /aws/connect/ai-agent-logs \
  --start-time $(date -v-10M +%s000) \
  --filter-pattern "ai_agent_id" \
  --query 'events[*].message' --output text
```
