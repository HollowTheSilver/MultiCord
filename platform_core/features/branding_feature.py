"""
Branding Feature - Technical Visual Customization
================================================

Optional technical feature for visual customization and branding.
Provides bot appearance enhancements without business logic coupling.

TECHNICAL ONLY - No pricing, billing, or subscription features.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from ..container.technical_feature_container import TechnicalFeature, FeatureConfiguration, BotContext


class BrandingFeature(TechnicalFeature):
    """
    Technical branding feature for visual customization.
    
    Provides optional visual enhancements:
    - Custom embed colors
    - Bot avatar and name customization
    - Custom help messages and descriptions
    - Logo and icon injection for templates
    
    NO BUSINESS LOGIC - Pure technical enhancement.
    """
    
    def __init__(self, config: Optional[FeatureConfiguration] = None):
        """Initialize branding feature."""
        if config is None:
            config = FeatureConfiguration(
                feature_name="branding_enhancement",
                feature_type="technical",
                description="Optional visual customization and branding",
                version="1.0.0",
                configuration={
                    "embed_colors": {
                        "primary": "#5865F2",
                        "success": "#57F287", 
                        "warning": "#FEE75C",
                        "error": "#ED4245"
                    },
                    "bot_customization": {
                        "display_name": "",
                        "avatar_url": "",
                        "custom_status": "Powered by MultiCord Platform"
                    },
                    "branding_text": {
                        "footer_text": "MultiCord Platform",
                        "help_description": "Professional Discord bot management",
                        "custom_prefix": "🤖"
                    }
                }
            )
        super().__init__(config)
    
    @property
    def feature_name(self) -> str:
        """Name of this technical feature."""
        return "branding_enhancement"
    
    @property
    def feature_type(self) -> str:
        """Type of feature."""
        return "technical"
    
    async def _do_initialize(self) -> None:
        """Initialize branding feature resources."""
        self.logger.info("Initializing branding customization resources")
        
        # Validate color configurations
        self._validate_color_config()
        
        # Prepare branding assets directory
        self.assets_directory = Path("platform_assets/branding")
        self.assets_directory.mkdir(parents=True, exist_ok=True)
    
    def _validate_color_config(self) -> None:
        """Validate color configuration values."""
        colors = self.config.configuration.get("embed_colors", {})
        
        for color_name, color_value in colors.items():
            if not isinstance(color_value, str) or not color_value.startswith("#"):
                self.logger.warning(f"Invalid color format for {color_name}: {color_value}")
                # Set default color
                colors[color_name] = "#5865F2"
    
    async def apply_to_bot_context(self, context: BotContext) -> bool:
        """
        Apply branding enhancements to bot context.
        
        Creates environment variables and configuration files that
        bots can optionally use for visual customization.
        
        Args:
            context: Bot context with instance and configuration
            
        Returns:
            True if branding applied successfully
        """
        try:
            client_id = context.bot_instance.client_id
            self.logger.info(f"Applying branding enhancements to {client_id}")
            
            # Step 1: Create branding configuration file
            branding_config_path = await self._create_branding_config_file(context)
            
            # Step 2: Set environment variables for bot discovery
            self._set_branding_environment_variables(context, branding_config_path)
            
            # Step 3: Create optional assets directory
            await self._setup_bot_assets_directory(context)
            
            self.logger.info(f"✅ Branding enhancements applied to {client_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to apply branding to {context.bot_instance.client_id}: {e}")
            return False
    
    async def _create_branding_config_file(self, context: BotContext) -> Path:
        """Create branding configuration file for bot."""
        config_dir = context.log_directory.parent / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        branding_config_path = config_dir / "branding.json"
        
        # Merge default config with custom configuration
        branding_config = {
            "enabled": True,
            "colors": self.config.configuration.get("embed_colors", {}),
            "customization": self.config.configuration.get("bot_customization", {}),
            "text": self.config.configuration.get("branding_text", {}),
            "platform_info": {
                "powered_by": "MultiCord Platform",
                "version": "2.0.0"
            }
        }
        
        # Write configuration file
        with open(branding_config_path, 'w', encoding='utf-8') as f:
            json.dump(branding_config, f, indent=2, ensure_ascii=False)
        
        return branding_config_path
    
    def _set_branding_environment_variables(self, context: BotContext, config_path: Path) -> None:
        """Set environment variables for branding discovery."""
        # Add branding configuration path
        context.environment_config["MULTICORD_BRANDING_CONFIG"] = str(config_path)
        
        # Add primary branding colors as environment variables for easy access
        colors = self.config.configuration.get("embed_colors", {})
        context.environment_config["MULTICORD_PRIMARY_COLOR"] = colors.get("primary", "#5865F2")
        context.environment_config["MULTICORD_SUCCESS_COLOR"] = colors.get("success", "#57F287")
        
        # Add branding text
        text_config = self.config.configuration.get("branding_text", {})
        context.environment_config["MULTICORD_FOOTER_TEXT"] = text_config.get("footer_text", "MultiCord Platform")
        context.environment_config["MULTICORD_CUSTOM_PREFIX"] = text_config.get("custom_prefix", "🤖")
    
    async def _setup_bot_assets_directory(self, context: BotContext) -> None:
        """Set up assets directory for bot branding resources."""
        assets_dir = context.log_directory.parent / "assets" / "branding"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        # Create placeholder files for custom assets
        readme_content = "# MultiCord Branding Assets\n\nOptional branding customization directory."
        readme_file = assets_dir / "README.md"
        
        if not readme_file.exists():
            with open(readme_file, 'w', encoding='utf-8') as f:
                f.write(readme_content)
    
    def get_configuration_schema(self) -> Dict[str, Any]:
        """Get configuration schema for branding feature."""
        return {
            "type": "object",
            "properties": {
                "embed_colors": {"type": "object"},
                "bot_customization": {"type": "object"},
                "branding_text": {"type": "object"}
            },
            "additionalProperties": True
        }
    
    async def cleanup(self) -> None:
        """Clean up branding feature resources."""
        self.logger.info("Cleaning up branding feature resources")