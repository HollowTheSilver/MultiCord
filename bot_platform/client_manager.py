"""
Client Manager - Multi-Client Management & FLAGS System
=======================================================

Manages client creation, configuration, and lifecycle with FLAGS system.
Handles template processing, database backend selection, and business model support.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from core.utils.loguruConfig import configure_logger


@dataclass
class ClientInfo:
    """Client information and configuration."""
    client_id: str
    display_name: str
    plan: str
    monthly_fee: float
    status: str
    discord_token: Optional[str]
    owner_ids: str
    branding: Dict[str, Any]
    notes: str
    created_at: str
    last_updated: str


class ClientManager:
    """Manages client creation, configuration, and lifecycle operations."""

    def __init__(self, clients_db_path: str = "bot_platform/clients_db.json"):
        """Initialize client manager."""
        self.clients_db_path = Path(clients_db_path)
        self.clients: Dict[str, ClientInfo] = {}
        self.template_dir = Path("clients/_template")

        self.logger = configure_logger(
            log_dir="bot_platform/logs",
            level="INFO",
            format_extra=True,
            discord_compat=True
        )

        # Ensure template directory exists
        self.template_dir.mkdir(parents=True, exist_ok=True)

        # Load existing clients
        self._load_clients_db()

        # Ensure templates exist
        self._ensure_templates_exist()

    def create_client(self, client_id: str, display_name: str, plan: str = "custom",
                     template_info: Optional[Dict] = None, flags: Optional[Dict] = None,
                     database_backend: str = "sqlite", **kwargs) -> bool:
        """
        Create a new client with FLAGS system.

        Args:
            client_id: Unique client identifier
            display_name: Human-readable client name
            plan: Business plan (basic/premium/enterprise/custom)
            template_info: Template metadata for template-based clients
            flags: Pre-configured FLAGS dictionary
            database_backend: Database backend selection (sqlite/firestore/postgresql)
            **kwargs: Additional configuration options
        """
        try:
            if client_id in self.clients:
                self.logger.error(f"Client {client_id} already exists")
                return False

            # Create client directory
            client_dir = Path(f"clients/{client_id}")
            client_dir.mkdir(parents=True, exist_ok=True)

            # Setup client templates
            if template_info:
                self._setup_template_based_client(client_dir, template_info)
            else:
                self._setup_default_client(client_dir)

            # Create client info
            client_info = ClientInfo(
                client_id=client_id,
                display_name=display_name,
                plan=plan,
                monthly_fee=self._get_plan_fee_amount(plan),
                status="created",
                discord_token=kwargs.get("discord_token"),
                owner_ids=kwargs.get("owner_ids", ""),
                branding=kwargs.get("branding", {}),
                notes=kwargs.get("notes", ""),
                created_at=datetime.now(timezone.utc).isoformat(),
                last_updated=datetime.now(timezone.utc).isoformat()
            )

            # Configure client files
            self._configure_client_flags(
                client_dir, display_name, plan, template_info,
                flags, database_backend, **kwargs
            )
            self._configure_client_env(client_dir, client_info, **kwargs)
            self._configure_client_branding(client_dir, client_info.branding, **kwargs)
            self._configure_client_config(client_dir, display_name, plan)

            # Create custom_cogs directory
            custom_cogs_dir = client_dir / "custom_cogs"
            custom_cogs_dir.mkdir(exist_ok=True)

            # Copy template-specific cogs if available
            if template_info:
                self._setup_template_cogs(custom_cogs_dir, template_info)

            # Register client
            self.clients[client_id] = client_info
            self._save_clients_db()

            self.logger.info(f"Created client {client_id} using FLAGS system")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create client {client_id}: {e}")
            # Cleanup on failure
            client_dir = Path(f"clients/{client_id}")
            if client_dir.exists():
                shutil.rmtree(client_dir, ignore_errors=True)
            return False

    def _setup_template_based_client(self, client_dir: Path, template_info: Dict) -> None:
        """Set up client directory using template system."""
        template_path = template_info.get('path')
        if template_path and Path(template_path).exists():
            # Copy template files to client directory
            for template_file in Path(template_path).glob("*.template"):
                target_file = client_dir / template_file.name
                shutil.copy2(template_file, target_file)

        # Ensure flags.py.template exists
        flags_template = client_dir / "flags.py.template"
        if not flags_template.exists():
            self._create_default_flags_template(flags_template)

    def _setup_default_client(self, client_dir: Path) -> None:
        """Set up client directory using default template system."""
        if self.template_dir.exists():
            for template_file in self.template_dir.glob("*.template"):
                target_file = client_dir / template_file.name
                shutil.copy2(template_file, target_file)

    def _configure_client_flags(self, client_dir: Path, display_name: str, plan: str,
                               template_info: Optional[Dict], flags: Optional[Dict],
                               database_backend: str, **kwargs) -> None:
        """Configure client flags.py file with UTF-8 encoding."""
        template_file = client_dir / "flags.py.template"
        flags_file = client_dir / "flags.py"

        if not template_file.exists():
            self._create_default_flags_template(template_file)

        # Read template with UTF-8 encoding
        with open(template_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Prepare substitutions
        substitutions = self._prepare_flags_substitutions(
            display_name, plan, template_info, flags, database_backend, **kwargs
        )

        # Apply substitutions
        for key, value in substitutions.items():
            content = content.replace(f"{{{key}}}", str(value))

        # Write flags file with UTF-8 encoding
        with open(flags_file, 'w', encoding='utf-8') as f:
            f.write(content)

        # Remove template
        template_file.unlink()

    def _prepare_flags_substitutions(self, display_name: str, plan: str,
                                   template_info: Optional[Dict], flags: Optional[Dict],
                                   database_backend: str, **kwargs) -> Dict[str, str]:
        """Prepare substitution variables for FLAGS template."""

        # Get plan configuration
        plan_config = self._get_plan_config(plan)

        # Template information
        template_name = template_info.get('name', 'Custom Template') if template_info else 'Custom Template'
        template_version = template_info.get('metadata', {}).get('version', '1.0.0') if template_info else '1.0.0'
        template_category = template_info.get('metadata', {}).get('category', 'custom') if template_info else 'custom'
        template_author = template_info.get('metadata', {}).get('author', 'User') if template_info else 'User'
        template_description = template_info.get('metadata', {}).get('description', 'Custom client') if template_info else 'Custom client'

        # Base substitutions
        substitutions = {
            "DISPLAY_NAME": display_name,
            "PLAN": plan,
            "DATABASE_BACKEND": database_backend,
            "TEMPLATE_NAME": template_name,
            "TEMPLATE_VERSION": template_version,
            "TEMPLATE_CATEGORY": template_category,
            "TEMPLATE_AUTHOR": template_author,
            "TEMPLATE_DESCRIPTION": template_description,
            "TEMPLATE_UPDATED": datetime.now(timezone.utc).isoformat(),
            "CREATED_AT": datetime.now(timezone.utc).isoformat(),
            "PLATFORM_VERSION": "2.0.1",
            "PLAN_BASED": "True" if plan != "custom" else "False",
            "MONTHLY_FEE": self._get_plan_fee(plan),
        }

        # Add plan-based configuration
        substitutions.update(plan_config)

        return substitutions

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

    def _setup_template_cogs(self, custom_cogs_dir: Path, template_info: Dict) -> None:
        """Set up template-specific cogs."""
        template_path = template_info.get('path')
        if not template_path:
            return

        template_cogs_dir = Path(template_path) / "custom_cogs"
        if template_cogs_dir.exists():
            for cog_file in template_cogs_dir.glob("*.py"):
                if not cog_file.name.startswith("_"):
                    target_file = custom_cogs_dir / cog_file.name
                    shutil.copy2(cog_file, target_file)

    def _create_default_flags_template(self, template_file: Path) -> None:
        """Create default flags.py.template if none exists."""
        flags_content = '''"""Client FLAGS Configuration for {DISPLAY_NAME}"""

# FLAGS system - General-purpose feature configuration
FLAGS = {
    # Core platform flags
    "base_commands": True,
    "permission_system": True,
    "error_handling": True,
    "logging_enabled": True,
    
    # Template-populated flags
    "moderation_enabled": {MODERATION_ENABLED},
    "custom_commands_enabled": {CUSTOM_COMMANDS_ENABLED},
    "analytics_enabled": {ANALYTICS_ENABLED},
    "automod_enabled": {AUTOMOD_ENABLED},
    
    # Database configuration
    "database": {
        "backend": "{DATABASE_BACKEND}",
        "config": {}
    },
    
    # Limits
    "limits": {
        "max_custom_commands": {MAX_CUSTOM_COMMANDS},
        "max_automod_rules": {MAX_AUTOMOD_RULES},
        "analytics_retention_days": {ANALYTICS_RETENTION_DAYS}
    },
    
    # User customizable
    "custom_embeds": True,
    "debug_mode": False,
    
    # Custom user flags
    "custom": {}
}
'''

        with open(template_file, 'w', encoding='utf-8') as f:
            f.write(flags_content)

    def _get_plan_config(self, plan: str) -> Dict[str, str]:
        """Get plan-specific feature configuration for FLAGS system."""
        plan_configs = {
            "basic": {
                "MODERATION_ENABLED": "True",
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
                "MODERATION_ENABLED": "True",
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
                "MODERATION_ENABLED": "True",
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
            },
            "custom": {
                # Template-based clients with sensible defaults
                "MODERATION_ENABLED": "False",
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
                "MAX_CUSTOM_COMMANDS": "25",
                "MAX_AUTOMOD_RULES": "0",
                "MAX_TICKET_CATEGORIES": "0",
                "ANALYTICS_RETENTION_DAYS": "0"
            }
        }

        return plan_configs.get(plan, plan_configs["custom"])

    def _get_plan_fee(self, plan: str) -> str:
        """Get monthly fee for plan as string."""
        fees = {
            "basic": "$200",
            "premium": "$350",
            "enterprise": "$500",
            "custom": "$0"
        }
        return fees.get(plan, "$0")

    def _get_plan_fee_amount(self, plan: str) -> float:
        """Get monthly fee for plan as float."""
        fees = {
            "basic": 200.0,
            "premium": 350.0,
            "enterprise": 500.0,
            "custom": 0.0
        }
        return fees.get(plan, 0.0)

    def _ensure_templates_exist(self) -> None:
        """Ensure all necessary template files exist."""
        # Create template directory if it doesn't exist
        self.template_dir.mkdir(parents=True, exist_ok=True)

        # Ensure flags.py.template exists
        flags_template = self.template_dir / "flags.py.template"
        if not flags_template.exists():
            self._create_template_flags()

        # Ensure other templates exist
        self._create_template_env()
        self._create_template_config()
        self._create_template_branding()

    def _create_template_flags(self) -> None:
        """Create template flags.py with UTF-8 encoding."""
        flags_content = '''"""Client FLAGS Configuration for {DISPLAY_NAME}"""

# FLAGS system - General-purpose feature configuration
# Template: {TEMPLATE_NAME} | Plan: {PLAN}
FLAGS = {
    # ================== Core Platform FLAGS ================== #
    "base_commands": True,
    "permission_system": True,
    "error_handling": True,
    "logging_enabled": True,
    
    # ================== Template-Populated FLAGS ================== #
    "moderation_enabled": {MODERATION_ENABLED},
    "custom_commands_enabled": {CUSTOM_COMMANDS_ENABLED},
    "analytics_enabled": {ANALYTICS_ENABLED},
    "automod_enabled": {AUTOMOD_ENABLED},
    "tickets_enabled": {TICKETS_ENABLED},
    "forms_enabled": {FORMS_ENABLED},
    "polls_enabled": {POLLS_ENABLED},
    "advanced_logging_enabled": {ADVANCED_LOGGING_ENABLED},
    "integrations_enabled": {CUSTOM_INTEGRATIONS_ENABLED},
    "api_access_enabled": {API_ACCESS_ENABLED},
    "priority_support_enabled": {PRIORITY_SUPPORT_ENABLED},
    
    # ================== Database Configuration ================== #
    "database": {
        "backend": "{DATABASE_BACKEND}",
        "config": {}
    },
    
    # ================== Limits and Quotas ================== #
    "limits": {
        "max_custom_commands": {MAX_CUSTOM_COMMANDS},
        "max_automod_rules": {MAX_AUTOMOD_RULES},
        "max_ticket_categories": {MAX_TICKET_CATEGORIES},
        "analytics_retention_days": {ANALYTICS_RETENTION_DAYS},
        "max_concurrent_operations": 50,
        "rate_limit_per_user": 30,
    },
    
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
        "name": "{TEMPLATE_NAME}",
        "version": "{TEMPLATE_VERSION}",
        "category": "{TEMPLATE_CATEGORY}",
        "database_recommended": "{DATABASE_BACKEND}",
    },
    
    # ================== Custom User FLAGS ================== #
    "custom": {}
}
'''

        flags_template_file = self.template_dir / "flags.py.template"
        with open(flags_template_file, 'w', encoding='utf-8') as f:
            f.write(flags_content)

    def _create_template_env(self) -> None:
        """Create template .env file if it doesn't exist."""
        env_template = self.template_dir / ".env.template"
        if env_template.exists():
            return

        env_content = '''# Discord Bot Multi-Client Platform - Client Configuration
# Generated for client: {CLIENT_NAME}
# Platform Version: 2.0.1

# ========================================( Discord Configuration )======================================== #

# Required: Your Discord bot token for this client
DISCORD_TOKEN={DISCORD_TOKEN}

# Bot identification
BOT_NAME="{BOT_NAME}"
BOT_VERSION="2.0.1"
BOT_DESCRIPTION=""

# Command settings
COMMAND_PREFIX="!"
CASE_INSENSITIVE_COMMANDS="true"

# ========================================( Permission System )======================================== #

# Bot owner user IDs (comma-separated) - highest permission level
OWNER_IDS="{OWNER_IDS}"

# Allowed guild IDs (comma-separated, leave empty for no restrictions)
ALLOWED_GUILDS=""

# ========================================( Plan-Based Features )======================================== #

# Auto-moderation settings (based on plan)
AUTOMOD_ENABLED="{AUTOMOD_ENABLED}"
MAX_AUTOMOD_RULES="{MAX_AUTOMOD_RULES}"

# Custom commands (plan-based limits)
CUSTOM_COMMANDS_ENABLED="{CUSTOM_COMMANDS_ENABLED}"
MAX_CUSTOM_COMMANDS="{MAX_CUSTOM_COMMANDS}"

# Analytics (premium+ feature)
ANALYTICS_ENABLED="{ANALYTICS_ENABLED}"
ANALYTICS_RETENTION_DAYS="{ANALYTICS_RETENTION_DAYS}"
'''

        with open(env_template, 'w', encoding='utf-8') as f:
            f.write(env_content)

    def _create_template_config(self) -> None:
        """Create template config.py with UTF-8 encoding."""
        config_template = self.template_dir / "config.py.template"
        if config_template.exists():
            return

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

        with open(config_template, 'w', encoding='utf-8') as f:
            f.write(config_content)

    def _create_template_branding(self) -> None:
        """Create template branding.py with UTF-8 encoding."""
        branding_template = self.template_dir / "branding.py.template"
        if branding_template.exists():
            return

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

        with open(branding_template, 'w', encoding='utf-8') as f:
            f.write(branding_content)

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
            # Remove from memory
            del self.clients[client_id]

            # Remove client directory
            client_dir = Path(f"clients/{client_id}")
            if client_dir.exists():
                shutil.rmtree(client_dir)

            # Save updated database
            self._save_clients_db()

            self.logger.info(f"Deleted client {client_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete client {client_id}: {e}")
            return False

    def _load_clients_db(self) -> None:
        """Load clients database from file."""
        if not self.clients_db_path.exists():
            return

        try:
            with open(self.clients_db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for client_id, client_data in data.items():
                self.clients[client_id] = ClientInfo(**client_data)

            self.logger.info(f"Loaded {len(self.clients)} clients from database")

        except Exception as e:
            self.logger.error(f"Failed to load clients database: {e}")

    def _save_clients_db(self) -> None:
        """Save clients database to file."""
        try:
            # Ensure directory exists
            self.clients_db_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to serializable format
            data = {client_id: asdict(client_info) for client_id, client_info in self.clients.items()}

            with open(self.clients_db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"Failed to save clients database: {e}")
