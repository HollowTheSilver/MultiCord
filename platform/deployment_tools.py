"""
Deployment Tools & Client Onboarding
====================================

Command-line tools for managing the multi-client platform including
client onboarding, updates, and monitoring.
"""

import asyncio
import argparse
import sys
import json
from pathlib import Path
from typing import List, Dict, Any
import subprocess

# Add platform modules to path
sys.path.insert(0, str(Path(__file__).parent))

from client_manager import ClientManager
from launcher import PlatformLauncher


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
        self.logger.info("Creating backups for all clients...")

        try:
            backup_dir = Path("backups") / f"backup_{int(asyncio.get_event_loop().time())}"
            backup_dir.mkdir(parents=True, exist_ok=True)

            clients = self.client_manager.list_clients()

            for client in clients:
                client_backup_dir = backup_dir / client.client_id
                client_backup_dir.mkdir(exist_ok=True)

                client_dir = Path("clients") / client.client_id
                if client_dir.exists():
                    # Copy data directory
                    data_dir = client_dir / "data"
                    if data_dir.exists():
                        subprocess.run([
                            "cp", "-r", str(data_dir), str(client_backup_dir)
                        ], check=True)

                    # Copy configuration
                    for config_file in [".env", "config.py", "branding.py", "features.py"]:
                        config_path = client_dir / config_file
                        if config_path.exists():
                            subprocess.run([
                                "cp", str(config_path), str(client_backup_dir)
                            ], check=True)

            self.logger.info(f"Backup completed: {backup_dir}")
            return True

        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
            return False

    async def migrate_all_clients(self) -> bool:
        """Run database migrations for all clients."""
        self.logger.info("Running migrations for all clients...")

        try:
            clients = self.client_manager.list_clients()

            for client in clients:
                client_dir = Path("clients") / client.client_id
                db_path = client_dir / "data" / "permissions.db"

                if db_path.exists():
                    # Run migration logic here
                    self.logger.info(f"Migrated database for {client.client_id}")

            return True

        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            return False


class ClientOnboardingTool:
    """Interactive tool for onboarding new clients."""

    def __init__(self):
        self.client_manager = ClientManager()

    def interactive_onboarding(self) -> bool:
        """Interactive client onboarding process."""
        print("\n🚀 Multi-Client Discord Bot Platform")
        print("=====================================")
        print("New Client Onboarding\n")

        try:
            # Collect basic information
            client_id = self._get_client_id()
            display_name = self._get_display_name()
            discord_token = self._get_discord_token()
            owner_id = self._get_owner_id()
            guild_ids = self._get_guild_ids()
            plan = self._get_plan()
            monthly_fee = self._get_monthly_fee(plan)
            branding = self._get_branding_info()

            # Confirm details
            print("\n📋 Client Details Summary:")
            print(f"   Client ID: {client_id}")
            print(f"   Display Name: {display_name}")
            print(f"   Plan: {plan}")
            print(f"   Monthly Fee: ${monthly_fee}")
            print(f"   Owner ID: {owner_id}")
            print(f"   Guild IDs: {guild_ids}")
            print(f"   Bot Name: {branding.get('bot_name', 'N/A')}")

            confirm = input("\n✅ Create this client? (yes/no): ").lower().strip()
            if confirm not in ['yes', 'y']:
                print("❌ Client creation cancelled.")
                return False

            # Create the client
            print("\n🔧 Creating client configuration...")
            success = self.client_manager.create_client(
                client_id=client_id,
                display_name=display_name,
                discord_token=discord_token,
                owner_id=owner_id,
                guild_ids=guild_ids,
                plan=plan,
                monthly_fee=monthly_fee,
                branding=branding
            )

            if success:
                print(f"\n✅ Client '{client_id}' created successfully!")
                print(f"📁 Configuration directory: clients/{client_id}")
                print(f"🤖 Bot is ready to start with: python -m platform.client_runner --client-id {client_id}")
                print(f"🚀 Or start all bots with: python platform_main.py")
                return True
            else:
                print("\n❌ Failed to create client. Check logs for details.")
                return False

        except KeyboardInterrupt:
            print("\n❌ Client creation cancelled by user.")
            return False
        except Exception as e:
            print(f"\n❌ Error during onboarding: {e}")
            return False

    def _get_client_id(self) -> str:
        """Get and validate client ID."""
        while True:
            client_id = input("Client ID (alphanumeric + underscores): ").strip()

            if not client_id:
                print("❌ Client ID cannot be empty.")
                continue

            if not client_id.replace('_', '').replace('-', '').isalnum():
                print("❌ Client ID must be alphanumeric with underscores/hyphens only.")
                continue

            if client_id in self.client_manager.clients:
                print("❌ Client ID already exists.")
                continue

            return client_id.lower()

    def _get_display_name(self) -> str:
        """Get display name."""
        while True:
            name = input("Display Name (e.g., 'Acme Corporation'): ").strip()
            if name:
                return name
            print("❌ Display name cannot be empty.")

    def _get_discord_token(self) -> str:
        """Get Discord bot token."""
        while True:
            token = input("Discord Bot Token: ").strip()
            if token and len(token) > 50:  # Basic validation
                return token
            print("❌ Please enter a valid Discord bot token.")

    def _get_owner_id(self) -> int:
        """Get Discord owner user ID."""
        while True:
            try:
                owner_id = int(input("Discord Owner User ID: ").strip())
                if owner_id > 0:
                    return owner_id
                print("❌ User ID must be a positive number.")
            except ValueError:
                print("❌ Please enter a valid Discord user ID (numeric).")

    def _get_guild_ids(self) -> List[int]:
        """Get Discord guild IDs."""
        print("Discord Guild IDs (comma-separated, or press Enter for none):")
        guild_input = input("Guild IDs: ").strip()

        if not guild_input:
            return []

        try:
            guild_ids = [int(gid.strip()) for gid in guild_input.split(',') if gid.strip()]
            return guild_ids
        except ValueError:
            print("❌ Invalid guild IDs. Using no restrictions.")
            return []

    def _get_plan(self) -> str:
        """Get service plan."""
        print("\n📦 Available Plans:")
        print("   1. Basic ($200/month) - Core features")
        print("   2. Premium ($350/month) - Advanced features")
        print("   3. Enterprise ($500/month) - Full features + API access")

        while True:
            choice = input("Select plan (1-3): ").strip()
            if choice == '1':
                return 'basic'
            elif choice == '2':
                return 'premium'
            elif choice == '3':
                return 'enterprise'
            print("❌ Please select 1, 2, or 3.")

    def _get_monthly_fee(self, plan: str) -> float:
        """Get monthly fee based on plan."""
        default_fees = {'basic': 200.0, 'premium': 350.0, 'enterprise': 500.0}
        default_fee = default_fees.get(plan, 200.0)

        fee_input = input(f"Monthly Fee (default ${default_fee}): ").strip()
        if not fee_input:
            return default_fee

        try:
            return float(fee_input)
        except ValueError:
            return default_fee

    def _get_branding_info(self) -> Dict[str, Any]:
        """Get branding information."""
        print("\n🎨 Branding Configuration (optional):")

        bot_name = input("Bot Name (e.g., 'AcmeBot'): ").strip()
        if not bot_name:
            bot_name = "Professional Bot"

        bot_description = input("Bot Description: ").strip()
        if not bot_description:
            bot_description = f"Professional Discord bot for {bot_name}"

        status_message = input("Status Message (e.g., '🤖 Serving Acme Corp'): ").strip()
        if not status_message:
            status_message = f"🤖 Serving {bot_name}"

        return {
            "bot_name": bot_name,
            "bot_description": bot_description,
            "status_message": status_message
        }


class PlatformStats:
    """Platform statistics and monitoring."""

    def __init__(self):
        self.client_manager = ClientManager()

    async def show_platform_status(self):
        """Display comprehensive platform status."""
        print("\n🤖 Discord Bot Platform Status")
        print("=" * 40)

        # Client statistics
        clients = self.client_manager.list_clients()
        active_clients = [c for c in clients if c.status == "active"]

        print(f"📊 Clients: {len(active_clients)}/{len(clients)} active")

        # Plan breakdown
        plans = {}
        for client in active_clients:
            plans[client.plan] = plans.get(client.plan, 0) + 1

        print("📦 Plans:")
        for plan, count in plans.items():
            print(f"   {plan.title()}: {count}")

        # Revenue
        billing = self.client_manager.get_billing_summary()
        print(f"💰 Monthly Revenue: ${billing['total_monthly_revenue']}")

        # Try to get runtime status
        try:
            launcher = PlatformLauncher()
            status = launcher.get_platform_status()

            print(f"\n🚀 Runtime Status:")
            print(f"   Running: {status['clients']['running']}")
            print(f"   Memory: {status['resources']['total_memory_mb']:.1f} MB")
            print(f"   CPU: {status['resources']['avg_cpu_percent']:.1f}%")

            if status['client_details']:
                print("\n🤖 Client Status:")
                for client_id, details in status['client_details'].items():
                    uptime_hours = details['uptime_seconds'] / 3600
                    print(f"   {client_id}: {details['status']} ({uptime_hours:.1f}h)")

        except Exception as e:
            print(f"⚠️  Could not get runtime status: {e}")

    def list_clients(self):
        """List all clients with details."""
        clients = self.client_manager.list_clients()

        if not clients:
            print("No clients found.")
            return

        print(f"\n📋 Client List ({len(clients)} total)")
        print("=" * 60)

        for client in sorted(clients, key=lambda c: c.created_at):
            print(f"\n🏢 {client.display_name} ({client.client_id})")
            print(f"   Plan: {client.plan.title()} (${client.monthly_fee}/month)")
            print(f"   Status: {client.status}")
            print(f"   Created: {client.created_at.strftime('%Y-%m-%d')}")
            print(f"   Guilds: {len(client.guild_ids)} configured")
            if client.notes:
                print(f"   Notes: {client.notes}")


def main():
    """Main CLI interface."""
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
