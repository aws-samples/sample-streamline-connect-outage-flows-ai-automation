#!/bin/bash
# Cleanup script for SupervisorAIAgentStack orphaned resources
# Run this before redeploying after a failed stack creation
#
# Usage: ./scripts/cleanup-failed-deploy.sh
# Requires: AWS CLI configured with appropriate profile and region
set -euo pipefail

PROFILE="${AWS_PROFILE:-your-aws-profile}"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="SupervisorAIAgentStack"

run_aws() {
  aws --profile "$PROFILE" --region "$REGION" "$@"
}

echo "=== Cleaning up orphaned resources from failed deployments ==="
echo "  Profile: $PROFILE | Region: $REGION"

# 1. Delete failed CloudFormation stack
echo "Deleting stack $STACK_NAME (if exists)..."
run_aws cloudformation delete-stack --stack-name "$STACK_NAME" 2>/dev/null || true
run_aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" 2>/dev/null || true
echo "  ✅ Stack deleted"

# 2. Delete orphaned log groups (extracted from CDK template if available, else fallback)
echo "Deleting orphaned log groups..."
TEMPLATE="cdk.out/SupervisorAIAgentStack.template.json"
if [ -f "$TEMPLATE" ]; then
  LOG_GROUPS=$(python3 -c "
import json, sys
with open('$TEMPLATE') as f:
    t = json.load(f)
for v in t.get('Resources', {}).values():
    if v.get('Type') == 'AWS::Logs::LogGroup':
        name = v.get('Properties', {}).get('LogGroupName', '')
        if name:
            print(name)
" 2>/dev/null)
else
  LOG_GROUPS=$(for fn in auth manager backup restore tester; do echo "/aws/lambda/supervisor-ai-agent-$fn"; done)
fi
while IFS= read -r LOG_GROUP; do
  [ -z "$LOG_GROUP" ] && continue
  run_aws logs delete-log-group --log-group-name "$LOG_GROUP" 2>/dev/null && echo "  ✅ Deleted $LOG_GROUP" || echo "  ⏭️  $LOG_GROUP not found"
done <<< "$LOG_GROUPS"

# 3. Delete orphaned secret
echo "Deleting orphaned secret..."
run_aws secretsmanager delete-secret --secret-id supervisor-ai-agent-pin --force-delete-without-recovery 2>/dev/null \
  && echo "  ✅ Deleted supervisor-ai-agent-pin" \
  || echo "  ⏭️  supervisor-ai-agent-pin not found"

# 4. Delete orphaned S3 buckets
echo "Checking for orphaned S3 buckets..."
while IFS= read -r bucket; do
  [ -z "$bucket" ] && continue
  echo "  Found bucket: $bucket"
  OBJECTS=$(run_aws s3api list-objects-v2 --bucket "$bucket" --max-items 1 --query 'KeyCount' --output text 2>/dev/null || echo "0")
  if [ "$OBJECTS" != "0" ]; then
    echo "  Emptying bucket $bucket..."
    run_aws s3 rm "s3://$bucket" --recursive 2>/dev/null
  fi
  run_aws s3 rb "s3://$bucket" 2>/dev/null && echo "  ✅ Deleted $bucket" || echo "  ⚠️  Could not delete $bucket"
done < <(run_aws s3api list-buckets --query 'Buckets[?contains(Name,`supervisoraiagent`) || contains(Name,`supervisor-ai-agent`)].Name' --output text 2>/dev/null | tr '\t' '\n')

# 5. Delete orphaned SNS topics
echo "Checking for orphaned SNS topics..."
while IFS= read -r arn; do
  [ -z "$arn" ] && continue
  run_aws sns delete-topic --topic-arn "$arn" 2>/dev/null && echo "  ✅ Deleted $arn" || echo "  ⚠️  Could not delete $arn"
done < <(run_aws sns list-topics --query 'Topics[?contains(TopicArn,`SupervisorAIAgent`)].TopicArn' --output text 2>/dev/null | tr '\t' '\n')

# 6. Delete orphaned IAM roles
echo "Checking for orphaned IAM roles..."
while IFS= read -r role; do
  [ -z "$role" ] && continue
  # Detach managed policies
  while IFS= read -r policy; do
    [ -z "$policy" ] && continue
    run_aws iam detach-role-policy --role-name "$role" --policy-arn "$policy" 2>/dev/null
  done < <(run_aws iam list-attached-role-policies --role-name "$role" --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null | tr '\t' '\n')
  # Delete inline policies
  while IFS= read -r policy; do
    [ -z "$policy" ] && continue
    run_aws iam delete-role-policy --role-name "$role" --policy-name "$policy" 2>/dev/null
  done < <(run_aws iam list-role-policies --role-name "$role" --query 'PolicyNames[]' --output text 2>/dev/null | tr '\t' '\n')
  run_aws iam delete-role --role-name "$role" 2>/dev/null && echo "  ✅ Deleted role $role" || echo "  ⚠️  Could not delete role $role"
done < <(run_aws iam list-roles --query 'Roles[?contains(RoleName,`SupervisorAIAgentStack`)].RoleName' --output text 2>/dev/null | tr '\t' '\n')

echo ""
echo "=== Cleanup complete. Ready to redeploy. ==="
