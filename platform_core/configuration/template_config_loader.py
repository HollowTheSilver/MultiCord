"""
Template Configuration System
============================

System for loading, managing, and persisting template configurations.
Provides customization capabilities for template-based bots with PostgreSQL persistence.
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path
from uuid import UUID
import logging

from ..infrastructure.postgresql_pool import PostgreSQLConnectionPool
from ..services.template_discovery_service import TemplateMetadata


@dataclass
class TemplateConfiguration:
    """Complete template configuration with customizations."""
    
    instance_id: UUID
    template_name: str
    base_config: Dict[str, Any]
    user_overrides: Dict[str, Any]
    computed_config: Dict[str, Any]
    enabled_features: List[str]
    disabled_features: List[str]
    environment_overrides: Dict[str, str]
    
    @classmethod
    def from_template(cls, 
                     instance_id: UUID,
                     template_metadata: TemplateMetadata,
                     user_overrides: Dict[str, Any] = None,
                     environment_overrides: Dict[str, str] = None) -> 'TemplateConfiguration':
        """Create template configuration from metadata with user customizations."""
        
        user_overrides = user_overrides or {}
        environment_overrides = environment_overrides or {}
        
        # Base configuration from template
        base_config = {
            "display_name": template_metadata.display_name,
            "version": template_metadata.version,
            "main_file": template_metadata.main_file,
            "commands": template_metadata.commands,
            "technical_features": template_metadata.technical_features,
            "configuration_schema": template_metadata.configuration_schema
        }
        
        # Apply user overrides
        computed_config = cls._merge_configurations(base_config, user_overrides)
        
        # Determine enabled/disabled features
        all_features = set(template_metadata.features)
        feature_overrides = user_overrides.get("features", {})
        
        enabled_features = []
        disabled_features = []
        
        for feature in all_features:
            if feature_overrides.get(feature, True):
                enabled_features.append(feature)
            else:
                disabled_features.append(feature)
        
        return cls(
            instance_id=instance_id,
            template_name=template_metadata.name,
            base_config=base_config,
            user_overrides=user_overrides,
            computed_config=computed_config,
            enabled_features=enabled_features,
            disabled_features=disabled_features,
            environment_overrides=environment_overrides
        )
    
    @staticmethod
    def _merge_configurations(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge configuration dictionaries."""
        result = base.copy()
        
        for key, value in overrides.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = TemplateConfiguration._merge_configurations(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def get_effective_environment(self, base_environment: Dict[str, str] = None) -> Dict[str, str]:
        """Get the effective environment variables for this template configuration."""
        effective_env = base_environment.copy() if base_environment else {}
        
        # Add template environment
        template_env = self.computed_config.get("environment", {})
        effective_env.update(template_env)
        
        # Add user environment overrides
        effective_env.update(self.environment_overrides)
        
        return effective_env
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "instance_id": str(self.instance_id),
            "template_name": self.template_name,
            "base_config": self.base_config,
            "user_overrides": self.user_overrides,
            "computed_config": self.computed_config,
            "enabled_features": self.enabled_features,
            "disabled_features": self.disabled_features,
            "environment_overrides": self.environment_overrides
        }


class TemplateConfigurationLoader:
    """
    Service for loading and managing template configurations.
    
    Provides template customization with PostgreSQL persistence following
    MultiCord's clean architecture principles.
    """
    
    def __init__(self, 
                 db_pool: PostgreSQLConnectionPool = None,
                 logger: logging.Logger = None):
        """
        Initialize template configuration loader.
        
        Args:
            db_pool: PostgreSQL connection pool for persistence
            logger: Logger instance for service operations
        """
        self.db_pool = db_pool
        self.logger = logger or logging.getLogger(__name__)
        
        # Configuration cache
        self._config_cache: Dict[UUID, TemplateConfiguration] = {}
    
    async def load_template_configuration(self, 
                                        instance_id: UUID,
                                        template_metadata: TemplateMetadata,
                                        user_preferences: Dict[str, Any] = None) -> TemplateConfiguration:
        """
        Load complete template configuration for a bot instance.
        
        Args:
            instance_id: Bot instance ID
            template_metadata: Template metadata from discovery service
            user_preferences: User customization preferences
            
        Returns:
            Complete template configuration with all customizations applied
        """
        try:
            # Check cache first
            if instance_id in self._config_cache:
                cached_config = self._config_cache[instance_id]
                if cached_config.template_name == template_metadata.name:
                    return cached_config
            
            # Load user overrides from PostgreSQL
            user_overrides = await self._load_user_overrides(instance_id)
            
            # Merge with provided preferences
            if user_preferences:
                user_overrides = TemplateConfiguration._merge_configurations(
                    user_overrides, user_preferences
                )
            
            # Load environment overrides
            env_overrides = await self._load_environment_overrides(instance_id)
            
            # Create configuration
            config = TemplateConfiguration.from_template(
                instance_id=instance_id,
                template_metadata=template_metadata,
                user_overrides=user_overrides,
                environment_overrides=env_overrides
            )
            
            # Cache configuration
            self._config_cache[instance_id] = config
            
            self.logger.debug(f"Loaded template configuration for instance {instance_id}")
            return config
            
        except Exception as e:
            self.logger.error(f"Failed to load template configuration for {instance_id}: {e}")
            
            # Return minimal configuration as fallback
            return TemplateConfiguration.from_template(instance_id, template_metadata)
    
    async def save_template_configuration(self, config: TemplateConfiguration) -> bool:
        """
        Save template configuration to PostgreSQL.
        
        Args:
            config: Template configuration to save
            
        Returns:
            True if saved successfully
        """
        try:
            if not self.db_pool:
                self.logger.warning("No database pool configured, cannot save template configuration")
                return False
            
            # Save user overrides
            await self._save_user_overrides(config.instance_id, config.user_overrides)
            
            # Save environment overrides
            await self._save_environment_overrides(config.instance_id, config.environment_overrides)
            
            # Update cache
            self._config_cache[config.instance_id] = config
            
            self.logger.debug(f"Saved template configuration for instance {config.instance_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save template configuration: {e}")
            return False
    
    async def update_template_preferences(self, 
                                        instance_id: UUID,
                                        preferences: Dict[str, Any]) -> bool:
        """
        Update user preferences for a template configuration.
        
        Args:
            instance_id: Bot instance ID
            preferences: New preferences to apply
            
        Returns:
            True if updated successfully
        """
        try:
            # Load existing configuration
            if instance_id not in self._config_cache:
                self.logger.warning(f"No cached configuration found for instance {instance_id}")
                return False
            
            config = self._config_cache[instance_id]
            
            # Merge new preferences
            updated_overrides = TemplateConfiguration._merge_configurations(
                config.user_overrides, preferences
            )
            
            # Recompute configuration
            config.user_overrides = updated_overrides
            config.computed_config = TemplateConfiguration._merge_configurations(
                config.base_config, updated_overrides
            )
            
            # Save to database
            return await self.save_template_configuration(config)
            
        except Exception as e:
            self.logger.error(f"Failed to update template preferences: {e}")
            return False
    
    async def get_template_defaults(self, template_name: str) -> Dict[str, Any]:
        """
        Get default configuration values for a template.
        
        Args:
            template_name: Name of template
            
        Returns:
            Default configuration dictionary
        """
        try:
            # This would typically load from template metadata
            # For now, return empty dict as placeholder
            return {}
            
        except Exception as e:
            self.logger.error(f"Failed to get template defaults for {template_name}: {e}")
            return {}
    
    async def validate_template_configuration(self, config: TemplateConfiguration) -> bool:
        """
        Validate that a template configuration is valid and complete.
        
        Args:
            config: Template configuration to validate
            
        Returns:
            True if configuration is valid
        """
        try:
            # Check required fields
            required_fields = ["template_name", "computed_config"]
            for field in required_fields:
                if not hasattr(config, field) or getattr(config, field) is None:
                    self.logger.error(f"Template configuration missing required field: {field}")
                    return False
            
            # Validate computed configuration structure
            computed = config.computed_config
            if not isinstance(computed, dict):
                self.logger.error("Computed configuration must be a dictionary")
                return False
            
            # Check for required configuration keys
            required_keys = ["main_file"]
            for key in required_keys:
                if key not in computed:
                    self.logger.error(f"Template configuration missing required key: {key}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Template configuration validation failed: {e}")
            return False
    
    async def _load_user_overrides(self, instance_id: UUID) -> Dict[str, Any]:
        """Load user configuration overrides from PostgreSQL."""
        if not self.db_pool:
            return {}
        
        try:
            # Placeholder for PostgreSQL query
            # Would load from instance_feature_assignments or similar table
            self.logger.debug(f"Would load user overrides for instance {instance_id}")
            return {}
            
        except Exception as e:
            self.logger.error(f"Failed to load user overrides: {e}")
            return {}
    
    async def _save_user_overrides(self, instance_id: UUID, overrides: Dict[str, Any]) -> None:
        """Save user configuration overrides to PostgreSQL."""
        if not self.db_pool:
            return
        
        try:
            # Placeholder for PostgreSQL update
            # Would save to instance_feature_assignments or similar table
            self.logger.debug(f"Would save user overrides for instance {instance_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to save user overrides: {e}")
    
    async def _load_environment_overrides(self, instance_id: UUID) -> Dict[str, str]:
        """Load environment variable overrides from PostgreSQL."""
        if not self.db_pool:
            return {}
        
        try:
            # Placeholder for PostgreSQL query
            # Would load from bot_instances configuration_data JSONB field
            self.logger.debug(f"Would load environment overrides for instance {instance_id}")
            return {}
            
        except Exception as e:
            self.logger.error(f"Failed to load environment overrides: {e}")
            return {}
    
    async def _save_environment_overrides(self, instance_id: UUID, overrides: Dict[str, str]) -> None:
        """Save environment variable overrides to PostgreSQL."""
        if not self.db_pool:
            return
        
        try:
            # Placeholder for PostgreSQL update
            # Would update bot_instances configuration_data JSONB field
            self.logger.debug(f"Would save environment overrides for instance {instance_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to save environment overrides: {e}")