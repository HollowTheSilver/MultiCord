"""
Template Discovery Service
=========================

Service for discovering, validating, and managing Discord bot templates.
Provides clean separation between template management and execution strategy.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

from ..entities.process_info import ProcessInfo
from ..infrastructure.postgresql_pool import PostgreSQLConnectionPool


@dataclass
class TemplateMetadata:
    """Template metadata with validation and feature information."""
    
    name: str
    display_name: str
    description: str
    version: str
    author: str
    template_type: str
    main_file: str
    features: List[str]
    requirements: List[Dict[str, Any]]
    environment: Dict[str, str]
    commands: List[str]
    technical_features: Dict[str, bool]
    configuration_schema: Dict[str, Any]
    template_path: Path
    created_at: datetime
    last_modified: datetime
    
    @classmethod
    def from_config(cls, name: str, config: Dict[str, Any], template_path: Path) -> 'TemplateMetadata':
        """Create template metadata from configuration dictionary."""
        stat = template_path.stat()
        
        return cls(
            name=name,
            display_name=config.get("display_name", name.replace("_", " ").title()),
            description=config.get("description", ""),
            version=config.get("version", "1.0.0"),
            author=config.get("author", "Unknown"),
            template_type=config.get("template_type", "custom"),
            main_file=config.get("main_file", "bot.py"),
            features=config.get("features", []),
            requirements=config.get("requirements", []),
            environment=config.get("environment", {}),
            commands=config.get("commands", []),
            technical_features=config.get("technical_features", {}),
            configuration_schema=config.get("configuration_schema", {}),
            template_path=template_path,
            created_at=datetime.fromtimestamp(stat.st_ctime, timezone.utc),
            last_modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert template metadata to dictionary for API responses."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "template_type": self.template_type,
            "main_file": self.main_file,
            "features": self.features,
            "requirements": self.requirements,
            "environment": self.environment,
            "commands": self.commands,
            "technical_features": self.technical_features,
            "configuration_schema": self.configuration_schema,
            "created_at": self.created_at.isoformat(),
            "last_modified": self.last_modified.isoformat()
        }


class TemplateDiscoveryService:
    """
    Service for template discovery and management.
    
    Provides clean separation of template management from execution strategy,
    following MultiCord's clean architecture principles.
    """
    
    def __init__(self, 
                 templates_directory: Path = None,
                 db_pool: PostgreSQLConnectionPool = None,
                 logger: logging.Logger = None):
        """
        Initialize template discovery service.
        
        Args:
            templates_directory: Directory containing bot templates
            db_pool: PostgreSQL connection pool for metadata storage
            logger: Logger instance for service operations
        """
        self.templates_directory = templates_directory or Path("templates")
        self.db_pool = db_pool
        self.logger = logger or logging.getLogger(__name__)
        
        # Ensure templates directory exists
        self.templates_directory.mkdir(exist_ok=True)
        
        # Cache for discovered templates
        self._template_cache: Dict[str, TemplateMetadata] = {}
        self._cache_last_updated: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes
    
    async def discover_templates(self, force_refresh: bool = False) -> List[TemplateMetadata]:
        """
        Discover all available templates.
        
        Args:
            force_refresh: Force cache refresh even if still valid
            
        Returns:
            List of discovered template metadata
        """
        try:
            # Check cache validity
            if not force_refresh and self._is_cache_valid():
                return list(self._template_cache.values())
            
            self.logger.info("Discovering templates from directory...")
            
            discovered_templates = {}
            
            # Scan templates directory
            if self.templates_directory.exists():
                for template_dir in self.templates_directory.iterdir():
                    if template_dir.is_dir():
                        template_metadata = await self._load_template_metadata(template_dir)
                        if template_metadata:
                            discovered_templates[template_metadata.name] = template_metadata
                        else:
                            self.logger.warning(f"Skipping invalid template directory: {template_dir.name}")
            
            # Update cache
            self._template_cache = discovered_templates
            self._cache_last_updated = datetime.now(timezone.utc)
            
            # Persist to PostgreSQL if available
            if self.db_pool:
                await self._persist_template_metadata(list(discovered_templates.values()))
            
            self.logger.info(f"Discovered {len(discovered_templates)} templates")
            return list(discovered_templates.values())
            
        except Exception as e:
            self.logger.error(f"Failed to discover templates: {e}")
            return []
    
    async def get_template(self, template_name: str) -> Optional[TemplateMetadata]:
        """
        Get specific template metadata by name.
        
        Args:
            template_name: Name of template to retrieve
            
        Returns:
            Template metadata if found, None otherwise
        """
        try:
            # Ensure templates are discovered
            if not self._is_cache_valid():
                await self.discover_templates()
            
            return self._template_cache.get(template_name)
            
        except Exception as e:
            self.logger.error(f"Failed to get template '{template_name}': {e}")
            return None
    
    async def validate_template(self, template_name: str) -> bool:
        """
        Validate that a template is properly configured and available.
        
        Args:
            template_name: Name of template to validate
            
        Returns:
            True if template is valid and available
        """
        try:
            template = await self.get_template(template_name)
            if not template:
                return False
            
            # Check that main file exists
            main_file_path = template.template_path / template.main_file
            if not main_file_path.exists():
                self.logger.error(f"Template '{template_name}' main file not found: {template.main_file}")
                return False
            
            # Validate configuration schema
            if not await self._validate_template_configuration(template):
                return False
            
            # Check for required files based on features
            if not await self._validate_template_features(template):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Template validation failed for '{template_name}': {e}")
            return False
    
    async def get_templates_by_feature(self, feature_name: str) -> List[TemplateMetadata]:
        """
        Get all templates that provide a specific feature.
        
        Args:
            feature_name: Feature to search for
            
        Returns:
            List of templates providing the feature
        """
        try:
            all_templates = await self.discover_templates()
            return [
                template for template in all_templates 
                if feature_name in template.features
            ]
            
        except Exception as e:
            self.logger.error(f"Failed to get templates by feature '{feature_name}': {e}")
            return []
    
    async def get_compatible_templates(self, required_features: Set[str]) -> List[TemplateMetadata]:
        """
        Get templates compatible with required features.
        
        Args:
            required_features: Set of features that must be supported
            
        Returns:
            List of compatible templates
        """
        try:
            all_templates = await self.discover_templates()
            compatible = []
            
            for template in all_templates:
                template_features = set(template.features)
                if required_features.issubset(template_features):
                    compatible.append(template)
            
            return compatible
            
        except Exception as e:
            self.logger.error(f"Failed to get compatible templates: {e}")
            return []
    
    async def _load_template_metadata(self, template_dir: Path) -> Optional[TemplateMetadata]:
        """Load template metadata from directory."""
        try:
            config_file = template_dir / "template.json"
            if not config_file.exists():
                return None
            
            # Load template configuration
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Validate required fields
            required_fields = ["display_name", "main_file"]
            if not all(field in config for field in required_fields):
                self.logger.warning(f"Template {template_dir.name} missing required fields")
                return None
            
            # Create metadata object
            return TemplateMetadata.from_config(template_dir.name, config, template_dir)
            
        except Exception as e:
            self.logger.error(f"Failed to load template metadata from {template_dir}: {e}")
            return None
    
    async def _validate_template_configuration(self, template: TemplateMetadata) -> bool:
        """Validate template configuration schema."""
        try:
            # Check for circular dependencies in requirements
            for req in template.requirements:
                if req.get("type") == "template":
                    dep_name = req.get("name")
                    if dep_name == template.name:
                        self.logger.error(f"Template '{template.name}' has circular dependency on itself")
                        return False
            
            # Validate environment variables format
            if template.environment:
                for key, value in template.environment.items():
                    if not isinstance(key, str) or not isinstance(value, str):
                        self.logger.error(f"Invalid environment variable format in template '{template.name}'")
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Template configuration validation failed: {e}")
            return False
    
    async def _validate_template_features(self, template: TemplateMetadata) -> bool:
        """Validate template feature availability."""
        try:
            # Check that referenced features actually exist in MultiCord platform
            known_features = {
                "branding_enhancement",
                "monitoring_service", 
                "logging_enhancement",
                "permission_management"
            }
            
            for feature in template.features:
                if feature not in known_features:
                    self.logger.warning(f"Template '{template.name}' references unknown feature: {feature}")
                    # Don't fail validation for unknown features - they might be custom
            
            return True
            
        except Exception as e:
            self.logger.error(f"Template feature validation failed: {e}")
            return False
    
    async def _persist_template_metadata(self, templates: List[TemplateMetadata]) -> None:
        """Persist template metadata to PostgreSQL."""
        if not self.db_pool:
            return
        
        try:
            # Implementation for PostgreSQL template metadata storage
            # This would integrate with the platform_features table
            # to track available templates and their capabilities
            self.logger.debug(f"Would persist {len(templates)} templates to PostgreSQL")
            
        except Exception as e:
            self.logger.error(f"Failed to persist template metadata: {e}")
    
    def _is_cache_valid(self) -> bool:
        """Check if template cache is still valid."""
        if not self._cache_last_updated:
            return False
        
        age_seconds = (datetime.now(timezone.utc) - self._cache_last_updated).total_seconds()
        return age_seconds < self._cache_ttl_seconds