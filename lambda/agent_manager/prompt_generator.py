"""
AI Prompt generation module for intent management.

Generates updated AI Prompt text that handles disabled intents gracefully
while maintaining normal behavior for enabled intents.
"""

from typing import List, Optional
from aws_lambda_powertools import Logger

from agent_manager.intent_configuration import IntentConfiguration, Intent


class PromptGenerator:
    """Generates AI Prompts with intent management instructions."""
    
    def __init__(self, logger: Logger):
        """
        Initialize prompt generator.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger
    
    def generate_prompt_with_intent_management(
        self,
        original_prompt: str,
        intent_config: IntentConfiguration
    ) -> str:
        """
        Generate updated AI Prompt text with intent management instructions.
        
        This method:
        1. Analyzes the original prompt to identify personality and tone
        2. Generates instructions for recognizing disabled intent requests
        3. Generates instructions for explaining unavailability
        4. Generates instructions for suggesting alternatives
        5. Ensures no technical details in customer-facing prompts
        6. Maintains agent personality and tone
        
        Args:
            original_prompt: Original AI Prompt text
            intent_config: Intent configuration with enabled/disabled intents
            
        Returns:
            Updated AI Prompt text with intent management instructions
        """
        disabled_intents = intent_config.get_disabled_intents()
        enabled_intents = intent_config.get_enabled_intents()
        
        self.logger.info(
            "Generating prompt with intent management",
            extra={
                "disabledCount": len(disabled_intents),
                "enabledCount": len(enabled_intents)
            }
        )
        
        # If no intents are disabled, return original prompt
        if not disabled_intents:
            self.logger.info("No disabled intents, returning original prompt")
            return original_prompt
        
        # Build intent management instructions
        intent_instructions = self._build_intent_instructions(
            disabled_intents,
            enabled_intents
        )
        
        # Insert instructions into prompt
        updated_prompt = self._insert_instructions(
            original_prompt,
            intent_instructions
        )
        
        return updated_prompt
    
    def _build_intent_instructions(
        self,
        disabled_intents: List[Intent],
        enabled_intents: List[Intent]
    ) -> str:
        """
        Build intent management instructions section.
        
        Args:
            disabled_intents: List of disabled intents
            enabled_intents: List of enabled intents
            
        Returns:
            Intent management instructions text
        """
        instructions = []
        
        instructions.append("\n## Temporary Service Adjustments\n")
        instructions.append(
            "Some capabilities are temporarily unavailable. "
            "Handle these requests with care and empathy.\n"
        )
        
        # List disabled capabilities
        if disabled_intents:
            instructions.append("\n### Currently Unavailable:\n")
            for intent in disabled_intents:
                instructions.append(f"- {intent.description}\n")
            
            instructions.append(
                "\nWhen customers request these services:\n"
                "1. Acknowledge their request warmly\n"
                "2. Explain that this specific capability is temporarily unavailable\n"
                "3. Apologize for the inconvenience\n"
                "4. Offer alternative ways to help if available\n"
                "5. Do NOT mention technical details like 'intent management' or 'system configuration'\n"
            )
        
        # Suggest alternatives if available
        if enabled_intents:
            instructions.append("\n### Available Alternatives:\n")
            instructions.append("You can still help customers with:\n")
            for intent in enabled_intents[:5]:  # Show top 5 alternatives
                instructions.append(f"- {intent.description}\n")
            
            if len(enabled_intents) > 5:
                instructions.append(f"- And {len(enabled_intents) - 5} other services\n")
        
        instructions.append(
            "\nMaintain your helpful and professional tone throughout. "
            "Focus on what you CAN do for the customer.\n"
        )
        
        return ''.join(instructions)
    
    def _insert_instructions(
        self,
        original_prompt: str,
        instructions: str
    ) -> str:
        """
        Insert intent management instructions into original prompt.
        
        Strategy:
        1. Look for a good insertion point (after introduction, before main instructions)
        2. If no clear point found, append to the end
        3. Preserve original formatting and structure
        
        Args:
            original_prompt: Original prompt text
            instructions: Intent management instructions to insert
            
        Returns:
            Updated prompt with instructions inserted
        """
        # Try to find insertion point after introduction
        insertion_markers = [
            "\n## ",  # Markdown section
            "\n# ",   # Markdown header
            "\n\n",   # Double newline (paragraph break)
        ]
        
        insertion_point = -1
        for marker in insertion_markers:
            pos = original_prompt.find(marker, 100)  # Skip first 100 chars
            if pos != -1:
                insertion_point = pos
                break
        
        if insertion_point != -1:
            # Insert at found position
            updated_prompt = (
                original_prompt[:insertion_point] +
                "\n" + instructions + "\n" +
                original_prompt[insertion_point:]
            )
        else:
            # Append to end
            updated_prompt = original_prompt + "\n\n" + instructions
        
        return updated_prompt
    
    def generate_example_response(
        self,
        intent: Intent,
        is_disabled: bool
    ) -> str:
        """
        Generate example response for testing purposes.
        
        Args:
            intent: Intent to generate response for
            is_disabled: Whether the intent is disabled
            
        Returns:
            Example response text
        """
        if is_disabled:
            return (
                f"I understand you'd like help with {intent.description}. "
                f"I apologize, but this service is temporarily unavailable. "
                f"I'm here to help with other requests. What else can I assist you with today?"
            )
        else:
            return (
                f"I'd be happy to help you with {intent.description}. "
                f"Let me assist you with that right away."
            )
