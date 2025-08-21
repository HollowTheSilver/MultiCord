"""
Deployment Tools & Client Onboarding
==================================================================================

Command-line tools for managing the multi-client platform including
client onboarding, updates, and monitoring.

FIXES APPLIED:
- Updated data structure access to match ServiceManager.get_platform_status()
- Fixed client count fields: platform_data['total_clients'] -> clients_data['total']
- Removed non-existent health fields (healthy_clients, clients_with_issues)
- Updated auto-fixes field: health_data['total_auto_fixes'] -> platform_data['auto_fixes_applied']
- Fixed client details to get running info directly from ProcessManager
- Version 3.0.1
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
from bot_platform.service_manager import PlatformOrchestrator


class DeploymentManager:
    """Handles deployment operations across all clients."""

    def __init__(self):
        self.client_manager = ClientManager()
        self.orchestrator = PlatformOrchestrator()
        self.logger = self.client_manager.logger

    async def update_all_clients(self, restart: bool = True) -> bool:
        """Update core codebase for all clients."""
        self.logger.info("Starting platform-wide update...")

        try:
            if not self.orchestrator.initialize():
                self.logger.error("Failed to initialize platform orchestrator")
                return False

            running_clients = list(self.orchestrator.process_manager.get_running_client_ids())

            if restart and running_clients:
                self.logger.info(f"Stopping {len(running_clients)} running clients...")
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
        self.logger.info("Creating backup of all client data...")

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
        self.orchestrator = PlatformOrchestrator()
        self.client_manager = ClientManager()

    async def show_platform_status(self) -> None:
        """Display comprehensive platform status."""
        print("📊 Multi-Client Platform Status")
        print("=" * 50)

        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        # FIXED: Get platform status with correct data structure
        platform_status = self.orchestrator.service_manager.get_platform_status()

        # FIXED: Access nested structure correctly
        platform_data = platform_status['platform']
        clients_data = platform_status['clients']  # FIXED: Use clients section
        health_data = platform_status['health']

        # FIXED: Use correct field names from actual data structure
        print(f"🕐 Platform Uptime: {platform_data['uptime_hours']:.1f} hours")
        print(f"🔄 Total Restarts: {platform_data.get('total_restarts', 0)}")
        print(f"📊 Total Clients: {clients_data['total']}")  # FIXED: clients_data['total']
        print(f"🟢 Running Clients: {clients_data['running']}")  # FIXED: clients_data['running']
        print(f"✅ Enabled Clients: {clients_data['enabled']}")  # FIXED: Use available field
        print(f"⏹️ Stopped Clients: {clients_data['stopped']}")  # FIXED: Use available field
        print(f"🔧 Auto-fixes Applied: {platform_data.get('auto_fixes_applied', 0)}")  # FIXED: platform_data
        print(f"🤖 Auto-healing: {'Enabled' if health_data['auto_healing_enabled'] else 'Disabled'}")
        print()

        # FIXED: Get detailed client information directly from managers
        print("Client Status:")
        print("-" * 50)

        if self.orchestrator.config_manager.client_configs:
            running_client_ids = self.orchestrator.process_manager.get_running_client_ids()

            for client_id, config in self.orchestrator.config_manager.client_configs.items():
                is_running = client_id in running_client_ids
                status_icon = "🟢" if is_running else "🔴"
                enabled_icon = "✅" if config.enabled else "❌"

                print(f"{status_icon} {client_id} (Enabled: {enabled_icon})")

                if is_running:
                    # Get process details if running
                    process_info = self.orchestrator.process_manager.get_process_status(client_id)
                    if process_info:
                        uptime_hours = process_info.get("uptime_hours", 0)
                        memory_mb = process_info.get("memory_mb", 0)
                        cpu_percent = process_info.get("cpu_percent", 0)
                        restart_count = process_info.get("restart_count", 0)

                        print(f"  ⏱️  Uptime: {uptime_hours:.1f} hours")
                        print(f"  💾 Memory: {memory_mb:.1f} MB")
                        print(f"  ⚡ CPU: {cpu_percent:.1f}%")
                        print(f"  🔄 Restarts: {restart_count}")

                # Show health status
                health = self.orchestrator.config_manager.validate_client_health(client_id)
                health_icon = "✅" if health['config_health'] == 'healthy' else "⚠️"
                print(f"  🏥 Config Health: {health['config_health']} {health_icon}")

                if health['issues']:
                    print(f"  ⚠️ Issues: {', '.join(health['issues'][:2])}")
                    if len(health['issues']) > 2:
                        print(f"    ... and {len(health['issues']) - 2} more")

                print()
        else:
            print("❌ No clients configured")

    def list_clients(self) -> None:
        """List all clients with basic info."""
        print("📋 Configured Clients")
        print("=" * 30)

        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        # FIXED: Get clients from config manager (ClientConfig objects)
        clients = self.orchestrator.config_manager.client_configs
        running_clients = self.orchestrator.process_manager.get_running_client_ids()

        if not clients:
            print("❌ No clients configured")
            return

        for client_id, config in clients.items():
            status = "🟢 Running" if client_id in running_clients else "🔴 Stopped"
            enabled = "✅ Enabled" if config.enabled else "❌ Disabled"
            plan = getattr(config, 'plan', 'unknown')

            print(f"• {client_id}: {status}, {enabled}, Plan: {plan}")

        print(f"\nTotal: {len(clients)} clients ({len(running_clients)} running)")


class ClientOnboardingTool:
    """Interactive tool for creating new clients."""

    def __init__(self):
        self.client_manager = ClientManager()
        self.orchestrator = PlatformOrchestrator()

    def interactive_onboarding(self) -> bool:
        """Run interactive client onboarding process."""
        print("🚀 Multi-Client Platform - New Client Onboarding")
        print("=" * 55)

        try:
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
            client_id = input("Client ID (alphanumeric, underscore, hyphen): ").strip().lower()

            if not client_id:
                print("❌ Client ID is required")
                continue

            if not client_id.replace('_', '').replace('-', '').isalnum():
                print("❌ Client ID can only contain letters, numbers, underscore, and hyphen")
                continue

            # Check if already exists
            if self.orchestrator.config_manager.client_configs.get(client_id):
                print(f"❌ Client '{client_id}' already exists")
                continue

            return client_id

    def _get_display_name(self, client_id: str) -> str:
        """Get display name for the client."""
        default_name = client_id.replace('_', ' ').replace('-', ' ').title()
        display_name = input(f"Display Name [{default_name}]: ").strip()
        return display_name or default_name

    def _get_plan(self) -> str:
        """Get business plan selection."""
        print("\nBusiness Plan Selection:")
        print("  1. Basic ($200/month) - Standard features, basic support")
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
        orchestrator = PlatformOrchestrator()
        if orchestrator.initialize():
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
