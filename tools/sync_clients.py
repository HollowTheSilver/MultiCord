#!/usr/bin/env python3
"""
Client Database Sync Tool
=========================

Synchronizes client directories with the client manager database.
Adds missing clients that were created manually to the database.

Usage:
    python sync_clients.py           # Sync all clients
    python sync_clients.py --dry-run # Show what would be synced
"""

import os
import re
from pathlib import Path
from datetime import datetime, timezone
import argparse
import sys

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from bot_platform.client_manager import ClientManager
except ImportError:
    print("❌ Could not import ClientManager. Make sure you're in the project root.")
    sys.exit(1)


class ClientSyncer:
    """Syncs client directories with the client manager database."""

    def __init__(self):
        self.client_manager = ClientManager()
        self.clients_dir = Path("clients")

    def sync_clients(self, dry_run: bool = False) -> bool:
        """Sync all client directories with the database."""
        print("🔄 Client Database Sync Tool")
        print("=" * 40)

        if not self.clients_dir.exists():
            print("❌ No clients directory found")
            return False

        # Find all client directories
        client_dirs = [d for d in self.clients_dir.iterdir()
                       if d.is_dir() and not d.name.startswith("_")]

        if not client_dirs:
            print("❌ No client directories found")
            return False

        print(f"📁 Found {len(client_dirs)} client directories")
        print(f"🗄️ Database has {len(self.client_manager.clients)} clients")

        # Find clients that exist as directories but not in database
        missing_clients = []
        for client_dir in client_dirs:
            client_id = client_dir.name
            if client_id not in self.client_manager.clients:
                missing_clients.append(client_dir)

        if not missing_clients:
            print("✅ All clients are already in the database")
            return True

        print(f"\n🔍 Found {len(missing_clients)} clients missing from database:")
        for client_dir in missing_clients:
            print(f"   • {client_dir.name}")

        if dry_run:
            print("\n🔍 DRY RUN - No changes will be made")
            for client_dir in missing_clients:
                client_info = self._extract_client_info(client_dir)
                print(f"\nWould add: {client_dir.name}")
                print(f"   Name: {client_info['display_name']}")
                print(f"   Plan: {client_info['plan']}")
                print(f"   Bot Name: {client_info['bot_name']}")
            return True

        # Add missing clients to database
        added_count = 0
        for client_dir in missing_clients:
            try:
                if self._add_client_to_database(client_dir):
                    added_count += 1
                    print(f"✅ Added {client_dir.name} to database")
                else:
                    print(f"❌ Failed to add {client_dir.name}")
            except Exception as e:
                print(f"❌ Error adding {client_dir.name}: {e}")

        print(f"\n📊 Summary: Added {added_count}/{len(missing_clients)} clients to database")
        return added_count == len(missing_clients)

    def _extract_client_info(self, client_dir: Path) -> dict:
        """Extract client information from .env and branding files."""
        client_id = client_dir.name
        info = {
            'client_id': client_id,
            'display_name': client_id.replace('_', ' ').title(),
            'plan': 'basic',
            'bot_name': client_id.replace('_', ' ').title(),
            'discord_token': '',
            'owner_ids': ''
        }

        # Extract from .env file
        env_file = client_dir / ".env"
        if env_file.exists():
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract BOT_NAME
                bot_name_match = re.search(r'^BOT_NAME="?([^"]*)"?', content, re.MULTILINE)
                if bot_name_match:
                    info['bot_name'] = bot_name_match.group(1)

                # Extract DISCORD_TOKEN
                token_match = re.search(r'^DISCORD_TOKEN=(.*)$', content, re.MULTILINE)
                if token_match:
                    info['discord_token'] = token_match.group(1).strip('"\'')

                # Extract OWNER_IDS
                owner_match = re.search(r'^OWNER_IDS="?([^"]*)"?', content, re.MULTILINE)
                if owner_match:
                    info['owner_ids'] = owner_match.group(1)

            except Exception as e:
                print(f"   ⚠️ Could not read .env for {client_id}: {e}")

        # Extract from branding file
        branding_file = client_dir / "branding.py"
        if branding_file.exists():
            try:
                with open(branding_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract bot_name from branding
                branding_name_match = re.search(r'"bot_name":\s*"([^"]*)"', content)
                if branding_name_match:
                    info['display_name'] = branding_name_match.group(1)

            except Exception as e:
                print(f"   ⚠️ Could not read branding.py for {client_id}: {e}")

        # Determine plan based on features (rough guess)
        if 'enterprise' in client_id.lower() or 'API_ACCESS_ENABLED="true"' in str(env_file):
            info['plan'] = 'enterprise'
        elif 'premium' in client_id.lower():
            info['plan'] = 'premium'

        return info

    def _add_client_to_database(self, client_dir: Path) -> bool:
        """Add a client to the database."""
        client_info = self._extract_client_info(client_dir)

        # Use the client manager's create_client method but skip file creation
        from bot_platform.client_manager import ClientInfo

        client_data = ClientInfo(
            client_id=client_info['client_id'],
            display_name=client_info['display_name'],
            plan=client_info['plan'],
            monthly_fee={'basic': 200.0, 'premium': 350.0, 'enterprise': 500.0}.get(client_info['plan'], 200.0),
            discord_token=client_info['discord_token'],
            owner_ids=client_info['owner_ids'],
            branding={'bot_name': client_info['bot_name']},
            notes=f"Synced from existing directory on {datetime.now().strftime('%Y-%m-%d')}"
        )

        # Add to the manager's clients dict and save
        self.client_manager.clients[client_info['client_id']] = client_data
        self.client_manager._save_clients_db()

        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Sync client directories with database")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without making changes")

    args = parser.parse_args()

    syncer = ClientSyncer()
    success = syncer.sync_clients(args.dry_run)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
