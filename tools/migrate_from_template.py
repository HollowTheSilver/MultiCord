#!/usr/bin/env python3
"""
Migration Script for Multi-Client Platform (Windows Compatible)
================================================================

Converts existing single-bot template to multi-client architecture.
Production-ready with proper encoding and Windows path handling.
"""

import os
import shutil
import json
from pathlib import Path
from typing import Dict, List, Any
import subprocess
import sys
from datetime import datetime, timezone


class PlatformMigrator:
    """Migrates existing bot template to multi-client architecture."""

    def __init__(self, source_dir: str = "."):
        """Initialize migrator with source directory."""
        self.source_dir = Path(source_dir).resolve()
        self.target_dir = self.source_dir / "discord-bot-platform"

        # Verify source is the template
        self._verify_source_template()

    def _verify_source_template(self) -> None:
        """Verify this is the Discord bot template."""
        required_files = [
            "main.py",
            "utils/permissions.py",
            "utils/embeds.py",
            "config/settings.py",
            "cogs/base_commands.py"
        ]

        missing_files = []
        for file_path in required_files:
            # Use Path for cross-platform compatibility
            full_path = self.source_dir / Path(file_path)
            if not full_path.exists():
                missing_files.append(file_path)

        if missing_files:
            print(f"❌ This doesn't appear to be the Discord bot template.")
            print(f"Missing files: {', '.join(missing_files)}")
            print(f"Current directory: {self.source_dir}")
            print(f"Files found:")
            for item in self.source_dir.iterdir():
                if item.is_file() and item.suffix == '.py':
                    print(f"  ✓ {item.name}")
                elif item.is_dir() and not item.name.startswith('.'):
                    print(f"  📁 {item.name}/")
            sys.exit(1)

        print("✅ Discord bot template detected")

    def migrate(self) -> bool:
        """Perform the complete migration."""
        print("🚀 Starting Migration to Multi-Client Platform")
        print("=" * 50)

        try:
            # Step 1: Create target directory structure
            self._create_directory_structure()

            # Step 2: Move core files
            self._migrate_core_files()

            # Step 3: Create platform files
            self._create_platform_files()

            # Step 4: Create client template
            self._create_client_template()

            # Step 5: Create first client from existing config
            self._create_default_client()

            # Step 6: Create deployment scripts
            self._create_deployment_scripts()

            # Step 7: Update requirements
            self._update_requirements()

            # Step 8: Create documentation
            self._create_documentation()

            print("\n✅ Migration completed successfully!")
            print(f"📁 New platform location: {self.target_dir}")
            print("\n🚀 Next Steps:")
            print("1. cd discord-bot-platform")
            print("2. pip install -r requirements.txt")
            print("3. Copy platform code from artifacts into platform/ files")
            print("4. Update clients/default/.env with your Discord token")
            print("5. python platform_main.py --client default  # Test first client")
            print("6. python -m platform.deployment_tools new-client  # Create additional clients")

            return True

        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _create_directory_structure(self) -> None:
        """Create the multi-client directory structure."""
        print("📁 Creating directory structure...")

        directories = [
            "core",
            "core/utils",
            "core/cogs",
            "core/config",
            "clients",
            "clients/_template",
            "clients/_template/custom_cogs",
            "clients/_template/data",
            "clients/_template/logs",
            "platform",
            "platform/logs",
            "tools",
            "deploy",
            "backups"
        ]

        for directory in directories:
            (self.target_dir / directory).mkdir(parents=True, exist_ok=True)

        print(f"   Created {len(directories)} directories")

    def _migrate_core_files(self) -> None:
        """Move existing template files to core directory."""
        print("📦 Migrating core files...")

        # Map of source -> target paths
        file_mappings = {
            # Core application
            "main.py": "core/application.py",

            # Utils (keep all)
            "utils": "core/utils",

            # Configuration
            "config": "core/config",

            # Base cogs
            "cogs": "core/cogs",

            # Other important files
            "requirements.txt": "requirements.txt",
            "README.md": "README_ORIGINAL.md",
            "LICENSE": "LICENSE",
            ".gitignore": ".gitignore"
        }

        for source, target in file_mappings.items():
            source_path = self.source_dir / source
            target_path = self.target_dir / target

            if source_path.exists():
                if source_path.is_dir():
                    if target_path.exists():
                        shutil.rmtree(target_path)
                    shutil.copytree(source_path, target_path)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, target_path)

                print(f"   Moved {source} -> {target}")

    def _create_platform_files(self) -> None:
        """Create platform management files."""
        print("🔧 Creating platform files...")

        # Create __init__.py files
        init_content = '"""Multi-Client Discord Bot Platform"""\n'

        platform_files = {
            "platform/__init__.py": init_content,
            "platform/launcher.py": self._get_launcher_skeleton(),
            "platform/client_runner.py": self._get_client_runner_skeleton(),
            "platform/client_manager.py": self._get_client_manager_skeleton(),
            "platform/deployment_tools.py": self._get_deployment_tools_skeleton(),
            "platform_main.py": self._get_platform_main_skeleton()
        }

        for file_path, content in platform_files.items():
            full_path = self.target_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)

        print(f"   Created {len(platform_files)} platform files")
        print("   📝 Platform files created as skeletons - copy code from artifacts")

    def _get_launcher_skeleton(self) -> str:
        return '''"""
Platform Launcher System
========================

TODO: Copy the complete code from the "Platform Launcher System" artifact.
This skeleton ensures the file structure is correct.
"""

# TODO: Implement platform launcher
# Copy code from artifact: "Platform Launcher System"

class PlatformLauncher:
    def __init__(self):
        pass

    async def run(self):
        print("TODO: Implement platform launcher")
        print("Copy code from 'Platform Launcher System' artifact")

if __name__ == "__main__":
    import asyncio
    launcher = PlatformLauncher()
    asyncio.run(launcher.run())
'''

    def _get_client_runner_skeleton(self) -> str:
        return '''"""
Client Runner System
===================

TODO: Copy the complete code from the "Client Runner System" artifact.
"""

# TODO: Implement client runner
# Copy code from artifact: "Client Runner System"

class ClientRunner:
    def __init__(self, client_id: str):
        self.client_id = client_id

    async def run(self):
        print(f"TODO: Implement client runner for {self.client_id}")
        print("Copy code from 'Client Runner System' artifact")

if __name__ == "__main__":
    print("Use: python -m platform.client_runner --client-id CLIENT_NAME")
'''

    def _get_client_manager_skeleton(self) -> str:
        return '''"""
Client Management System
========================

TODO: Copy the complete code from the "Client Management System" artifact.
"""

# TODO: Implement client manager
# Copy code from artifact: "Client Management System"

class ClientManager:
    def __init__(self):
        pass

    def create_client(self, **kwargs):
        print("TODO: Implement client creation")
        print("Copy code from 'Client Management System' artifact")
        return False

if __name__ == "__main__":
    print("Use platform.deployment_tools for client management")
'''

    def _get_deployment_tools_skeleton(self) -> str:
        return '''"""
Deployment Tools & Client Onboarding
====================================

TODO: Copy the complete code from the "Deployment Tools" artifact.
"""

# TODO: Implement deployment tools
# Copy code from artifact: "Deployment Tools & Client Onboarding"

def main():
    print("TODO: Implement deployment tools")
    print("Copy code from 'Deployment Tools & Client Onboarding' artifact")

if __name__ == "__main__":
    main()
'''

    def _get_platform_main_skeleton(self) -> str:
        return '''#!/usr/bin/env python3
"""
Multi-Client Discord Bot Platform
=================================

TODO: Copy the complete code from the "Platform Main Entry Point" artifact.
"""

# TODO: Implement platform main
# Copy code from artifact: "Platform Main Entry Point"

async def main():
    print("TODO: Implement platform main")
    print("Copy code from 'Platform Main Entry Point' artifact")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
'''

    def _create_client_template(self) -> None:
        """Create client template files."""
        print("📋 Creating client template...")

        template_dir = self.target_dir / "clients" / "_template"

        # Create template .env
        env_template = """# Discord Bot Configuration for {CLIENT_NAME}
DISCORD_TOKEN={DISCORD_TOKEN}
BOT_NAME="{BOT_NAME}"
BOT_VERSION="2.0.0"
BOT_DESCRIPTION="{BOT_DESCRIPTION}"
COMMAND_PREFIX="!"
OWNER_IDS="{OWNER_IDS}"
ALLOWED_GUILDS="{ALLOWED_GUILDS}"
STATUS_MESSAGES="{STATUS_MESSAGE}:custom"
LOG_LEVEL="INFO"
"""

        with open(template_dir / ".env.template", 'w', encoding='utf-8') as f:
            f.write(env_template)

        # Create template config.py
        config_template = '''"""Client Configuration"""
CLIENT_CONFIG = {
    "bot_config": {
        "COMMAND_PREFIX": "!",
        "ENABLE_SLASH_COMMANDS": True,
        "STATUS_CYCLE_INTERVAL": 300,
    },
    "client_info": {
        "display_name": "{DISPLAY_NAME}",
        "plan": "{PLAN}",
        "created_at": "{CREATED_AT}",
    }
}
'''

        with open(template_dir / "config.py.template", 'w', encoding='utf-8') as f:
            f.write(config_template)

        # Create template branding.py
        branding_template = '''"""Client Branding Configuration"""
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

        with open(template_dir / "branding.py.template", 'w', encoding='utf-8') as f:
            f.write(branding_template)

        # Create template features.py
        features_template = '''"""Client Feature Configuration"""
FEATURES = {
    "base_commands": True,
    "permission_system": True,
    "moderation": {MODERATION_ENABLED},
    "custom_commands": {CUSTOM_COMMANDS_ENABLED},
    "limits": {
        "max_custom_commands": {MAX_CUSTOM_COMMANDS},
    }
}
'''

        with open(template_dir / "features.py.template", 'w', encoding='utf-8') as f:
            f.write(features_template)

        print("   Created client template files")

    def _create_default_client(self) -> None:
        """Create default client from existing configuration."""
        print("🤖 Creating default client...")

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

        # Create default client directory
        default_client_dir = self.target_dir / "clients" / "default"
        default_client_dir.mkdir(exist_ok=True)

        # Create subdirectories
        for subdir in ["custom_cogs", "data", "logs"]:
            (default_client_dir / subdir).mkdir(exist_ok=True)

        # Create default .env - avoid emojis that cause encoding issues
        default_env = f"""# Default Client Configuration
DISCORD_TOKEN={env_values.get('DISCORD_TOKEN', 'your_token_here')}
BOT_NAME="{env_values.get('BOT_NAME', 'Professional Bot')}"
BOT_VERSION="2.0.0"
BOT_DESCRIPTION="Professional Discord bot - Default Client"
COMMAND_PREFIX="{env_values.get('COMMAND_PREFIX', '!')}"
OWNER_IDS="{env_values.get('OWNER_IDS', 'your_user_id')}"
ALLOWED_GUILDS="{env_values.get('ALLOWED_GUILDS', '')}"
STATUS_MESSAGES="Professional Bot Online:custom"
LOG_LEVEL="INFO"
"""

        with open(default_client_dir / ".env", 'w', encoding='utf-8') as f:
            f.write(default_env)

        # Create default config.py
        default_config = '''"""Default Client Configuration"""
CLIENT_CONFIG = {
    "bot_config": {
        "COMMAND_PREFIX": "!",
        "ENABLE_SLASH_COMMANDS": True,
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
        default_branding = '''"""Default Client Branding"""
BRANDING = {
    "bot_name": "Professional Bot",
    "bot_description": "A professional Discord bot",
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
        default_features = '''"""Default Client Features"""
FEATURES = {
    "base_commands": True,
    "permission_system": True,
    "moderation": True,
    "custom_commands": True,
    "limits": {
        "max_custom_commands": 25,
    }
}
'''

        with open(default_client_dir / "features.py", 'w', encoding='utf-8') as f:
            f.write(default_features)

        print("   Created default client configuration")

    def _create_deployment_scripts(self) -> None:
        """Create deployment and management scripts."""
        print("🚀 Creating deployment scripts...")

        # Cross-platform start script (Python-based)
        start_script = '''#!/usr/bin/env python3
"""
Platform Start Script
=====================
Cross-platform start script for the Discord Bot Platform.
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    print("🚀 Starting Multi-Client Discord Bot Platform")
    print("=" * 48)

    # Check if virtual environment exists
    venv_path = Path("venv")
    if not venv_path.exists():
        print("📦 Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "venv"])

    # Determine activation script based on platform
    if os.name == 'nt':  # Windows
        activate_script = venv_path / "Scripts" / "activate.bat"
        python_executable = venv_path / "Scripts" / "python.exe"
    else:  # Unix-like
        activate_script = venv_path / "bin" / "activate"
        python_executable = venv_path / "bin" / "python"

    # Install requirements
    print("📚 Installing requirements...")
    subprocess.run([str(python_executable), "-m", "pip", "install", "-r", "requirements.txt"])

    # Start platform
    print("🤖 Starting platform...")
    subprocess.run([str(python_executable), "platform_main.py"])

if __name__ == "__main__":
    main()
'''

        with open(self.target_dir / "start.py", 'w', encoding='utf-8') as f:
            f.write(start_script)

        # Setup script
        setup_script = '''#!/usr/bin/env python3
"""Platform Setup Script"""

import subprocess
import sys
from pathlib import Path

def main():
    print("🔧 Setting up Multi-Client Discord Bot Platform")
    print("=" * 48)

    # Install requirements
    print("📚 Installing Python requirements...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    subprocess.run([sys.executable, "-m", "pip", "install", "psutil"])

    # Create necessary directories
    dirs = ["platform/logs", "backups", "data"]
    for directory in dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"   Created directory: {directory}")

    print("✅ Setup complete!")
    print("🚀 Next steps:")
    print("1. Copy platform code from artifacts into platform/ files")
    print("2. Update clients/default/.env with your Discord token")
    print("3. Run 'python platform_main.py --client default' to test")

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


def main():
    """Main migration entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate Discord bot template to multi-client platform")
    parser.add_argument("--source", default=".", help="Source directory (default: current directory)")
    parser.add_argument("--force", action="store_true", help="Force migration even if target exists")

    args = parser.parse_args()

    # Check if target already exists
    target_dir = Path(args.source) / "discord-bot-platform"
    if target_dir.exists() and not args.force:
        print(f"❌ Target directory already exists: {target_dir}")
        print("Use --force to overwrite, or remove the directory first")
        sys.exit(1)

    if target_dir.exists() and args.force:
        print(f"🗑️ Removing existing target directory: {target_dir}")
        shutil.rmtree(target_dir)

    # Perform migration
    migrator = PlatformMigrator(args.source)
    success = migrator.migrate()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
