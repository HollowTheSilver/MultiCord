"""
Template Manager - Multi-Source Template Discovery & Management
==============================================================

Manages template discovery, metadata processing, and repository synchronization.
Integrates with existing ClientManager FLAGS system.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from core.utils.loguruConfig import configure_logger


class TemplateManager:
    """Discovers and manages templates from multiple sources."""

    def __init__(self, platform_config_path: str = "platform_config.json"):
        """Initialize template manager."""
        self.builtin_path = Path("templates/builtin")
        self.community_path = Path("templates/community")
        self.platform_config_path = Path(platform_config_path)

        self.logger = configure_logger(
            log_dir="bot_platform/logs",
            level="INFO",
            format_extra=True,
            discord_compat=True
        )

        # Load template sources configuration
        self.template_sources = self._load_template_sources_config()

        # Ensure template directories exist
        self._ensure_template_directories()

        # Create built-in templates if they don't exist
        self._ensure_builtin_templates()

    def _load_template_sources_config(self) -> List[Dict[str, Any]]:
        """Load template sources from platform configuration."""
        try:
            if self.platform_config_path.exists():
                with open(self.platform_config_path, 'r') as f:
                    config = json.load(f)
                return config.get("template_sources", self._default_template_sources())
            else:
                return self._default_template_sources()
        except Exception as e:
            self.logger.warning(f"Failed to load template sources config: {e}")
            return self._default_template_sources()

    def _default_template_sources(self) -> List[Dict[str, Any]]:
        """Default template sources configuration."""
        return [
            {
                "name": "Built-in Templates",
                "type": "local",
                "path": "templates/builtin/",
                "enabled": True
            }
        ]

    def discover_templates(self) -> List[Dict[str, Any]]:
        """Discover all available templates from all enabled sources."""
        templates = []

        for source in self.template_sources:
            if not source.get("enabled", True):
                continue

            try:
                if source["type"] == "local":
                    templates.extend(self._scan_local_templates(source))
                elif source["type"] == "git":
                    templates.extend(self._scan_git_templates(source))

            except Exception as e:
                self.logger.error(f"Failed to scan templates from {source['name']}: {e}")

        return templates

    def _scan_local_templates(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scan templates from local directory."""
        templates = []
        source_path = Path(source["path"])

        if not source_path.exists():
            return templates

        for template_dir in source_path.iterdir():
            if template_dir.is_dir() and not template_dir.name.startswith("."):
                metadata = self._load_template_metadata(template_dir)
                if metadata:
                    metadata["source"] = source["name"]
                    metadata["path"] = str(template_dir)
                    templates.append(metadata)

        return templates

    def _scan_git_templates(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scan templates from Git repository."""
        local_path = self.community_path / source["name"].lower().replace(" ", "_")

        # Sync repository
        if self._sync_git_repository(source, local_path):
            # Treat as local templates after sync
            local_source = {"path": str(local_path), "name": source["name"]}
            return self._scan_local_templates(local_source)

        return []

    def _sync_git_repository(self, source: Dict[str, Any], local_path: Path) -> bool:
        """Sync Git repository to local path."""
        try:
            if local_path.exists():
                # Pull updates
                result = subprocess.run(
                    ["git", "pull"],
                    cwd=local_path,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    self.logger.warning(f"Git pull failed for {source['name']}: {result.stderr}")
                    return False
            else:
                # Initial clone
                local_path.parent.mkdir(parents=True, exist_ok=True)
                result = subprocess.run(
                    ["git", "clone", source["url"], str(local_path)],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    self.logger.error(f"Git clone failed for {source['name']}: {result.stderr}")
                    return False

            self.logger.info(f"Successfully synced Git repository: {source['name']}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to sync Git repository {source['name']}: {e}")
            return False

    def _load_template_metadata(self, template_path: Path) -> Optional[Dict[str, Any]]:
        """Load template metadata from template.json."""
        metadata_file = template_path / "template.json"

        if not metadata_file.exists():
            # Create basic metadata for templates without template.json
            return self._create_basic_metadata(template_path)

        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

            # Validate required fields
            required_fields = ["name", "description", "version"]
            for field in required_fields:
                if field not in metadata:
                    self.logger.warning(f"Template {template_path.name} missing required field: {field}")
                    return None

            return metadata

        except Exception as e:
            self.logger.error(f"Failed to load metadata for {template_path.name}: {e}")
            return None

    def _create_basic_metadata(self, template_path: Path) -> Dict[str, Any]:
        """Create basic metadata for templates without template.json."""
        return {
            "name": template_path.name.replace("_", " ").title(),
            "description": f"Template: {template_path.name}",
            "version": "1.0.0",
            "author": "Platform User",
            "category": "custom",
            "difficulty": "intermediate",
            "default_flags": {},
            "customizable_flags": [],
            "path": str(template_path)
        }

    def get_template_by_name(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get specific template by name."""
        templates = self.discover_templates()

        for template in templates:
            if template["name"].lower() == template_name.lower():
                return template

        return None

    def _ensure_template_directories(self) -> None:
        """Ensure all template directories exist."""
        self.builtin_path.mkdir(parents=True, exist_ok=True)
        self.community_path.mkdir(parents=True, exist_ok=True)

    def _ensure_builtin_templates(self) -> None:
        """Create built-in templates if they don't exist."""
        builtin_templates = [
            "blank",
            "moderation_bot",
            "music_bot",
            "economy_bot"
        ]

        for template_name in builtin_templates:
            template_dir = self.builtin_path / template_name
            if not template_dir.exists():
                self._create_builtin_template(template_name, template_dir)

    def _create_builtin_template(self, template_name: str, template_dir: Path) -> None:
        """Create a built-in template directory with metadata."""
        template_dir.mkdir(parents=True, exist_ok=True)

        # Create template.json based on template type
        metadata = self._get_builtin_template_metadata(template_name)

        metadata_file = template_dir / "template.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Create template files based on type
        self._create_template_files(template_name, template_dir, metadata)

        self.logger.info(f"Created built-in template: {template_name}")

    def _get_builtin_template_metadata(self, template_name: str) -> Dict[str, Any]:
        """Get metadata for built-in templates."""
        metadata_map = {
            "blank": {
                "name": "Blank Template",
                "description": "Basic Discord bot setup with minimal configuration",
                "version": "1.0.0",
                "author": "Discord Platform Team",
                "category": "basic",
                "difficulty": "beginner",
                "discord_py_version": ">=2.3.0",
                "tags": ["basic", "starter", "minimal"],
                "default_flags": {
                    "base_commands": True,
                    "permission_system": True,
                    "error_handling": True,
                    "logging_enabled": True,
                    "database_backend": "sqlite"
                },
                "recommended_database": "sqlite",
                "database_features": {
                    "requires_real_time": False,
                    "high_write_volume": False,
                    "complex_queries": False
                },
                "customizable_flags": [
                    "logging_enabled",
                    "database_backend"
                ],
                "required_permissions": [],
                "cogs": [],
                "dependencies": []
            },
            "moderation_bot": {
                "name": "Moderation Bot",
                "description": "Complete moderation system with auto-mod, warnings, and appeals",
                "version": "1.2.0",
                "author": "Discord Platform Team",
                "category": "moderation",
                "difficulty": "beginner",
                "discord_py_version": ">=2.3.0",
                "tags": ["moderation", "automod", "appeals", "warnings"],
                "default_flags": {
                    "moderation_enabled": True,
                    "auto_mod_spam": True,
                    "auto_mod_toxicity": False,
                    "max_warnings": 3,
                    "ban_appeal_system": True,
                    "database_backend": "sqlite",
                    "limits": {
                        "max_moderation_rules": 50,
                        "warning_expiry_days": 30
                    }
                },
                "recommended_database": "firestore",
                "database_features": {
                    "requires_real_time": True,
                    "high_write_volume": False,
                    "complex_queries": True
                },
                "customizable_flags": [
                    "auto_mod_toxicity",
                    "max_warnings",
                    "ban_appeal_system",
                    "limits.max_moderation_rules"
                ],
                "required_permissions": ["manage_messages", "ban_members", "kick_members"],
                "optional_integrations": ["webhook_logging", "audit_system"],
                "cogs": ["moderation", "automod", "appeals"],
                "dependencies": []
            },
            "music_bot": {
                "name": "Music Bot",
                "description": "Full-featured music streaming bot with playlists and queue management",
                "version": "1.1.0",
                "author": "Discord Platform Team",
                "category": "entertainment",
                "difficulty": "intermediate",
                "discord_py_version": ">=2.3.0",
                "tags": ["music", "streaming", "playlists", "entertainment"],
                "default_flags": {
                    "music_enabled": True,
                    "playlist_support": True,
                    "queue_management": True,
                    "youtube_support": True,
                    "spotify_integration": False,
                    "database_backend": "sqlite",
                    "limits": {
                        "max_queue_size": 100,
                        "max_playlist_size": 500
                    }
                },
                "recommended_database": "firestore",
                "database_features": {
                    "requires_real_time": True,
                    "high_write_volume": True,
                    "complex_queries": False
                },
                "customizable_flags": [
                    "spotify_integration",
                    "limits.max_queue_size",
                    "limits.max_playlist_size"
                ],
                "required_permissions": ["connect", "speak"],
                "optional_integrations": ["spotify_api", "youtube_api"],
                "cogs": ["music", "playlist", "queue"],
                "dependencies": ["youtube-dl", "PyNaCl"]
            },
            "economy_bot": {
                "name": "Economy Bot",
                "description": "Complete economy system with currency, leveling, and virtual shop",
                "version": "1.0.0",
                "author": "Discord Platform Team",
                "category": "economy",
                "difficulty": "intermediate",
                "discord_py_version": ">=2.3.0",
                "tags": ["economy", "currency", "leveling", "shop"],
                "default_flags": {
                    "economy_enabled": True,
                    "leveling_system": True,
                    "virtual_shop": True,
                    "daily_rewards": True,
                    "gambling_games": False,
                    "database_backend": "sqlite",
                    "limits": {
                        "max_daily_reward": 1000,
                        "max_bet_amount": 5000,
                        "level_up_multiplier": 1.5
                    }
                },
                "recommended_database": "postgresql",
                "database_features": {
                    "requires_real_time": False,
                    "high_write_volume": True,
                    "complex_queries": True
                },
                "customizable_flags": [
                    "gambling_games",
                    "limits.max_daily_reward",
                    "limits.max_bet_amount"
                ],
                "required_permissions": [],
                "optional_integrations": ["payment_gateway"],
                "cogs": ["economy", "leveling", "shop"],
                "dependencies": []
            }
        }

        return metadata_map.get(template_name, {})

    def _create_template_files(self, template_name: str, template_dir: Path, metadata: Dict[str, Any]) -> None:
        """Create template files for built-in templates."""
        # Create custom_cogs directory if template has cogs
        if metadata.get("cogs"):
            cogs_dir = template_dir / "custom_cogs"
            cogs_dir.mkdir(exist_ok=True)

            # Create placeholder cog files
            for cog_name in metadata["cogs"]:
                cog_file = cogs_dir / f"{cog_name}.py"
                self._create_placeholder_cog(cog_file, cog_name, template_name)

        # Create flags.py.template with template-specific defaults
        self._create_flags_template(template_dir, template_name, metadata)

        # Create branding.py.template with template-specific theming
        self._create_branding_template(template_dir, template_name, metadata)

    def _create_placeholder_cog(self, cog_file: Path, cog_name: str, template_name: str) -> None:
        """Create placeholder cog file."""
        cog_content = f'''"""
{cog_name.title()} Cog for {template_name.replace("_", " ").title()}
============================================

Placeholder cog - implement your {cog_name} functionality here.
"""

import discord
from discord.ext import commands


class {cog_name.title()}Cog(commands.Cog):
    """Placeholder {cog_name} cog for {template_name}."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="{cog_name}")
    async def {cog_name}_command(self, ctx):
        """Placeholder {cog_name} command."""
        await ctx.send(f"🚧 {cog_name.title()} functionality coming soon!")


async def setup(bot):
    await bot.add_cog({cog_name.title()}Cog(bot))
'''

        with open(cog_file, 'w') as f:
            f.write(cog_content)

    def _create_flags_template(self, template_dir: Path, template_name: str, metadata: Dict[str, Any]) -> None:
        """Create flags.py.template with template-specific defaults."""
        default_flags = metadata.get("default_flags", {})

        flags_content = f'''"""Client FLAGS Configuration for {{DISPLAY_NAME}}"""

# FLAGS system - Template: {metadata.get("name", template_name)}
# Generated from template metadata - Version: {metadata.get("version", "1.0.0")}
FLAGS = {{
    # ================== Core Platform FLAGS ================== #
    "base_commands": {default_flags.get("base_commands", True)},
    "permission_system": {default_flags.get("permission_system", True)},
    "error_handling": {default_flags.get("error_handling", True)},
    "logging_enabled": {default_flags.get("logging_enabled", True)},

    # ================== Template-Specific FLAGS ================== #'''

        # Add template-specific flags
        for key, value in default_flags.items():
            if key not in ["base_commands", "permission_system", "error_handling", "logging_enabled",
                           "database_backend", "limits"]:
                flags_content += f'\n    "{key}": {json.dumps(value)},'

        flags_content += f'''

    # ================== Database Configuration ================== #
    "database": {{
        "backend": "{{DATABASE_BACKEND}}",
        "config": {{}}
    }},

    # ================== Limits and Quotas ================== #
    "limits": {json.dumps(default_flags.get("limits", {}), indent=8)[1:-1].replace("\\n", "\\n    ")},

    # ================== User-Customizable FLAGS ================== #
    "custom_embeds": True,
    "webhook_notifications": False,
    "debug_mode": False,
    "cache_enabled": True,
    "auto_cleanup": True,

    # ================== Plan-Based Features (Optional) ================== #
    "plan_features": {{
        "plan_name": "{{PLAN}}",
        "monthly_fee": "{{MONTHLY_FEE}}",
        "support_level": "community",
        "priority_support": {{PRIORITY_SUPPORT_ENABLED}},
        "api_access": {{API_ACCESS_ENABLED}},
    }},

    # ================== Template Metadata ================== #
    "template_info": {{
        "name": "{metadata.get('name', template_name)}",
        "version": "{metadata.get('version', '1.0.0')}",
        "category": "{metadata.get('category', 'custom')}",
        "author": "{metadata.get('author', 'Platform User')}",
        "description": "{metadata.get('description', '')}",
        "database_recommended": "{{DATABASE_BACKEND}}",
    }},

    # ================== Custom User FLAGS ================== #
    "custom": {{}}
}}
'''

        flags_file = template_dir / "flags.py.template"
        with open(flags_file, 'w') as f:
            f.write(flags_content)

    def _create_branding_template(self, template_dir: Path, template_name: str, metadata: Dict[str, Any]) -> None:
        """Create branding.py.template with template-specific theming."""
        category = metadata.get("category", "custom")

        # Template-specific color schemes
        color_schemes = {
            "moderation": {
                "default": "0xe74c3c",  # Red
                "success": "0x2ecc71",  # Green
                "error": "0xe74c3c",  # Red
                "warning": "0xf39c12"  # Orange
            },
            "entertainment": {
                "default": "0x9b59b6",  # Purple
                "success": "0x1abc9c",  # Turquoise
                "error": "0xe74c3c",  # Red
                "warning": "0xf39c12"  # Orange
            },
            "economy": {
                "default": "0xf1c40f",  # Gold
                "success": "0x2ecc71",  # Green
                "error": "0xe74c3c",  # Red
                "warning": "0xf39c12"  # Orange
            },
            "basic": {
                "default": "0x3498db",  # Blue
                "success": "0x2ecc71",  # Green
                "error": "0xe74c3c",  # Red
                "warning": "0xf39c12"  # Orange
            }
        }

        colors = color_schemes.get(category, color_schemes["basic"])

        branding_content = f'''"""Branding Configuration for {{DISPLAY_NAME}}"""

# Template: {metadata.get("name", template_name)} - {metadata.get("category", "custom").title()} Bot
BRANDING = {{
    # ================== Bot Identity ================== #
    "bot_name": "{{BOT_NAME}}",
    "bot_description": "{metadata.get('description', 'Discord Bot')}",
    "bot_version": "{{BOT_VERSION}}",

    # ================== Visual Theme - {category.title()} Template ================== #
    "embed_colors": {{
        "default": {colors["default"]},
        "success": {colors["success"]}, 
        "error": {colors["error"]},
        "warning": {colors["warning"]},
        "info": {colors["default"]}
    }},

    # ================== Status Messages ================== #
    "status_messages": [
        ("{metadata.get('name', template_name).replace('_', ' ')}", "playing"),
        ("{{SERVER_COUNT}} servers", "watching"),
        ("{{COMMAND_PREFIX}}help for commands", "listening")
    ],

    # ================== Footer & Branding ================== #
    "footer_text": "Powered by {{DISPLAY_NAME}}",
    "embed_footer_icon": None,
    "embed_thumbnail": None,

    # ================== Template-Specific Branding ================== #
    "template_theme": {{
        "category": "{category}",
        "primary_color": {colors["default"]},
        "accent_color": {colors["success"]},
        "template_name": "{metadata.get('name', template_name)}"
    }}
}}
'''

        branding_file = template_dir / "branding.py.template"
        with open(branding_file, 'w') as f:
            f.write(branding_content)
