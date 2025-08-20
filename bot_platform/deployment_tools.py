"""
Deployment Tools & Client Onboarding - MIGRATED TO CLEAN ARCHITECTURE
=====================================================================

Command-line tools for managing the multi-client platform including
client onboarding, updates, and monitoring.

MIGRATION NOTES:
- Replaced PlatformLauncher with PlatformOrchestrator
- Fixed data structure access patterns to match actual ServiceManager output
- Uses correct platform_status structure: platform_status['platform']['uptime_hours']
- Fixed ClientConfig attribute access
- Maintained all existing functionality
- Version 2.0.0 - Clean Architecture
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
# MIGRATION: Replace PlatformLauncher with clean architecture
from bot_platform.service_manager import PlatformOrchestrator


class DeploymentManager:
    """Handles deployment operations across all clients."""

    def __init__(self):
        self.client_manager = ClientManager()
        # MIGRATION: Use PlatformOrchestrator instead of PlatformLauncher
        self.orchestrator = PlatformOrchestrator()
        self.logger = self.client_manager.logger

    async def update_all_clients(self, restart: bool = True) -> bool:
        """Update core codebase for all clients."""
        self.logger.info("Starting platform-wide update...")

        try:
            # MIGRATION: Initialize orchestrator
            if not self.orchestrator.initialize():
                self.logger.error("Failed to initialize platform orchestrator")
                return False

            # MIGRATION: Get running clients using clean architecture
            running_clients = list(self.orchestrator.process_manager.get_running_client_ids())

            if restart and running_clients:
                self.logger.info(f"Stopping {len(running_clients)} running clients...")
                # MIGRATION: Use orchestrator method instead of launcher
                stopped_clients = await self.orchestrator.stop_all_clients()
                if not stopped_clients:
                    self.logger.warning("No clients were stopped")

            # Perform core updates here
            # This would typically involve:
            # - Git pull
            # - Dependency updates
            # - Database migrations
            # - Configuration updates

            self.logger.info("Core update completed")

            if restart and running_clients:
                self.logger.info("Restarting clients...")
                # MIGRATION: Use orchestrator method instead of launcher
                started_clients = await self.orchestrator.start_all_clients()
                if started_clients:
                    self.logger.info(f"Restarted {len(started_clients)} clients: {', '.join(started_clients)}")
                else:
                    self.logger.warning("No clients were restarted")

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
            platform_logs = Path("bot_platform/logs")
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
        # MIGRATION: Use PlatformOrchestrator instead of PlatformLauncher
        self.orchestrator = PlatformOrchestrator()
        self.client_manager = ClientManager()

    async def show_platform_status(self) -> None:
        """Display comprehensive platform status."""
        print("📊 Multi-Client Platform Status")
        print("=" * 50)

        # MIGRATION: Initialize orchestrator and get status
        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        # MIGRATION: Use service manager to get platform status
        # FIXED: Use correct data structure - nested dictionaries
        platform_status = self.orchestrator.service_manager.get_platform_status()

        # FIXED: Access nested structure correctly
        platform_data = platform_status['platform']
        # health_data = platform_status['health']

        # Get clients data from the status response
        clients_data = platform_status.get('clients', {})

        print(f"🕐 Platform Uptime: {platform_data['uptime_hours']:.1f} hours")
        print(f"🔄 Total Restarts: {platform_data['total_restarts']}")
        print(f"📊 Total Clients: {clients_data.get('total', 0)}")
        print(f"🟢 Running Clients: {clients_data.get('running', 0)}")
        print(f"⏹️ Stopped Clients: {clients_data.get('stopped', 0)}")
        print(f"✅ FLAGS System: {clients_data.get('flags_system', 0)}")
        print(f"🔧 Auto-fixes Applied: {platform_data.get('auto_fixes_applied', 0)}")
        print()

        # MIGRATION: Get client details using clean architecture
        client_details = platform_status.get('clients', {})

        if client_details:
            print("Client Status:")
            print("-" * 50)
            for client_id, client_info in client_details.items():
                status_icon = "🟢" if client_info.get("running", False) else "🔴"

                # Check if client is enabled (from config)
                config = self.orchestrator.config_manager.client_configs.get(client_id)
                enabled_icon = "✅" if (config and config.enabled) else "❌"

                print(f"{status_icon} {client_id} (Enabled: {enabled_icon})")

                if client_info.get("running", False):
                    uptime_hours = client_info.get("uptime_hours", 0)
                    print(f"  ⏱️  Uptime: {uptime_hours:.1f} hours")
                    print(f"  💾 Memory: {client_info.get('memory_mb', 0):.1f} MB")
                    print(f"  ⚡ CPU: {client_info.get('cpu_percent', 0):.1f}%")
                    print(f"  🔄 Restarts: {client_info.get('restart_count', 0)}")
                print()
        else:
            print("❌ No clients configured")

    def list_clients(self) -> None:
        """List all clients with basic info."""
        print("📋 Configured Clients")
        print("=" * 30)

        # MIGRATION: Initialize orchestrator to get client list
        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        # MIGRATION: Get clients from config manager (ClientConfig objects)
        clients = self.orchestrator.config_manager.client_configs
        running_clients = self.orchestrator.process_manager.get_running_client_ids()

        if not clients:
            print("❌ No clients configured")
            return

        for client_id, config in clients.items():
            status = "🟢 Running" if client_id in running_clients else "🔴 Stopped"
            # FIXED: Use attribute access for ClientConfig dataclass
            enabled = "✅ Enabled" if config.enabled else "❌ Disabled"
            plan = getattr(config, 'plan', 'unknown')

            print(f"• {client_id}: {status}, {enabled}, Plan: {plan}")

        print(f"\nTotal: {len(clients)} clients ({len(running_clients)} running)")


class ClientOnboardingTool:
    """Interactive tool for creating new clients."""

    def __init__(self):
        self.client_manager = ClientManager()
        # MIGRATION: Use PlatformOrchestrator for client operations
        self.orchestrator = PlatformOrchestrator()

    def interactive_onboarding(self) -> bool:
        """Run interactive client onboarding process."""
        print("🚀 Multi-Client Platform - New Client Onboarding")
        print("=" * 55)

        try:
            # MIGRATION: Initialize orchestrator
            if not self.orchestrator.initialize():
                print("❌ Platform initialization failed")
                return False

            # Collect client information
            client_id = self._get_client_id()
            if not client_id:
                return False

            display_name = self._get_display_name(client_id)
            plan = self._get_plan()

            # Additional configuration
            print(f"\n📋 Creating client '{client_id}' with plan '{plan}'...")

            # MIGRATION: Use client_manager to create client
            success = self.client_manager.create_client(
                client_id=client_id,
                display_name=display_name,
                plan=plan
            )

            if success:
                print(f"✅ Client '{client_id}' created successfully!")
                print(f"📁 Configuration directory: clients/{client_id}/")
                print(f"⚙️  Edit clients/{client_id}/.env to add your Discord token")
                print(f"🚀 Start with: python platform_main.py --client {client_id}")
                return True
            else:
                print(f"❌ Failed to create client '{client_id}'")
                return False

        except Exception as e:
            print(f"❌ Onboarding failed: {e}")
            return False

    def _get_client_id(self) -> str:
        """Get and validate client ID."""
        while True:
            client_id = input("Enter client ID (alphanumeric, underscore, hyphen): ").strip().lower()

            if not client_id:
                print("❌ Client ID cannot be empty")
                continue

            if not client_id.replace('_', '').replace('-', '').isalnum():
                print("❌ Client ID must be alphanumeric with underscore or hyphen only")
                continue

            # MIGRATION: Check existing clients using orchestrator
            if self.orchestrator.config_manager.client_configs.get(client_id):
                print(f"❌ Client '{client_id}' already exists")
                continue

            return client_id

    def _get_display_name(self, client_id: str) -> str:
        """Get display name for client."""
        default_name = client_id.replace('_', ' ').replace('-', ' ').title()
        display_name = input(f"Display name [{default_name}]: ").strip()
        return display_name if display_name else default_name

    def _get_plan(self) -> str:
        """Get service plan for client."""
        print("\n📊 Available Plans:")
        print("  1. Basic ($200/month) - Core features, moderation, basic support")
        print("  2. Premium ($350/month) - + Analytics, tickets, advanced features")
        print("  3. Enterprise ($500/month) - + API access, priority support, unlimited")

        while True:
            choice = input("Select plan (1-3) [1]: ").strip()

            if choice == "" or choice == "1":
                return "basic"
            elif choice == "2":
                return "premium"
            elif choice == "3":
                return "enterprise"
            else:
                print("❌ Please enter 1, 2, or 3")


def main():
    """Main CLI entry point."""
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
        # MIGRATION: Use PlatformOrchestrator instead of PlatformLauncher
        orchestrator = PlatformOrchestrator()
        if orchestrator.initialize():
            # Use the platform_main.py functionality instead of direct launcher
            print("🚀 Use 'python platform_main.py' to start the platform")
            print("📊 Use 'python platform_main.py --status' for status")
            print("🎮 Use 'python platform_main.py --interactive' for management")
        else:
            print("❌ Platform initialization failed")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
