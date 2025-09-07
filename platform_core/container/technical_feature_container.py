"""
Technical Feature Container
==========================

Dependency injection container for optional technical features.
Provides clean registration and resolution of technical enhancements
with PostgreSQL configuration persistence.

NO BUSINESS LOGIC - Technical infrastructure only.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Type, TypeVar, Generic, Callable
from dataclasses import dataclass, asdict
from uuid import UUID
import json
from pathlib import Path

from ..entities.bot_instance import BotInstance
from ..infrastructure.postgresql_pool import PostgreSQLConnectionPool

T = TypeVar('T', bound='TechnicalFeature')


@dataclass
class FeatureConfiguration:
    """Configuration for a technical feature."""
    feature_name: str
    feature_type: str
    enabled: bool = True
    configuration: Dict[str, Any] = None
    dependencies: List[str] = None
    description: str = ""
    version: str = "1.0.0"
    
    def __post_init__(self):
        if self.configuration is None:
            self.configuration = {}
        if self.dependencies is None:
            self.dependencies = []


@dataclass 
class BotContext:
    """Context provided to technical features during application."""
    bot_instance: BotInstance
    environment_config: Dict[str, Any]
    log_directory: Path
    feature_config: Dict[str, Any]


class TechnicalFeature(ABC):
    """
    Abstract base class for technical platform features.
    
    All features are technical infrastructure only - no business logic.
    Features enhance bot capabilities without coupling to the core platform.
    """
    
    def __init__(self, config: FeatureConfiguration):
        """
        Initialize technical feature with configuration.
        
        Args:
            config: Feature configuration
        """
        self.config = config
        self.logger = logging.getLogger(f"MultiCord.Feature.{config.feature_name}")
        self._initialized = False
    
    @property
    @abstractmethod
    def feature_name(self) -> str:
        """Name of this technical feature."""
        pass
    
    @property  
    @abstractmethod
    def feature_type(self) -> str:
        """Type of feature (technical, monitoring, enhancement)."""
        pass
    
    @property
    def dependencies(self) -> List[str]:
        """List of required feature dependencies."""
        return self.config.dependencies
    
    @property
    def is_initialized(self) -> bool:
        """Whether feature has been initialized."""
        return self._initialized
    
    async def initialize(self) -> bool:
        """
        Initialize the technical feature.
        
        Override this method to perform feature-specific initialization.
        
        Returns:
            True if initialization successful
        """
        try:
            await self._do_initialize()
            self._initialized = True
            self.logger.info(f"Technical feature {self.feature_name} initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize feature {self.feature_name}: {e}")
            return False
    
    async def _do_initialize(self) -> None:
        """Override this method for custom initialization logic."""
        pass
    
    @abstractmethod
    async def apply_to_bot_context(self, context: BotContext) -> bool:
        """
        Apply technical feature to bot context.
        
        This method is called when a bot is started with this feature enabled.
        Apply technical enhancements without modifying bot code.
        
        Args:
            context: Bot context with instance and configuration
            
        Returns:
            True if feature applied successfully
        """
        pass
    
    async def cleanup(self) -> None:
        """
        Clean up feature resources.
        
        Override this method to perform cleanup when feature is disabled.
        """
        self.logger.info(f"Cleaning up technical feature {self.feature_name}")
    
    def get_configuration_schema(self) -> Dict[str, Any]:
        """
        Get JSON schema for feature configuration validation.
        
        Override this method to provide configuration schema.
        
        Returns:
            JSON schema dict
        """
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": True
        }
    
    def validate_configuration(self, config: Dict[str, Any]) -> bool:
        """
        Validate feature configuration against schema.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if configuration is valid
        """
        try:
            # Basic validation - override for custom validation
            schema = self.get_configuration_schema()
            # Could use jsonschema library here for full validation
            return True
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False


class FeatureRegistrationError(Exception):
    """Exception raised during feature registration."""
    pass


class FeatureDependencyError(Exception):
    """Exception raised when feature dependencies cannot be resolved."""
    pass


class TechnicalFeatureContainer:
    """
    Dependency injection container for technical features.
    
    Manages registration, resolution, and lifecycle of technical features
    with PostgreSQL configuration persistence.
    """
    
    def __init__(self, 
                 db_pool: Optional[PostgreSQLConnectionPool] = None,
                 logger: logging.Logger = None):
        """
        Initialize feature container.
        
        Args:
            db_pool: PostgreSQL connection pool for configuration persistence
            logger: Logger instance
        """
        self.db_pool = db_pool
        self.logger = logger or logging.getLogger(__name__)
        
        # Feature registry
        self._feature_factories: Dict[str, Callable[[], TechnicalFeature]] = {}
        self._feature_instances: Dict[str, TechnicalFeature] = {}
        self._feature_configurations: Dict[str, FeatureConfiguration] = {}
        
        # Dependency graph
        self._dependency_graph: Dict[str, List[str]] = {}
        
        self._initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize the feature container.
        
        Loads feature configurations from PostgreSQL if available.
        
        Returns:
            True if initialization successful
        """
        try:
            self.logger.info("Initializing Technical Feature Container")
            
            if self.db_pool:
                await self._load_feature_configurations_from_db()
            else:
                self.logger.info("No database pool - using in-memory feature configuration")
            
            self._initialized = True
            self.logger.info("✓ Technical Feature Container initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize feature container: {e}")
            return False
    
    def register_feature(self, 
                        feature_factory: Callable[[], TechnicalFeature],
                        config: Optional[FeatureConfiguration] = None) -> None:
        """
        Register a technical feature factory.
        
        Args:
            feature_factory: Factory function that creates feature instance
            config: Optional feature configuration (will be created if not provided)
            
        Raises:
            FeatureRegistrationError: If registration fails
        """
        try:
            # Create temporary instance to get feature info
            temp_instance = feature_factory()
            feature_name = temp_instance.feature_name
            
            # Create default configuration if not provided
            if config is None:
                config = FeatureConfiguration(
                    feature_name=temp_instance.feature_name,
                    feature_type=temp_instance.feature_type,
                    dependencies=temp_instance.dependencies,
                    description=f"Technical feature: {feature_name}"
                )
            
            # Validate feature type
            if config.feature_type not in ["technical", "monitoring", "enhancement"]:
                raise FeatureRegistrationError(
                    f"Invalid feature type '{config.feature_type}'. Must be: technical, monitoring, enhancement"
                )
            
            # Register factory and configuration
            self._feature_factories[feature_name] = feature_factory
            self._feature_configurations[feature_name] = config
            
            # Update dependency graph
            self._dependency_graph[feature_name] = config.dependencies.copy()
            
            self.logger.info(f"✓ Registered technical feature: {feature_name} ({config.feature_type})")
            
        except Exception as e:
            raise FeatureRegistrationError(f"Failed to register feature: {e}")
    
    async def get_feature(self, feature_name: str) -> Optional[TechnicalFeature]:
        """
        Get or create a technical feature instance.
        
        Args:
            feature_name: Name of feature to get
            
        Returns:
            Feature instance if available, None otherwise
        """
        try:
            # Return existing instance if available
            if feature_name in self._feature_instances:
                return self._feature_instances[feature_name]
            
            # Check if feature is registered
            if feature_name not in self._feature_factories:
                self.logger.warning(f"Feature {feature_name} not registered")
                return None
            
            # Resolve dependencies first
            if not await self._resolve_dependencies(feature_name):
                self.logger.error(f"Could not resolve dependencies for {feature_name}")
                return None
            
            # Create feature instance
            config = self._feature_configurations[feature_name]
            factory = self._feature_factories[feature_name]
            feature_instance = factory()
            
            # Initialize feature
            if not await feature_instance.initialize():
                self.logger.error(f"Failed to initialize feature {feature_name}")
                return None
            
            # Store instance
            self._feature_instances[feature_name] = feature_instance
            
            self.logger.info(f"✓ Created and initialized feature: {feature_name}")
            return feature_instance
            
        except Exception as e:
            self.logger.error(f"Failed to get feature {feature_name}: {e}")
            return None
    
    async def apply_features_to_bot(self, 
                                  bot_instance: BotInstance, 
                                  feature_names: List[str],
                                  environment_config: Dict[str, Any],
                                  log_directory: Path) -> List[str]:
        """
        Apply technical features to a bot instance.
        
        Args:
            bot_instance: Bot instance to enhance
            feature_names: List of feature names to apply
            environment_config: Bot environment configuration
            log_directory: Bot log directory
            
        Returns:
            List of successfully applied feature names
        """
        applied_features = []
        
        try:
            for feature_name in feature_names:
                feature = await self.get_feature(feature_name)
                if not feature:
                    self.logger.warning(f"Could not load feature {feature_name}")
                    continue
                
                # Create bot context
                feature_config = self._feature_configurations.get(feature_name, {})
                context = BotContext(
                    bot_instance=bot_instance,
                    environment_config=environment_config,
                    log_directory=log_directory,
                    feature_config=feature_config.configuration if hasattr(feature_config, 'configuration') else {}
                )
                
                # Apply feature
                try:
                    success = await feature.apply_to_bot_context(context)
                    if success:
                        applied_features.append(feature_name)
                        self.logger.info(f"✓ Applied feature {feature_name} to bot {bot_instance.client_id}")
                    else:
                        self.logger.warning(f"Feature {feature_name} failed to apply to bot {bot_instance.client_id}")
                        
                except Exception as e:
                    self.logger.error(f"Error applying feature {feature_name}: {e}")
            
            return applied_features
            
        except Exception as e:
            self.logger.error(f"Error applying features to bot {bot_instance.client_id}: {e}")
            return applied_features
    
    def list_available_features(self) -> List[Dict[str, Any]]:
        """
        List all available technical features.
        
        Returns:
            List of feature information dictionaries
        """
        features = []
        
        for feature_name, config in self._feature_configurations.items():
            is_loaded = feature_name in self._feature_instances
            features.append({
                "name": feature_name,
                "type": config.feature_type,
                "description": config.description,
                "version": config.version,
                "dependencies": config.dependencies,
                "enabled": config.enabled,
                "loaded": is_loaded
            })
        
        return features
    
    async def _resolve_dependencies(self, feature_name: str) -> bool:
        """
        Resolve feature dependencies recursively.
        
        Args:
            feature_name: Feature to resolve dependencies for
            
        Returns:
            True if all dependencies resolved successfully
        """
        try:
            dependencies = self._dependency_graph.get(feature_name, [])
            
            for dependency in dependencies:
                # Check if dependency is registered
                if dependency not in self._feature_factories:
                    raise FeatureDependencyError(f"Dependency {dependency} not registered")
                
                # Ensure dependency is loaded
                if dependency not in self._feature_instances:
                    dependency_feature = await self.get_feature(dependency)
                    if not dependency_feature:
                        raise FeatureDependencyError(f"Failed to load dependency {dependency}")
            
            return True
            
        except FeatureDependencyError:
            raise
        except Exception as e:
            self.logger.error(f"Error resolving dependencies for {feature_name}: {e}")
            return False
    
    async def _load_feature_configurations_from_db(self) -> None:
        """Load feature configurations from PostgreSQL."""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.get_transaction() as conn:
                rows = await conn.fetch("SELECT * FROM platform_features WHERE enabled = true")
                
                for row in rows:
                    feature_name = row['feature_name']
                    
                    # Only load if we have a factory for this feature
                    if feature_name in self._feature_factories:
                        config = FeatureConfiguration(
                            feature_name=feature_name,
                            feature_type=row['feature_type'],
                            enabled=True,
                            configuration=row.get('configuration_schema', {}),
                            description=row.get('description', '')
                        )
                        
                        self._feature_configurations[feature_name] = config
                        self.logger.info(f"Loaded configuration for feature {feature_name}")
        
        except Exception as e:
            self.logger.warning(f"Could not load feature configurations from database: {e}")
    
    async def save_feature_configuration(self, feature_name: str, config: FeatureConfiguration) -> bool:
        """
        Save feature configuration to PostgreSQL.
        
        Args:
            feature_name: Name of feature
            config: Configuration to save
            
        Returns:
            True if saved successfully
        """
        if not self.db_pool:
            self.logger.warning("No database pool - cannot save feature configuration")
            return False
        
        try:
            async with self.db_pool.get_transaction() as conn:
                await conn.execute("""
                    INSERT INTO platform_features (
                        feature_name, feature_type, configuration_schema, 
                        enabled, description, version
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (feature_name) DO UPDATE SET
                        configuration_schema = $3, enabled = $4, 
                        description = $5, version = $6
                """, config.feature_name, config.feature_type, 
                json.dumps(config.configuration), config.enabled, 
                config.description, config.version)
            
            self.logger.info(f"Saved configuration for feature {feature_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save feature configuration {feature_name}: {e}")
            return False
    
    async def cleanup(self) -> None:
        """Clean up all loaded features and resources."""
        self.logger.info("Cleaning up Technical Feature Container")
        
        for feature_name, feature in self._feature_instances.items():
            try:
                await feature.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up feature {feature_name}: {e}")
        
        self._feature_instances.clear()
        self.logger.info("✓ Feature container cleanup complete")