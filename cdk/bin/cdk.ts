#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { SupervisorAIAgentStack } from '../lib/supervisor-ai-agent-stack';

const app = new cdk.App();

// Get configuration from context or environment variables
const account = process.env.CDK_DEFAULT_ACCOUNT || app.node.tryGetContext('account');
const region = process.env.CDK_DEFAULT_REGION || app.node.tryGetContext('region') || 'us-east-1';

new SupervisorAIAgentStack(app, 'SupervisorAIAgentStack', {
  env: {
    account: account,
    region: region,
  },
  description: 'Supervisor AI Agent for Amazon Connect Outage Management',
  synthesizer: new cdk.CliCredentialsStackSynthesizer(),
});
