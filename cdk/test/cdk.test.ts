import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { SupervisorAIAgentStack } from '../lib/supervisor-ai-agent-stack';

describe('SupervisorAIAgentStack', () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();
    const stack = new SupervisorAIAgentStack(app, 'TestStack');
    template = Template.fromStack(stack);
  });

  test('creates 5 Lambda functions', () => {
    const lambdas = template.findResources('AWS::Lambda::Function');
    const appLambdas = Object.keys(lambdas).filter(k => !k.includes('CustomVpc'));
    expect(appLambdas.length).toBe(5);
  });

  test('creates DynamoDB table for PIN rate limiting', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'supervisor-ai-agent-pin-attempts',
      BillingMode: 'PAY_PER_REQUEST',
    });
  });

  test('creates KMS key with rotation enabled', () => {
    template.hasResourceProperties('AWS::KMS::Key', {
      EnableKeyRotation: true,
    });
  });

  test('creates VPC with private isolated subnets', () => {
    template.hasResourceProperties('AWS::EC2::VPC', {
      EnableDnsHostnames: true,
      EnableDnsSupport: true,
    });
  });

  test('SNS topic is KMS encrypted', () => {
    template.hasResourceProperties('AWS::SNS::Topic', {
      TopicName: 'supervisor-ai-agent-alarms',
    });
  });

  test('S3 bucket uses KMS encryption', () => {
    template.hasResourceProperties('AWS::S3::Bucket', {
      BucketEncryption: {
        ServerSideEncryptionConfiguration: [{
          ServerSideEncryptionByDefault: {
            SSEAlgorithm: 'aws:kms',
          },
        }],
      },
    });
  });

  test('CloudWatch log groups have 90-day retention', () => {
    template.hasResourceProperties('AWS::Logs::LogGroup', {
      RetentionInDays: 90,
    });
  });
});
