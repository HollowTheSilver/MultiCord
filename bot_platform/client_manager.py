"""
Client Management System
========================

Tools for managing clients, onboarding new clients, and maintaining
client configurations across the platform.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.utils.loguruConfig import configure_logger


@dataclass
class ClientInfo:
    """Information about a client."""
    client_id: str
    display_name: str
    created_at: datetime
    discord_token: str
    owner_id: int
    guild_ids: List[int]
    plan: str = "basic"
    status: str = "active"
    monthly_fee: float = 200.0
    custom_features: List[str] = None
    branding: Dict[str, Any] = None
    notes: str = ""

    def __post_init__(self):
        if self.custom_features is None:
            self.custom_features = []
        if self.branding is None:
            self.branding = {}


class ClientManager:
    """Manages client onboarding, configuration, and maintenance."""

    def __init__(self):
        """Initialize client manager."""
        self.clients_dir = Path("clients")
        self.template_dir = self.clients_dir / "_template"
        self.clients_db = Path("platform") / "clients.json"

        self.logger = configure_logger(
            log_dir="platform/logs",
            level="INFO",
            format_extra=True
        )

        # Ensure directories exist
        self.clients_dir.mkdir(exist_ok=True)
        self.clients_db.parent.mkdir(exist_ok=True)

        # Load existing clients
        self.clients = self._load_clients_db()

    def _load_clients_db(self) -> Dict[str, ClientInfo]:
        """Load clients database."""
        if not self.clients_db.exists():
            return {}

        try:
            with open(self.clients_db, 'r') as f:
                data = json.load(f)

            clients = {}
            for client_data in data.get("clients", []):
                # Convert datetime strings back to datetime objects
                if "created_at" in client_data:
                    client_data["created_at"] = datetime.fromisoformat(client_data["created_at"])

                client_info = ClientInfo(**client_data)
                clients[client_info.client_id] = client_info

            return clients

        except Exception as e:
            self.logger.error(f"Failed to load clients database: {e}")
            return {}

    def _save_clients_db(self) -> None:
        """Save clients database."""
        try:
            # Convert datetime objects to ISO format strings
            clients_data = []
            for client_info in self.clients.values():
                client_dict = {
                    "client_id": client_info.client_id,
                    "display_name": client_info.display_name,
                    "created_at": client_info.created_at.isoformat(),
                    "discord_token": client_info.discord_token,
                    "owner_id": client_info.owner_id,
                    "guild_ids": client_info.guild_ids,
                    "plan": client_info.plan,
                    "status": client_info.status,
                    "monthly_fee": client_info.monthly_fee,
                    "custom_features": client_info.custom_features,
                    "branding": client_info.branding,
                    "notes": client_info.notes
                }
                clients_data.append(client_dict)

            data = {"clients": clients_data}

            with open(self.clients_db, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            self.logger.error(f"Failed to save clients database: {e}")

    def create_client(
            self,
            client_id: str,
            display_name: str,
            discord_token: str,
            owner_id: int,
            guild_ids: List[int] = None,
            plan: str = "basic",
            monthly_fee: float = 200.0,
            branding: Dict[str, Any] = None,
            **kwargs
    ) -> bool:
        """
        Create a new client with comprehensive configuration support.

        Args:
            client_id: Unique identifier for the client
            display_name: Human-readable client name
            discord_token: Discord bot token
            owner_id: Discord user ID of the client owner
            guild_ids: List of Discord guild IDs the bot will serve
            plan: Service plan (basic, premium, enterprise)
            monthly_fee: Monthly fee in USD
            branding: Custom branding configuration
            **kwargs: Additional configuration options for comprehensive setup

        Returns:
            True if successful, False otherwise
        """
        if client_id in self.clients:
            self.logger.error(f"Client {client_id} already exists")
            return False

        try:
            # Create client directory
            client_dir = self.clients_dir / client_id
            if client_dir.exists():
                self.logger.error(f"Client directory already exists: {client_dir}")
                return False

            # Copy template
            if self.template_dir.exists():
                shutil.copytree(self.template_dir, client_dir)
                self.logger.info(f"Copied template to {client_dir}")
            else:
                self._create_default_template()
                shutil.copytree(self.template_dir, client_dir)

            # Configure client files with comprehensive options
            self._configure_client_env(
                client_dir, client_id, discord_token, owner_id,
                guild_ids or [], branding or {}, **kwargs
            )
            self._configure_client_config(client_dir, display_name, plan)
            self._configure_client_branding(client_dir, branding or {}, **kwargs)
            self._configure_client_features(client_dir, plan)

            # Create client info
            client_info = ClientInfo(
                client_id=client_id,
                display_name=display_name,
                created_at=datetime.now(timezone.utc),
                discord_token=discord_token,
                owner_id=owner_id,
                guild_ids=guild_ids or [],
                plan=plan,
                monthly_fee=monthly_fee,
                branding=branding or {}
            )

            self.clients[client_id] = client_info
            self._save_clients_db()

            self.logger.info(f"Successfully created client: {client_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create client {client_id}: {e}")
            # Cleanup on failure
            client_dir = self.clients_dir / client_id
            if client_dir.exists():
                shutil.rmtree(client_dir)
            return False

    def _create_default_template(self) -> None:
        """Create default template if it doesn't exist."""
        self.logger.info("Creating default client template")
        self.template_dir.mkdir(exist_ok=True)

        # Create template files
        self._create_template_env()
        self._create_template_config()
        self._create_template_branding()
        self._create_template_features()

        # Create directories
        (self.template_dir / "custom_cogs").mkdir(exist_ok=True)
        (self.template_dir / "data").mkdir(exist_ok=True)
        (self.template_dir / "logs").mkdir(exist_ok=True)

    def _create_template_env(self) -> None:
        """Create comprehensive template .env file with all configuration options."""
        env_content = """# Discord Bot Multi-Client Platform - Client Configuration
    # Generated for client: {CLIENT_NAME}
    # Platform Version: 2.0.1

    # ========================================( Discord Configuration )======================================== #

    # Required: Your Discord bot token for this client
    DISCORD_TOKEN={DISCORD_TOKEN}

    # Bot identification
    BOT_NAME="{BOT_NAME}"
    BOT_VERSION="2.0.1"
    BOT_DESCRIPTION="{BOT_DESCRIPTION}"

    # Command settings
    COMMAND_PREFIX="!"
    CASE_INSENSITIVE_COMMANDS="true"

    # ========================================( Discord Intents )======================================== #

    # Enable member intents (required for member-related events)
    ENABLE_MEMBER_INTENTS="true"

    # Enable message content intent (required for message content access)
    ENABLE_MESSAGE_CONTENT_INTENT="true"

    # Enable presence intent (optional, for member status/activity)
    ENABLE_PRESENCE_INTENT="false"

    # ========================================( Permission System )======================================== #

    # Bot owner user IDs (comma-separated) - highest permission level
    OWNER_IDS="{OWNER_IDS}"

    # Allowed guild IDs (comma-separated, leave empty for no restrictions)
    # If specified, bot will only respond in these guilds
    ALLOWED_GUILDS="{ALLOWED_GUILDS}"

    # Permission system is configured through Discord commands:
    # - Use "/permissions-setup" to auto-configure role mappings
    # - Use "/permissions-set-role @Role LEVEL" for manual role configuration
    # - Use "/permissions-set-command command LEVEL" to customize command requirements
    # - All settings are stored per-guild and database-backed

    # Available permission levels: EVERYONE, MEMBER, MODERATOR, LEAD_MOD, ADMIN, LEAD_ADMIN, OWNER
    # Enhanced hierarchy supports complex server structures with senior/lead roles

    # ========================================( Logging Configuration )======================================== #

    # Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_LEVEL="INFO"

    # Directory for log files (client-specific path set automatically)
    LOG_DIR="logs"

    # Log file rotation settings
    LOG_ROTATION="10 MB"
    LOG_RETENTION="1 week"
    LOG_COMPRESSION="zip"

    # ========================================( Bot Behavior )======================================== #

    # Status cycling
    ENABLE_STATUS_CYCLING="true"
    STATUS_CYCLE_INTERVAL="300"

    # Custom status messages (format: "message1:type1,message2:type2")
    # Types: playing, watching, listening, streaming, competing, custom
    # Client-specific status:
    STATUS_MESSAGES="{STATUS_MESSAGE}:custom"
    # Multiple status example (cycles automatically):
    # STATUS_MESSAGES="with Discord.py:playing,for new members:watching,to commands:listening,🤖 Online and ready!:custom"

    # Health checks
    ENABLE_HEALTH_CHECKS="true"
    HEALTH_CHECK_INTERVAL="300"

    # ========================================( Database Configuration )======================================== #

    # Database URL (client-specific path set automatically)
    # The platform automatically creates isolated databases per client
    DATABASE_URL="data/permissions.db"

    # Database connection settings
    DATABASE_POOL_SIZE="10"
    DATABASE_TIMEOUT="30"

    # ========================================( Cache Configuration )======================================== #

    # Redis URL for caching (optional)
    # Example: redis://localhost:6379/0
    REDIS_URL=""

    # Cache settings
    CACHE_TTL="3600"

    # ========================================( API Configuration )======================================== #

    # Rate limiting for external APIs
    API_RATE_LIMIT="100"
    API_TIMEOUT="30"

    # ========================================( Features )======================================== #

    # Enable slash commands
    ENABLE_SLASH_COMMANDS="true"

    # Enable traditional message commands
    ENABLE_MESSAGE_COMMANDS="true"

    # Auto-sync slash commands on startup (disable in production)
    ENABLE_AUTO_SYNC="false"

    # ========================================( Performance )======================================== #

    # Maximum worker threads for background tasks
    MAX_WORKERS="2"

    # Maximum queue size for background processing
    MAX_QUEUE_SIZE="1000"

    # Chunk size for bulk operations
    CHUNK_SIZE="100"

    # ========================================( Development )======================================== #

    # Enable debug mode (additional logging, error details)
    DEBUG_MODE="false"

    # Development guild ID for slash command testing
    DEV_GUILD_ID=""

    # ========================================( Client-Specific Features )======================================== #

    # Features controlled by client plan and branding
    # These are managed by the platform - see features.py for details

    # ========================================( External Services )======================================== #

    # Example third-party API keys (add as needed per client)
    # OPENAI_API_KEY=""
    # GITHUB_TOKEN=""
    # WEATHER_API_KEY=""

    # Webhook URLs for monitoring/alerts (client-specific)
    # ERROR_WEBHOOK_URL=""
    # STATUS_WEBHOOK_URL=""

    # ========================================( Optional Modules )======================================== #

    # Module enablement is controlled by client features configuration
    # See features.py for client-specific module settings

    # Legacy compatibility - these may be overridden by features.py
    # ENABLE_MODERATION="true"
    # ENABLE_MUSIC="false"
    # ENABLE_ECONOMY="false"
    # ENABLE_LEVELING="false"

    # Module-specific settings (client-customizable)
    # MODERATION_LOG_CHANNEL=""
    # MUSIC_DEFAULT_VOLUME="50"
    # ECONOMY_DAILY_AMOUNT="100"

    # ========================================( Platform Integration )======================================== #

    # Platform-managed variables (set automatically)
    CLIENT_ID="{CLIENT_NAME}"
    CLIENT_PATH="clients/{CLIENT_NAME}"
    PLATFORM_VERSION="2.0.1"
    """
        with open(self.template_dir / ".env.template", 'w') as f:
            f.write(env_content)

    def _create_template_config(self) -> None:
        """Create template config.py file."""
        config_content = '''"""
Client Configuration
===================

Client-specific configuration overrides and settings.
"""

CLIENT_CONFIG = {
    # Bot configuration overrides
    "bot_config": {
        "COMMAND_PREFIX": "!",
        "ENABLE_SLASH_COMMANDS": True,
        "ENABLE_MESSAGE_COMMANDS": True,
        "STATUS_CYCLE_INTERVAL": 300,
    },
    
    # Client metadata
    "client_info": {
        "display_name": "{DISPLAY_NAME}",
        "plan": "{PLAN}",
        "created_at": "{CREATED_AT}",
    },
    
    # Performance settings
    "performance": {
        "max_memory_mb": 512,
        "max_cpu_percent": 80,
    },
    
    # Feature flags
    "features": {
        "moderation": True,
        "music": False,
        "economy": False,
        "leveling": False,
        "custom_commands": True,
    }
}
'''
        with open(self.template_dir / "config.py.template", 'w') as f:
            f.write(config_content)

    def _create_template_branding(self) -> None:
        """Create template branding.py file."""
        branding_content = '''"""
Client Branding Configuration
============================

Custom branding, colors, and styling for this client.
"""

import discord

BRANDING = {
    # Bot branding
    "bot_name": "{BOT_NAME}",
    "bot_description": "{BOT_DESCRIPTION}",
    
    # Embed colors (Discord color integers)
    "embed_colors": {
        "default": 0x3498db,    # Blue
        "success": 0x2ecc71,   # Green
        "error": 0xe74c3c,     # Red
        "warning": 0xf39c12,   # Orange
        "info": 0x3498db,      # Blue
    },
    
    # Status messages
    "status_messages": [
        ("{STATUS_MESSAGE}", "custom")
    ],
    
    # Footer branding
    "footer_text": "Powered by {BOT_NAME}",
    "footer_icon": None,  # URL to footer icon
    
    # Custom emojis (if available)
    "custom_emojis": {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
        "loading": "⏳",
    },
    
    # Embed styling
    "embed_style": {
        "show_timestamps": True,
        "show_user_avatars": True,
        "show_footer_branding": True,
    }
}
'''
        with open(self.template_dir / "branding.py.template", 'w') as f:
            f.write(branding_content)

    def _create_template_features(self) -> None:
        """Create template features.py file."""
        features_content = '''"""
Client Feature Configuration
===========================

Feature flags and module enablement for this client.
"""

FEATURES = {
    # Core features (always enabled)
    "base_commands": True,
    "permission_system": True,
    "error_handling": True,
    
    # Optional features based on plan
    "moderation": {MODERATION_ENABLED},
    "music": {MUSIC_ENABLED},
    "economy": {ECONOMY_ENABLED},
    "leveling": {LEVELING_ENABLED},
    "custom_commands": {CUSTOM_COMMANDS_ENABLED},
    "analytics": {ANALYTICS_ENABLED},
    "automod": {AUTOMOD_ENABLED},
    "tickets": {TICKETS_ENABLED},
    "forms": {FORMS_ENABLED},
    "polls": {POLLS_ENABLED},
    
    # Advanced features (premium/enterprise only)
    "advanced_logging": {ADVANCED_LOGGING_ENABLED},
    "custom_integrations": {CUSTOM_INTEGRATIONS_ENABLED},
    "api_access": {API_ACCESS_ENABLED},
    "priority_support": {PRIORITY_SUPPORT_ENABLED},
    
    # Limits based on plan
    "limits": {
        "max_custom_commands": {MAX_CUSTOM_COMMANDS},
        "max_automod_rules": {MAX_AUTOMOD_RULES},
        "max_ticket_categories": {MAX_TICKET_CATEGORIES},
        "analytics_retention_days": {ANALYTICS_RETENTION_DAYS},
    }
}
'''
        with open(self.template_dir / "features.py.template", 'w') as f:
            f.write(features_content)

    def _configure_client_env(self, client_dir: Path, client_id: str, discord_token: str,
                              owner_id: int, guild_ids: List[int], branding: Dict[str, Any], **kwargs) -> None:
        """Configure client .env file with comprehensive variable substitution."""
        template_file = client_dir / ".env.template"
        env_file = client_dir / ".env"

        if template_file.exists():
            with open(template_file, 'r') as f:
                content = f.read()

            # Comprehensive substitutions for all template variables
            substitutions = {
                # Basic client info
                "CLIENT_NAME": client_id,
                "DISCORD_TOKEN": discord_token,
                "BOT_NAME": branding.get("bot_name", f"{client_id.title()} Bot"),
                "BOT_DESCRIPTION": branding.get("bot_description", f"Discord bot for {client_id}"),
                "OWNER_IDS": str(owner_id),
                "ALLOWED_GUILDS": ",".join(map(str, guild_ids)) if guild_ids else "",
                "STATUS_MESSAGE": kwargs.get("status_message", f"Serving {client_id}"),

                # Advanced configuration options
                "COMMAND_PREFIX": kwargs.get("command_prefix", "!"),
                "LOG_LEVEL": kwargs.get("log_level", "INFO"),
                "DEBUG_MODE": str(kwargs.get("debug_mode", False)).lower(),
                "DEV_GUILD_ID": str(kwargs.get("dev_guild_id", "")),

                # Performance settings
                "MAX_WORKERS": str(kwargs.get("max_workers", 2)),
                "MAX_QUEUE_SIZE": str(kwargs.get("max_queue_size", 1000)),
                "CHUNK_SIZE": str(kwargs.get("chunk_size", 100)),

                # Database settings
                "DATABASE_POOL_SIZE": str(kwargs.get("database_pool_size", 10)),
                "DATABASE_TIMEOUT": str(kwargs.get("database_timeout", 30)),

                # Cache settings
                "CACHE_TTL": str(kwargs.get("cache_ttl", 3600)),
                "REDIS_URL": kwargs.get("redis_url", ""),

                # API settings
                "API_RATE_LIMIT": str(kwargs.get("api_rate_limit", 100)),
                "API_TIMEOUT": str(kwargs.get("api_timeout", 30)),

                # Feature flags
                "ENABLE_SLASH_COMMANDS": str(kwargs.get("enable_slash_commands", True)).lower(),
                "ENABLE_MESSAGE_COMMANDS": str(kwargs.get("enable_message_commands", True)).lower(),
                "ENABLE_AUTO_SYNC": str(kwargs.get("enable_auto_sync", False)).lower(),
                "ENABLE_STATUS_CYCLING": str(kwargs.get("enable_status_cycling", True)).lower(),
                "ENABLE_HEALTH_CHECKS": str(kwargs.get("enable_health_checks", True)).lower(),

                # Intent settings
                "ENABLE_MEMBER_INTENTS": str(kwargs.get("enable_member_intents", True)).lower(),
                "ENABLE_MESSAGE_CONTENT_INTENT": str(kwargs.get("enable_message_content_intent", True)).lower(),
                "ENABLE_PRESENCE_INTENT": str(kwargs.get("enable_presence_intent", False)).lower(),

                # Logging settings
                "LOG_ROTATION": kwargs.get("log_rotation", "10 MB"),
                "LOG_RETENTION": kwargs.get("log_retention", "1 week"),
                "LOG_COMPRESSION": kwargs.get("log_compression", "zip"),

                # Timing settings
                "STATUS_CYCLE_INTERVAL": str(kwargs.get("status_cycle_interval", 300)),
                "HEALTH_CHECK_INTERVAL": str(kwargs.get("health_check_interval", 300)),

                # External service placeholders
                "ERROR_WEBHOOK_URL": kwargs.get("error_webhook_url", ""),
                "STATUS_WEBHOOK_URL": kwargs.get("status_webhook_url", ""),
            }

            # Apply all substitutions
            for key, value in substitutions.items():
                content = content.replace(f"{{{key}}}", str(value))

            # Write the configured .env file
            with open(env_file, 'w') as f:
                f.write(content)

            # Remove template
            template_file.unlink()

    def _configure_client_config(self, client_dir: Path, display_name: str, plan: str) -> None:
        """Configure client config.py file."""
        template_file = client_dir / "config.py.template"
        config_file = client_dir / "config.py"

        if template_file.exists():
            with open(template_file, 'r') as f:
                content = f.read()

            # Substitute variables
            substitutions = {
                "DISPLAY_NAME": display_name,
                "PLAN": plan,
                "CREATED_AT": datetime.now(timezone.utc).isoformat()
            }

            for key, value in substitutions.items():
                content = content.replace(f"{{{key}}}", str(value))

            with open(config_file, 'w') as f:
                f.write(content)

            # Remove template
            template_file.unlink()

    def _configure_client_branding(self, client_dir: Path, branding: Dict[str, Any], **kwargs) -> None:
        """Configure client branding.py file."""
        template_file = client_dir / "branding.py.template"
        branding_file = client_dir / "branding.py"

        if template_file.exists():
            with open(template_file, 'r') as f:
                content = f.read()

            # Substitute variables
            substitutions = {
                "BOT_NAME": branding.get("bot_name", kwargs.get("bot_name", "Custom Bot")),
                "BOT_DESCRIPTION": branding.get("bot_description", kwargs.get("bot_description", "A Discord bot")),
                "STATUS_MESSAGE": kwargs.get("status_message", "Ready to serve!")
            }

            for key, value in substitutions.items():
                content = content.replace(f"{{{key}}}", str(value))

            with open(branding_file, 'w') as f:
                f.write(content)

            # Remove template
            template_file.unlink()

    def _configure_client_features(self, client_dir: Path, plan: str) -> None:
        """Configure client features.py file."""
        template_file = client_dir / "features.py.template"
        features_file = client_dir / "features.py"

        if template_file.exists():
            with open(template_file, 'r') as f:
                content = f.read()

            # Define plan-based features
            plan_features = {
                "basic": {
                    "MODERATION_ENABLED": "True",
                    "MUSIC_ENABLED": "False",
                    "ECONOMY_ENABLED": "False",
                    "LEVELING_ENABLED": "False",
                    "CUSTOM_COMMANDS_ENABLED": "True",
                    "ANALYTICS_ENABLED": "False",
                    "AUTOMOD_ENABLED": "False",
                    "TICKETS_ENABLED": "False",
                    "FORMS_ENABLED": "False",
                    "POLLS_ENABLED": "True",
                    "ADVANCED_LOGGING_ENABLED": "False",
                    "CUSTOM_INTEGRATIONS_ENABLED": "False",
                    "API_ACCESS_ENABLED": "False",
                    "PRIORITY_SUPPORT_ENABLED": "False",
                    "MAX_CUSTOM_COMMANDS": "10",
                    "MAX_AUTOMOD_RULES": "0",
                    "MAX_TICKET_CATEGORIES": "0",
                    "ANALYTICS_RETENTION_DAYS": "0"
                },
                "premium": {
                    "MODERATION_ENABLED": "True",
                    "MUSIC_ENABLED": "True",
                    "ECONOMY_ENABLED": "True",
                    "LEVELING_ENABLED": "True",
                    "CUSTOM_COMMANDS_ENABLED": "True",
                    "ANALYTICS_ENABLED": "True",
                    "AUTOMOD_ENABLED": "True",
                    "TICKETS_ENABLED": "True",
                    "FORMS_ENABLED": "True",
                    "POLLS_ENABLED": "True",
                    "ADVANCED_LOGGING_ENABLED": "False",
                    "CUSTOM_INTEGRATIONS_ENABLED": "False",
                    "API_ACCESS_ENABLED": "False",
                    "PRIORITY_SUPPORT_ENABLED": "True",
                    "MAX_CUSTOM_COMMANDS": "50",
                    "MAX_AUTOMOD_RULES": "10",
                    "MAX_TICKET_CATEGORIES": "5",
                    "ANALYTICS_RETENTION_DAYS": "90"
                },
                "enterprise": {
                    "MODERATION_ENABLED": "True",
                    "MUSIC_ENABLED": "True",
                    "ECONOMY_ENABLED": "True",
                    "LEVELING_ENABLED": "True",
                    "CUSTOM_COMMANDS_ENABLED": "True",
                    "ANALYTICS_ENABLED": "True",
                    "AUTOMOD_ENABLED": "True",
                    "TICKETS_ENABLED": "True",
                    "FORMS_ENABLED": "True",
                    "POLLS_ENABLED": "True",
                    "ADVANCED_LOGGING_ENABLED": "True",
                    "CUSTOM_INTEGRATIONS_ENABLED": "True",
                    "API_ACCESS_ENABLED": "True",
                    "PRIORITY_SUPPORT_ENABLED": "True",
                    "MAX_CUSTOM_COMMANDS": "200",
                    "MAX_AUTOMOD_RULES": "50",
                    "MAX_TICKET_CATEGORIES": "20",
                    "ANALYTICS_RETENTION_DAYS": "365"
                }
            }

            features = plan_features.get(plan, plan_features["basic"])

            # Substitute variables
            for key, value in features.items():
                content = content.replace(f"{{{key}}}", value)

            with open(features_file, 'w') as f:
                f.write(content)

            # Remove template
            template_file.unlink()

    def get_client(self, client_id: str) -> Optional[ClientInfo]:
        """Get client information by ID."""
        return self.clients.get(client_id)

    def list_clients(self) -> Dict[str, ClientInfo]:
        """Get all clients."""
        return self.clients.copy()

    def update_client(self, client_id: str, **updates) -> bool:
        """Update client information."""
        if client_id not in self.clients:
            return False

        try:
            client_info = self.clients[client_id]

            # Update allowed fields
            allowed_updates = ['display_name', 'plan', 'monthly_fee', 'status', 'branding', 'notes']
            for key, value in updates.items():
                if key in allowed_updates:
                    setattr(client_info, key, value)

            self._save_clients_db()
            self.logger.info(f"Updated client {client_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update client {client_id}: {e}")
            return False

    def delete_client(self, client_id: str) -> bool:
        """Delete a client and its configuration."""
        if client_id not in self.clients:
            return False

        try:
            # Remove client directory
            client_dir = self.clients_dir / client_id
            if client_dir.exists():
                shutil.rmtree(client_dir)

            # Remove from database
            del self.clients[client_id]
            self._save_clients_db()

            self.logger.info(f"Deleted client {client_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete client {client_id}: {e}")
            return False


if __name__ == "__main__":
    print("Use platform.deployment_tools for client management")
