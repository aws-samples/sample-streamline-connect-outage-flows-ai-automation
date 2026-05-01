"""
Intent Configuration data model for managing agent intents.

This module provides data structures and methods for tracking which intents
are enabled or disabled for each AI agent.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime
import json


@dataclass
class Intent:
    """Represents a single intent with its status."""
    
    name: str
    description: str
    enabled: bool = True
    disabled_at: Optional[str] = None  # ISO 8601 timestamp
    disabled_by: Optional[str] = None  # Caller phone number
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Intent':
        """Create Intent from dictionary."""
        return cls(**data)


@dataclass
class IntentConfiguration:
    """Configuration tracking enabled/disabled intents for an AI agent."""
    
    agent_id: str
    timestamp: str  # ISO 8601 timestamp
    intents: List[Intent] = field(default_factory=list)
    version: int = 1
    
    def get_enabled_intents(self) -> List[Intent]:
        """
        Get list of enabled intents.
        
        Returns:
            List of Intent objects where enabled=True
        """
        return [intent for intent in self.intents if intent.enabled]
    
    def get_disabled_intents(self) -> List[Intent]:
        """
        Get list of disabled intents.
        
        Returns:
            List of Intent objects where enabled=False
        """
        return [intent for intent in self.intents if not intent.enabled]
    
    def disable_intent(self, intent_name: str, caller: str) -> bool:
        """
        Disable a specific intent.
        
        Args:
            intent_name: Name of the intent to disable
            caller: Phone number of the caller making the change
            
        Returns:
            True if intent was found and disabled, False otherwise
        """
        for intent in self.intents:
            if intent.name == intent_name:
                intent.enabled = False
                intent.disabled_at = datetime.utcnow().isoformat() + 'Z'
                intent.disabled_by = caller
                return True
        return False
    
    def enable_intent(self, intent_name: str) -> bool:
        """
        Enable a specific intent.
        
        Args:
            intent_name: Name of the intent to enable
            
        Returns:
            True if intent was found and enabled, False otherwise
        """
        for intent in self.intents:
            if intent.name == intent_name:
                intent.enabled = True
                intent.disabled_at = None
                intent.disabled_by = None
                return True
        return False
    
    def enable_all_intents(self) -> None:
        """Enable all intents."""
        for intent in self.intents:
            intent.enabled = True
            intent.disabled_at = None
            intent.disabled_by = None
    
    def to_dict(self) -> dict:
        """
        Convert to dictionary for serialization.
        
        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            'agent_id': self.agent_id,
            'timestamp': self.timestamp,
            'intents': [intent.to_dict() for intent in self.intents],
            'version': self.version
        }
    
    def to_json(self) -> str:
        """
        Serialize to JSON string.
        
        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'IntentConfiguration':
        """
        Create IntentConfiguration from dictionary.
        
        Args:
            data: Dictionary with configuration data
            
        Returns:
            IntentConfiguration instance
        """
        intents = [Intent.from_dict(intent_data) for intent_data in data.get('intents', [])]
        return cls(
            agent_id=data['agent_id'],
            timestamp=data['timestamp'],
            intents=intents,
            version=data.get('version', 1)
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'IntentConfiguration':
        """
        Deserialize from JSON string.
        
        Args:
            json_str: JSON string representation
            
        Returns:
            IntentConfiguration instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)
