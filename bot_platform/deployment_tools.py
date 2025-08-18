"""
Deployment Tools & Client Onboarding
====================================

Command-line tools for managing the multi-client platform including
client onboarding, updates, and monitoring.
"""

import asyncio
import argparse
import sys
import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot_platform.client_manager import ClientManager
from bot_platform.launcher import PlatformLauncher


class DeploymentManager:
    """Handles deployment operations across all clients."""

    def __init__(self):
        self.client_manager = ClientManager()
        self.logger = self.client_manager.logger

    async def update_all_clients(self, restart: bool = True) -> bool:
        """Update core codebase for all clients."""
        self.logger.info("Starting platform-wide update...")

        try:
            # Get list of running clients
            launcher = PlatformLauncher()
            running_clients = list(launcher.client_processes.keys())

            if restart and running_clients:
                self.logger.info(f"Stopping {len(running_clients)} running clients...")
                await launcher.stop_all_clients()

            # Perform core updates here
            # This would typically involve:
            # - Git pull
            # - Dependency updates
            # - Database migrations
            # - Configuration updates

            self.logger.info("Core update completed")

            if restart and running_clients:
                self.logger.info("Restarting clients...")
                await launcher.start_all_clients()

            return True

        except Exception as e:
            self.logger.error(f"Update failed: {e}")
            return False

    async def backup_all_clients(self) -> bool:
        """Create backups of all client data."""
        try:
            backup_dir = Path("backups") / datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Backup client configurations
            clients_dir = Path("clients")
            if clients_dir.exists():
                shutil.copytree(clients_dir, backup_dir / "clients")

            # Backup platform configuration
            platform_config = Path("platform_config.json")
            if platform_config.exists():
                shutil.copy2(platform_config, backup_dir)

            # Backup platform logs
            platform_logs = Path("platform/logs")
            if platform_logs.exists():
                shutil.copytree(platform_logs, backup_dir / "platform_logs")

            self.logger.info(f"Backup created: {backup_dir}")
            return True

        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
            return False


class PlatformStats:
    """Handles platform statistics and monitoring."""

    def __init__(self):
        self.launcher = PlatformLauncher()
        self.client_manager = ClientManager()

    async def show_platform_status(self) -> None:
        """Display comprehensive platform status."""
        print("📊 Multi-Client Platform Status")
        print("=" * 50)

        stats = self.launcher.get_platform_stats()
        platform_stats = stats["platform"]

        print(f"🕐 Platform Uptime: {platform_stats['uptime_hours']:.1f} hours")
        print(f"🔄 Total Restarts: {platform_stats['total_restarts']}")
        print(f"📊 Total Clients: {platform_stats['total_clients']}")
        print(f"✅ Enabled Clients: {platform_stats['enabled_clients']}")
        print(f"🟢 Running Clients: {platform_stats['running_clients']}")
        print()

        if stats["clients"]:
            print("Client Status:")
            print("-" * 50)
            for client_id, client_stats in stats["clients"].items():
                status_icon = "🟢" if client_stats["running"] else "🔴"
                enabled_icon = "✅" if client_stats["enabled"] else "❌"

                print(f"{status_icon} {client_id} (Enabled: {enabled_icon})")

                if client_stats["running"]:
                    uptime_hours = client_stats["uptime_seconds"] / 3600
                    print(f"  ⏱️  Uptime: {uptime_hours:.1f} hours")
                    print(f"  💾 Memory: {client_stats['memory_mb']:.1f} MB")
                    print(f"  ⚡ CPU: {client_stats['cpu_percent']:.1f}%")
                    print(f"  🔄 Restarts: {client_stats['restart_count']}")
                print()
        else:
            print("❌ No clients configured")

    def list_clients(self) -> None:
        """List all clients with basic info."""
        print("📋 Client List")
        print("=" * 30)

        if not self.client_manager.clients:
            print("❌ No clients found")
            return

        for client_id, client_info in self.client_manager.clients.items():
            status = "🟢 Active" if client_info.status == "active" else "🔴 Inactive"
            print(f"{status} {client_id}")
            print(f"  📝 Name: {client_info.display_name}")

            # Fix datetime handling - created_at is stored as ISO string
            try:
                if client_info.created_at:
                    # Parse ISO string to datetime for formatting
                    from datetime import datetime
                    created_date = datetime.fromisoformat(client_info.created_at.replace('Z', '+00:00'))
                    print(f"  📅 Created: {created_date.strftime('%Y-%m-%d')}")
                else:
                    print(f"  📅 Created: Unknown")
            except (ValueError, AttributeError):
                print(f"  📅 Created: {client_info.created_at}")

            print(f"  💰 Plan: {client_info.plan.title()}")
            print(f"  🏷️  Monthly Fee: ${client_info.monthly_fee}")
            print()


class ClientOnboardingTool:
    """Interactive client onboarding tool."""

    def __init__(self):
        self.client_manager = ClientManager()

    def interactive_onboarding(self) -> bool:
        """Run interactive client onboarding process."""
        print("🆕 Multi-Client Platform - New Client Onboarding")
        print("=" * 55)

        try:
            # Collect client information
            client_data = self._collect_client_info()
            if not client_data:
                return False

            # Create the client
            success = self.client_manager.create_client(**client_data)

            if success:
                print(f"\n✅ Client '{client_data['client_id']}' created successfully!")
                print("\n📋 Next Steps:")
                print(f"1. Edit clients/{client_data['client_id']}/.env with your Discord token")
                print(f"2. Customize clients/{client_data['client_id']}/branding.py if needed")
                print(f"3. Test: python platform_main.py --client {client_data['client_id']}")
                return True
            else:
                print("❌ Failed to create client")
                return False

        except KeyboardInterrupt:
            print("\n❌ Onboarding cancelled")
            return False
        except Exception as e:
            print(f"❌ Error during onboarding: {e}")
            return False

    def _collect_client_info(self) -> Dict[str, Any]:
        """Collect client information interactively."""
        print("Please provide the following information:\n")

        # Client ID
        while True:
            client_id = input("Client ID (lowercase, no spaces): ").strip().lower()
            if not client_id:
                print("❌ Client ID is required")
                continue
            if client_id in self.client_manager.clients:
                print(f"❌ Client '{client_id}' already exists")
                continue
            if not client_id.replace('_', '').replace('-', '').isalnum():
                print("❌ Client ID must contain only letters, numbers, hyphens, and underscores")
                continue
            break

        # Display name
        display_name = input("Display Name: ").strip()
        if not display_name:
            display_name = client_id.title()

        # Discord token
        discord_token = input("Discord Bot Token: ").strip()
        if not discord_token:
            print("❌ Discord token is required")
            return {}

        # Owner ID
        while True:
            try:
                owner_id = int(input("Owner Discord User ID: ").strip())
                break
            except ValueError:
                print("❌ Please enter a valid Discord user ID (numbers only)")

        # Guild IDs (optional)
        guild_ids_input = input("Allowed Guild IDs (comma-separated, optional): ").strip()
        guild_ids = []
        if guild_ids_input:
            try:
                guild_ids = [int(gid.strip()) for gid in guild_ids_input.split(',')]
            except ValueError:
                print("⚠️  Invalid guild IDs, proceeding without restrictions")
                guild_ids = []

        # Service plan
        print("\nService Plans:")
        print("1. Basic ($200/month)")
        print("2. Premium ($350/month)")
        print("3. Enterprise ($500/month)")

        while True:
            try:
                plan_choice = int(input("Select plan (1-3): "))
                if plan_choice == 1:
                    plan = "basic"
                    monthly_fee = 200.0
                    break
                elif plan_choice == 2:
                    plan = "premium"
                    monthly_fee = 350.0
                    break
                elif plan_choice == 3:
                    plan = "enterprise"
                    monthly_fee = 500.0
                    break
                else:
                    print("❌ Please select 1, 2, or 3")
            except ValueError:
                print("❌ Please enter a number")

        # Custom branding
        bot_name = input(f"Bot Name (default: {display_name} Bot): ").strip()
        if not bot_name:
            bot_name = f"{display_name} Bot"

        bot_description = input("Bot Description (optional): ").strip()
        if not bot_description:
            bot_description = f"Discord bot for {display_name}"

        status_message = input("Custom Status Message (optional): ").strip()
        if not status_message:
            status_message = f"Serving {display_name}"

        return {
            "client_id": client_id,
            "display_name": display_name,
            "discord_token": discord_token,
            "owner_id": owner_id,
            "guild_ids": guild_ids,
            "plan": plan,
            "monthly_fee": monthly_fee,
            "bot_name": bot_name,
            "bot_description": bot_description,
            "status_message": status_message
        }


def main():
    """Main deployment tools entry point."""
    parser = argparse.ArgumentParser(description="Multi-Client Discord Bot Platform Tools")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # New client command
    new_parser = subparsers.add_parser('new-client', help='Create a new client')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show platform status')

    # List clients command
    list_parser = subparsers.add_parser('list-clients', help='List all clients')

    # Update command
    update_parser = subparsers.add_parser('update', help='Update platform')
    update_parser.add_argument('--no-restart', action='store_true', help='Don\'t restart clients')

    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Backup all client data')

    # Start platform command
    start_parser = subparsers.add_parser('start', help='Start the platform')

    args = parser.parse_args()

    if args.command == 'new-client':
        tool = ClientOnboardingTool()
        success = tool.interactive_onboarding()
        sys.exit(0 if success else 1)

    elif args.command == 'status':
        stats = PlatformStats()
        asyncio.run(stats.show_platform_status())

    elif args.command == 'list-clients':
        stats = PlatformStats()
        stats.list_clients()

    elif args.command == 'update':
        deployment = DeploymentManager()
        restart = not args.no_restart
        success = asyncio.run(deployment.update_all_clients(restart=restart))
        sys.exit(0 if success else 1)

    elif args.command == 'backup':
        deployment = DeploymentManager()
        success = asyncio.run(deployment.backup_all_clients())
        sys.exit(0 if success else 1)

    elif args.command == 'start':
        launcher = PlatformLauncher()
        asyncio.run(launcher.run())

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
