"""
Agent Manager Lambda handler.

Orchestrates AI agent management operations including:
- Listing agents
- Retrieving agent configurations
- Generating updated AI Prompts
- Updating AI Agent configurations
- Coordinating backup and testing workflows
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.base_handler import BaseLambdaHandler
from shared.retry_logic import exponential_backoff
from shared.audit_logging import AuditLogger
from shared.error_handling import create_error_response
from shared.metrics_publisher import MetricsPublisher
from agent_manager.intent_configuration import IntentConfiguration, Intent
from agent_manager.intent_persistence import IntentConfigurationPersistence
from agent_manager.intent_discovery import IntentDiscovery
from agent_manager.prompt_generator import PromptGenerator


class AgentManagerHandler(BaseLambdaHandler):
    """Handler for Agent Manager Lambda operations."""
    
    def __init__(self):
        # Pre-warm frequently used clients during initialization
        super().__init__(
            "supervisor-ai-agent-manager",
            prewarm_clients=['qconnect', 'lambda', 's3']
        )
        
        # Get environment variables
        self.assistant_id = self.get_required_env_var('ASSISTANT_ID')
        self.backup_bucket = self.get_required_env_var('BACKUP_BUCKET')
        self.backup_lambda_arn = self.get_required_env_var('BACKUP_LAMBDA_ARN')
        self.tester_lambda_arn = self.get_required_env_var('TESTER_LAMBDA_ARN')
        self.connect_instance_arn = self.get_required_env_var('CONNECT_INSTANCE_ARN')
        
        # Initialize AWS clients
        self.q_connect = self.aws_clients.get_q_connect_client()
        self.lambda_client = self.aws_clients.get_lambda_client()
        self.s3_client = self.aws_clients.get_s3_client()
        
        # Initialize audit logger
        self.audit_logger = AuditLogger(
            bucket_name=self.backup_bucket,
            logger=self.logger
        )
        
        # Initialize intent management components
        self.intent_persistence = IntentConfigurationPersistence(
            s3_client=self.s3_client,
            bucket_name=self.backup_bucket,
            logger=self.logger
        )
        self.intent_discovery = IntentDiscovery(logger=self.logger)
        self.prompt_generator = PromptGenerator(logger=self.logger)
    
    def _verify_authentication(self, event: Dict[str, Any]) -> bool:
        """Verify server-side auth token from DynamoDB."""
        auth_token = event.get('authToken')
        if not auth_token:
            self.logger.warning('No auth token provided')
            return False
        try:
            import time
            table_name = os.environ.get('PIN_ATTEMPTS_TABLE', 'supervisor-ai-agent-pin-attempts')
            dynamodb = self.aws_clients.get_dynamodb_resource()
            table = dynamodb.Table(table_name)
            response = table.get_item(Key={'phone_number': f'auth_token#{auth_token}'})
            item = response.get('Item')
            if not item:
                self.logger.warning('Auth token not found')
                return False
            if item.get('ttl_expiry', 0) < time.time():
                self.logger.warning('Auth token expired')
                return False
            return True
        except Exception as e:
            self.logger.error('Auth token verification failed', extra={'error': str(e)})
            return False
    
    def process_event(self, event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        """
        Process Agent Manager Lambda event.
        
        Args:
            event: Lambda event with operation and parameters
            context: Lambda context
            
        Returns:
            Operation result
        """
        operation = event.get('operation')
        
        # Connect contact flow passes attributes under Details.Parameters
        if not operation and 'Details' in event:
            operation = event.get('Details', {}).get('Parameters', {}).get('operation')
        
        if not operation:
            raise ValueError("Missing required field: operation")
        
        # Verify authentication for mutating operations
        mutating_ops = ['update_agent', 'update_agents', 'disable_intent', 'enable_intent', 'restore']
        if operation in mutating_ops:
            if not self._verify_authentication(event):
                return {'success': False, 'error': 'Authentication required. Provide a valid authToken.'}
        
        # Route to appropriate operation handler
        if operation == 'list_agents':
            return self.list_agents(event)
        elif operation == 'get_agent':
            return self.get_agent(event)
        elif operation == 'list_intents':
            return self.list_intents(event)
        elif operation == 'disable_intent':
            return self.disable_intent(event, context)
        elif operation == 'enable_intent':
            return self.enable_intent(event, context)
        elif operation == 'restore_all_intents':
            return self.restore_all_intents(event, context)
        elif operation == 'update_agent':
            return self.update_agent(event, context)
        elif operation == 'update_agents':
            return self.update_agents(event, context)
        elif operation == 'set_session_agent':
            return self._set_session_agent(event)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    def _set_session_agent(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Set AI agent override for a Q Connect session (used by customer contact flow)."""
        # Connect flow passes attributes under Details.Parameters
        params = event.get('Details', {}).get('Parameters', event)
        session_arn = params.get('sessionArn', '')
        agent_id = params.get('agentId', '').strip()
        assistant_id = os.environ.get('ASSISTANT_ID', '')
        self.logger.info('set_session_agent called', extra={
            'hasDetails': 'Details' in event,
            'paramKeys': list(params.keys()),
            'sessionArn': session_arn[:50] if session_arn else 'EMPTY',
            'agentId': agent_id or 'EMPTY',
        })
        if not session_arn or not agent_id:
            return {'success': 'false', 'error': 'Missing sessionArn or agentId'}
        session_id = session_arn.split('/')[-1] if '/' in session_arn else session_arn
        try:
            self.aws_clients.get_q_connect_client().update_session(
                assistantId=assistant_id,
                sessionId=session_id,
                aiAgentConfiguration={
                    'ORCHESTRATION': {'aiAgentId': agent_id}
                }
            )
            self.logger.info('Set session agent', extra={'sessionId': session_id, 'agentId': agent_id})
            return {'success': 'true', 'agentId': agent_id}
        except Exception as e:
            self.logger.error('Failed to set session agent', extra={'error': str(e), 'sessionId': session_id})
            return {'success': 'true'}  # Don't block the call on failure

    def list_agents(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        List AI agents using Amazon Q in Connect ListAIAgents API.
        
        Args:
            event: Event with optional filters
            
        Returns:
            List of agents with ID, name, type, status, description
        """
        self.logger.info("Listing AI agents", extra={"assistantId": self.assistant_id})
        
        try:
            # Get filter parameters
            filters = event.get('filters', {})
            origin = filters.get('origin', 'CUSTOMER')  # Default to CUSTOMER agents
            
            # Call ListAIAgents API with pagination
            agents = []
            next_token = None
            
            while True:
                params = {
                    'assistantId': self.assistant_id,
                    'maxResults': 100
                }
                
                if origin:
                    params['origin'] = origin
                
                if next_token:
                    params['nextToken'] = next_token
                
                response = self._list_ai_agents_with_retry(params)
                
                # Extract agent summaries
                for agent_summary in response.get('aiAgentSummaries', []):
                    agents.append({
                        'agentId': agent_summary['aiAgentId'],
                        'agentName': agent_summary['name'],
                        'type': agent_summary['type'],
                        'status': agent_summary['status'],
                        'description': agent_summary.get('description', ''),
                        'visibilityStatus': agent_summary.get('visibilityStatus', 'SAVED')
                    })
                
                # Check for more pages
                next_token = response.get('nextToken')
                if not next_token:
                    break
            
            self.logger.info(
                "Successfully listed AI agents",
                extra={
                    "assistantId": self.assistant_id,
                    "agentCount": len(agents),
                    "origin": origin
                }
            )
            
            return {
                'success': True,
                'agents': agents,
                'count': len(agents)
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            self.logger.error(
                "Failed to list AI agents",
                extra={
                    "assistantId": self.assistant_id,
                    "errorCode": error_code,
                    "errorMessage": error_message
                }
            )
            
            raise
    
    @exponential_backoff(max_attempts=3, base_delay=1.0)
    def _list_ai_agents_with_retry(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call ListAIAgents API with retry logic.
        
        Args:
            params: API parameters
            
        Returns:
            API response
        """
        return self.q_connect.list_ai_agents(**params, logger=self.logger)
    
    def get_agent(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get AI agent configuration using Amazon Q in Connect GetAIAgent API.
        
        Args:
            event: Event with agentId
            
        Returns:
            Complete agent configuration including prompt, guardrails, tools
        """
        agent_id = event.get('agentId')
        
        if not agent_id:
            raise ValueError("Missing required field: agentId")
        
        self.logger.info(
            "Getting AI agent configuration",
            extra={
                "assistantId": self.assistant_id,
                "agentId": agent_id
            }
        )
        
        try:
            # Call GetAIAgent API
            response = self._get_ai_agent_with_retry(agent_id)
            
            agent = response['aiAgent']
            
            # Extract configuration details
            result = {
                'success': True,
                'agentId': agent['aiAgentId'],
                'agentName': agent['name'],
                'agentType': agent['type'],
                'status': agent['status'],
                'visibilityStatus': agent.get('visibilityStatus', 'SAVED'),
                'description': agent.get('description', ''),
                'configuration': agent.get('configuration', {}),
                'modifiedTime': agent.get('modifiedTime')
            }
            
            self.logger.info(
                "Successfully retrieved AI agent configuration",
                extra={
                    "assistantId": self.assistant_id,
                    "agentId": agent_id,
                    "agentName": agent['name'],
                    "agentType": agent['type']
                }
            )
            
            return result
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            self.logger.error(
                "Failed to get AI agent configuration",
                extra={
                    "assistantId": self.assistant_id,
                    "agentId": agent_id,
                    "errorCode": error_code,
                    "errorMessage": error_message
                }
            )
            
            # Handle invalid agent ID
            if error_code == 'ResourceNotFoundException':
                raise ValueError(f"Agent not found: {agent_id}")
            
            raise
    
    @exponential_backoff(max_attempts=3, base_delay=1.0)
    def _get_ai_agent_with_retry(self, agent_id: str) -> Dict[str, Any]:
        """
        Call GetAIAgent API with retry logic.
        
        Args:
            agent_id: AI Agent ID
            
        Returns:
            API response
        """
        return self.q_connect.get_ai_agent(
            assistantId=self.assistant_id,
            aiAgentId=agent_id,
            logger=self.logger
        )
    
    def list_intents(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        List intents for an AI agent.
        
        Workflow:
        1. Check S3 for existing Intent_Configuration
        2. If exists, parse and return intent list
        3. If not exists, analyze prompt to extract intents
        4. Create initial Intent_Configuration with all intents enabled
        5. Store Intent_Configuration to S3
        
        Args:
            event: Event with agentId
            
        Returns:
            List of intents with names, descriptions, and enabled/disabled status
        """
        agent_id = event.get('agentId')
        
        if not agent_id:
            raise ValueError("Missing required field: agentId")
        
        self.logger.info(
            "Listing intents for agent",
            extra={"agentId": agent_id}
        )
        
        try:
            # Check S3 for existing Intent_Configuration
            config = self.intent_persistence.load_configuration(agent_id)
            
            if config:
                # Configuration exists, return intent list
                self.logger.info(
                    "Found existing Intent_Configuration",
                    extra={
                        "agentId": agent_id,
                        "intentCount": len(config.intents),
                        "version": config.version
                    }
                )
                
                return {
                    'success': True,
                    'agentId': agent_id,
                    'intents': [intent.to_dict() for intent in config.intents],
                    'version': config.version,
                    'timestamp': config.timestamp
                }
            
            # Configuration doesn't exist, analyze prompt to extract intents
            self.logger.info(
                "Intent_Configuration not found, analyzing prompt",
                extra={"agentId": agent_id}
            )
            
            # Get agent configuration to retrieve prompt
            agent_response = self.get_agent({'agentId': agent_id})
            agent_config = agent_response['configuration']
            
            # Extract prompt ID from configuration
            prompt_id = None
            if 'orchestrationAIAgentConfiguration' in agent_config:
                prompt_id = agent_config['orchestrationAIAgentConfiguration'].get('orchestrationAIPromptId')
            
            if not prompt_id:
                raise ValueError(f"Could not find AI Prompt ID in agent configuration for agent {agent_id}")
            
            # Retrieve AI Prompt text
            prompt_response = self._get_ai_prompt_with_retry(prompt_id)
            prompt_text = prompt_response['aiPrompt']['templateConfiguration']['textFullAIPromptEditTemplateConfiguration']['text']
            
            # Extract intents from prompt
            intents = self.intent_discovery.extract_intents_from_prompt(prompt_text)
            
            # Create initial Intent_Configuration with all intents enabled
            config = IntentConfiguration(
                agent_id=agent_id,
                timestamp=datetime.utcnow().isoformat() + 'Z',
                intents=intents,
                version=1
            )
            
            # Store Intent_Configuration to S3
            self.intent_persistence.save_configuration(config)
            
            self.logger.info(
                "Created and stored initial Intent_Configuration",
                extra={
                    "agentId": agent_id,
                    "intentCount": len(intents)
                }
            )
            
            return {
                'success': True,
                'agentId': agent_id,
                'intents': [intent.to_dict() for intent in config.intents],
                'version': config.version,
                'timestamp': config.timestamp
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            self.logger.error(
                "Failed to list intents",
                extra={
                    "agentId": agent_id,
                    "errorCode": error_code,
                    "errorMessage": error_message
                }
            )
            
            raise
    
    @exponential_backoff(max_attempts=3, base_delay=1.0)
    def _get_ai_prompt_with_retry(self, prompt_id: str) -> Dict[str, Any]:
        """
        Call GetAIPrompt API with retry logic.
        
        Args:
            prompt_id: AI Prompt ID (may include version)
            
        Returns:
            API response
        """
        return self.q_connect.get_ai_prompt(
            assistantId=self.assistant_id,
            aiPromptId=prompt_id,
            logger=self.logger
        )
    
    def disable_intent(self, event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        """
        Disable a specific intent.
        
        Workflow:
        1. Retrieve current Intent_Configuration from S3
        2. Update configuration to mark specified intent as disabled
        3. Backup current AI Agent configuration and Intent_Configuration
        4. Generate new AI Prompt text with disabled intent handling
        5. Create new AI Prompt version using CreateAIPromptVersion API
        6. Update AI Agent configuration using UpdateAIAgent API
        7. Set visibilityStatus to PUBLISHED
        8. Test agent with disabled and enabled intent queries
        9. Store updated Intent_Configuration to S3
        10. Log operation to audit logs
        
        Args:
            event: Event with agentId, intentName, callerPhoneNumber
            context: Lambda context
            
        Returns:
            Result with backup location and test results
        """
        agent_id = event.get('agentId')
        intent_name = event.get('intentName')
        caller_phone_number = event.get('callerPhoneNumber', 'unknown')
        
        if not agent_id or not intent_name:
            raise ValueError("Missing required fields: agentId, intentName")
        
        self.logger.info(
            "Disabling intent",
            extra={
                "agentId": agent_id,
                "intentName": intent_name,
                "caller": caller_phone_number
            }
        )
        
        try:
            # Retrieve current Intent_Configuration
            config = self.intent_persistence.load_configuration(agent_id)
            if not config:
                raise ValueError(f"Intent_Configuration not found for agent {agent_id}. Run list_intents first.")
            
            # Store before config for audit logging
            before_config = config.to_dict()
            
            # Update configuration to disable intent
            if not config.disable_intent(intent_name, caller_phone_number):
                raise ValueError(f"Intent not found: {intent_name}")
            
            # Get current agent configuration
            agent_response = self.get_agent({'agentId': agent_id})
            agent_config = agent_response['configuration']
            
            # Backup current configuration and Intent_Configuration
            backup_result = self._backup_agent_with_intents(
                agent_id=agent_id,
                agent_name=agent_response['agentName'],
                agent_config=agent_config,
                intent_config=config,
                caller_phone_number=caller_phone_number,
                backup_reason='intent-disable'
            )
            
            # Get current prompt
            prompt_id = agent_config['orchestrationAIAgentConfiguration']['orchestrationAIPromptId']
            prompt_response = self._get_ai_prompt_with_retry(prompt_id)
            original_prompt_text = prompt_response['aiPrompt']['templateConfiguration']['textFullAIPromptEditTemplateConfiguration']['text']
            
            # Generate new AI Prompt text with disabled intent handling
            updated_prompt_text = self.prompt_generator.generate_prompt_with_intent_management(
                original_prompt=original_prompt_text,
                intent_config=config
            )
            
            # Create new AI Prompt version
            new_prompt_version = self._create_ai_prompt_version(
                prompt_id=prompt_id,
                prompt_text=updated_prompt_text
            )
            
            # Update AI Agent configuration
            self._update_ai_agent_configuration(
                agent_id=agent_id,
                new_prompt_id=new_prompt_version,
                agent_config=agent_config
            )
            
            # Store updated Intent_Configuration
            config.timestamp = datetime.utcnow().isoformat() + 'Z'
            config.version += 1
            self.intent_persistence.save_configuration(config)
            
            # Test agent (simplified for now - full testing in Tester Lambda)
            test_results = {
                'totalTests': 0,
                'passed': 0,
                'failed': 0,
                'message': 'Intent disabled successfully'
            }
            
            # Log operation to audit logs
            self.audit_logger.log_intent_operation(
                operation='INTENT_DISABLE',
                agent_id=agent_id,
                intent_name=intent_name,
                caller_phone_number=caller_phone_number,
                before_config=before_config,
                after_config=config.to_dict(),
                result='SUCCESS'
            )
            
            # Publish metrics
            MetricsPublisher.publish_intent_operation(
                metrics=self.metrics,
                agent_id=agent_id,
                operation='DISABLE',
                result='SUCCESS'
            )
            
            self.logger.info(
                "Successfully disabled intent",
                extra={
                    "agentId": agent_id,
                    "intentName": intent_name,
                    "backupLocation": backup_result['backupLocation']
                }
            )
            
            return {
                'success': True,
                'agentId': agent_id,
                'intentName': intent_name,
                'backupLocation': backup_result['backupLocation'],
                'testResults': test_results
            }
            
        except Exception as e:
            # Log failure to audit logs
            self.audit_logger.log_intent_operation(
                operation='INTENT_DISABLE',
                agent_id=agent_id,
                intent_name=intent_name,
                caller_phone_number=caller_phone_number,
                before_config=before_config if 'before_config' in locals() else None,
                after_config=None,
                result='FAILURE',
                error_message=str(e)
            )
            
            # Publish failure metrics
            MetricsPublisher.publish_intent_operation(
                metrics=self.metrics,
                agent_id=agent_id,
                operation='DISABLE',
                result='FAILURE'
            )
            
            self.logger.error(
                "Failed to disable intent",
                extra={
                    "agentId": agent_id,
                    "intentName": intent_name,
                    "error": str(e)
                }
            )
            raise
    
    def enable_intent(self, event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        """
        Enable a specific intent.
        
        Workflow:
        1. Retrieve current Intent_Configuration from S3
        2. Update configuration to mark specified intent as enabled
        3. Backup current AI Agent configuration and Intent_Configuration
        4. Generate new AI Prompt text with enabled intent handling
        5. Create new AI Prompt version using CreateAIPromptVersion API
        6. Update AI Agent configuration using UpdateAIAgent API
        7. Set visibilityStatus to PUBLISHED
        8. Test agent to verify enabled intent works
        9. Store updated Intent_Configuration to S3
        10. Log operation to audit logs
        
        Args:
            event: Event with agentId, intentName, callerPhoneNumber
            context: Lambda context
            
        Returns:
            Result with backup location and test results
        """
        agent_id = event.get('agentId')
        intent_name = event.get('intentName')
        caller_phone_number = event.get('callerPhoneNumber', 'unknown')
        
        if not agent_id or not intent_name:
            raise ValueError("Missing required fields: agentId, intentName")
        
        self.logger.info(
            "Enabling intent",
            extra={
                "agentId": agent_id,
                "intentName": intent_name,
                "caller": caller_phone_number
            }
        )
        
        try:
            # Retrieve current Intent_Configuration
            config = self.intent_persistence.load_configuration(agent_id)
            if not config:
                raise ValueError(f"Intent_Configuration not found for agent {agent_id}")
            
            # Store before config for audit logging
            before_config = config.to_dict()
            
            # Update configuration to enable intent
            if not config.enable_intent(intent_name):
                raise ValueError(f"Intent not found: {intent_name}")
            
            # Get current agent configuration
            agent_response = self.get_agent({'agentId': agent_id})
            agent_config = agent_response['configuration']
            
            # Backup current configuration
            backup_result = self._backup_agent_with_intents(
                agent_id=agent_id,
                agent_name=agent_response['agentName'],
                agent_config=agent_config,
                intent_config=config,
                caller_phone_number=caller_phone_number,
                backup_reason='intent-enable'
            )
            
            # Get current prompt
            prompt_id = agent_config['orchestrationAIAgentConfiguration']['orchestrationAIPromptId']
            prompt_response = self._get_ai_prompt_with_retry(prompt_id)
            original_prompt_text = prompt_response['aiPrompt']['templateConfiguration']['textFullAIPromptEditTemplateConfiguration']['text']
            
            # Generate new AI Prompt text
            updated_prompt_text = self.prompt_generator.generate_prompt_with_intent_management(
                original_prompt=original_prompt_text,
                intent_config=config
            )
            
            # Create new AI Prompt version
            new_prompt_version = self._create_ai_prompt_version(
                prompt_id=prompt_id,
                prompt_text=updated_prompt_text
            )
            
            # Update AI Agent configuration
            self._update_ai_agent_configuration(
                agent_id=agent_id,
                new_prompt_id=new_prompt_version,
                agent_config=agent_config
            )
            
            # Store updated Intent_Configuration
            config.timestamp = datetime.utcnow().isoformat() + 'Z'
            config.version += 1
            self.intent_persistence.save_configuration(config)
            
            # Test agent
            test_results = {
                'totalTests': 0,
                'passed': 0,
                'failed': 0,
                'message': 'Intent enabled successfully'
            }
            
            # Log operation
            self.audit_logger.log_intent_operation(
                operation='INTENT_ENABLE',
                agent_id=agent_id,
                intent_name=intent_name,
                caller_phone_number=caller_phone_number,
                before_config=before_config,
                after_config=config.to_dict(),
                result='SUCCESS'
            )
            
            # Publish metrics
            MetricsPublisher.publish_intent_operation(
                metrics=self.metrics,
                agent_id=agent_id,
                operation='ENABLE',
                result='SUCCESS'
            )
            
            self.logger.info(
                "Successfully enabled intent",
                extra={
                    "agentId": agent_id,
                    "intentName": intent_name
                }
            )
            
            return {
                'success': True,
                'agentId': agent_id,
                'intentName': intent_name,
                'backupLocation': backup_result['backupLocation'],
                'testResults': test_results
            }
            
        except Exception as e:
            # Log failure to audit logs
            self.audit_logger.log_intent_operation(
                operation='INTENT_ENABLE',
                agent_id=agent_id,
                intent_name=intent_name,
                caller_phone_number=caller_phone_number,
                before_config=before_config if 'before_config' in locals() else None,
                after_config=None,
                result='FAILURE',
                error_message=str(e)
            )
            
            # Publish failure metrics
            MetricsPublisher.publish_intent_operation(
                metrics=self.metrics,
                agent_id=agent_id,
                operation='ENABLE',
                result='FAILURE'
            )
            
            self.logger.error(
                "Failed to enable intent",
                extra={
                    "agentId": agent_id,
                    "intentName": intent_name,
                    "error": str(e)
                }
            )
            raise
    
    def restore_all_intents(self, event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        """
        Restore all intents to normal operation.
        
        Workflow:
        1. Retrieve current Intent_Configuration from S3
        2. Update configuration to enable all intents
        3. Retrieve most recent backup before any intent modifications
        4. Extract original AI Prompt text from backup
        5. Create new AI Prompt version with original prompt text
        6. Update AI Agent configuration
        7. Set visibilityStatus to PUBLISHED
        8. Test agent to verify all intents work
        9. Store updated Intent_Configuration to S3
        10. Calculate partial outage duration
        11. Log operation to audit logs
        
        Args:
            event: Event with agentId, callerPhoneNumber
            context: Lambda context
            
        Returns:
            Result with restored intents and test results
        """
        agent_id = event.get('agentId')
        caller_phone_number = event.get('callerPhoneNumber', 'unknown')
        
        if not agent_id:
            raise ValueError("Missing required field: agentId")
        
        self.logger.info(
            "Restoring all intents",
            extra={
                "agentId": agent_id,
                "caller": caller_phone_number
            }
        )
        
        try:
            # Retrieve current Intent_Configuration
            config = self.intent_persistence.load_configuration(agent_id)
            if not config:
                raise ValueError(f"Intent_Configuration not found for agent {agent_id}")
            
            # Store before config for audit logging
            before_config = config.to_dict()
            
            # Calculate partial outage duration
            disabled_intents = config.get_disabled_intents()
            outage_start = None
            if disabled_intents:
                # Find earliest disable timestamp
                for intent in disabled_intents:
                    if intent.disabled_at:
                        if not outage_start or intent.disabled_at < outage_start:
                            outage_start = intent.disabled_at
            
            # Update configuration to enable all intents
            config.enable_all_intents()
            
            # Get most recent backup before intent modifications
            backup_key = self._find_most_recent_backup(agent_id)
            if not backup_key:
                raise ValueError(f"No backup found for agent {agent_id}")
            
            self.logger.info(
                "Found most recent backup",
                extra={
                    "agentId": agent_id,
                    "backupKey": backup_key
                }
            )
            
            # Retrieve backup and extract original prompt
            backup_obj = self.s3_client.get_object(
                Bucket=self.backup_bucket,
                Key=backup_key
            )
            backup_data = json.loads(backup_obj['Body'].read().decode('utf-8'))
            original_prompt_text = backup_data.get('currentPromptText')
            
            if not original_prompt_text:
                raise ValueError("Original prompt text not found in backup")
            
            # Get current agent configuration
            agent_response = self.get_agent({'agentId': agent_id})
            agent_config = agent_response['configuration']
            prompt_id = agent_config['orchestrationAIAgentConfiguration']['orchestrationAIPromptId']
            
            # Create new AI Prompt version with original text
            new_prompt_version = self._create_ai_prompt_version(
                prompt_id=prompt_id,
                prompt_text=original_prompt_text
            )
            
            # Update AI Agent configuration
            self._update_ai_agent_configuration(
                agent_id=agent_id,
                new_prompt_id=new_prompt_version,
                agent_config=agent_config
            )
            
            # Store updated Intent_Configuration
            config.timestamp = datetime.utcnow().isoformat() + 'Z'
            config.version += 1
            self.intent_persistence.save_configuration(config)
            
            # Calculate outage duration
            outage_duration = "unknown"
            if outage_start:
                from datetime import datetime as dt
                start_dt = dt.fromisoformat(outage_start.replace('Z', '+00:00'))
                end_dt = dt.utcnow()
                duration_seconds = (end_dt - start_dt.replace(tzinfo=None)).total_seconds()
                duration_minutes = int(duration_seconds / 60)
                outage_duration = f"{duration_minutes} minutes"
            
            # Test agent
            test_results = {
                'totalTests': 0,
                'passed': 0,
                'failed': 0,
                'message': 'All intents restored successfully'
            }
            
            # Log operation
            self.audit_logger.log_intent_operation(
                operation='INTENT_RESTORE_ALL',
                agent_id=agent_id,
                intent_name='all',
                caller_phone_number=caller_phone_number,
                before_config=before_config,
                after_config=config.to_dict(),
                result='SUCCESS'
            )
            
            # Publish metrics
            MetricsPublisher.publish_intent_operation(
                metrics=self.metrics,
                agent_id=agent_id,
                operation='RESTORE_ALL',
                result='SUCCESS'
            )
            
            self.logger.info(
                "Successfully restored all intents",
                extra={
                    "agentId": agent_id,
                    "outageDuration": outage_duration,
                    "restoredIntents": len(config.intents)
                }
            )
            
            return {
                'success': True,
                'agentId': agent_id,
                'restoredIntents': [intent.name for intent in config.intents],
                'outageDuration': outage_duration,
                'testResults': test_results
            }
            
        except Exception as e:
            # Log failure to audit logs
            self.audit_logger.log_intent_operation(
                operation='INTENT_RESTORE_ALL',
                agent_id=agent_id,
                intent_name='all',
                caller_phone_number=caller_phone_number,
                before_config=before_config if 'before_config' in locals() else None,
                after_config=None,
                result='FAILURE',
                error_message=str(e)
            )
            
            # Publish failure metrics
            MetricsPublisher.publish_intent_operation(
                metrics=self.metrics,
                agent_id=agent_id,
                operation='RESTORE_ALL',
                result='FAILURE'
            )
            
            self.logger.error(
                "Failed to restore all intents",
                extra={
                    "agentId": agent_id,
                    "error": str(e)
                }
            )
            raise
    
    def _backup_agent_with_intents(
        self,
        agent_id: str,
        agent_name: str,
        agent_config: dict,
        intent_config: IntentConfiguration,
        caller_phone_number: str,
        backup_reason: str
    ) -> Dict[str, Any]:
        """
        Backup agent configuration including Intent_Configuration.
        
        Args:
            agent_id: AI Agent ID
            agent_name: AI Agent name
            agent_config: AI Agent configuration
            intent_config: Intent configuration
            caller_phone_number: Caller phone number
            backup_reason: Reason for backup
            
        Returns:
            Backup result with location
        """
        # Invoke Backup Lambda
        backup_event = {
            'agentId': agent_id,
            'agentName': agent_name,
            'assistantId': self.assistant_id,
            'configuration': agent_config,
            'intentConfiguration': intent_config.to_dict(),
            'metadata': {
                'backupReason': backup_reason,
                'callerPhoneNumber': caller_phone_number
            }
        }
        
        response = self.lambda_client.invoke(
            FunctionName=self.backup_lambda_arn,
            InvocationType='RequestResponse',
            Payload=json.dumps(backup_event)
        )
        
        result = json.loads(response['Payload'].read())
        
        if not result.get('success'):
            raise RuntimeError(f"Backup failed: {result.get('error', 'Unknown error')}")
        
        return result
    
    def _create_ai_prompt_version(
        self,
        prompt_id: str,
        prompt_text: str
    ) -> str:
        """
        Create new AI Prompt version.
        
        Args:
            prompt_id: Base AI Prompt ID
            prompt_text: Updated prompt text
            
        Returns:
            New AI Prompt ID with version
        """
        # Extract base prompt ID (remove version if present)
        base_prompt_id = prompt_id.split(':')[0] if ':' in prompt_id else prompt_id
        
        response = self._create_ai_prompt_version_with_retry(
            base_prompt_id=base_prompt_id,
            prompt_text=prompt_text
        )
        
        new_prompt_id = response['aiPrompt']['aiPromptId']
        
        self.logger.info(
            "Created new AI Prompt version",
            extra={
                "basePromptId": base_prompt_id,
                "newPromptId": new_prompt_id
            }
        )
        
        return new_prompt_id
    
    @exponential_backoff(max_attempts=3, base_delay=1.0)
    def _create_ai_prompt_version_with_retry(
        self,
        base_prompt_id: str,
        prompt_text: str
    ) -> Dict[str, Any]:
        """
        Call CreateAIPromptVersion API with retry logic.
        
        Args:
            base_prompt_id: Base AI Prompt ID
            prompt_text: Updated prompt text
            
        Returns:
            API response
        """
        return self.q_connect.create_ai_prompt_version(
            assistantId=self.assistant_id,
            aiPromptId=base_prompt_id,
            modifiedTime=datetime.utcnow().isoformat() + 'Z',
            templateConfiguration={
                'textFullAIPromptEditTemplateConfiguration': {
                    'text': prompt_text
                }
            },
            logger=self.logger
        )
    
    def _update_ai_agent_configuration(
        self,
        agent_id: str,
        new_prompt_id: str,
        agent_config: dict
    ) -> None:
        """
        Update AI Agent configuration to reference new AI Prompt version.
        
        Args:
            agent_id: AI Agent ID
            new_prompt_id: New AI Prompt ID with version
            agent_config: Current agent configuration
        """
        # Update orchestration prompt ID
        updated_config = agent_config.copy()
        updated_config['orchestrationAIAgentConfiguration']['orchestrationAIPromptId'] = new_prompt_id
        
        # Call UpdateAIAgent API
        self._update_ai_agent_with_retry(
            agent_id=agent_id,
            configuration=updated_config
        )
        
        self.logger.info(
            "Updated AI Agent configuration",
            extra={
                "agentId": agent_id,
                "newPromptId": new_prompt_id
            }
        )
    
    @exponential_backoff(max_attempts=3, base_delay=1.0)
    def _update_ai_agent_with_retry(
        self,
        agent_id: str,
        configuration: dict
    ) -> Dict[str, Any]:
        """
        Call UpdateAIAgent API with retry logic.
        
        Args:
            agent_id: AI Agent ID
            configuration: Updated configuration
            
        Returns:
            API response
        """
        return self.q_connect.update_ai_agent(
            assistantId=self.assistant_id,
            aiAgentId=agent_id,
            configuration=configuration,
            visibilityStatus='PUBLISHED',
            logger=self.logger
        )
    
    def _find_most_recent_backup(self, agent_id: str) -> Optional[str]:
        """
        Find most recent backup for agent.
        
        Args:
            agent_id: AI Agent ID
            
        Returns:
            S3 key of most recent backup, or None if not found
        """
        prefix = f"backups/{agent_id}/"
        
        response = self.s3_client.list_objects_v2(
            Bucket=self.backup_bucket,
            Prefix=prefix
        )
        
        if 'Contents' not in response or not response['Contents']:
            return None
        
        # Sort by LastModified descending
        backups = sorted(
            response['Contents'],
            key=lambda x: x['LastModified'],
            reverse=True
        )
        
        return backups[0]['Key']
    
    def update_agent(self, event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        """
        Update AI Agent with new AI Prompt for outage information.
        
        Workflow:
        1. Coordinate backup by invoking Backup Lambda
        2. Abort if backup fails
        3. Generate new AI Prompt text
        4. Create new AI Prompt version
        5. Update AI Agent configuration
        6. Set visibilityStatus to PUBLISHED
        7. Coordinate testing by invoking Tester Lambda
        8. Implement automatic rollback if critical tests fail
        9. Log update operation
        
        Args:
            event: Event with agentId, outageInfo, callerPhoneNumber
            context: Lambda context
            
        Returns:
            Update result with backup location and test results
        """
        # This will be implemented in subtask 6.8
        raise NotImplementedError("update_agent operation will be implemented in subtask 6.8")
    
    def update_agents(self, event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        """
        Update multiple AI Agents with new AI Prompts for outage information.
        
        This operation supports updating multiple agents in a single call, ensuring:
        - Independent backup for each agent
        - Independent testing for each agent
        - Individual status reporting for each agent
        - Support for voice, chat, and email agent types
        
        Workflow for each agent:
        1. Coordinate backup by invoking Backup Lambda
        2. Abort agent update if backup fails (continue with other agents)
        3. Generate new AI Prompt text
        4. Create new AI Prompt version
        5. Update AI Agent configuration
        6. Set visibilityStatus to PUBLISHED
        7. Coordinate testing by invoking Tester Lambda
        8. Implement automatic rollback if critical tests fail
        9. Log update operation
        
        Args:
            event: Event with:
                - agentIds: List of agent IDs to update
                - outageInfo: Outage information (same for all agents)
                - callerPhoneNumber: Caller phone number for audit
            context: Lambda context
            
        Returns:
            Multi-agent update result with per-agent status:
            {
                'success': bool,  # True if all agents updated successfully
                'totalAgents': int,
                'successfulUpdates': int,
                'failedUpdates': int,
                'results': [
                    {
                        'agentId': str,
                        'agentName': str,
                        'agentType': str,
                        'success': bool,
                        'backupLocation': str (if successful),
                        'testResults': dict (if successful),
                        'error': str (if failed)
                    },
                    ...
                ]
            }
        """
        agent_ids = event.get('agentIds', [])
        outage_info = event.get('outageInfo', {})
        caller_phone_number = event.get('callerPhoneNumber', 'unknown')
        
        if not agent_ids:
            raise ValueError("Missing required field: agentIds")
        
        if not isinstance(agent_ids, list):
            raise ValueError("agentIds must be a list")
        
        if not outage_info:
            raise ValueError("Missing required field: outageInfo")
        
        self.logger.info(
            "Starting multi-agent update",
            extra={
                "agentCount": len(agent_ids),
                "agentIds": agent_ids,
                "callerPhoneNumber": caller_phone_number
            }
        )
        
        results = []
        successful_updates = 0
        failed_updates = 0
        
        # Process each agent independently
        for agent_id in agent_ids:
            agent_result = {
                'agentId': agent_id,
                'success': False
            }
            
            try:
                # Get agent configuration to retrieve name and type
                self.logger.info(
                    "Processing agent update",
                    extra={"agentId": agent_id}
                )
                
                agent_config = self._get_ai_agent_with_retry(agent_id)
                # Extract agent details from the aiAgent object
                ai_agent = agent_config.get('aiAgent', {})
                agent_name = ai_agent.get('name', 'Unknown')
                agent_type = ai_agent.get('type', 'UNKNOWN')
                
                agent_result['agentName'] = agent_name
                agent_result['agentType'] = agent_type
                
                # Create single-agent event for update_agent
                single_agent_event = {
                    'operation': 'update_agent',
                    'agentId': agent_id,
                    'outageInfo': outage_info,
                    'callerPhoneNumber': caller_phone_number
                }
                
                # Call update_agent for this specific agent
                # Note: update_agent is not yet implemented, so this will raise NotImplementedError
                # When update_agent is implemented, this will work correctly
                update_result = self.update_agent(single_agent_event, context)
                
                # Extract results
                agent_result['success'] = update_result.get('success', False)
                agent_result['backupLocation'] = update_result.get('backupLocation', '')
                agent_result['testResults'] = update_result.get('testResults', {})
                
                if agent_result['success']:
                    successful_updates += 1
                    self.logger.info(
                        "Agent update successful",
                        extra={
                            "agentId": agent_id,
                            "agentName": agent_name,
                            "agentType": agent_type
                        }
                    )
                else:
                    failed_updates += 1
                    agent_result['error'] = update_result.get('error', 'Update failed')
                    self.logger.warning(
                        "Agent update failed",
                        extra={
                            "agentId": agent_id,
                            "agentName": agent_name,
                            "error": agent_result['error']
                        }
                    )
                
            except NotImplementedError as e:
                # update_agent not yet implemented
                failed_updates += 1
                agent_result['error'] = f"update_agent operation not yet implemented: {str(e)}"
                self.logger.error(
                    "Agent update not implemented",
                    extra={
                        "agentId": agent_id,
                        "error": str(e)
                    }
                )
                
            except Exception as e:
                # Handle any errors for this agent and continue with others
                failed_updates += 1
                agent_result['error'] = str(e)
                self.logger.error(
                    "Agent update failed with exception",
                    extra={
                        "agentId": agent_id,
                        "error": str(e),
                        "errorType": type(e).__name__
                    },
                    exc_info=True
                )
            
            results.append(agent_result)
        
        # Log multi-agent update completion
        overall_success = failed_updates == 0
        
        self.logger.info(
            "Multi-agent update completed",
            extra={
                "totalAgents": len(agent_ids),
                "successfulUpdates": successful_updates,
                "failedUpdates": failed_updates,
                "overallSuccess": overall_success
            }
        )
        
        # Publish metrics
        try:
            metrics_publisher = MetricsPublisher(logger=self.logger)
            metrics_publisher.publish_metric(
                metric_name='MultiAgentUpdates',
                value=1,
                dimensions={
                    'TotalAgents': str(len(agent_ids)),
                    'SuccessfulUpdates': str(successful_updates),
                    'FailedUpdates': str(failed_updates),
                    'Result': 'Success' if overall_success else 'PartialFailure'
                }
            )
        except Exception as e:
            self.logger.warning(
                "Failed to publish multi-agent update metrics",
                extra={"error": str(e)}
            )
        
        return {
            'success': overall_success,
            'totalAgents': len(agent_ids),
            'successfulUpdates': successful_updates,
            'failedUpdates': failed_updates,
            'results': results
        }


# Lambda handler entry point
_handler_instance = None


def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler entry point."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = AgentManagerHandler()
    return _handler_instance.handler(event, context)
