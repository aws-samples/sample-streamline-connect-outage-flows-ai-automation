"""
Intent discovery module for extracting intents from AI Agent prompts.

Analyzes AI Prompt text to identify capabilities/intents using pattern matching.
"""

import re
from typing import List, Dict
from aws_lambda_powertools import Logger

from agent_manager.intent_configuration import Intent


class IntentDiscovery:
    """Discovers intents from AI Agent tool configurations or prompt text."""
    
    def __init__(self, logger: Logger):
        """
        Initialize intent discovery.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger
    
    def extract_intents_from_agent(self, agent_config: Dict, prompt_text: str = '') -> List[Intent]:
        """
        Extract intents from agent configuration, preferring toolConfigurations.
        
        Falls back to prompt text scraping only if toolConfigurations is empty.
        
        Args:
            agent_config: Agent configuration dict from GetAIAgent API
            prompt_text: AI Prompt text (fallback only)
            
        Returns:
            List of Intent objects (all enabled by default)
        """
        # Primary: extract from toolConfigurations (structural, accurate)
        intents = self._extract_from_tool_configurations(agent_config)
        if intents:
            self.logger.info(
                "Discovered intents from toolConfigurations",
                extra={"intentCount": len(intents)}
            )
            return intents
        
        # Fallback: regex scraping (less reliable)
        if prompt_text:
            self.logger.info("No toolConfigurations found, falling back to prompt text scraping")
            return self.extract_intents_from_prompt(prompt_text)
        
        return [Intent(name="general_assistance", description="General customer assistance", enabled=True)]
    
    def _extract_from_tool_configurations(self, agent_config: Dict) -> List[Intent]:
        """
        Extract intents from agent's toolConfigurations (ORCHESTRATION agents).
        
        Args:
            agent_config: Agent configuration from GetAIAgent API
            
        Returns:
            List of Intent objects
        """
        intents = []
        
        # Navigate to tool configurations
        orch_config = agent_config.get('orchestrationAIAgentConfiguration', {})
        tool_configs = orch_config.get('toolConfigurations', [])
        
        for tool in tool_configs:
            tool_name = tool.get('name', '')
            tool_description = tool.get('description', tool_name)
            
            if tool_name:
                intent_name = self._normalize_intent_name(tool_name)
                if intent_name:
                    intents.append(Intent(
                        name=intent_name,
                        description=tool_description,
                        enabled=True
                    ))
        
        return intents
    
    def extract_intents_from_prompt(self, prompt_text: str) -> List[Intent]:
        """
        Extract intents from AI Prompt text using pattern matching.
        
        This method looks for common patterns that indicate agent capabilities:
        - "can help with X"
        - "able to X"
        - "assist with X"
        - Bullet lists of capabilities
        - Numbered lists of services
        
        Args:
            prompt_text: AI Prompt text to analyze
            
        Returns:
            List of Intent objects (all enabled by default)
        """
        self.logger.info("Extracting intents from prompt text")
        
        intents = []
        
        # Pattern 1: "can help with X" or "can assist with X"
        can_help_pattern = r"can (?:help|assist) (?:with|you with) ([^.,;:\n]+)"
        matches = re.finditer(can_help_pattern, prompt_text, re.IGNORECASE)
        for match in matches:
            capability = match.group(1).strip()
            intent_name = self._normalize_intent_name(capability)
            if intent_name and not self._intent_exists(intents, intent_name):
                intents.append(Intent(
                    name=intent_name,
                    description=capability,
                    enabled=True
                ))
        
        # Pattern 2: "able to X"
        able_to_pattern = r"able to ([^.,;:\n]+)"
        matches = re.finditer(able_to_pattern, prompt_text, re.IGNORECASE)
        for match in matches:
            capability = match.group(1).strip()
            intent_name = self._normalize_intent_name(capability)
            if intent_name and not self._intent_exists(intents, intent_name):
                intents.append(Intent(
                    name=intent_name,
                    description=capability,
                    enabled=True
                ))
        
        # Pattern 3: Bullet lists (- X, * X, • X)
        bullet_pattern = r"^[\s]*[-*•]\s+([^:\n]+?)(?::|$)"
        matches = re.finditer(bullet_pattern, prompt_text, re.MULTILINE)
        for match in matches:
            capability = match.group(1).strip()
            intent_name = self._normalize_intent_name(capability)
            if intent_name and not self._intent_exists(intents, intent_name):
                intents.append(Intent(
                    name=intent_name,
                    description=capability,
                    enabled=True
                ))
        
        # Pattern 4: Numbered lists (1. X, 2. X)
        numbered_pattern = r"^\s*\d+\.\s+([^:\n]+?)(?::|$)"
        matches = re.finditer(numbered_pattern, prompt_text, re.MULTILINE)
        for match in matches:
            capability = match.group(1).strip()
            intent_name = self._normalize_intent_name(capability)
            if intent_name and not self._intent_exists(intents, intent_name):
                intents.append(Intent(
                    name=intent_name,
                    description=capability,
                    enabled=True
                ))
        
        # Pattern 5: "provide X" or "offer X"
        provide_pattern = r"(?:provide|offer) ([^.,;:\n]+)"
        matches = re.finditer(provide_pattern, prompt_text, re.IGNORECASE)
        for match in matches:
            capability = match.group(1).strip()
            intent_name = self._normalize_intent_name(capability)
            if intent_name and not self._intent_exists(intents, intent_name):
                intents.append(Intent(
                    name=intent_name,
                    description=capability,
                    enabled=True
                ))
        
        self.logger.info(
            "Extracted intents from prompt",
            extra={"intentCount": len(intents)}
        )
        
        # If no intents found, create a generic one
        if not intents:
            self.logger.warning("No intents extracted, creating generic intent")
            intents.append(Intent(
                name="general_assistance",
                description="General customer assistance",
                enabled=True
            ))
        
        return intents
    
    def _normalize_intent_name(self, capability: str) -> str:
        """
        Normalize capability text to intent name.
        
        Converts "Check account balance" to "check_account_balance"
        
        Args:
            capability: Capability description
            
        Returns:
            Normalized intent name (lowercase, underscores)
        """
        # Remove common prefixes
        capability = re.sub(r'^(?:help with|assist with|provide|offer)\s+', '', capability, flags=re.IGNORECASE)
        
        # Convert to lowercase and replace spaces/special chars with underscores
        intent_name = re.sub(r'[^\w\s]', '', capability.lower())
        intent_name = re.sub(r'\s+', '_', intent_name.strip())
        
        # Limit length
        if len(intent_name) > 50:
            intent_name = intent_name[:50]
        
        return intent_name
    
    def _intent_exists(self, intents: List[Intent], intent_name: str) -> bool:
        """
        Check if intent already exists in list.
        
        Args:
            intents: List of existing intents
            intent_name: Intent name to check
            
        Returns:
            True if intent exists
        """
        return any(intent.name == intent_name for intent in intents)
