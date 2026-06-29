import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as connect from 'aws-cdk-lib/aws-connect';
import * as wisdom from 'aws-cdk-lib/aws-wisdom';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as cloudwatchActions from 'aws-cdk-lib/aws-cloudwatch-actions';
import { Construct } from 'constructs';

export interface SupervisorAIAgentStackProps extends cdk.StackProps {
  // Configuration parameters will be added here
}

export class SupervisorAIAgentStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: SupervisorAIAgentStackProps) {
    super(scope, id, props);

    // Helper function for local bundling with venv
    const createLocalBundler = (functionDir: string) => ({
      tryBundle(outputDir: string) {
        const { execFileSync } = require('child_process');
        const path = require('path');
        
        // Validate functionDir to prevent path traversal
        if (!/^[a-zA-Z0-9_\-]+$/.test(functionDir)) {
          throw new Error(`Invalid function directory name: ${functionDir}`);
        }
        
        try {
          const lambdaDir = path.resolve('../lambda');
          const venvDir = path.join(lambdaDir, '.bundling-venv');
          
          // Resolve and verify path stays within lambdaDir
          const safeFunctionDir = path.resolve(lambdaDir, functionDir);
          if (!safeFunctionDir.startsWith(path.resolve(lambdaDir) + path.sep)) {
            throw new Error(`Path traversal detected: ${functionDir}`);
          }
          
          // Create venv
          execFileSync('python3', ['-m', 'venv', venvDir], { cwd: lambdaDir, stdio: 'inherit' });
          
          // Install dependencies
          const pipPath = path.join(venvDir, 'bin', 'pip');
          execFileSync(pipPath, ['install', '-r', path.join(safeFunctionDir, 'requirements.txt'), '-t', outputDir], { cwd: lambdaDir, stdio: 'inherit' });
          
          // Copy Lambda code
          execFileSync('cp', ['-r', safeFunctionDir, 'shared', path.join(outputDir, '/')], { cwd: lambdaDir, stdio: 'inherit' });
          
          // Cleanup venv
          execFileSync('rm', ['-rf', venvDir], { cwd: lambdaDir });
          
          return true;
        } catch (error) {
          console.error('Local bundling failed:', error);
          return false;
        }
      }
    });

    // Stack parameters for configuration
    const connectInstanceId = new cdk.CfnParameter(this, 'ConnectInstanceId', {
      type: 'String',
      description: 'Amazon Connect instance ID',
    });

    const qConnectAssistantId = new cdk.CfnParameter(this, 'QConnectAssistantId', {
      type: 'String',
      description: 'Amazon Q in Connect assistant ID',
    });

    const productionAgentIds = new cdk.CfnParameter(this, 'ProductionAgentIds', {
      type: 'CommaDelimitedList',
      description: 'Comma-separated list of production AI agent IDs to manage',
    });

    const supervisorPinSecretArn = new cdk.CfnParameter(this, 'SupervisorPinSecretArn', {
      type: 'String',
      description: 'ARN of pre-created Secrets Manager secret containing supervisor PIN (create with: aws secretsmanager create-secret --name supervisor-ai-agent-pin --secret-string \'{"pin":"YOUR_PIN"}\')',
    });

    const notificationEmail = new cdk.CfnParameter(this, 'NotificationEmail', {
      type: 'String',
      description: 'Email address for CloudWatch alarm notifications',
    });

    // ========================================
    // KMS Key for Backup Encryption
    // ========================================
    const backupEncryptionKey = new kms.Key(this, 'BackupEncryptionKey', {
      alias: 'supervisor-ai-agent-backup',
      description: 'KMS key for encrypting supervisor AI agent backups and audit logs',
      enableKeyRotation: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ========================================
    // S3 Bucket for Backups, Intent Configs, and Audit Logs
    // ========================================
    const backupBucket = new s3.Bucket(this, 'BackupBucket', {
      bucketName: `supervisor-ai-agent-backups-${this.account}-${this.region}`,
      versioned: true,
      encryption: s3.BucketEncryption.KMS,
      encryptionKey: backupEncryptionKey,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      lifecycleRules: [
        {
          id: 'TransitionBackupsToIA',
          enabled: true,
          prefix: 'backups/',
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(30),
            },
            {
              storageClass: s3.StorageClass.GLACIER,
              transitionAfter: cdk.Duration.days(90),
            },
          ],
          expiration: cdk.Duration.days(365),
        },
        {
          id: 'TransitionIntentConfigsToIA',
          enabled: true,
          prefix: 'intent-configs/',
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(30),
            },
          ],
          // Intent configs don't expire - keep indefinitely
        },
        {
          id: 'RetainAuditLogs',
          enabled: true,
          prefix: 'audit-logs/',
          expiration: cdk.Duration.days(365),
        },
      ],
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ========================================
    // Secrets Manager - Import pre-created secret for Supervisor PIN
    // ========================================
    const supervisorPinSecret = secretsmanager.Secret.fromSecretCompleteArn(
      this, 'SupervisorPinSecret', supervisorPinSecretArn.valueAsString
    );

    // ========================================
    // DynamoDB Table for PIN Rate Limiting and Auth Tokens
    // ========================================
    const pinAttemptsTable = new dynamodb.Table(this, 'PinAttemptsTable', {
      tableName: 'supervisor-ai-agent-pin-attempts',
      partitionKey: { name: 'phone_number', type: dynamodb.AttributeType.STRING },
      timeToLiveAttribute: 'ttl_expiry',
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ========================================
    // Secrets Manager - Inter-Lambda Signing Key
    // ========================================
    const signingKeySecret = new secretsmanager.Secret(this, 'SigningKeySecret', {
      secretName: 'supervisor-ai-agent-signing-key',
      description: 'HMAC signing key for inter-Lambda request authentication',
      generateSecretString: { excludePunctuation: true, passwordLength: 64 },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ========================================
    // VPC for Lambda Network Isolation (T-0005/T-0017)
    // ========================================
    const lambdaVpc = new ec2.Vpc(this, 'LambdaVpc', {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        { name: 'private-isolated', subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      ],
    });

    // Security group for Lambda functions
    const lambdaSg = new ec2.SecurityGroup(this, 'LambdaSecurityGroup', {
      vpc: lambdaVpc,
      description: 'Security group for Lambda functions - outbound to VPC endpoints only',
      allowAllOutbound: false,
    });
    lambdaSg.addEgressRule(ec2.Peer.ipv4(lambdaVpc.vpcCidrBlock), ec2.Port.tcp(443), 'HTTPS to VPC interface endpoints');
    lambdaSg.addEgressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(443), 'HTTPS to S3/DynamoDB gateway endpoints (no internet - VPC has no IGW/NAT)');

    // Gateway endpoints (no cost)
    const s3Endpoint = lambdaVpc.addGatewayEndpoint('S3Endpoint', { service: ec2.GatewayVpcEndpointAwsService.S3 });
    const dynamoEndpoint = lambdaVpc.addGatewayEndpoint('DynamoDBEndpoint', { service: ec2.GatewayVpcEndpointAwsService.DYNAMODB });

    // Interface endpoints
    const endpointSg = new ec2.SecurityGroup(this, 'VpcEndpointSg', {
      vpc: lambdaVpc,
      description: 'Security group for VPC interface endpoints',
      allowAllOutbound: false,
    });
    endpointSg.addIngressRule(lambdaSg, ec2.Port.tcp(443), 'HTTPS from Lambda');

    const interfaceEndpointProps = {
      vpc: lambdaVpc,
      privateDnsEnabled: true,
      securityGroups: [endpointSg],
      subnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
    };

    lambdaVpc.addInterfaceEndpoint('SecretsManagerEndpoint', { service: ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER, ...interfaceEndpointProps });
    lambdaVpc.addInterfaceEndpoint('CloudWatchLogsEndpoint', { service: ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS, ...interfaceEndpointProps });
    lambdaVpc.addInterfaceEndpoint('LambdaEndpoint', { service: ec2.InterfaceVpcEndpointAwsService.LAMBDA, ...interfaceEndpointProps });

    // Lambda VPC configuration (reused by all functions)
    const lambdaVpcConfig = {
      vpc: lambdaVpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      securityGroups: [lambdaSg],
    };

    // ========================================
    // IAM Roles for Lambda Functions
    // ========================================

    // Authentication Lambda Role
    const authLambdaRole = new iam.Role(this, 'AuthLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Execution role for Authentication Lambda',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
      ],
    });

    // Grant read access to supervisor PIN secret
    supervisorPinSecret.grantRead(authLambdaRole);

    // Grant Auth Lambda read/write access to PIN attempts table
    pinAttemptsTable.grantReadWriteData(authLambdaRole);

    // Grant read access to signing key for inter-Lambda verification
    signingKeySecret.grantRead(authLambdaRole);

    // Agent Manager Lambda Role
    const agentManagerLambdaRole = new iam.Role(this, 'AgentManagerLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Execution role for Agent Manager Lambda',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Grant read/write access to S3 bucket for backups and intent configs
    backupBucket.grantReadWrite(agentManagerLambdaRole, 'backups/*');
    backupBucket.grantReadWrite(agentManagerLambdaRole, 'intent-configs/*');
    backupBucket.grantWrite(agentManagerLambdaRole, 'audit-logs/*');

    // Grant AgentManager Lambda read access to PIN attempts table (for auth token verification)
    pinAttemptsTable.grantReadData(agentManagerLambdaRole);

    // Grant read access to signing key for inter-Lambda signing
    signingKeySecret.grantRead(agentManagerLambdaRole);

    // Grant permissions to invoke other Lambda functions
    agentManagerLambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['lambda:InvokeFunction'],
        resources: [
          `arn:aws:lambda:${this.region}:${this.account}:function:supervisor-ai-agent-backup`,
          `arn:aws:lambda:${this.region}:${this.account}:function:supervisor-ai-agent-tester`,
        ],
      })
    );

    // Grant permissions for Amazon Q in Connect operations
    agentManagerLambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'qconnect:ListAIAgents',
          'qconnect:GetAIAgent',
          'qconnect:UpdateAIAgent',
          'qconnect:GetAIPrompt',
          'qconnect:CreateAIPromptVersion',
          'qconnect:UpdateSession',
          'wisdom:UpdateSession',
        ],
        resources: [
          `arn:aws:qconnect:${this.region}:${this.account}:assistant/${qConnectAssistantId.valueAsString}`,
          `arn:aws:qconnect:${this.region}:${this.account}:assistant/${qConnectAssistantId.valueAsString}/*`,
          `arn:aws:wisdom:${this.region}:${this.account}:assistant/${qConnectAssistantId.valueAsString}`,
          `arn:aws:wisdom:${this.region}:${this.account}:assistant/${qConnectAssistantId.valueAsString}/*`,
          `arn:aws:wisdom:${this.region}:${this.account}:session/${qConnectAssistantId.valueAsString}/*`,
        ],
      })
    );

    // Backup Lambda Role
    const backupLambdaRole = new iam.Role(this, 'BackupLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Execution role for Backup Lambda',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
      ],
    });

    // Grant read/write access to S3 bucket for backups and intent configs
    backupBucket.grantReadWrite(backupLambdaRole, 'backups/*');
    backupBucket.grantRead(backupLambdaRole, 'intent-configs/*');
    backupBucket.grantWrite(backupLambdaRole, 'audit-logs/*');

    // Grant read access to signing key for inter-Lambda verification
    signingKeySecret.grantRead(backupLambdaRole);

    // Restore Lambda Role
    const restoreLambdaRole = new iam.Role(this, 'RestoreLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Execution role for Restore Lambda',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Grant read access to S3 bucket for backups and intent configs
    backupBucket.grantRead(restoreLambdaRole, 'backups/*');
    backupBucket.grantRead(restoreLambdaRole, 'intent-configs/*');
    backupBucket.grantWrite(restoreLambdaRole, 'audit-logs/*');

    // Grant read access to signing key for inter-Lambda verification
    signingKeySecret.grantRead(restoreLambdaRole);

    // Grant permissions to invoke other Lambda functions
    restoreLambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['lambda:InvokeFunction'],
        resources: [
          `arn:aws:lambda:${this.region}:${this.account}:function:supervisor-ai-agent-manager`,
          `arn:aws:lambda:${this.region}:${this.account}:function:supervisor-ai-agent-tester`,
        ],
      })
    );

    // Tester Lambda Role
    const testerLambdaRole = new iam.Role(this, 'TesterLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Execution role for Tester Lambda',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Grant write access to S3 bucket for audit logs
    backupBucket.grantWrite(testerLambdaRole, 'audit-logs/*');

    // Grant read access to signing key for inter-Lambda verification
    signingKeySecret.grantRead(testerLambdaRole);

    // Grant permissions for Amazon Q in Connect operations
    testerLambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'qconnect:CreateSession',
          'qconnect:GetRecommendations',
        ],
        resources: [
          `arn:aws:qconnect:${this.region}:${this.account}:assistant/${qConnectAssistantId.valueAsString}`,
          `arn:aws:qconnect:${this.region}:${this.account}:assistant/${qConnectAssistantId.valueAsString}/*`,
        ],
      })
    );

    // ========================================
    // Lambda Functions
    // ========================================

    // Lambda layer for AWS Parameters and Secrets Lambda Extension
    const secretsExtensionLayer = lambda.LayerVersion.fromLayerVersionArn(
      this,
      'SecretsExtensionLayer',
      `arn:aws:lambda:${this.region}:177933569100:layer:AWS-Parameters-and-Secrets-Lambda-Extension:11`
    );

    // Authentication Lambda
    const authLambda = new lambda.Function(this, 'AuthLambda', {
      functionName: 'supervisor-ai-agent-auth',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'auth.handler.lambda_handler',
      ...lambdaVpcConfig,
      code: lambda.Code.fromAsset('../lambda', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r auth/requirements.txt -t /asset-output && cp -au . /asset-output'
          ],
          local: createLocalBundler('auth')
        }
      }),
      role: authLambdaRole,
      memorySize: 256,
      timeout: cdk.Duration.seconds(30),
      logGroup: new logs.LogGroup(this, 'AuthLogGroup', {
        logGroupName: '/aws/lambda/supervisor-ai-agent-auth',
        retention: logs.RetentionDays.THREE_MONTHS,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
      environment: {
        SECRET_ARN: supervisorPinSecret.secretArn,
        PIN_ATTEMPTS_TABLE: pinAttemptsTable.tableName,
        SIGNING_KEY_SECRET_ARN: signingKeySecret.secretArn,
        LOG_LEVEL: 'INFO',
        POWERTOOLS_SERVICE_NAME: 'supervisor-ai-agent-auth',
        POWERTOOLS_METRICS_NAMESPACE: 'SupervisorAIAgent',
      },
      layers: [secretsExtensionLayer],
      description: 'Validates caller phone number and PIN for supervisor authentication',
    });

    // Agent Manager Lambda
    const agentManagerLambda = new lambda.Function(this, 'AgentManagerLambda', {
      functionName: 'supervisor-ai-agent-manager',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'agent_manager.handler.lambda_handler',
      code: lambda.Code.fromAsset('../lambda', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r agent_manager/requirements.txt -t /asset-output && cp -au . /asset-output'
          ],
          local: createLocalBundler('agent_manager')
        }
      }),
      role: agentManagerLambdaRole,
      memorySize: 512,
      timeout: cdk.Duration.seconds(120),
      logGroup: new logs.LogGroup(this, 'AgentManagerLogGroup', {
        logGroupName: '/aws/lambda/supervisor-ai-agent-manager',
        retention: logs.RetentionDays.THREE_MONTHS,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
      environment: {
        ASSISTANT_ID: qConnectAssistantId.valueAsString,
        BACKUP_BUCKET: backupBucket.bucketName,
        BACKUP_LAMBDA_ARN: `arn:aws:lambda:${this.region}:${this.account}:function:supervisor-ai-agent-backup`,
        TESTER_LAMBDA_ARN: `arn:aws:lambda:${this.region}:${this.account}:function:supervisor-ai-agent-tester`,
        CONNECT_INSTANCE_ARN: `arn:aws:connect:${this.region}:${this.account}:instance/${connectInstanceId.valueAsString}`,
        PRODUCTION_AGENT_IDS: cdk.Fn.join(',', productionAgentIds.valueAsList),
        PIN_ATTEMPTS_TABLE: pinAttemptsTable.tableName,
        SIGNING_KEY_SECRET_ARN: signingKeySecret.secretArn,
        LOG_LEVEL: 'INFO',
        POWERTOOLS_SERVICE_NAME: 'supervisor-ai-agent-manager',
        POWERTOOLS_METRICS_NAMESPACE: 'SupervisorAIAgent',
      },
      description: 'Orchestrates AI agent management operations including prompt updates and intent management',
    });

    // Backup Lambda
    const backupLambda = new lambda.Function(this, 'BackupLambda', {
      functionName: 'supervisor-ai-agent-backup',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'backup.handler.lambda_handler',
      ...lambdaVpcConfig,
      code: lambda.Code.fromAsset('../lambda', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r backup/requirements.txt -t /asset-output && cp -au . /asset-output'
          ],
          local: createLocalBundler('backup')
        }
      }),
      role: backupLambdaRole,
      memorySize: 256,
      timeout: cdk.Duration.seconds(60),
      logGroup: new logs.LogGroup(this, 'BackupLogGroup', {
        logGroupName: '/aws/lambda/supervisor-ai-agent-backup',
        retention: logs.RetentionDays.THREE_MONTHS,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
      environment: {
        BACKUP_BUCKET: backupBucket.bucketName,
        SIGNING_KEY_SECRET_ARN: signingKeySecret.secretArn,
        LOG_LEVEL: 'INFO',
        POWERTOOLS_SERVICE_NAME: 'supervisor-ai-agent-backup',
        POWERTOOLS_METRICS_NAMESPACE: 'SupervisorAIAgent',
      },
      description: 'Backs up AI agent prompts and configurations to S3',
    });

    // Restore Lambda
    const restoreLambda = new lambda.Function(this, 'RestoreLambda', {
      functionName: 'supervisor-ai-agent-restore',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'restore.handler.lambda_handler',
      code: lambda.Code.fromAsset('../lambda', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r restore/requirements.txt -t /asset-output && cp -au . /asset-output'
          ],
          local: createLocalBundler('restore')
        }
      }),
      role: restoreLambdaRole,
      memorySize: 256,
      timeout: cdk.Duration.seconds(90),
      logGroup: new logs.LogGroup(this, 'RestoreLogGroup', {
        logGroupName: '/aws/lambda/supervisor-ai-agent-restore',
        retention: logs.RetentionDays.THREE_MONTHS,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
      environment: {
        BACKUP_BUCKET: backupBucket.bucketName,
        AGENT_MANAGER_LAMBDA_ARN: agentManagerLambda.functionArn,
        TESTER_LAMBDA_ARN: `arn:aws:lambda:${this.region}:${this.account}:function:supervisor-ai-agent-tester`,
        SIGNING_KEY_SECRET_ARN: signingKeySecret.secretArn,
        LOG_LEVEL: 'INFO',
        POWERTOOLS_SERVICE_NAME: 'supervisor-ai-agent-restore',
        POWERTOOLS_METRICS_NAMESPACE: 'SupervisorAIAgent',
      },
      description: 'Restores AI agent prompts from S3 backups',
    });

    // Tester Lambda
    const testerLambda = new lambda.Function(this, 'TesterLambda', {
      functionName: 'supervisor-ai-agent-tester',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'tester.handler.lambda_handler',
      code: lambda.Code.fromAsset('../lambda', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r tester/requirements.txt -t /asset-output && cp -au . /asset-output'
          ],
          local: createLocalBundler('tester')
        }
      }),
      role: testerLambdaRole,
      memorySize: 512,
      timeout: cdk.Duration.seconds(90),
      logGroup: new logs.LogGroup(this, 'TesterLogGroup', {
        logGroupName: '/aws/lambda/supervisor-ai-agent-tester',
        retention: logs.RetentionDays.THREE_MONTHS,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
      environment: {
        ASSISTANT_ID: qConnectAssistantId.valueAsString,
        SIGNING_KEY_SECRET_ARN: signingKeySecret.secretArn,
        LOG_LEVEL: 'INFO',
        POWERTOOLS_SERVICE_NAME: 'supervisor-ai-agent-tester',
        POWERTOOLS_METRICS_NAMESPACE: 'SupervisorAIAgent',
      },
      description: 'Validates updated AI agents through automated testing',
    });

    // Update Lambda ARNs in environment variables now that functions are created
    agentManagerLambda.addEnvironment('BACKUP_LAMBDA_ARN', backupLambda.functionArn);
    agentManagerLambda.addEnvironment('TESTER_LAMBDA_ARN', testerLambda.functionArn);
    restoreLambda.addEnvironment('TESTER_LAMBDA_ARN', testerLambda.functionArn);

    // ========================================
    // CloudWatch Log Groups and Alarms
    // ========================================

    // Log groups are auto-created by Lambda with retention set via logRetention on each function

    // SNS topic for alarm notifications (encrypted with KMS)
    const alarmTopic = new sns.Topic(this, 'AlarmTopic', {
      topicName: 'supervisor-ai-agent-alarms',
      displayName: 'Supervisor AI Agent Alarms',
      masterKey: backupEncryptionKey,
    });

    // Restrict SNS publish to CloudWatch Alarms and account root only
    alarmTopic.addToResourcePolicy(new iam.PolicyStatement({
      sid: 'AllowCloudWatchAlarmsPublish',
      effect: iam.Effect.ALLOW,
      principals: [new iam.ServicePrincipal('cloudwatch.amazonaws.com')],
      actions: ['sns:Publish'],
      resources: [alarmTopic.topicArn],
    }));

    // Grant CloudWatch Alarms permission to use the KMS key for SNS encryption
    backupEncryptionKey.grant(
      new iam.ServicePrincipal('cloudwatch.amazonaws.com'),
      'kms:Decrypt',
      'kms:GenerateDataKey*',
    );

    // Subscribe notification email to alarm topic
    alarmTopic.addSubscription(
      new snsSubscriptions.EmailSubscription(
        notificationEmail.valueAsString
      )
    );

    // Alarm: High authentication failure rate
    const authFailureAlarm = new cloudwatch.Alarm(this, 'AuthFailureAlarm', {
      alarmName: 'SupervisorAIAgent-HighAuthFailureRate',
      alarmDescription: 'Alert when authentication failure rate is high (>10 failures in 5 minutes)',
      metric: new cloudwatch.Metric({
        namespace: 'SupervisorAIAgent',
        metricName: 'AuthenticationAttempts',
        dimensionsMap: {
          Result: 'FAILURE',
        },
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 10,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    authFailureAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    // Alarm: Prompt update failures
    const promptUpdateFailureAlarm = new cloudwatch.Alarm(this, 'PromptUpdateFailureAlarm', {
      alarmName: 'SupervisorAIAgent-PromptUpdateFailure',
      alarmDescription: 'Alert when prompt update operations fail',
      metric: new cloudwatch.Metric({
        namespace: 'SupervisorAIAgent',
        metricName: 'PromptUpdates',
        dimensionsMap: {
          Result: 'FAILURE',
        },
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 0,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    promptUpdateFailureAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    // Alarm: Critical test failures
    const criticalTestFailureAlarm = new cloudwatch.Alarm(this, 'CriticalTestFailureAlarm', {
      alarmName: 'SupervisorAIAgent-CriticalTestFailure',
      alarmDescription: 'Alert when critical tests fail after agent updates',
      metric: new cloudwatch.Metric({
        namespace: 'SupervisorAIAgent',
        metricName: 'CriticalTestFailures',
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 0,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    criticalTestFailureAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    // Alarm: Phone spoofing detection (T-0001) - rapid phone validation failures
    const phoneSpoofingAlarm = new cloudwatch.Alarm(this, 'PhoneSpoofingAlarm', {
      alarmName: 'SupervisorAIAgent-PhoneSpoofingDetection',
      alarmDescription: 'Alert when >5 phone validation failures in 5 minutes (possible spoofing)',
      metric: new cloudwatch.Metric({
        namespace: 'SupervisorAIAgent',
        metricName: 'AuthenticationAttempts',
        dimensionsMap: { Result: 'FAILURE' },
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 5,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    phoneSpoofingAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    // Alarm: PIN lockout detection (T-0002)
    const pinLockoutAlarm = new cloudwatch.Alarm(this, 'PinLockoutAlarm', {
      alarmName: 'SupervisorAIAgent-PinLockout',
      alarmDescription: 'Alert when a phone number is locked out due to failed PIN attempts',
      metric: new cloudwatch.Metric({
        namespace: 'SupervisorAIAgent',
        metricName: 'PinLockout',
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 0,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    pinLockoutAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    // Alarm: Unusual authenticated sessions (T-0003) - >3 sessions in 1 hour
    const unusualSessionsAlarm = new cloudwatch.Alarm(this, 'UnusualSessionsAlarm', {
      alarmName: 'SupervisorAIAgent-UnusualAuthSessions',
      alarmDescription: 'Alert when >3 authenticated sessions in 1 hour (possible stolen credentials)',
      metric: new cloudwatch.Metric({
        namespace: 'SupervisorAIAgent',
        metricName: 'AuthenticatedSession',
        statistic: 'Sum',
        period: cdk.Duration.hours(1),
      }),
      threshold: 3,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    unusualSessionsAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    // Alarm: Lambda errors for all functions
    const createLambdaErrorAlarm = (lambdaFunc: lambda.Function, alarmId: string) => {
      const alarm = new cloudwatch.Alarm(this, alarmId, {
        alarmName: `SupervisorAIAgent-${lambdaFunc.functionName}-Errors`,
        alarmDescription: `Alert when ${lambdaFunc.functionName} error rate exceeds 5%`,
        metric: lambdaFunc.metricErrors({
          statistic: 'Sum',
          period: cdk.Duration.minutes(5),
        }),
        threshold: 5,
        evaluationPeriods: 1,
        comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      });
      alarm.addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));
      return alarm;
    };

    createLambdaErrorAlarm(authLambda, 'AuthLambdaErrorAlarm');
    createLambdaErrorAlarm(agentManagerLambda, 'AgentManagerLambdaErrorAlarm');
    createLambdaErrorAlarm(backupLambda, 'BackupLambdaErrorAlarm');
    createLambdaErrorAlarm(restoreLambda, 'RestoreLambdaErrorAlarm');
    createLambdaErrorAlarm(testerLambda, 'TesterLambdaErrorAlarm');

    // Alarm: Lambda throttling for all functions
    const createLambdaThrottleAlarm = (lambdaFunc: lambda.Function, alarmId: string) => {
      const alarm = new cloudwatch.Alarm(this, alarmId, {
        alarmName: `SupervisorAIAgent-${lambdaFunc.functionName}-Throttles`,
        alarmDescription: `Alert when ${lambdaFunc.functionName} is being throttled`,
        metric: lambdaFunc.metricThrottles({
          statistic: 'Sum',
          period: cdk.Duration.minutes(5),
        }),
        threshold: 0,
        evaluationPeriods: 1,
        comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      });
      alarm.addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));
      return alarm;
    };

    createLambdaThrottleAlarm(authLambda, 'AuthLambdaThrottleAlarm');
    createLambdaThrottleAlarm(agentManagerLambda, 'AgentManagerLambdaThrottleAlarm');
    createLambdaThrottleAlarm(backupLambda, 'BackupLambdaThrottleAlarm');
    createLambdaThrottleAlarm(restoreLambda, 'RestoreLambdaThrottleAlarm');
    createLambdaThrottleAlarm(testerLambda, 'TesterLambdaThrottleAlarm');

    // ========================================
    // Stack Outputs
    // ========================================
    new cdk.CfnOutput(this, 'StackRegion', {
      value: this.region,
      description: 'AWS Region for this stack',
    });

    new cdk.CfnOutput(this, 'StackAccount', {
      value: this.account,
      description: 'AWS Account ID for this stack',
    });

    new cdk.CfnOutput(this, 'BackupBucketName', {
      value: backupBucket.bucketName,
      description: 'S3 bucket name for backups, intent configs, and audit logs',
      exportName: 'SupervisorAIAgent-BackupBucketName',
    });

    new cdk.CfnOutput(this, 'BackupBucketArn', {
      value: backupBucket.bucketArn,
      description: 'S3 bucket ARN for backups, intent configs, and audit logs',
      exportName: 'SupervisorAIAgent-BackupBucketArn',
    });

    new cdk.CfnOutput(this, 'SupervisorPinSecretArnOutput', {
      value: supervisorPinSecret.secretArn,
      description: 'ARN of Secrets Manager secret containing supervisor PIN',
      exportName: 'SupervisorAIAgent-SupervisorPinSecretArn',
    });

    new cdk.CfnOutput(this, 'AuthLambdaRoleArn', {
      value: authLambdaRole.roleArn,
      description: 'ARN of Authentication Lambda execution role',
      exportName: 'SupervisorAIAgent-AuthLambdaRoleArn',
    });

    new cdk.CfnOutput(this, 'AgentManagerLambdaRoleArn', {
      value: agentManagerLambdaRole.roleArn,
      description: 'ARN of Agent Manager Lambda execution role',
      exportName: 'SupervisorAIAgent-AgentManagerLambdaRoleArn',
    });

    new cdk.CfnOutput(this, 'BackupLambdaRoleArn', {
      value: backupLambdaRole.roleArn,
      description: 'ARN of Backup Lambda execution role',
      exportName: 'SupervisorAIAgent-BackupLambdaRoleArn',
    });

    new cdk.CfnOutput(this, 'RestoreLambdaRoleArn', {
      value: restoreLambdaRole.roleArn,
      description: 'ARN of Restore Lambda execution role',
      exportName: 'SupervisorAIAgent-RestoreLambdaRoleArn',
    });

    new cdk.CfnOutput(this, 'TesterLambdaRoleArn', {
      value: testerLambdaRole.roleArn,
      description: 'ARN of Tester Lambda execution role',
      exportName: 'SupervisorAIAgent-TesterLambdaRoleArn',
    });

    new cdk.CfnOutput(this, 'AuthLambdaArn', {
      value: authLambda.functionArn,
      description: 'ARN of Authentication Lambda function',
      exportName: 'SupervisorAIAgent-AuthLambdaArn',
    });

    new cdk.CfnOutput(this, 'AuthLambdaName', {
      value: authLambda.functionName,
      description: 'Name of Authentication Lambda function',
      exportName: 'SupervisorAIAgent-AuthLambdaName',
    });

    new cdk.CfnOutput(this, 'AgentManagerLambdaArn', {
      value: agentManagerLambda.functionArn,
      description: 'ARN of Agent Manager Lambda function',
      exportName: 'SupervisorAIAgent-AgentManagerLambdaArn',
    });

    new cdk.CfnOutput(this, 'AgentManagerLambdaName', {
      value: agentManagerLambda.functionName,
      description: 'Name of Agent Manager Lambda function',
      exportName: 'SupervisorAIAgent-AgentManagerLambdaName',
    });

    new cdk.CfnOutput(this, 'BackupLambdaArn', {
      value: backupLambda.functionArn,
      description: 'ARN of Backup Lambda function',
      exportName: 'SupervisorAIAgent-BackupLambdaArn',
    });

    new cdk.CfnOutput(this, 'BackupLambdaName', {
      value: backupLambda.functionName,
      description: 'Name of Backup Lambda function',
      exportName: 'SupervisorAIAgent-BackupLambdaName',
    });

    new cdk.CfnOutput(this, 'RestoreLambdaArn', {
      value: restoreLambda.functionArn,
      description: 'ARN of Restore Lambda function',
      exportName: 'SupervisorAIAgent-RestoreLambdaArn',
    });

    new cdk.CfnOutput(this, 'RestoreLambdaName', {
      value: restoreLambda.functionName,
      description: 'Name of Restore Lambda function',
      exportName: 'SupervisorAIAgent-RestoreLambdaName',
    });

    new cdk.CfnOutput(this, 'TesterLambdaArn', {
      value: testerLambda.functionArn,
      description: 'ARN of Tester Lambda function',
      exportName: 'SupervisorAIAgent-TesterLambdaArn',
    });

    new cdk.CfnOutput(this, 'TesterLambdaName', {
      value: testerLambda.functionName,
      description: 'Name of Tester Lambda function',
      exportName: 'SupervisorAIAgent-TesterLambdaName',
    });

    new cdk.CfnOutput(this, 'AlarmTopicArn', {
      value: alarmTopic.topicArn,
      description: 'ARN of SNS topic for CloudWatch alarms',
      exportName: 'SupervisorAIAgent-AlarmTopicArn',
    });

    new cdk.CfnOutput(this, 'ConnectInstanceIdOutput', {
      value: connectInstanceId.valueAsString,
      description: 'Amazon Connect instance ID (from parameters)',
    });

    new cdk.CfnOutput(this, 'QConnectAssistantIdOutput', {
      value: qConnectAssistantId.valueAsString,
      description: 'Amazon Q in Connect assistant ID (from parameters)',
    });

    // ========================================
    // Amazon Connect Contact Flow
    // ========================================
    // PIN validation is handled by the Supervisor AI Agent via MCP tool
    // (no separate Lex PIN bot needed). Flow: phone auth → Conversational AI bot → disconnect.

    // Contact Flow JSON definition
    // CDK deploys phone auth flow only. AI agent blocks added manually via console
    // after creating Conversational AI bot (Step 3 of supervisor-ai-agent-setup.md).

    const contactFlowContent = JSON.stringify({
      Version: '2019-10-30',
      StartAction: 'action-logging',
      Metadata: {
        entryPointPosition: { x: 20, y: 200 },
        snapToGrid: false,
        ActionMetadata: {
          'action-logging': { position: { x: 200, y: 200 } },
          'action-1': { position: { x: 420, y: 200 } },
          'action-2': { position: { x: 640, y: 200 } },
          'action-3': { position: { x: 860, y: 200 } },
          'action-4': { position: { x: 1080, y: 200 } },
          'action-unauthorized': { position: { x: 1080, y: 420 } },
          'action-authenticated': { position: { x: 1300, y: 200 } },
          'action-set-flowtype': { position: { x: 1190, y: 200 } },
          'action-disconnect': { position: { x: 1520, y: 300 } },
        },
      },
      Actions: [
        {
          Identifier: 'action-logging',
          Type: 'UpdateFlowLoggingBehavior',
          Parameters: { FlowLoggingBehavior: 'Enabled' },
          Transitions: { NextAction: 'action-1', Errors: [], Conditions: [] },
        },
        {
          Identifier: 'action-1',
          Type: 'UpdateContactRecordingBehavior',
          Parameters: { RecordingBehavior: { RecordedParticipants: ['Agent', 'Customer'] } },
          Transitions: { NextAction: 'action-2', Errors: [], Conditions: [] },
        },
        {
          Identifier: 'action-2',
          Type: 'UpdateContactAttributes',
          Parameters: { Attributes: { CallerPhoneNumber: '$.CustomerEndpoint.Address' } },
          Transitions: {
            NextAction: 'action-3',
            Errors: [{ ErrorType: 'NoMatchingError', NextAction: 'action-disconnect' }],
            Conditions: [],
          },
        },
        {
          Identifier: 'action-3',
          Type: 'InvokeLambdaFunction',
          Parameters: {
            LambdaFunctionARN: authLambda.functionArn,
            InvocationTimeLimitSeconds: '8',
            LambdaInvocationAttributes: {
              operation: 'validate_phone',
              phoneNumber: '$.Attributes.CallerPhoneNumber',
            },
            ResponseValidation: { ResponseType: 'STRING_MAP' },
          },
          Transitions: {
            NextAction: 'action-4',
            Errors: [{ ErrorType: 'NoMatchingError', NextAction: 'action-disconnect' }],
            Conditions: [],
          },
        },
        {
          Identifier: 'action-4',
          Type: 'Compare',
          Parameters: { ComparisonValue: '$.External.authenticated' },
          Transitions: {
            NextAction: 'action-unauthorized',
            Errors: [{ ErrorType: 'NoMatchingCondition', NextAction: 'action-unauthorized' }],
            Conditions: [{
              NextAction: 'action-set-flowtype',
              Condition: { Operator: 'Equals', Operands: ['true'] },
            }],
          },
        },
        {
          Identifier: 'action-unauthorized',
          Type: 'MessageParticipant',
          Parameters: { Text: 'Your phone number is not authorized to access this system. Goodbye.' },
          Transitions: {
            NextAction: 'action-disconnect',
            Errors: [{ ErrorType: 'NoMatchingError', NextAction: 'action-disconnect' }],
            Conditions: [],
          },
        },
        // Placeholder: replace this block with Conversational AI bot via Connect console
        {
          Identifier: 'action-set-flowtype',
          Type: 'UpdateContactAttributes',
          Parameters: { Attributes: { FlowType: 'SUPERVISOR' } },
          Transitions: {
            NextAction: 'action-authenticated',
            Errors: [{ ErrorType: 'NoMatchingError', NextAction: 'action-disconnect' }],
            Conditions: [],
          },
        },
        {
          Identifier: 'action-authenticated',
          Type: 'MessageParticipant',
          Parameters: { Text: 'Phone authenticated. Please complete setup by adding the Conversational AI bot block in the Connect console.' },
          Transitions: {
            NextAction: 'action-disconnect',
            Errors: [{ ErrorType: 'NoMatchingError', NextAction: 'action-disconnect' }],
            Conditions: [],
          },
        },
        {
          Identifier: 'action-disconnect',
          Type: 'DisconnectParticipant',
          Parameters: {},
          Transitions: {},
        },
      ],
    });

    // Create Contact Flow
    const supervisorContactFlow = new connect.CfnContactFlow(this, 'SupervisorContactFlow', {
      name: 'SupervisorAIAgentFlow',
      description: 'Contact flow for Supervisor AI Agent with phone authentication and AI-driven PIN validation',
      type: 'CONTACT_FLOW',
      content: contactFlowContent,
      instanceArn: `arn:aws:connect:${this.region}:${this.account}:instance/${connectInstanceId.valueAsString}`,
      state: 'ACTIVE',
    });

    // Grant Connect permission to invoke Authentication Lambda
    authLambda.addPermission('AllowConnectInvoke', {
      principal: new iam.ServicePrincipal('connect.amazonaws.com'),
      action: 'lambda:InvokeFunction',
      sourceArn: `arn:aws:connect:${this.region}:${this.account}:instance/${connectInstanceId.valueAsString}`,
    });

    // ========================================
    // Stack Outputs for Contact Flow
    // ========================================
    new cdk.CfnOutput(this, 'SupervisorContactFlowId', {
      value: supervisorContactFlow.attrContactFlowArn,
      description: 'Amazon Connect Supervisor Contact Flow ARN',
      exportName: 'SupervisorAIAgent-ContactFlowArn',
    });

    // ========================================
    // Customer Contact Flow
    // ========================================

    const customerContactFlowContent = JSON.stringify({
      Version: '2019-10-30',
      StartAction: 'action-logging',
      Metadata: {
        entryPointPosition: { x: 20, y: 200 },
        snapToGrid: false,
        ActionMetadata: {
          'action-logging': { position: { x: 200, y: 200 } },
          'action-recording': { position: { x: 420, y: 200 } },
          'action-set-flowtype': { position: { x: 530, y: 200 } },
          'action-placeholder': { position: { x: 640, y: 200 } },
          'action-disconnect': { position: { x: 860, y: 200 } },
        },
      },
      Actions: [
        {
          Identifier: 'action-logging',
          Type: 'UpdateFlowLoggingBehavior',
          Parameters: { FlowLoggingBehavior: 'Enabled' },
          Transitions: { NextAction: 'action-recording', Errors: [], Conditions: [] },
        },
        {
          Identifier: 'action-recording',
          Type: 'UpdateContactRecordingBehavior',
          Parameters: { RecordingBehavior: { RecordedParticipants: ['Agent', 'Customer'] } },
          Transitions: { NextAction: 'action-set-flowtype', Errors: [], Conditions: [] },
        },
        {
          Identifier: 'action-set-flowtype',
          Type: 'UpdateContactAttributes',
          Parameters: { Attributes: { FlowType: 'CUSTOMER' } },
          Transitions: {
            NextAction: 'action-placeholder',
            Errors: [{ ErrorType: 'NoMatchingError', NextAction: 'action-disconnect' }],
            Conditions: [],
          },
        },
        {
          Identifier: 'action-placeholder',
          Type: 'MessageParticipant',
          Parameters: { Text: 'Customer flow setup in progress. Please add the Conversational AI bot block in the Connect console.' },
          Transitions: {
            NextAction: 'action-disconnect',
            Errors: [{ ErrorType: 'NoMatchingError', NextAction: 'action-disconnect' }],
            Conditions: [],
          },
        },
        {
          Identifier: 'action-disconnect',
          Type: 'DisconnectParticipant',
          Parameters: {},
          Transitions: {},
        },
      ],
    });

    const customerContactFlow = new connect.CfnContactFlow(this, 'CustomerContactFlow', {
      name: 'CustomerContactFlow',
      description: 'Customer-facing contact flow for Production AI Agent',
      type: 'CONTACT_FLOW',
      content: customerContactFlowContent,
      instanceArn: `arn:aws:connect:${this.region}:${this.account}:instance/${connectInstanceId.valueAsString}`,
      state: 'ACTIVE',
    });

    new cdk.CfnOutput(this, 'CustomerContactFlowArn', {
      value: customerContactFlow.attrContactFlowArn,
      description: 'Amazon Connect Customer Contact Flow ARN',
      exportName: 'SupervisorAIAgent-CustomerContactFlowArn',
    });

    // ========================================
    // Amazon Q in Connect Supervisor AI Agent
    // ========================================

    // System prompt for Supervisor AI Agent (condensed version)
    const supervisorSystemPrompt = `You are the Supervisor AI Agent for Amazon Connect Outage Management. You help operations managers update production AI agent prompts during service outages through natural language conversation.

## MANDATORY PIN AUTHENTICATION
BEFORE performing ANY operation or discussing ANY capabilities, you MUST validate the caller's PIN:
1. Your FIRST message MUST ask: "Welcome to the Supervisor AI Agent. For security, please provide your 6-digit PIN."
2. Use the validate_pin tool with the provided PIN
3. If validation fails, inform the caller and allow up to 3 total attempts
4. If all 3 attempts fail, say "Maximum authentication attempts exceeded. Goodbye." and use the Complete tool to end the session
5. NEVER proceed to any other tool or operation without successful PIN validation
6. NEVER reveal whether a PIN was partially correct
7. After successful validation, greet the manager and ask how you can help

Your role is to:
1. Greet authenticated operations managers warmly and professionally
2. Understand outage situations through natural conversation
3. Extract critical information (affected services, available services, recovery time)
4. Explain planned changes clearly before execution
5. Request explicit confirmation before making updates
6. Coordinate backend operations through tool integrations
7. Report results with test validation details

## Conversational Style
- Professional: Maintain a calm, competent demeanor during high-stress situations
- Supportive: Acknowledge the urgency and provide reassurance
- Clear: Use simple, direct language without technical jargon
- Efficient: Move conversations forward purposefully while being thorough

## Greeting
After successful PIN authentication:
"Authentication successful. Hello, this is the Supervisor AI Agent for outage management. I'm here to help you update production AI agent prompts during service disruptions. What situation are you dealing with today?"

## Operational Modes
Support two modes based on the operations manager's description:

### Full Outage Mode
Use when describing complete service outages, multiple capabilities unavailable, or broad disruptions.
Indicators: "system down", "service unavailable", "everything is broken", "major outage"

### Intent-Level Mode
Use when describing specific capability issues, targeted degradation, or need to disable specific functionality.
Indicators: "disable [feature]", "turn off [capability]", "list what the agent can do"

## Outage Information Extraction
Extract: affected services, available services, estimated recovery time.
If missing critical information, ask targeted clarifying questions.

## Change Explanation (Full Outage Mode)
Before updating, explain:
- Current configuration
- Planned changes (what will be marked unavailable, what remains available)
- What this means for customers
- That a backup will be created

## Confirmation Requirement
CRITICAL: Never proceed without explicit confirmation.
Acceptable: "Yes", "Yes, proceed", "Go ahead", "That's correct", "Do it", "Make the changes"
Declined: "No", "Wait", "Hold on", "That's not right", "Let me think about it"

## Intent Management Operations

### Listing Capabilities
When asked "what can the agent do?", use list_agent_intents tool and present in natural language.

### Disabling Intents
1. Confirm intent name and current status
2. Explain impact (customers told unavailable, alternatives suggested, others continue)
3. Request confirmation
4. Use disable_intent tool
5. Report results with test validation

### Enabling Intents
1. Confirm intent name and current status
2. Explain impact (customers can use normally again)
3. Request confirmation
4. Use enable_intent tool
5. Report results with test validation

### Restoring All Intents
1. Confirm operation
2. Use restore_all_intents tool
3. Report results with duration and test validation

## Tool Usage
Use configured tools to execute operations after confirmation. All tools handle backup, testing, and audit logging automatically.

## Result Reporting
After successful operations, provide comprehensive confirmation including:
- Update/restore completion status
- Backup location
- Testing results (total tests, passed, failed)
- Sample responses showing how the agent now behaves
- Next steps

## Error Handling
If a tool call fails, translate errors to user-friendly messages and provide guidance on next steps.

## Important Reminders
1. Always create backups before updates (handled automatically by tools)
2. Always test after updates (handled automatically by tools)
3. Never proceed without confirmation (your responsibility)
4. Explain changes clearly
5. Report results comprehensively
6. Maintain professional composure
7. Be efficient but thorough
8. Handle errors gracefully
9. Support both operational modes
10. Preserve agent personality in updates`;

    // ========================================
    // NOTE: AI Prompt and AI Agent resources are created manually
    // after CDK deployment. See docs/deployment/supervisor-ai-agent-setup.md
    // The system prompt above is used during manual configuration.
    // ========================================

    // Grant Q Connect permission to invoke Lambda functions
    agentManagerLambda.addPermission('AllowQConnectInvoke', {
      principal: new iam.ServicePrincipal('wisdom.amazonaws.com'),
      action: 'lambda:InvokeFunction',
      sourceArn: `arn:aws:wisdom:${this.region}:${this.account}:assistant/${qConnectAssistantId.valueAsString}`,
    });

    agentManagerLambda.addPermission('AllowConnectInvoke', {
      principal: new iam.ServicePrincipal('connect.amazonaws.com'),
      action: 'lambda:InvokeFunction',
      sourceArn: `arn:aws:connect:${this.region}:${this.account}:instance/${connectInstanceId.valueAsString}`,
    });

    restoreLambda.addPermission('AllowQConnectInvoke', {
      principal: new iam.ServicePrincipal('wisdom.amazonaws.com'),
      action: 'lambda:InvokeFunction',
      sourceArn: `arn:aws:wisdom:${this.region}:${this.account}:assistant/${qConnectAssistantId.valueAsString}`,
    });

    authLambda.addPermission('AllowQConnectInvoke', {
      principal: new iam.ServicePrincipal('wisdom.amazonaws.com'),
      action: 'lambda:InvokeFunction',
      sourceArn: `arn:aws:wisdom:${this.region}:${this.account}:assistant/${qConnectAssistantId.valueAsString}`,
    });
  }
}
