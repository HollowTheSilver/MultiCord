#!/usr/bin/env python3
"""
Status Message Configuration Migration Script
============================================

Migrates STATUS_MESSAGES from .env files to branding.py files,
establishing branding.py as the single source of truth.

This script:
1. Scans all client .env files for STATUS_MESSAGES
2. Extracts and parses the status messages
3. Updates/creates branding.py files with proper status configuration
4. Comments out STATUS_MESSAGES in .env files
5. Preserves existing branding configuration
"""

import os
import re
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Any
from datetime import datetime


class StatusMessageMigrator:
    """Handles migration of status messages from .env to branding.py"""

    def __init__(self):
        self.clients_dir = Path("clients")
        self.backup_dir = Path("backups") / f"status_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.migrated_clients = []
        self.errors = []

    def migrate_all_clients(self) -> bool:
        """Migrate status messages for all clients."""
        print("🚀 Starting Status Message Migration")
        print("=" * 50)

        if not self.clients_dir.exists():
            print("❌ No clients directory found")
            return False

        # Create backup
        self._create_backup()

        # Find all client directories
        client_dirs = [d for d in self.clients_dir.iterdir()
                       if d.is_dir() and not d.name.startswith("_")]

        if not client_dirs:
            print("❌ No client directories found")
            return False

        print(f"📁 Found {len(client_dirs)} client(s) to migrate")

        # Migrate each client
        for client_dir in client_dirs:
            try:
                self._migrate_client(client_dir)
            except Exception as e:
                error_msg = f"Failed to migrate {client_dir.name}: {e}"
                self.errors.append(error_msg)
                print(f"❌ {error_msg}")

        # Report results
        self._print_migration_report()
        return len(self.errors) == 0

    def _create_backup(self) -> None:
        """Create backup of clients directory."""
        print("💾 Creating backup...")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.clients_dir, self.backup_dir / "clients")
        print(f"   Backup created: {self.backup_dir}")

    def _migrate_client(self, client_dir: Path) -> None:
        """Migrate a single client's status messages."""
        client_name = client_dir.name
        print(f"\n🔄 Migrating client: {client_name}")

        env_file = client_dir / ".env"
        branding_file = client_dir / "branding.py"

        # Extract status messages from .env
        status_messages = self._extract_status_messages_from_env(env_file)

        if not status_messages:
            print(f"   ℹ️  No STATUS_MESSAGES found in .env")
            # Still update branding.py template if it doesn't exist
            if not branding_file.exists():
                self._create_default_branding(branding_file, client_name)
            return

        print(f"   📤 Found {len(status_messages)} status message(s) in .env")

        # Update branding.py with status messages
        self._update_branding_file(branding_file, client_name, status_messages)

        # Comment out STATUS_MESSAGES in .env
        self._comment_out_env_status_messages(env_file)

        self.migrated_clients.append(client_name)
        print(f"   ✅ Migration completed for {client_name}")

    def _extract_status_messages_from_env(self, env_file: Path) -> List[Tuple[str, str]]:
        """Extract STATUS_MESSAGES from .env file."""
        if not env_file.exists():
            return []

        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find STATUS_MESSAGES line
            pattern = r'^STATUS_MESSAGES=(.*)$'
            match = re.search(pattern, content, re.MULTILINE)

            if not match:
                return []

            status_value = match.group(1).strip('"\'')

            # Parse status messages
            messages = []
            if status_value:
                # Handle format: "message1:type1,message2:type2"
                for status_pair in status_value.split(","):
                    status_pair = status_pair.strip()
                    if ":" in status_pair:
                        message, status_type = status_pair.split(":", 1)
                        messages.append((message.strip(), status_type.strip()))
                    else:
                        # Default to custom type if no type specified
                        messages.append((status_pair, "custom"))

            return messages

        except Exception as e:
            print(f"   ⚠️  Warning: Could not parse .env file: {e}")
            return []

    def _update_branding_file(self, branding_file: Path, client_name: str,
                              status_messages: List[Tuple[str, str]]) -> None:
        """Update or create branding.py with status messages."""

        # Load existing branding if it exists
        existing_branding = self._load_existing_branding(branding_file)

        # Determine bot name from existing branding or client name
        bot_name = existing_branding.get('bot_name', client_name.replace('_', ' ').title())
        bot_description = existing_branding.get('bot_description', f"Discord bot for {bot_name}")

        # Create branding content
        branding_content = f'''"""Client Branding Configuration for {bot_name}"""

BRANDING = {{
    "bot_name": "{bot_name}",
    "bot_description": "{bot_description}",
    "embed_colors": {{
        "default": 0x3498db,
        "success": 0x2ecc71,
        "error": 0xe74c3c,
        "warning": 0xf39c12,
    }},
    # ✅ Migrated from .env STATUS_MESSAGES
    "status_messages": {self._format_status_messages(status_messages)},
    "footer_text": "Powered by {bot_name}",
}}
'''

        # Write the file
        with open(branding_file, 'w', encoding='utf-8') as f:
            f.write(branding_content)

        print(f"   📝 Updated branding.py with {len(status_messages)} status messages")

    def _load_existing_branding(self, branding_file: Path) -> Dict[str, Any]:
        """Load existing branding configuration if available."""
        if not branding_file.exists():
            return {}

        try:
            # Simple extraction of bot_name and bot_description
            with open(branding_file, 'r', encoding='utf-8') as f:
                content = f.read()

            branding = {}

            # Extract bot_name
            name_match = re.search(r'"bot_name":\s*"([^"]*)"', content)
            if name_match:
                branding['bot_name'] = name_match.group(1)

            # Extract bot_description
            desc_match = re.search(r'"bot_description":\s*"([^"]*)"', content)
            if desc_match:
                branding['bot_description'] = desc_match.group(1)

            return branding

        except Exception:
            return {}

    def _format_status_messages(self, status_messages: List[Tuple[str, str]]) -> str:
        """Format status messages for Python code."""
        if not status_messages:
            return '[("🤖 Online", "custom")]'

        formatted_messages = []
        for message, status_type in status_messages:
            formatted_messages.append(f'("{message}", "{status_type}")')

        if len(formatted_messages) == 1:
            return f'[{formatted_messages[0]}]'
        else:
            return '[\n        ' + ',\n        '.join(formatted_messages) + '\n    ]'

    def _comment_out_env_status_messages(self, env_file: Path) -> None:
        """Comment out STATUS_MESSAGES line in .env file."""
        if not env_file.exists():
            return

        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            modified = False
            for i, line in enumerate(lines):
                if line.strip().startswith('STATUS_MESSAGES='):
                    lines[i] = f"# MIGRATED TO branding.py: {line}"
                    modified = True
                    break

            if modified:
                with open(env_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                print(f"   📝 Commented out STATUS_MESSAGES in .env")

        except Exception as e:
            print(f"   ⚠️  Warning: Could not update .env file: {e}")

    def _create_default_branding(self, branding_file: Path, client_name: str) -> None:
        """Create default branding.py file."""
        bot_name = client_name.replace('_', ' ').title()

        content = f'''"""Client Branding Configuration for {bot_name}"""

BRANDING = {{
    "bot_name": "{bot_name}",
    "bot_description": "Professional Discord bot",
    "embed_colors": {{
        "default": 0x3498db,
        "success": 0x2ecc71,
        "error": 0xe74c3c,
        "warning": 0xf39c12,
    }},
    "status_messages": [("🤖 {bot_name} Online", "custom")],
    "footer_text": "Powered by {bot_name}",
}}
'''

        with open(branding_file, 'w', encoding='utf-8') as f:
            f.write(content)

    def _print_migration_report(self) -> None:
        """Print migration results."""
        print("\n" + "=" * 50)
        print("📊 Migration Results")
        print("=" * 50)

        if self.migrated_clients:
            print(f"✅ Successfully migrated {len(self.migrated_clients)} client(s):")
            for client in self.migrated_clients:
                print(f"   - {client}")

        if self.errors:
            print(f"❌ Errors encountered ({len(self.errors)}):")
            for error in self.errors:
                print(f"   - {error}")

        print(f"\n💾 Backup available at: {self.backup_dir}")
        print("\n🎯 Next Steps:")
        print("1. Test your clients: python platform_main.py --client default")
        print("2. Verify status cycling is working properly")
        print("3. Update client_runner.py with enhanced _apply_branding method")
        print(f"4. If issues occur, restore from backup: {self.backup_dir}")


def main():
    """Main migration function."""
    migrator = StatusMessageMigrator()
    success = migrator.migrate_all_clients()

    if success:
        print("\n🎉 Migration completed successfully!")
        return 0
    else:
        print("\n⚠️  Migration completed with errors - check backup if needed")
        return 1


if __name__ == "__main__":
    exit(main())
