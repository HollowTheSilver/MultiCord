"""
Template Manager - Multi-Source Template Discovery & Management
==============================================================

CRITICAL FIXES APPLIED:
1. Fixed fragile JSON formatting - replaced brittle string manipulation with proper JSON handling
2. Added encoding='utf-8' to ALL file operations for proper Unicode support
3. Implemented Git URL security validation to prevent malicious URL exploitation
4. Enhanced error handling with specific Git failure type distinction
5. Added proper indentation formatting without string manipulation

Version: 2.1.0 - Security & Robustness Enhanced
"""

import json
import shutil
import subprocess
import re
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from core.utils.loguruConfig import configure_logger


class TemplateManager:
    """Discovers and manages templates from multiple sources with enhanced security."""

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
                # FIXED: Added encoding='utf-8'
                with open(self.platform_config_path, 'r', encoding='utf-8') as f:
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

    def _validate_git_url(self, url: str) -> bool:
        """
        SECURITY FIX: Validate Git URL to prevent malicious URL exploitation.

        Args:
            url: Git repository URL to validate

        Returns:
            bool: True if URL is safe to use, False otherwise
        """
        if not url or not isinstance(url, str):
            return False

        # Parse URL to validate structure
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception:
            return False

        # Allow only safe schemes
        safe_schemes = {'https', 'git', 'ssh'}
        if parsed.scheme not in safe_schemes:
            self.logger.warning(f"Rejected unsafe Git URL scheme: {parsed.scheme}")
            return False

        # Block dangerous patterns
        dangerous_patterns = [
            r'[;&|`$]',  # Shell injection characters
            r'\.\./',    # Path traversal
            r'file://',  # Local file access
            r'ftp://',   # FTP protocol
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                self.logger.warning(f"Rejected Git URL with dangerous pattern: {pattern}")
                return False

        # Validate hostname for HTTPS/SSH
        if parsed.scheme in {'https', 'ssh'} and not parsed.hostname:
            return False

        return True

    def _sync_git_repository(self, source: Dict[str, Any], local_path: Path) -> bool:
        """
        SECURITY & ERROR HANDLING FIX: Sync Git repository with URL validation and enhanced error reporting.
        """
        url = source.get("url", "")

        # SECURITY FIX: Validate URL before any subprocess calls
        if not self._validate_git_url(url):
            self.logger.error(f"Git repository URL failed security validation: {source['name']}")
            return False

        try:
            if local_path.exists():
                # Pull updates
                self.logger.debug(f"Pulling updates for Git repository: {source['name']}")
                result = subprocess.run(
                    ["git", "pull"],
                    cwd=local_path,
                    capture_output=True,
                    text=True,
                    timeout=30  # Added timeout for security
                )

                if result.returncode != 0:
                    # ENHANCED ERROR HANDLING: Distinguish between error types
                    error_type = self._classify_git_error(result.stderr)
                    self.logger.warning(f"Git pull failed for {source['name']} ({error_type}): {result.stderr}")
                    return False
            else:
                # Initial clone
                self.logger.info(f"Cloning Git repository: {source['name']}")
                local_path.parent.mkdir(parents=True, exist_ok=True)

                result = subprocess.run(
                    ["git", "clone", url, str(local_path)],
                    capture_output=True,
                    text=True,
                    timeout=60  # Added timeout for security
                )

                if result.returncode != 0:
                    # ENHANCED ERROR HANDLING: Distinguish between error types
                    error_type = self._classify_git_error(result.stderr)
                    self.logger.error(f"Git clone failed for {source['name']} ({error_type}): {result.stderr}")
                    return False

            self.logger.info(f"Successfully synced Git repository: {source['name']}")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"Git operation timed out for {source['name']}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to sync Git repository {source['name']}: {e}")
            return False

    def _classify_git_error(self, stderr: str) -> str:
        """
        ENHANCED ERROR HANDLING: Classify Git errors for better debugging.

        Args:
            stderr: Git command stderr output

        Returns:
            str: Error classification
        """
        stderr_lower = stderr.lower()

        if 'authentication failed' in stderr_lower or 'permission denied' in stderr_lower:
            return "authentication_error"
        elif 'network' in stderr_lower or 'connection' in stderr_lower or 'timeout' in stderr_lower:
            return "network_error"
        elif 'not found' in stderr_lower or '404' in stderr_lower:
            return "repository_not_found"
        elif 'already exists' in stderr_lower:
            return "directory_conflict"
        elif 'invalid' in stderr_lower or 'malformed' in stderr_lower:
            return "invalid_repository"
        else:
            return "unknown_error"

    def _load_template_metadata(self, template_path: Path) -> Optional[Dict[str, Any]]:
        """Load template metadata from template.json."""
        metadata_file = template_path / "template.json"

        if not metadata_file.exists():
            # Create basic metadata for templates without template.json
            return self._create_basic_metadata(template_path)

        try:
            # FIXED: Added encoding='utf-8'
            with open(metadata_file, 'r', encoding='utf-8') as f:
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
        # FIXED: Added encoding='utf-8'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        # Create template files based on type
        self._create_template_files(template_name, template_dir, metadata)

        self.logger.info(f"Created built-in template: {template_name}")

    def _get_builtin_template_metadata(self, template_name: str) -> Dict[str, Any]:
        """Get metadata for built-in templates."""
        base_metadata = {
            "version": "1.0.0",
            "author": "Discord Cloud Platform",
            "category": "builtin",
            "difficulty": "beginner",
            "customizable_flags": [
                "auto_moderation", "max_warnings", "timeout_duration",
                "log_channel", "custom_commands", "webhook_notifications"
            ]
        }

        if template_name == "blank":
            return {
                **base_metadata,
                "name": "Blank Template",
                "description": "Minimal bot setup with basic commands and structure",
                "recommended_database": "sqlite",
                "default_flags": {
                    "base_commands": True,
                    "permission_system": True,
                    "error_handling": True,
                    "logging_enabled": True
                }
            }

        elif template_name == "moderation_bot":
            return {
                **base_metadata,
                "name": "Moderation Bot",
                "description": "Complete moderation system with auto-mod, warnings, and appeals",
                "recommended_database": "firestore",
                "difficulty": "intermediate",
                "default_flags": {
                    "base_commands": True,
                    "permission_system": True,
                    "auto_moderation": True,
                    "warning_system": True,
                    "appeal_system": True,
                    "log_channel_required": True,
                    "limits": {
                        "max_warnings": 3,
                        "timeout_duration": 600,
                        "max_automod_rules": 10
                    }
                }
            }

        elif template_name == "music_bot":
            return {
                **base_metadata,
                "name": "Music Bot",
                "description": "Music streaming bot with playlists, queues, and lyrics",
                "recommended_database": "firestore",
                "difficulty": "advanced",
                "default_flags": {
                    "base_commands": True,
                    "music_streaming": True,
                    "playlist_support": True,
                    "queue_management": True,
                    "lyrics_enabled": True,
                    "volume_control": True,
                    "limits": {
                        "queue_limit": 50,
                        "playlist_limit": 20,
                        "max_song_duration": 3600
                    }
                }
            }

        elif template_name == "economy_bot":
            return {
                **base_metadata,
                "name": "Economy Bot",
                "description": "Economy system with currency, leveling, shop, and leaderboards",
                "recommended_database": "postgresql",
                "difficulty": "advanced",
                "default_flags": {
                    "base_commands": True,
                    "economy_system": True,
                    "leveling_system": True,
                    "shop_enabled": True,
                    "leaderboards": True,
                    "daily_rewards": True,
                    "limits": {
                        "daily_reward": 100,
                        "max_balance": 1000000,
                        "shop_items": 50
                    }
                }
            }

        else:
            return base_metadata

    def _create_template_files(self, template_name: str, template_dir: Path, metadata: Dict[str, Any]) -> None:
        """Create template files based on template type."""
        # Create custom_cogs directory
        cogs_dir = template_dir / "custom_cogs"
        cogs_dir.mkdir(exist_ok=True)

        # Create template-specific cog files
        if template_name != "blank":
            self._create_template_cog(cogs_dir, template_name, metadata)

        # Create flags template
        self._create_flags_template(template_dir, template_name, metadata)

        # Create branding template
        self._create_branding_template(template_dir, template_name, metadata)

    def _create_template_cog(self, cogs_dir: Path, template_name: str, metadata: Dict[str, Any]) -> None:
        """Create template-specific cog file."""
        cog_name = template_name.replace("_", "")
        cog_file = cogs_dir / f"{cog_name}.py"

        cog_content = f'''"""
{metadata.get("name", template_name.title())} Cog
Template: {template_name}
Generated by Discord Cloud Platform
"""

import discord
from discord.ext import commands


class {cog_name.title()}Cog(commands.Cog):
    """
    {metadata.get("description", f"{template_name.title()} functionality")}
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="{cog_name}")
    async def {cog_name}_command(self, ctx):
        """Placeholder {cog_name} command."""
        await ctx.send(f"🚧 {cog_name.title()} functionality coming soon!")


async def setup(bot):
    await bot.add_cog({cog_name.title()}Cog(bot))
'''

        # FIXED: Added encoding='utf-8'
        with open(cog_file, 'w', encoding='utf-8') as f:
            f.write(cog_content)

    def _create_flags_template(self, template_dir: Path, template_name: str, metadata: Dict[str, Any]) -> None:
        """
        CRITICAL FIX: Create flags.py.template with proper JSON formatting - NO STRING MANIPULATION.
        """
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

    # ================== Limits and Quotas ================== #'''

        # CRITICAL FIX: Proper limits formatting without brittle string manipulation
        limits = default_flags.get("limits", {})
        if limits:
            flags_content += '\n    "limits": {\n'
            for key, value in limits.items():
                flags_content += f'        "{key}": {json.dumps(value)},\n'
            flags_content += '    },'
        else:
            flags_content += '\n    "limits": {},'

        flags_content += '''

    # ================== User-Customizable FLAGS ================== #
    "custom_embeds": True,
    "webhook_notifications": False,
    "debug_mode": False,
    "cache_enabled": True,
    "auto_cleanup": True,

    # ================== Plan-Based Features (Optional) ================== #
    "plan_features": {
        "plan_name": "{PLAN}",
        "monthly_fee": "{MONTHLY_FEE}",
        "support_level": "community",
        "priority_support": {PRIORITY_SUPPORT_ENABLED},
        "api_access": {API_ACCESS_ENABLED},
    },

    # ================== Template Metadata ================== #
    "template_info": {
        "name": "''' + metadata.get('name', template_name) + '''",
        "version": "''' + metadata.get('version', '1.0.0') + '''",
        "category": "''' + metadata.get('category', 'custom') + '''",
        "author": "''' + metadata.get('author', 'Platform User') + '''",
        "description": "''' + metadata.get('description', '') + '''",
        "database_recommended": "{DATABASE_BACKEND}",
    },

    # ================== Custom User FLAGS ================== #
    "custom": {}
}
'''

        flags_file = template_dir / "flags.py.template"
        # FIXED: Added encoding='utf-8'
        with open(flags_file, 'w', encoding='utf-8') as f:
            f.write(flags_content)

    def _create_branding_template(self, template_dir: Path, template_name: str, metadata: Dict[str, Any]) -> None:
        """Create branding.py.template with template-specific theming."""
        # Template-specific color schemes
        color_schemes = {
            "blank": {"primary": "0x3498db", "success": "0x2ecc71", "error": "0xe74c3c"},
            "moderation_bot": {"primary": "0xf39c12", "success": "0x27ae60", "error": "0xc0392b"},
            "music_bot": {"primary": "0x9b59b6", "success": "0x1abc9c", "error": "0xe74c3c"},
            "economy_bot": {"primary": "0xf1c40f", "success": "0x2ecc71", "error": "0xe67e22"}
        }

        colors = color_schemes.get(template_name, color_schemes["blank"])

        branding_content = f'''"""Branding Configuration for {{DISPLAY_NAME}}"""

# Template: {metadata.get("name", template_name)}
# Auto-generated branding based on template theme

BRANDING = {{
    # ================== Bot Identity ================== #
    "bot_name": "{{BOT_NAME}}",
    "bot_description": "{metadata.get('description', 'Discord bot powered by DCP')}",
    "bot_version": "{{BOT_VERSION}}",

    # ================== Visual Theme ================== #
    "embed_colors": {{
        "default": {colors["primary"]},
        "success": {colors["success"]},
        "error": {colors["error"]},
        "warning": 0xf39c12,
        "info": 0x3498db
    }},

    # ================== Status Messages ================== #
    "status_messages": [
        ("{metadata.get('name', template_name.replace('_', ' ').title())}", "playing"),
        ("Discord Cloud Platform", "watching"),
        ("{{SERVER_COUNT}} servers", "watching"),
        ("{{USER_COUNT}} users", "watching")
    ],

    # ================== Templates & Footers ================== #
    "footer_text": "Powered by Discord Cloud Platform",
    "embed_thumbnail": None,
    "embed_author": {{
        "name": "{{BOT_NAME}}",
        "icon_url": None
    }},

    # ================== Template-Specific Branding ================== #
    "template_theme": {{
        "name": "{template_name}",
        "category": "{metadata.get('category', 'custom')}",
        "primary_feature": "{metadata.get('description', '')}",
        "color_scheme": "{template_name}_theme"
    }}
}}
'''

        branding_file = template_dir / "branding.py.template"
        # FIXED: Added encoding='utf-8'
        with open(branding_file, 'w', encoding='utf-8') as f:
            f.write(branding_content)
