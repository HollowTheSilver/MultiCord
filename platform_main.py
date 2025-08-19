#!/usr/bin/env python3
"""
Platform Main Entry Point - Clean Architecture
==============================================

Multi-client Discord bot platform with clean, professional architecture.
Uses dependency injection and separation of concerns.

Usage:
    python platform_main.py                    # Start all enabled clients
    python platform_main.py --client alpha     # Start specific client only
    python platform_main.py --status          # Show platform status
    python platform_main.py --interactive     # Interactive management mode

Author: HollowTheSilver
Version: 3.0.0 - Clean Architecture
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
        print("🚀 Starting Multi-Client Discord Bot Platform")
        print("=" * 50)

        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        try:
            if client_filter:
                # Start specific client only
                if client_filter in self.orchestrator.config_manager.client_configs:
                    print(f"🤖 Starting client: {client_filter}")
                    success = self.orchestrator.start_client(client_filter)
                    if success:
                        print(f"✅ Client {client_filter} started successfully")
                        # Keep running
                        self.running = True
                        self._setup_signal_handlers()
                        while self.running:
                            await asyncio.sleep(1)
                    else:
                        print(f"❌ Failed to start client {client_filter}")
                        return
                else:
                    print(f"❌ Client '{client_filter}' not found")
                    print("Available clients:")
                    for client_id in self.orchestrator.config_manager.client_configs:
                        print(f"  - {client_id}")
                    return
            else:
                # Start all enabled clients
                started_clients = await self.orchestrator.start_all_clients()
                if started_clients:
                    print(f"✅ Started {len(started_clients)} clients: {', '.join(started_clients)}")
                    # Keep running
                    self.running = True
                    self._setup_signal_handlers()

                    # Start health monitoring
                    await self.orchestrator.run_health_monitoring()
                else:
                    print("❌ No clients were started")

        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested by user")
        except Exception as e:
            print(f"❌ Platform error: {e}")
        finally:
            await self.orchestrator.shutdown()
            print("🔌 Platform shutdown complete")

    async def show_status(self) -> None:
        """Show enhanced platform status."""
        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        print("📊 Multi-Client Platform Status")
        print("=" * 50)

        # Get status from orchestrator
        status = self.orchestrator.get_status()

        if 'error' in status:
            print(f"❌ {status['error']}")
            return

        platform_stats = status["platform"]
        health_stats = status["health"]

        # Platform overview
        print(f"🕐 Platform Uptime: {platform_stats['uptime_hours']:.1f} hours")
        print(f"🔄 Total Restarts: {platform_stats['total_restarts']}")
        print(f"📊 Total Clients: {platform_stats['total_clients']}")
        print(f"🟢 Running Clients: {platform_stats['running_clients']}")
        print(f"✅ Healthy Clients: {health_stats['healthy_clients']}")
        print(f"⚠️ Clients with Issues: {health_stats['clients_with_issues']}")
        print(f"🔧 Auto-fixes Applied: {health_stats['total_auto_fixes']}")
        print(f"🤖 Auto-healing: {'Enabled' if health_stats['auto_healing_enabled'] else 'Disabled'}")
        print()

        # Client details
        if status["clients"]:
            print("Detailed Client Status:")
            print("-" * 50)

            for client_id, client_stats in status["clients"].items():
                is_running = client_stats.get("running", False)

                if is_running:
                    status_icon = "🟢"
                    pid = client_stats.get('pid', 'unknown')
                    uptime = client_stats.get('uptime_hours', 0)
                    memory = client_stats.get('memory_mb', 0)
                    cpu = client_stats.get('cpu_percent', 0)
                    source = client_stats.get('source', 'unknown')

                    print(f"{status_icon} {client_id}: RUNNING (PID: {pid}) • Uptime: {uptime:.1f}h • Source: {source}")
                    print(
                        f"   💾 Memory: {memory:.1f} MB • 🔄 CPU: {cpu:.1f}% • 🔄 Restarts: {client_stats.get('restart_count', 0)}")
                else:
                    status_icon = "🔴"
                    status_reason = client_stats.get('status', 'stopped')
                    print(f"{status_icon} {client_id}: STOPPED ({status_reason})")

                # Health indicator
                config_health = client_stats.get("health_status", {}).get("config_health", "unknown")
                health_icon = "✅" if config_health == "healthy" else "⚠️"
                print(f"   🏥 Config Health: {config_health} {health_icon}")

                # Show issues if any
                issues = client_stats.get("config_issues", [])
                if issues:
                    print(f"   ⚠️ Issues ({len(issues)}):")
                    for issue in issues[:3]:
                        print(f"      • {issue}")
                    if len(issues) > 3:
                        print(f"      • ... and {len(issues) - 3} more")

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
            print("  0. Exit management console")  # ← Clarified text

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
        """Start a client interactively."""
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
        """Restart a client interactively."""
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
                else:
                    print(f"❌ Failed to restart {client_id}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a valid number.")

    async def _start_all_interactive(self) -> None:
        """Start all enabled clients."""
        print("🚀 Starting all enabled clients...")
        started = await self.orchestrator.start_all_clients()
        if started:
            print(f"✅ Started {len(started)} clients: {', '.join(started)}")
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

        display_name = input("Display Name (optional): ").strip()
        if not display_name:
            display_name = client_id.replace('_', ' ').title()

        plan = input("Plan (basic/premium/enterprise) [basic]: ").strip().lower()
        if plan not in ['basic', 'premium', 'enterprise']:
            plan = 'basic'

        success = self.orchestrator.create_client(
            client_id=client_id,
            display_name=display_name,
            plan=plan
        )

        if success:
            print(f"✅ Created client: {client_id}")
        else:
            print(f"❌ Failed to create client: {client_id}")

    async def _delete_client_interactive(self) -> None:
        """Delete a client interactively."""
        clients = list(self.orchestrator.config_manager.client_configs.keys())
        if not clients:
            print("❌ No clients configured.")
            return

        print("⚠️ Delete Client (DESTRUCTIVE OPERATION)")
        print("\nConfigured Clients:")
        for i, client_id in enumerate(clients, 1):
            print(f"  {i}. {client_id}")

        try:
            choice = int(input(f"Select client to DELETE (1-{len(clients)}): "))
            if 1 <= choice <= len(clients):
                client_id = clients[choice - 1]

                confirm = input(f"⚠️ Are you sure you want to DELETE '{client_id}'? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    backup = input("Create backup before deletion? (Y/n): ").strip().lower()
                    create_backup = backup != 'n'

                    print(f"🗑️ Deleting {client_id}...")
                    success = self.orchestrator.delete_client(client_id, backup=create_backup)
                    if success:
                        print(f"✅ Deleted client: {client_id}")
                    else:
                        print(f"❌ Failed to delete client: {client_id}")
                else:
                    print("❌ Deletion cancelled.")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a valid number.")

    async def _run_diagnostics(self) -> None:
        """Run platform diagnostics."""
        print("🔍 Running Platform Diagnostics...")

        # Auto-heal platform
        fixes = self.orchestrator.service_manager.auto_heal_platform()
        if fixes > 0:
            print(f"🔧 Applied {fixes} auto-fixes")
        else:
            print("✅ No issues found")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(sig, frame):
            print(f"\n🛑 Received signal {sig}, shutting down...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Multi-Client Discord Bot Platform")
    parser.add_argument("--client", help="Start specific client only")
    parser.add_argument("--status", action="store_true", help="Show platform status")
    parser.add_argument("--interactive", action="store_true", help="Interactive management mode")
    parser.add_argument("--config", default="platform_config.json", help="Platform config file")

    args = parser.parse_args()

    # Create orchestrator with clean architecture
    orchestrator = PlatformOrchestrator(args.config)
    platform = PlatformMain(orchestrator)

    # Handle command-line arguments
    if args.status:
        await platform.show_status()
    elif args.interactive:
        await platform.interactive_mode()
    else:
        await platform.start_platform(args.client)


if __name__ == "__main__":
    asyncio.run(main())
