"""
BotInstance Entity - Core Domain Entity
======================================

Represents a bot instance configuration with PostgreSQL integration.
Manages bot metadata, execution strategy, and technical features.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
from enum import Enum


class BotStatus(Enum):
    """Bot instance status."""
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class BotInstance:
    """
    Core bot instance entity with PostgreSQL integration.
    
    Represents a configured bot instance that can be executed using
    different execution strategies (standard, template, enhanced).
    """
    # Core identifiers
    instance_id: UUID = field(default_factory=uuid4)
    node_id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    
    # Execution configuration
    execution_strategy: str = "standard"
    configuration_data: Dict[str, Any] = field(default_factory=dict)
    enabled_features: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Bot metadata
    discord_token_hash: Optional[str] = None  # For conflict detection only
    environment_config: Dict[str, Any] = field(default_factory=dict)
    status: BotStatus = BotStatus.CREATED
    
    def __post_init__(self):
        """Initialize computed fields."""
        if not self.client_id:
            raise ValueError("client_id is required")
        if self.execution_strategy not in ["standard", "template", "enhanced"]:
            raise ValueError(f"Invalid execution strategy: {self.execution_strategy}")
    
    def update_status(self, new_status: BotStatus) -> None:
        """Update bot status with timestamp."""
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)
    
    def add_feature(self, feature_name: str) -> None:
        """Add a technical feature to this bot instance."""
        if feature_name not in self.enabled_features:
            self.enabled_features.append(feature_name)
            self.updated_at = datetime.now(timezone.utc)
    
    def remove_feature(self, feature_name: str) -> None:
        """Remove a technical feature from this bot instance."""
        if feature_name in self.enabled_features:
            self.enabled_features.remove(feature_name)
            self.updated_at = datetime.now(timezone.utc)
    
    def has_feature(self, feature_name: str) -> bool:
        """Check if this bot instance has a specific feature enabled."""
        return feature_name in self.enabled_features
    
    def update_configuration(self, new_config: Dict[str, Any]) -> None:
        """Update configuration data."""
        self.configuration_data.update(new_config)
        self.updated_at = datetime.now(timezone.utc)
    
    def get_environment_variable(self, key: str, default: Any = None) -> Any:
        """Get an environment variable for this bot instance."""
        return self.environment_config.get(key, default)
    
    def set_environment_variable(self, key: str, value: Any) -> None:
        """Set an environment variable for this bot instance."""
        self.environment_config[key] = value
        self.updated_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "instance_id": str(self.instance_id),
            "node_id": str(self.node_id),
            "client_id": self.client_id,
            "execution_strategy": self.execution_strategy,
            "configuration_data": self.configuration_data,
            "enabled_features": self.enabled_features,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "discord_token_hash": self.discord_token_hash,
            "environment_config": self.environment_config,
            "status": self.status.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BotInstance':
        """Create BotInstance from dictionary."""
        return cls(
            instance_id=UUID(data["instance_id"]),
            node_id=UUID(data["node_id"]),
            client_id=data["client_id"],
            execution_strategy=data["execution_strategy"],
            configuration_data=data["configuration_data"],
            enabled_features=data["enabled_features"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            discord_token_hash=data.get("discord_token_hash"),
            environment_config=data.get("environment_config", {}),
            status=BotStatus(data.get("status", "created"))
        )
    
    def for_postgresql(self) -> Dict[str, Any]:
        """Convert to format suitable for PostgreSQL insertion."""
        import json
        return {
            "instance_id": self.instance_id,
            "node_id": self.node_id,
            "client_id": self.client_id,
            "execution_strategy": self.execution_strategy,
            "configuration_data": json.dumps(self.configuration_data),
            "enabled_features": json.dumps(self.enabled_features),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "discord_token_hash": self.discord_token_hash,
            "environment_config": json.dumps(self.environment_config)
        }
    
    @classmethod
    def from_postgresql(cls, row: Dict[str, Any]) -> 'BotInstance':
        """Create BotInstance from PostgreSQL row."""
        # PostgreSQL JSONB columns are already deserialized to Python objects
        # No need to json.loads() them
        return cls(
            instance_id=row["instance_id"],
            node_id=row["node_id"],
            client_id=row["client_id"],
            execution_strategy=row["execution_strategy"],
            configuration_data=row.get("configuration_data", {}) if isinstance(row.get("configuration_data"), dict) else {},
            enabled_features=row.get("enabled_features", []) if isinstance(row.get("enabled_features"), list) else [],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            discord_token_hash=row.get("discord_token_hash"),
            environment_config=row.get("environment_config", {}) if isinstance(row.get("environment_config"), dict) else {},
            status=BotStatus.CREATED  # Status managed separately
        )