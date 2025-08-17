"""
Client Manager System
===================================================
"""

import shutil
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

from core.utils.loguruConfig import configure_logger


@dataclass
class ClientInfo:
    """Information about a managed client."""
    client_id: str
    display_name: str
    plan: str = "basic"
    monthly_fee: float = 200.0
    created_at: str = ""
    last_updated: str = ""
    status: str = "active"
    discord_token: str = ""
    owner_ids: str = ""
    branding: Dict[str, Any] = None
    notes: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.last_updated:
            self.last_updated = self.created_at
        if self.branding is None:
            self.branding = {}


class ClientManager:
    """Enhanced client manager with corrected directory paths and UTF-8 support."""

    def __init__(self):
        """Initialize the client manager."""
        self.clients_dir = Path("clients")
        self.template_dir = self.clients_dir / "_template"
        # FIXED PATH: Use bot_platform instead of platform
        self.clients_db = Path("bot_platform/clients.json")

        # Setup logging - FIXED PATH: Use bot_platform instead of platform
        self.logger = configure_logger(
            log_dir="bot_platform/logs",
            level="INFO",
            format_extra=True,
            discord_compat=True
        )

        # Ensure database directory exists
        self.clients_db.parent.mkdir(parents=True, exist_ok=True)

        # Ensure template exists
        self._ensure_template_exists()

        # Load clients database
        self.clients = self._load_clients_db()

    def _load_clients_db(self) -> Dict[str, ClientInfo]:
        """Load clients from database file."""
        if not self.clients_db.exists():
            return {}

        try:
            with open(self.clients_db, 'r', encoding='utf-8') as f:
                data = json.load(f)

            clients = {}
            for client_id, client_data in data.items():
                clients[client_id] = ClientInfo(**client_data)

            self.logger.info(f"Loaded {len(clients)} clients from database")
            return clients

        except Exception as e:
            self.logger.error(f"Failed to load clients database: {e}")
            return {}

    def _save_clients_db(self) -> None:
        """Save clients to database file."""
        try:
            data = {}
            for client_id, client_info in self.clients.items():
                data[client_id] = asdict(client_info)

            with open(self.clients_db, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"Failed to save clients database: {e}")

    def create_client(self, client_id: str, **kwargs) -> bool:
        """Create a new client with comprehensive configuration."""
        try:
            # Validate client doesn't exist
            if client_id in self.clients:
                self.logger.error(f"Client {client_id} already exists")
                return False

            client_dir = self.clients_dir / client_id
            if client_dir.exists():
                self.logger.error(f"Client directory {client_dir} already exists")
                return False

            # Copy template to new client directory
            shutil.copytree(self.template_dir, client_dir)
            self.logger.info(f"Copied template to {client_dir}")

            # Create client info
            plan = kwargs.get('plan', 'basic')
            monthly_fee = {'basic': 200.0, 'premium': 350.0, 'enterprise': 500.0}.get(plan, 200.0)

            client_info = ClientInfo(
                client_id=client_id,
                display_name=kwargs.get('display_name', client_id.title()),
                plan=plan,
                monthly_fee=monthly_fee,
                discord_token=kwargs.get('discord_token', ''),
                owner_ids=kwargs.get('owner_ids', ''),
                branding=kwargs.get('branding', {}),
                notes=kwargs.get('notes', '')
            )

            # Configure client files with UTF-8 encoding
            self._configure_client_env(client_dir, client_info, **kwargs)
            self._configure_client_config(client_dir, client_info.display_name, plan)
            self._configure_client_branding(client_dir, client_info.branding, **kwargs)
            self._configure_client_features(client_dir, plan)

            # Save to database
            self.clients[client_id] = client_info
            self._save_clients_db()

            self.logger.info(f"Successfully created client {client_id} with plan {plan}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create client {client_id}: {e}")
            # Cleanup on failure
            if 'client_dir' in locals() and client_dir.exists():
                shutil.rmtree(client_dir, ignore_errors=True)
            return False

    def _ensure_template_exists(self) -> None:
        """Ensure client template directory exists."""
        if not self.template_dir.exists():
            self._create_default_template()

    def _create_default_template(self) -> None:
        """Create comprehensive default client template."""
        self.logger.info("Creating comprehensive client template")
        self.template_dir.mkdir(parents=True, exist_ok=True)

        # Create template files with UTF-8 encoding
        self._create_template_env()
        self._create_template_config()
        self._create_template_branding()
        self._create_template_features()

        # Create directories
        (self.template_dir / "custom_cogs").mkdir(exist_ok=True)
        (self.template_dir / "data").mkdir(exist_ok=True)
        (self.template_dir / "logs").mkdir(exist_ok=True)

    def _create_template_env(self) -> None:
        """Create comprehensive template .env file with UTF-8 encoding."""
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

# ========================================( Logging Configuration )======================================== #

# Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL="{LOG_LEVEL}"

# Directory for log files (client-specific path set automatically)
LOG_DIR="logs"

# Log file rotation settings
LOG_ROTATION="{LOG_ROTATION}"
LOG_RETENTION="{LOG_RETENTION}"
LOG_COMPRESSION="{LOG_COMPRESSION}"

# ========================================( Bot Behavior )======================================== #

# Status cycling
ENABLE_STATUS_CYCLING="true"
STATUS_CYCLE_INTERVAL="{STATUS_CYCLE_INTERVAL}"

# Custom status messages (format: "message1:type1,message2:type2")
# Types: playing, watching, listening, streaming, competing, custom
STATUS_MESSAGES="{STATUS_MESSAGE}:custom"

# Error handling
RESPOND_TO_UNKNOWN_COMMANDS="false"
DELETE_UNKNOWN_COMMANDS="false"

# Auto-moderation settings (based on plan)
AUTOMOD_ENABLED="{AUTOMOD_ENABLED}"
MAX_AUTOMOD_RULES="{MAX_AUTOMOD_RULES}"

# Custom commands (plan-based limits)
CUSTOM_COMMANDS_ENABLED="{CUSTOM_COMMANDS_ENABLED}"
MAX_CUSTOM_COMMANDS="{MAX_CUSTOM_COMMANDS}"

# Analytics (premium+ feature)
ANALYTICS_ENABLED="{ANALYTICS_ENABLED}"
ANALYTICS_RETENTION_DAYS="{ANALYTICS_RETENTION_DAYS}"

# Ticket system (premium+ feature)
TICKETS_ENABLED="{TICKETS_ENABLED}"
MAX_TICKET_CATEGORIES="{MAX_TICKET_CATEGORIES}"

# Forms and polls (enterprise feature)
FORMS_ENABLED="{FORMS_ENABLED}"
POLLS_ENABLED="{POLLS_ENABLED}"

# Advanced features (enterprise)
ADVANCED_LOGGING_ENABLED="{ADVANCED_LOGGING_ENABLED}"
CUSTOM_INTEGRATIONS_ENABLED="{CUSTOM_INTEGRATIONS_ENABLED}"
API_ACCESS_ENABLED="{API_ACCESS_ENABLED}"
PRIORITY_SUPPORT_ENABLED="{PRIORITY_SUPPORT_ENABLED}"

# ========================================( Commands & Features )======================================== #

# Features
ENABLE_SLASH_COMMANDS="true"
ENABLE_MESSAGE_COMMANDS="true"
ENABLE_AUTO_SYNC="false"

# Performance
MAX_WORKERS="4"
MAX_QUEUE_SIZE="1000"
CHUNK_SIZE="100"

# Development
DEBUG_MODE="false"
DEV_GUILD_ID=""

# Health monitoring
HEALTH_CHECK_INTERVAL="{HEALTH_CHECK_INTERVAL}"

# External service webhooks
ERROR_WEBHOOK_URL="{ERROR_WEBHOOK_URL}"
STATUS_WEBHOOK_URL="{STATUS_WEBHOOK_URL}"

# ========================================( Platform Integration )======================================== #

# Platform-managed variables (set automatically)
CLIENT_ID="{CLIENT_ID}"
CLIENT_PATH="clients/{CLIENT_ID}"
PLATFORM_VERSION="2.0.1"
"""

        # Write template with UTF-8 encoding
        with open(self.template_dir / ".env.template", 'w', encoding='utf-8') as f:
            f.write(env_content)

    def _create_template_config(self) -> None:
        """Create template config.py with UTF-8 encoding."""
        config_content = '''"""Client Configuration for {DISPLAY_NAME}"""

CLIENT_CONFIG = {
    "bot_config": {
        "COMMAND_PREFIX": "!",
        "ENABLE_STATUS_CYCLING": True,
        "STATUS_CYCLE_INTERVAL": 300,
        "ENABLE_SLASH_COMMANDS": True,
        "ENABLE_MESSAGE_COMMANDS": True,
    },
    "client_info": {
        "display_name": "{DISPLAY_NAME}",
        "plan": "{PLAN}",
        "created_at": "{CREATED_AT}",
    }
}
'''

        # Write template with UTF-8 encoding
        with open(self.template_dir / "config.py.template", 'w', encoding='utf-8') as f:
            f.write(config_content)

    def _create_template_branding(self) -> None:
        """Create template branding.py with UTF-8 encoding."""
        branding_content = '''"""Client Branding Configuration for {BOT_NAME}"""

BRANDING = {
    "bot_name": "{BOT_NAME}",
    "bot_description": "{BOT_DESCRIPTION}",
    "embed_colors": {
        "default": 0x3498db,
        "success": 0x2ecc71,
        "error": 0xe74c3c,
        "warning": 0xf39c12,
    },
    "status_messages": [("{STATUS_MESSAGE}", "custom")],
    "footer_text": "Powered by {BOT_NAME}",
}
'''

        # Write template with UTF-8 encoding
        with open(self.template_dir / "branding.py.template", 'w', encoding='utf-8') as f:
            f.write(branding_content)

    def _create_template_features(self) -> None:
        """Create template features.py with UTF-8 encoding."""
        features_content = '''"""Client Feature Configuration for {DISPLAY_NAME}"""

# Feature availability based on plan: {PLAN}
FEATURES = {
    # Core features (all plans)
    "base_commands": True,
    "permission_system": True,
    "moderation": True,
    
    # Plan-specific features
    "custom_commands": {CUSTOM_COMMANDS_ENABLED},
    "analytics": {ANALYTICS_ENABLED},
    "automod": {AUTOMOD_ENABLED},
    "tickets": {TICKETS_ENABLED},
    "forms": {FORMS_ENABLED},
    "polls": {POLLS_ENABLED},
    "advanced_logging": {ADVANCED_LOGGING_ENABLED},
    "custom_integrations": {CUSTOM_INTEGRATIONS_ENABLED},
    "api_access": {API_ACCESS_ENABLED},
    "priority_support": {PRIORITY_SUPPORT_ENABLED},
    
    # Limits
    "limits": {
        "max_custom_commands": {MAX_CUSTOM_COMMANDS},
        "max_automod_rules": {MAX_AUTOMOD_RULES},
        "max_ticket_categories": {MAX_TICKET_CATEGORIES},
        "analytics_retention_days": {ANALYTICS_RETENTION_DAYS}
    }
}
'''

        # Write template with UTF-8 encoding
        with open(self.template_dir / "features.py.template", 'w', encoding='utf-8') as f:
            f.write(features_content)

    def _configure_client_env(self, client_dir: Path, client_info: ClientInfo, **kwargs) -> None:
        """Configure client .env file with comprehensive settings and UTF-8 encoding."""
        template_file = client_dir / ".env.template"
        env_file = client_dir / ".env"

        if template_file.exists():
            # Read template with UTF-8 encoding
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Plan-based feature flags
            plan_config = self._get_plan_config(client_info.plan)

            # Substitute variables
            substitutions = {
                "CLIENT_NAME": client_info.display_name,
                "CLIENT_ID": client_info.client_id,
                "DISCORD_TOKEN": client_info.discord_token or "your_token_here",
                "BOT_NAME": kwargs.get("bot_name", f"{client_info.display_name} Bot"),
                "BOT_DESCRIPTION": kwargs.get("bot_description", f"Discord bot for {client_info.display_name}"),
                "OWNER_IDS": client_info.owner_ids,
                "ALLOWED_GUILDS": kwargs.get("allowed_guilds", ""),
                "STATUS_MESSAGE": kwargs.get("status_message", "Online and ready!"),

                # Logging settings
                "LOG_LEVEL": kwargs.get("log_level", "INFO"),
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

            # Add plan-specific configurations
            substitutions.update(plan_config)

            # Apply all substitutions
            for key, value in substitutions.items():
                content = content.replace(f"{{{key}}}", str(value))

            # Write the configured .env file with UTF-8 encoding
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(content)

            # Remove template
            template_file.unlink()

    def _get_plan_config(self, plan: str) -> Dict[str, str]:
        """Get plan-specific feature configuration."""
        plan_configs = {
            "basic": {
                "CUSTOM_COMMANDS_ENABLED": "True",
                "ANALYTICS_ENABLED": "False",
                "AUTOMOD_ENABLED": "False",
                "TICKETS_ENABLED": "False",
                "FORMS_ENABLED": "False",
                "POLLS_ENABLED": "False",
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
                "CUSTOM_COMMANDS_ENABLED": "True",
                "ANALYTICS_ENABLED": "True",
                "AUTOMOD_ENABLED": "True",
                "TICKETS_ENABLED": "True",
                "FORMS_ENABLED": "False",
                "POLLS_ENABLED": "False",
                "ADVANCED_LOGGING_ENABLED": "False",
                "CUSTOM_INTEGRATIONS_ENABLED": "False",
                "API_ACCESS_ENABLED": "False",
                "PRIORITY_SUPPORT_ENABLED": "False",
                "MAX_CUSTOM_COMMANDS": "50",
                "MAX_AUTOMOD_RULES": "5",
                "MAX_TICKET_CATEGORIES": "5",
                "ANALYTICS_RETENTION_DAYS": "30"
            },
            "enterprise": {
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

        return plan_configs.get(plan, plan_configs["basic"])

    def _configure_client_config(self, client_dir: Path, display_name: str, plan: str) -> None:
        """Configure client config.py file with UTF-8 encoding."""
        template_file = client_dir / "config.py.template"
        config_file = client_dir / "config.py"

        if template_file.exists():
            # Read template with UTF-8 encoding
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Substitute variables
            substitutions = {
                "DISPLAY_NAME": display_name,
                "PLAN": plan,
                "CREATED_AT": datetime.now(timezone.utc).isoformat()
            }

            for key, value in substitutions.items():
                content = content.replace(f"{{{key}}}", str(value))

            # Write config file with UTF-8 encoding
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(content)

            # Remove template
            template_file.unlink()

    def _configure_client_branding(self, client_dir: Path, branding: Dict[str, Any], **kwargs) -> None:
        """Configure client branding.py file with UTF-8 encoding."""
        template_file = client_dir / "branding.py.template"
        branding_file = client_dir / "branding.py"

        if template_file.exists():
            # Read template with UTF-8 encoding
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Substitute variables
            substitutions = {
                "BOT_NAME": branding.get("bot_name", kwargs.get("bot_name", "Custom Bot")),
                "BOT_DESCRIPTION": branding.get("bot_description", kwargs.get("bot_description", "A Discord bot")),
                "STATUS_MESSAGE": kwargs.get("status_message", "Ready to serve!")
            }

            for key, value in substitutions.items():
                content = content.replace(f"{{{key}}}", str(value))

            # Write branding file with UTF-8 encoding
            with open(branding_file, 'w', encoding='utf-8') as f:
                f.write(content)

            # Remove template
            template_file.unlink()

    def _configure_client_features(self, client_dir: Path, plan: str) -> None:
        """Configure client features.py file with UTF-8 encoding."""
        template_file = client_dir / "features.py.template"
        features_file = client_dir / "features.py"

        if template_file.exists():
            # Read template with UTF-8 encoding
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Get plan-specific features
            plan_config = self._get_plan_config(plan)

            # Substitute variables
            substitutions = {
                "DISPLAY_NAME": f"Client ({plan.title()} Plan)",
                "PLAN": plan,
            }

            # Add plan config
            substitutions.update(plan_config)

            for key, value in substitutions.items():
                content = content.replace(f"{{{key}}}", str(value))

            # Write features file with UTF-8 encoding
            with open(features_file, 'w', encoding='utf-8') as f:
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

            client_info.last_updated = datetime.now(timezone.utc).isoformat()
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

    def get_plan_summary(self) -> Dict[str, Any]:
        """Get summary of all plans and their features."""
        return {
            "basic": {
                "monthly_fee": 200.0,
                "features": ["Core Commands", "Moderation Tools", "Basic Permissions", "10 Custom Commands"],
                "description": "Essential Discord bot functionality for small servers"
            },
            "premium": {
                "monthly_fee": 350.0,
                "features": ["All Basic Features", "Analytics (30 days)", "Auto-Moderation (5 rules)",
                           "Ticket System (5 categories)", "50 Custom Commands"],
                "description": "Advanced features for growing communities"
            },
            "enterprise": {
                "monthly_fee": 500.0,
                "features": ["All Premium Features", "Analytics (365 days)", "Auto-Moderation (50 rules)",
                           "Advanced Ticket System (20 categories)", "Forms & Polls", "API Access",
                           "Priority Support", "200 Custom Commands"],
                "description": "Full-featured solution for large organizations"
            }
        }


if __name__ == "__main__":
    print("Use bot_platform.deployment_tools for client management")
