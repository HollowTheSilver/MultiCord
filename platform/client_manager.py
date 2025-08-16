"""
Client Management System
========================

Tools for managing clients, onboarding new clients, and maintaining
client configurations across the platform.
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone

from utils.loguruConfig import configure_logger


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
    """
    Manages client onboarding, configuration, and maintenance.
    """

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
            data = {
                "clients": [
                    {
                        "client_id": client.client_id,
                        "display_name": client.display_name,
                        "created_at": client.created_at.isoformat(),
                        "discord_token": client.discord_token,
                        "owner_id": client.owner_id,
                        "guild_ids": client.guild_ids,
                        "plan": client.plan,
                        "status": client.status,
                        "monthly_fee": client.monthly_fee,
                        "custom_features": client.custom_features,
                        "branding": client.branding,
                        "notes": client.notes
                    }
                    for client in self.clients.values()
                ]
            }

            with open(self.clients_db, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            self.logger.error(f"Failed to save clients database: {e}")

    def create_client(self,
                     client_id: str,
                     display_name: str,
                     discord_token: str,
                     owner_id: int,
                     guild_ids: List[int],
                     plan: str = "basic",
                     monthly_fee: float = 200.0,
                     branding: Dict[str, Any] = None) -> bool:
        """
        Create a new client with full configuration.

        Args:
            client_id: Unique identifier for the client
            display_name: Human-readable client name
            discord_token: Discord bot token
            owner_id: Discord user ID of the client owner
            guild_ids: List of Discord guild IDs the bot will serve
            plan: Service plan (basic, premium, enterprise)
            monthly_fee: Monthly fee in USD
            branding: Custom branding configuration

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

            # Configure client files
            self._configure_client_env(client_dir, client_id, discord_token, owner_id, guild_ids)
            self._configure_client_config(client_dir, display_name, plan)
            self._configure_client_branding(client_dir, branding or {})
            self._configure_client_features(client_dir, plan)

            # Create client info
            client_info = ClientInfo(
                client_id=client_id,
                display_name=display_name,
                created_at=datetime.now(timezone.utc),
                discord_token=discord_token,
                owner_id=owner_id,
                guild_ids=guild_ids,
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
        """Create template .env file."""
        env_content = """# Discord Bot Configuration for {CLIENT_NAME}
# Generated by Multi-Client Platform

# Required: Discord bot token
DISCORD_TOKEN={DISCORD_TOKEN}

# Bot identification
BOT_NAME="{BOT_NAME}"
BOT_VERSION="2.0.0"
BOT_DESCRIPTION="{BOT_DESCRIPTION}"

# Command settings
COMMAND_PREFIX="!"
CASE_INSENSITIVE_COMMANDS="true"

# Permission system
OWNER_IDS="{OWNER_IDS}"
ALLOWED_GUILDS="{ALLOWED_GUILDS}"

# Features
ENABLE_SLASH_COMMANDS="true"
ENABLE_MESSAGE_COMMANDS="true"
ENABLE_STATUS_CYCLING="true"
STATUS_CYCLE_INTERVAL="300"

# Client-specific status
STATUS_MESSAGES="{STATUS_MESSAGE}"

# Logging
LOG_LEVEL="INFO"
LOG_ROTATION="10 MB"
LOG_RETENTION="1 week"

# Performance
MAX_WORKERS="2"
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
                             owner_id: int, guild_ids: List[int]) -> None:
        """Configure client .env file."""
        template_path = client_dir / ".env.template"
        env_path = client_dir / ".env"

        if template_path.exists():
            with open(template_path, 'r') as f:
                content = f.read()

            # Replace placeholders
            replacements = {
                "{CLIENT_NAME}": client_id.replace("_", " ").title(),
                "{DISCORD_TOKEN}": discord_token,
                "{BOT_NAME}": f"{client_id.replace('_', ' ').title()} Bot",
                "{BOT_DESCRIPTION}": f"Professional Discord bot for {client_id.replace('_', ' ').title()}",
                "{OWNER_IDS}": str(owner_id),
                "{ALLOWED_GUILDS}": ",".join(map(str, guild_ids)) if guild_ids else "",
                "{STATUS_MESSAGE}": f"🤖 Serving {client_id.replace('_', ' ').title()}:custom"
            }

            for placeholder, value in replacements.items():
                content = content.replace(placeholder, value)

            with open(env_path, 'w') as f:
                f.write(content)

            template_path.unlink()  # Remove template file

    def _configure_client_config(self, client_dir: Path, display_name: str, plan: str) -> None:
        """Configure client config.py file."""
        template_path = client_dir / "config.py.template"
        config_path = client_dir / "config.py"

        if template_path.exists():
            with open(template_path, 'r') as f:
                content = f.read()

            replacements = {
                "{DISPLAY_NAME}": display_name,
                "{PLAN}": plan,
                "{CREATED_AT}": datetime.now(timezone.utc).isoformat()
            }

            for placeholder, value in replacements.items():
                content = content.replace(placeholder, value)

            with open(config_path, 'w') as f:
                f.write(content)

            template_path.unlink()

    def _configure_client_branding(self, client_dir: Path, branding: Dict[str, Any]) -> None:
        """Configure client branding.py file."""
        template_path = client_dir / "branding.py.template"
        branding_path = client_dir / "branding.py"

        if template_path.exists():
            with open(template_path, 'r') as f:
                content = f.read()

            replacements = {
                "{BOT_NAME}": branding.get("bot_name", "Professional Bot"),
                "{BOT_DESCRIPTION}": branding.get("bot_description", "A professional Discord bot"),
                "{STATUS_MESSAGE}": branding.get("status_message", "🤖 Online and ready!")
            }

            for placeholder, value in replacements.items():
                content = content.replace(placeholder, value)

            with open(branding_path, 'w') as f:
                f.write(content)

            template_path.unlink()

    def _configure_client_features(self, client_dir: Path, plan: str) -> None:
        """Configure client features.py file based on plan."""
        template_path = client_dir / "features.py.template"
        features_path = client_dir / "features.py"

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
                "MAX_CUSTOM_COMMANDS": "25",
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
                "ADVANCED_LOGGING_ENABLED": "True",
                "CUSTOM_INTEGRATIONS_ENABLED": "False",
                "API_ACCESS_ENABLED": "False",
                "PRIORITY_SUPPORT_ENABLED": "True",
                "MAX_CUSTOM_COMMANDS": "100",
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
                "MAX_CUSTOM_COMMANDS": "500",
                "MAX_AUTOMOD_RULES": "50",
                "MAX_TICKET_CATEGORIES": "20",
                "ANALYTICS_RETENTION_DAYS": "365"
            }
        }

        if template_path.exists():
            with open(template_path, 'r') as f:
                content = f.read()

            features = plan_features.get(plan, plan_features["basic"])

            for placeholder, value in features.items():
                content = content.replace(f"{{{placeholder}}}", value)

            with open(features_path, 'w') as f:
                f.write(content)

            template_path.unlink()

    def get_client_info(self, client_id: str) -> Optional[ClientInfo]:
        """Get information about a specific client."""
        return self.clients.get(client_id)

    def list_clients(self) -> List[ClientInfo]:
        """Get list of all clients."""
        return list(self.clients.values())

    def update_client(self, client_id: str, **updates) -> bool:
        """Update client information."""
        if client_id not in self.clients:
            return False

        client = self.clients[client_id]

        for key, value in updates.items():
            if hasattr(client, key):
                setattr(client, key, value)

        self._save_clients_db()
        return True

    def delete_client(self, client_id: str, confirm: bool = False) -> bool:
        """Delete a client and all associated data."""
        if not confirm:
            self.logger.warning("delete_client called without confirmation")
            return False

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

            self.logger.info(f"Deleted client: {client_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete client {client_id}: {e}")
            return False

    def get_billing_summary(self) -> Dict[str, Any]:
        """Get billing summary for all clients."""
        total_revenue = sum(client.monthly_fee for client in self.clients.values() if client.status == "active")

        return {
            "total_clients": len(self.clients),
            "active_clients": sum(1 for client in self.clients.values() if client.status == "active"),
            "total_monthly_revenue": total_revenue,
            "plans": {
                plan: sum(1 for client in self.clients.values() if client.plan == plan)
                for plan in ["basic", "premium", "enterprise"]
            }
        }
