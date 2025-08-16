#!/usr/bin/env python3
"""
Migration Script - Discord Bot Template to Multi-Client Platform
================================================================

Migrates an existing Discord bot template to the multi-client platform structure
with comprehensive configuration templates.
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Any


class TemplateMigrator:
    """Handles migration from single bot to multi-client platform."""

    def __init__(self, source_dir: str = ".", target_dir: str = "."):
        self.source_dir = Path(source_dir).resolve()
        self.target_dir = Path(target_dir).resolve()

        print(f"📁 Source: {self.source_dir}")
        print(f"📁 Target: {self.target_dir}")

    def migrate(self) -> bool:
        """Perform full migration to multi-client platform."""
        try:
            print("\n🚀 Starting Migration to Multi-Client Platform")
            print("=" * 55)

            # Core migration steps
            self._create_platform_structure()
            self._create_platform_files()
            self._create_client_template()
            self._create_default_client()
            self._create_deployment_scripts()
            self._update_requirements()
            self._create_documentation()

            print("\n✅ Migration completed successfully!")
            self._print_next_steps()
            return True

        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            return False

    def _create_platform_structure(self) -> None:
        """Create the platform directory structure."""
        print("📁 Creating platform structure...")

        directories = [
            "platform",
            "clients",
            "clients/_template",
            "clients/_template/custom_cogs",
            "clients/_template/data",
            "clients/_template/logs",
            "clients/default",
            "clients/default/custom_cogs",
            "clients/default/data",
            "clients/default/logs"
        ]

        for directory in directories:
            dir_path = self.target_dir / directory
            dir_path.mkdir(parents=True, exist_ok=True)

        print(f"   Created {len(directories)} directories")

    def _create_platform_files(self) -> None:
        """Create platform management files."""
        print("🔧 Creating platform files...")

        # Create __init__.py files
        init_content = '"""Multi-Client Discord Bot Platform"""\n'

        platform_files = {
            "platform/__init__.py": init_content,
            "clients/__init__.py": init_content,
            "clients/_template/__init__.py": "",
            "clients/default/__init__.py": ""
        }

        for file_path, content in platform_files.items():
            full_path = self.target_dir / file_path
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)

        print(f"   Created {len(platform_files)} platform structure files")
        print("   📝 Note: Copy platform code from artifacts to complete setup")

    def _create_client_template(self) -> None:
        """Create client template files with comprehensive configuration."""
        print("📋 Creating comprehensive client template...")

        template_dir = self.target_dir / "clients" / "_template"

        # Create comprehensive .env template
        env_template = """# Discord Bot Multi-Client Platform - Client Configuration
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

        with open(template_dir / ".env.template", 'w', encoding='utf-8') as f:
            f.write(env_template)

        # Create comprehensive config template
        config_template = '''"""
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
        "CASE_INSENSITIVE_COMMANDS": True,
        "ENABLE_STATUS_CYCLING": True,
        "ENABLE_HEALTH_CHECKS": True,
        "HEALTH_CHECK_INTERVAL": 300,
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
        "max_workers": 2,
        "max_queue_size": 1000,
        "chunk_size": 100,
    },

    # Database settings
    "database": {
        "pool_size": 10,
        "timeout": 30,
        "cache_ttl": 3600,
    },

    # Feature flags based on plan
    "features": {
        "moderation": True,
        "music": False,
        "economy": False,
        "leveling": False,
        "custom_commands": True,
        "analytics": False,
        "automod": False,
        "tickets": False,
        "forms": False,
        "polls": False,
        "advanced_logging": False,
        "custom_integrations": False,
        "api_access": False,
        "priority_support": False,
    }
}
'''

        with open(template_dir / "config.py.template", 'w', encoding='utf-8') as f:
            f.write(config_template)

        # Create comprehensive branding template
        branding_template = '''"""
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

        with open(template_dir / "branding.py.template", 'w', encoding='utf-8') as f:
            f.write(branding_template)

        # Create comprehensive features template
        features_template = '''"""
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

        with open(template_dir / "features.py.template", 'w', encoding='utf-8') as f:
            f.write(features_template)

        print("   Created comprehensive client template files")

    def _create_default_client(self) -> None:
        """Create default client from existing configuration."""
        print("🤖 Creating default client with comprehensive configuration...")

        # Try to read existing .env for default values
        env_path = self.source_dir / ".env"
        env_values = {}

        if env_path.exists():
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            env_values[key] = value.strip('"').strip("'")
            except Exception as e:
                print(f"   Warning: Could not read existing .env: {e}")

        # Create default client directory structure already created in _create_platform_structure

        # Create comprehensive default .env using original values where available
        default_env = f"""# Discord Bot Multi-Client Platform - Default Client Configuration
# Generated for client: default
# Platform Version: 2.0.1

# ========================================( Discord Configuration )======================================== #

# Required: Your Discord bot token for this client
DISCORD_TOKEN={env_values.get('DISCORD_TOKEN', 'your_token_here')}

# Bot identification  
BOT_NAME="{env_values.get('BOT_NAME', 'Professional Bot')}"
BOT_VERSION="2.0.1"
BOT_DESCRIPTION="{env_values.get('BOT_DESCRIPTION', 'Professional Discord bot - Default Client')}"

# Command settings
COMMAND_PREFIX="{env_values.get('COMMAND_PREFIX', '!')}"
CASE_INSENSITIVE_COMMANDS="{env_values.get('CASE_INSENSITIVE_COMMANDS', 'true')}"

# ========================================( Discord Intents )======================================== #

# Enable member intents (required for member-related events)
ENABLE_MEMBER_INTENTS="{env_values.get('ENABLE_MEMBER_INTENTS', 'true')}"

# Enable message content intent (required for message content access)
ENABLE_MESSAGE_CONTENT_INTENT="{env_values.get('ENABLE_MESSAGE_CONTENT_INTENT', 'true')}"

# Enable presence intent (optional, for member status/activity)
ENABLE_PRESENCE_INTENT="{env_values.get('ENABLE_PRESENCE_INTENT', 'false')}"

# ========================================( Permission System )======================================== #

# Bot owner user IDs (comma-separated) - highest permission level
OWNER_IDS="{env_values.get('OWNER_IDS', 'your_user_id')}"

# Allowed guild IDs (comma-separated, leave empty for no restrictions)
ALLOWED_GUILDS="{env_values.get('ALLOWED_GUILDS', '')}"

# ========================================( Logging Configuration )======================================== #

# Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL="{env_values.get('LOG_LEVEL', 'INFO')}"

# Directory for log files (client-specific path set automatically)
LOG_DIR="{env_values.get('LOG_DIR', 'logs')}"

# Log file rotation settings
LOG_ROTATION="{env_values.get('LOG_ROTATION', '10 MB')}"
LOG_RETENTION="{env_values.get('LOG_RETENTION', '1 week')}"
LOG_COMPRESSION="{env_values.get('LOG_COMPRESSION', 'zip')}"

# ========================================( Bot Behavior )======================================== #

# Status cycling
ENABLE_STATUS_CYCLING="{env_values.get('ENABLE_STATUS_CYCLING', 'true')}"
STATUS_CYCLE_INTERVAL="{env_values.get('STATUS_CYCLE_INTERVAL', '300')}"

# Custom status messages - preserve original or use default
STATUS_MESSAGES="{env_values.get('STATUS_MESSAGES', 'Professional Bot Online:custom')}"

# Health checks
ENABLE_HEALTH_CHECKS="{env_values.get('ENABLE_HEALTH_CHECKS', 'true')}"
HEALTH_CHECK_INTERVAL="{env_values.get('HEALTH_CHECK_INTERVAL', '300')}"

# ========================================( Database Configuration )======================================== #

# Database URL (client-specific path set automatically)
DATABASE_URL="{env_values.get('DATABASE_URL', 'data/permissions.db')}"

# Database connection settings
DATABASE_POOL_SIZE="{env_values.get('DATABASE_POOL_SIZE', '10')}"
DATABASE_TIMEOUT="{env_values.get('DATABASE_TIMEOUT', '30')}"

# ========================================( Cache Configuration )======================================== #

# Redis URL for caching (optional)
REDIS_URL="{env_values.get('REDIS_URL', '')}"

# Cache settings
CACHE_TTL="{env_values.get('CACHE_TTL', '3600')}"

# ========================================( API Configuration )======================================== #

# Rate limiting for external APIs
API_RATE_LIMIT="{env_values.get('API_RATE_LIMIT', '100')}"
API_TIMEOUT="{env_values.get('API_TIMEOUT', '30')}"

# ========================================( Features )======================================== #

# Enable slash commands
ENABLE_SLASH_COMMANDS="{env_values.get('ENABLE_SLASH_COMMANDS', 'true')}"

# Enable traditional message commands
ENABLE_MESSAGE_COMMANDS="{env_values.get('ENABLE_MESSAGE_COMMANDS', 'true')}"

# Auto-sync slash commands on startup (disable in production)
ENABLE_AUTO_SYNC="{env_values.get('ENABLE_AUTO_SYNC', 'false')}"

# ========================================( Performance )======================================== #

# Maximum worker threads for background tasks
MAX_WORKERS="{env_values.get('MAX_WORKERS', '4')}"

# Maximum queue size for background processing  
MAX_QUEUE_SIZE="{env_values.get('MAX_QUEUE_SIZE', '1000')}"

# Chunk size for bulk operations
CHUNK_SIZE="{env_values.get('CHUNK_SIZE', '100')}"

# ========================================( Development )======================================== #

# Enable debug mode (additional logging, error details)
DEBUG_MODE="{env_values.get('DEBUG_MODE', 'false')}"

# Development guild ID for slash command testing
DEV_GUILD_ID="{env_values.get('DEV_GUILD_ID', '')}"

# ========================================( Platform Integration )======================================== #

# Platform-managed variables (set automatically)
CLIENT_ID="default"
CLIENT_PATH="clients/default"
PLATFORM_VERSION="2.0.1"
"""

        default_client_dir = self.target_dir / "clients" / "default"
        with open(default_client_dir / ".env", 'w', encoding='utf-8') as f:
            f.write(default_env)

        # Create default config.py
        default_config = '''"""Default Client Configuration"""
CLIENT_CONFIG = {
    "bot_config": {
        "COMMAND_PREFIX": "!",
        "ENABLE_SLASH_COMMANDS": True,
        "ENABLE_MESSAGE_COMMANDS": True,
        "STATUS_CYCLE_INTERVAL": 300,
    },
    "client_info": {
        "display_name": "Default Client",
        "plan": "basic",
        "created_at": "2025-01-01T00:00:00Z",
    }
}
'''

        with open(default_client_dir / "config.py", 'w', encoding='utf-8') as f:
            f.write(default_config)

        # Create default branding.py
        default_branding = '''"""Default Client Branding Configuration"""
BRANDING = {
    "bot_name": "Professional Bot",
    "bot_description": "Professional Discord bot - Default Client",
    "embed_colors": {
        "default": 0x3498db,
        "success": 0x2ecc71,
        "error": 0xe74c3c,
        "warning": 0xf39c12,
    },
    "status_messages": [("Professional Bot Online", "custom")],
    "footer_text": "Powered by Professional Bot",
}
'''

        with open(default_client_dir / "branding.py", 'w', encoding='utf-8') as f:
            f.write(default_branding)

        # Create default features.py
        default_features = '''"""Default Client Feature Configuration"""
FEATURES = {
    "base_commands": True,
    "permission_system": True,
    "moderation": True,
    "custom_commands": True,
    "limits": {
        "max_custom_commands": 50,
    }
}
'''

        with open(default_client_dir / "features.py", 'w', encoding='utf-8') as f:
            f.write(default_features)

        print("   Created comprehensive default client configuration")

    def _create_deployment_scripts(self) -> None:
        """Create deployment and setup scripts."""
        print("🛠️ Creating deployment scripts...")

        # Create setup.py
        setup_script = '''#!/usr/bin/env python3
"""
Multi-Client Platform Setup Script
==================================

Sets up the multi-client Discord bot platform with all dependencies.
"""

import subprocess
import sys
from pathlib import Path

def install_requirements():
    """Install Python requirements."""
    print("📦 Installing Python requirements...")

    req_file = Path("requirements.txt")
    if req_file.exists():
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    else:
        print("⚠️ requirements.txt not found, installing core dependencies...")
        core_deps = [
            "discord.py>=2.3.0",
            "python-dotenv>=1.0.0", 
            "loguru>=0.7.0",
            "psutil>=5.9.0"
        ]
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + core_deps)

def create_directories():
    """Create necessary directories."""
    print("📁 Creating directories...")

    directories = [
        "platform/logs",
        "clients/default/data",
        "clients/default/logs", 
        "clients/_template/data",
        "clients/_template/logs"
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

def main():
    """Main setup function."""
    print("🚀 Setting up Multi-Client Discord Bot Platform")
    print("=" * 50)

    try:
        install_requirements()
        create_directories()

        print("\\n✅ Setup completed successfully!")
        print("\\n📋 Next steps:")
        print("1. Copy platform code from artifacts into platform/ files")
        print("2. Update clients/default/.env with your Discord token")
        print("3. Run 'python platform_main.py --client default' to test")

    except Exception as e:
        print(f"\\n❌ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''

        with open(self.target_dir / "setup.py", 'w', encoding='utf-8') as f:
            f.write(setup_script)

        print("   Created deployment scripts")

    def _update_requirements(self) -> None:
        """Update requirements.txt with platform dependencies."""
        print("📚 Updating requirements...")

        # Read existing requirements
        existing_reqs = []
        req_path = self.target_dir / "requirements.txt"

        if req_path.exists():
            with open(req_path, 'r', encoding='utf-8') as f:
                existing_reqs = [line.strip() for line in f if line.strip()]

        # Add platform-specific requirements
        platform_reqs = [
            "",
            "# Multi-Client Platform Dependencies",
            "psutil>=5.9.0              # Process monitoring",
            "# asyncpg>=0.28.0            # PostgreSQL support (optional)",
            "# aioredis>=2.0.0            # Redis support (optional)",
        ]

        # Combine requirements
        all_reqs = existing_reqs + platform_reqs

        with open(req_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(all_reqs))

        print("   Updated requirements.txt")

    def _create_documentation(self) -> None:
        """Create platform documentation."""
        print("📖 Creating documentation...")

        readme_content = '''# Multi-Client Discord Bot Platform

A professional platform for managing multiple Discord bot clients with shared core functionality.

## 🚀 Quick Start

### 1. Setup
```bash
python setup.py
```

### 2. Copy Platform Code
Copy the code from artifacts into the platform files:
- `platform/launcher.py` - Copy from "Platform Launcher System" artifact
- `platform/client_runner.py` - Copy from "Client Runner System" artifact
- `platform/client_manager.py` - Copy from "Client Management System" artifact
- `platform/deployment_tools.py` - Copy from "Deployment Tools" artifact
- `platform_main.py` - Copy from "Platform Main Entry Point" artifact

### 3. Configure Default Client
```bash
# Edit the default client configuration
notepad clients/default/.env  # Windows
# OR
nano clients/default/.env     # Linux/Mac

# Update DISCORD_TOKEN with your bot token
# Update OWNER_IDS with your Discord user ID
```

### 4. Test First Client
```bash
python platform_main.py --client default
```

### 5. Create Additional Clients
```bash
python -m platform.deployment_tools new-client
```

### 6. Start Full Platform
```bash
python platform_main.py
```

## 📁 Structure

```
discord-bot-platform/
├── core/                    # Your original bot code
├── clients/                 # Client configurations
│   ├── default/            # Default client
│   └── _template/          # Template for new clients
├── platform/               # Platform management
└── platform_main.py       # Main entry point
```

## 🔧 Management Commands

```bash
# View platform status
python platform_main.py --status

# Interactive management
python platform_main.py --interactive

# Start specific client
python platform_main.py --client client_name

# Create new client
python -m platform.deployment_tools new-client

# List all clients
python -m platform.deployment_tools list-clients
```

## 💼 Business Features

- **Multi-Client Management**: One codebase, multiple bot instances
- **Custom Branding**: Each client gets unique styling
- **Database Isolation**: Separate databases per client
- **Health Monitoring**: Automatic restart and health checks
- **Easy Deployment**: One-command updates

## 📊 Service Plans

- **Basic**: $200/month - Core features
- **Premium**: $350/month - Advanced features
- **Enterprise**: $500/month - Full features + API access

## 🔒 Security

- Complete data isolation between clients
- Separate environment variables and configurations
- Audit logging for permission changes
- Professional security practices

---

**Migration completed successfully!** 
Copy the platform code from artifacts and update your Discord tokens to get started.
'''

        with open(self.target_dir / "README.md", 'w', encoding='utf-8') as f:
            f.write(readme_content)

        print("   Created README.md")

    def _print_next_steps(self) -> None:
        """Print next steps for the user."""
        print("\n🚀 Next steps:")
        print("1. Copy platform code from artifacts into platform/ files")
        print("2. Update clients/default/.env with your Discord token")
        print("3. Run 'python platform_main.py --client default' to test")


def main():
    """Main migration entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate Discord bot template to multi-client platform")
    parser.add_argument("--source", default=".", help="Source directory (existing bot)")
    parser.add_argument("--target", default=".", help="Target directory (platform)")

    args = parser.parse_args()

    migrator = TemplateMigrator(args.source, args.target)
    success = migrator.migrate()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
