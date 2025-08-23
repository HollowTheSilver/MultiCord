#!/usr/bin/env python3
"""
Platform Main Entry Point
=======================================================================

Multi-client Discord bot platform with clean, professional architecture.
Uses dependency injection and separation of concerns.

FIXES APPLIED:
- Updated data structure access to match ServiceManager.get_platform_status()
- Fixed client count fields: platform_stats['total_clients'] -> clients_stats['total']
- Removed non-existent health fields (healthy_clients, clients_with_issues)
- Updated auto-fixes field: health_stats['total_auto_fixes'] -> platform_stats['auto_fixes_applied']
- Fixed client details to get running info directly from ProcessManager
- Added proper health status display for each client

Usage:
    python platform_main.py                    # Start all enabled clients
    python platform_main.py --client alpha     # Start specific client only
    python platform_main.py --status          # Show platform status
    python platform_main.py --interactive     # Interactive management mode

Author: HollowTheSilver
Version: 3.0.1
"""

import asyncio
import argparse
import signal
import sys
from pathlib import Path
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from bot_platform.process_manager import ProcessManager
from bot_platform.config_manager import ConfigManager
from bot_platform.service_manager import ServiceManager, PlatformOrchestrator


class PlatformMain:
    """Main platform controller with clean architecture."""

    def __init__(self, orchestrator: PlatformOrchestrator):
        """Initialize with dependency injection."""
        self.orchestrator = orchestrator
        self.running = False

    async def start_platform(self, client_filter: Optional[str] = None) -> None:
        """Start the platform with optional client filtering."""
        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        if client_filter:
            print(f"🚀 Starting single client: {client_filter}")
            success = self.orchestrator.start_client(client_filter)
            if success:
                print(f"✅ Client {client_filter} started successfully")
                # Run client in foreground
                await self._monitor_single_client(client_filter)
            else:
                print(f"❌ Failed to start client {client_filter}")
        else:
            print("🚀 Starting Multi-Client Platform")
            started_clients = await self.orchestrator.start_all_clients()
            if started_clients:
                print(f"✅ Started {len(started_clients)} clients: {', '.join(started_clients)}")
                await self._monitor_platform()
            else:
                print("❌ No clients were started")

    async def _monitor_single_client(self, client_id: str) -> None:
        """Monitor a single client until stopped."""
        self.running = True
        self._setup_signal_handlers()

        print(f"📊 Monitoring {client_id} (Ctrl+C to stop)")

        while self.running:
            if client_id not in self.orchestrator.process_manager.get_running_client_ids():
                print(f"❌ Client {client_id} has stopped")
                break
            await asyncio.sleep(5)

        print(f"👋 Stopped monitoring {client_id}")

    async def _monitor_platform(self) -> None:
        """Monitor the entire platform."""
        self.running = True
        self._setup_signal_handlers()

        print("📊 Platform monitoring active (Ctrl+C to stop)")

        while self.running:
            await asyncio.sleep(30)  # Check every 30 seconds
            # Auto-healing runs in ServiceManager

        print("👋 Platform monitoring stopped")

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown signal handlers."""

        def signal_handler(signum, frame):
            print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def show_status(self) -> None:
        """Display comprehensive platform status."""
        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        print("📊 Multi-Client Platform Status")
        print("=" * 50)

        # FIXED: Get status from orchestrator
        status = self.orchestrator.get_status()

        if 'error' in status:
            print(f"❌ {status['error']}")
            return

        # FIXED: Access nested structure correctly
        platform_stats = status["platform"]
        clients_stats = status["clients"]  # FIXED: Use clients section
        health_stats = status["health"]

        # FIXED: Use correct field names from actual data structure
        print(f"🕐 Platform Uptime: {platform_stats['uptime_hours']:.1f} hours")
        print(f"🔄 Total Restarts: {platform_stats['total_restarts']}")
        print(f"📊 Total Clients: {clients_stats['total']}")  # FIXED: clients_stats['total']
        print(f"🟢 Running Clients: {clients_stats['running']}")  # FIXED: clients_stats['running']
        print(f"✅ Enabled Clients: {clients_stats['enabled']}")  # FIXED: Use available field
        print(f"⏹️ Stopped Clients: {clients_stats['stopped']}")  # FIXED: Use available field
        print(f"🔧 Auto-fixes Applied: {platform_stats.get('auto_fixes_applied', 0)}")  # FIXED: platform_stats
        print(f"🤖 Auto-healing: {'Enabled' if health_stats['auto_healing_enabled'] else 'Disabled'}")
        print()

        # FIXED: Get detailed client information directly from managers
        if self.orchestrator.config_manager.client_configs:
            print("Detailed Client Status:")
            print("-" * 50)

            running_client_ids = self.orchestrator.process_manager.get_running_client_ids()

            for client_id, config in self.orchestrator.config_manager.client_configs.items():
                is_running = client_id in running_client_ids

                if is_running:
                    status_icon = "🟢"
                    process_info = self.orchestrator.process_manager.get_process_status(client_id)

                    if process_info:
                        pid = process_info.get('pid', 'unknown')
                        uptime = process_info.get('uptime_hours', 0)
                        memory = process_info.get('memory_mb', 0)
                        cpu = process_info.get('cpu_percent', 0)
                        source = process_info.get('source', 'unknown')
                        restart_count = process_info.get('restart_count', 0)

                        print(
                            f"{status_icon} {client_id}: RUNNING (PID: {pid}) • Uptime: {uptime:.1f}h • Source: {source}")
                        print(f"   💾 Memory: {memory:.1f} MB • ⚡ CPU: {cpu:.1f}% • 🔄 Restarts: {restart_count}")
                    else:
                        print(f"{status_icon} {client_id}: RUNNING (process info unavailable)")
                else:
                    status_icon = "🔴"
                    status_reason = "Not running"
                    enabled_status = "Enabled" if config.enabled else "Disabled"
                    print(f"{status_icon} {client_id}: STOPPED ({status_reason}) • {enabled_status}")

                # FIXED: Show health indicator
                health = self.orchestrator.config_manager.validate_client_health(client_id)
                health_icon = "✅" if health['config_health'] == 'healthy' else "⚠️"
                print(f"   🏥 Config Health: {health['config_health']} {health_icon}")

                # Show issues if any
                if health['issues']:
                    print(f"   ⚠️ Issues ({len(health['issues'])}):")
                    for issue in health['issues'][:3]:
                        print(f"      • {issue}")
                    if len(health['issues']) > 3:
                        print(f"      • ... and {len(health['issues']) - 3} more")

                print()

        else:
            print("❌ No clients configured")

        print("-" * 50)
        print("💡 Use --interactive for management options")

    async def interactive_mode(self) -> None:
        """Run interactive management console."""
        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        print("🎮 Interactive Platform Management")
        print("=" * 40)

        self.running = True
        self._setup_signal_handlers()

        while self.running:
            print("\nOptions:")
            print("  1. Show status")
            print("  2. Start client")
            print("  3. Stop client")
            print("  4. Restart client")
            print("  5. Start all clients")
            print("  6. Stop all clients")
            print("  7. Create new client")
            print("  8. Delete client")
            print("  9. Run diagnostics")
            print("  0. Exit management console")

            try:
                choice = input("\nSelect option (0-9): ").strip()

                if choice == "1":
                    await self.show_status()
                elif choice == "2":
                    await self._start_client_interactive()
                elif choice == "3":
                    await self._stop_client_interactive()
                elif choice == "4":
                    await self._restart_client_interactive()
                elif choice == "5":
                    await self._start_all_interactive()
                elif choice == "6":
                    await self._stop_all_interactive()
                elif choice == "7":
                    await self._create_client_interactive()
                elif choice == "8":
                    await self._delete_client_interactive()
                elif choice == "9":
                    await self._run_diagnostics()
                elif choice == "0":
                    print("👋 Exiting management console...")
                    self.running = False
                    break
                else:
                    print("❌ Invalid option. Please choose 0-9.")

            except (KeyboardInterrupt, EOFError):
                print("\n👋 Exiting management console...")
                print("✅ All running clients will continue running independently")
                self.running = False
                break
            except Exception as e:
                print(f"❌ Error: {e}")

        print("📋 Management console closed. Use 'python platform_main.py --status' to check client status.")

    async def _start_client_interactive(self) -> None:
        """Start a client interactively and exit console (terminal becomes occupied)."""
        clients = list(self.orchestrator.config_manager.client_configs.keys())
        if not clients:
            print("❌ No clients configured.")
            return

        print("\nAvailable Clients:")
        running_ids = self.orchestrator.process_manager.get_running_client_ids()

        for i, client_id in enumerate(clients, 1):
            status = "🟢 Running" if client_id in running_ids else "🔴 Stopped"
            print(f"  {i}. {client_id} ({status})")

        try:
            choice = int(input(f"Select client (1-{len(clients)}): "))
            if 1 <= choice <= len(clients):
                client_id = clients[choice - 1]
                print(f"🚀 Starting {client_id}...")
                success = self.orchestrator.start_client(client_id)
                if success:
                    print(f"✅ {client_id} started successfully")
                    print("\n" + "─" * 60)
                    print("📋 Interactive console closing - terminal now monitoring client")
                    print("💡 Open a new terminal for additional management:")
                    print("   python platform_main.py --interactive")
                    print("   python platform_main.py --status")
                    print("─" * 60)
                    # Exit interactive mode - terminal is now occupied by client process
                    self.running = False
                else:
                    print(f"❌ Failed to start {client_id}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a valid number.")

    async def _stop_client_interactive(self) -> None:
        """Stop a client interactively."""
        running_clients = list(self.orchestrator.process_manager.get_running_client_ids())
        if not running_clients:
            print("❌ No clients are currently running.")
            return

        print("\nRunning Clients:")
        for i, client_id in enumerate(running_clients, 1):
            print(f"  {i}. {client_id}")

        try:
            choice = int(input(f"Select client to stop (1-{len(running_clients)}): "))
            if 1 <= choice <= len(running_clients):
                client_id = running_clients[choice - 1]
                print(f"🛑 Stopping {client_id}...")
                success = self.orchestrator.stop_client(client_id)
                if success:
                    print(f"✅ {client_id} stopped successfully")
                else:
                    print(f"❌ Failed to stop {client_id}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a valid number.")

    async def _restart_client_interactive(self) -> None:
        """Restart a client interactively and exit console (terminal becomes occupied)."""
        clients = list(self.orchestrator.config_manager.client_configs.keys())
        if not clients:
            print("❌ No clients configured.")
            return

        print("\nConfigured Clients:")
        running_ids = self.orchestrator.process_manager.get_running_client_ids()

        for i, client_id in enumerate(clients, 1):
            status = "🟢 Running" if client_id in running_ids else "🔴 Stopped"
            print(f"  {i}. {client_id} ({status})")

        try:
            choice = int(input(f"Select client to restart (1-{len(clients)}): "))
            if 1 <= choice <= len(clients):
                client_id = clients[choice - 1]
                print(f"🔄 Restarting {client_id}...")
                success = self.orchestrator.restart_client(client_id)
                if success:
                    print(f"✅ {client_id} restarted successfully")
                    print("\n" + "─" * 60)
                    print("📋 Interactive console closing - terminal now monitoring client")
                    print("💡 Open a new terminal for additional management:")
                    print("   python platform_main.py --interactive")
                    print("   python platform_main.py --status")
                    print("─" * 60)
                    # Exit interactive mode - terminal is now occupied by client process
                    self.running = False
                else:
                    print(f"❌ Failed to restart {client_id}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a valid number.")

    async def _start_all_interactive(self) -> None:
        """Start all enabled clients and exit console (terminal becomes occupied)."""
        print("🚀 Starting all enabled clients...")
        started = await self.orchestrator.start_all_clients()

        if started:
            print(f"✅ Started {len(started)} clients: {', '.join(started)}")
            print("\n" + "─" * 60)
            print("📋 Interactive console closing - terminal now monitoring clients")
            print("💡 Open a new terminal for additional management:")
            print("   python platform_main.py --interactive")
            print("   python platform_main.py --status")
            print("─" * 60)
            # Exit interactive mode - terminal is now occupied by client processes
            self.running = False
        else:
            print("❌ No clients were started")

    async def _stop_all_interactive(self) -> None:
        """Stop all running clients."""
        print("🛑 Stopping all running clients...")
        stopped = await self.orchestrator.stop_all_clients()
        if stopped:
            print(f"✅ Stopped {len(stopped)} clients: {', '.join(stopped)}")
        else:
            print("ℹ️ No clients were running")

    async def _create_client_interactive(self) -> None:
        """Create a new client interactively."""
        print("🆕 Creating a new client...")

        client_id = input("Client ID (alphanumeric, underscore, hyphen): ").strip().lower()
        if not client_id:
            print("❌ Client ID is required.")
            return

        if client_id in self.orchestrator.config_manager.client_configs:
            print("❌ Client already exists.")
            return

        display_name = input(f"Display Name [{client_id.title()}]: ").strip()
        if not display_name:
            display_name = client_id.title()

        print("\nBusiness Plan:")
        print("  1. Basic ($200/month)")
        print("  2. Premium ($350/month)")
        print("  3. Enterprise ($500/month)")

        plan_choice = input("Select plan (1-3) [1]: ").strip() or "1"
        plan_map = {"1": "basic", "2": "premium", "3": "enterprise"}
        plan = plan_map.get(plan_choice, "basic")

        print(f"\n📋 Creating client '{client_id}' with plan '{plan}'...")

        # Use ClientManager to create the client
        from bot_platform.client_manager import ClientManager
        client_manager = ClientManager()

        success = client_manager.create_client(
            client_id=client_id,
            display_name=display_name,
            plan=plan
        )

        if success:
            print(f"✅ Client '{client_id}' created successfully!")
            print(f"📁 Configuration directory: clients/{client_id}/")
            print(f"⚙️  Edit clients/{client_id}/.env to add your Discord token")
        else:
            print(f"❌ Failed to create client '{client_id}'")

    async def _delete_client_interactive(self) -> None:
        """Delete a client interactively."""
        clients = list(self.orchestrator.config_manager.client_configs.keys())
        if not clients:
            print("❌ No clients configured.")
            return

        print("\nConfigured Clients:")
        for i, client_id in enumerate(clients, 1):
            print(f"  {i}. {client_id}")

        try:
            choice = int(input(f"Select client to delete (1-{len(clients)}): "))
            if 1 <= choice <= len(clients):
                client_id = clients[choice - 1]

                # Confirm deletion
                confirm = input(f"⚠️ Delete client '{client_id}' permanently? (yes/no): ").strip().lower()
                if confirm == "yes":
                    # Stop client if running
                    if client_id in self.orchestrator.process_manager.get_running_client_ids():
                        print(f"🛑 Stopping {client_id} first...")
                        self.orchestrator.stop_client(client_id)

                    # Use ClientManager to delete
                    from bot_platform.client_manager import ClientManager
                    client_manager = ClientManager()

                    success = client_manager.delete_client(client_id)
                    if success:
                        print(f"✅ Client '{client_id}' deleted successfully")
                    else:
                        print(f"❌ Failed to delete client '{client_id}'")
                else:
                    print("❌ Deletion cancelled")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a valid number.")

    async def _run_diagnostics(self) -> None:
        """Run platform diagnostics."""
        print("🔍 Running platform diagnostics...")

        # Basic health checks
        status = self.orchestrator.get_status()

        print("\n📊 Diagnostic Results:")
        print(f"✅ Platform initialized: {self.orchestrator.initialized}")
        print(f"✅ Config manager loaded: {len(self.orchestrator.config_manager.client_configs)} clients")
        print(f"✅ Process manager active: {len(self.orchestrator.process_manager.get_running_client_ids())} running")

        # Check for issues
        issues = []
        for client_id, config in self.orchestrator.config_manager.client_configs.items():
            health = self.orchestrator.config_manager.validate_client_health(client_id)
            if health['config_health'] != 'healthy':
                issues.extend([f"{client_id}: {issue}" for issue in health['issues']])

        if issues:
            print(f"\n⚠️ Found {len(issues)} configuration issues:")
            for issue in issues[:5]:
                print(f"  • {issue}")
            if len(issues) > 5:
                print(f"  • ... and {len(issues) - 5} more")
        else:
            print("\n✅ No configuration issues found")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Multi-Client Discord Bot Platform")
    parser.add_argument('--client', help='Start specific client only')
    parser.add_argument('--status', action='store_true', help='Show platform status and exit')
    parser.add_argument('--interactive', action='store_true', help='Interactive management mode')

    args = parser.parse_args()

    # Initialize platform
    orchestrator = PlatformOrchestrator()
    platform = PlatformMain(orchestrator)

    try:
        if args.status:
            await platform.show_status()
        elif args.interactive:
            await platform.interactive_mode()
        else:
            await platform.start_platform(args.client)
    except KeyboardInterrupt:
        print("\n👋 Shutdown complete")
    except Exception as e:
        print(f"❌ Platform error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
