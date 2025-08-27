"""
Platform Main - Fix Duplicate Client Creation Issue
==================================================

ISSUE #2 ROOT CAUSE FIX: Remove duplicate _create_client_interactive() 
and use the existing ClientOnboardingTool from deployment_tools.py

This eliminates code duplication and uses the sophisticated existing system.
"""

import asyncio
import signal
import sys
from typing import Optional
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from bot_platform.service_manager import PlatformOrchestrator
from bot_platform.deployment_tools import ClientOnboardingTool


class PlatformManager:
    """Main platform management interface."""

    def __init__(self):
        """Initialize platform manager."""
        self.orchestrator = PlatformOrchestrator()
        self.running = False

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            print(f"\n🛑 Received signal {sig}. Shutting down gracefully...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def run_single_client(self, client_id: str) -> None:
        """Run a single client with improved logging feedback."""
        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        print(f"🚀 Starting single client: {client_id}")

        success = self.orchestrator.start_client(client_id)

        if success:
            # Get log file location for user feedback
            log_path = self.orchestrator.process_manager.get_client_log_path(client_id)
            print(f"✅ Client {client_id} started successfully")
            if log_path:
                print(f"📁 Live logs: tail -f {log_path}")
                print(f"🔍 Status: python platform_main.py --status")

            print("\n🎯 Client is running. Press Ctrl+C to stop.")

            # Wait for shutdown signal
            self._setup_signal_handlers()
            self.running = True

            try:
                while self.running:
                    await asyncio.sleep(1)

                    # Check if client is still running
                    if client_id not in self.orchestrator.process_manager.get_running_client_ids():
                        print(f"⚠️ Client {client_id} has stopped")
                        break

            except KeyboardInterrupt:
                pass

            print(f"\n🛑 Stopping client {client_id}...")
            self.orchestrator.stop_client(client_id)
            print("✅ Client stopped")
        else:
            print(f"❌ Failed to start client {client_id}")
            print("💡 Check client configuration and logs")

    async def start_all_clients(self) -> None:
        """Start all enabled clients with improved feedback."""
        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        print("🚀 Starting all enabled clients...")
        started = await self.orchestrator.start_all_clients()

        if started:
            print(f"✅ Started {len(started)} clients: {', '.join(started)}")
            print("\n📁 View logs:")

            # Show log file locations for each started client
            for client_id in started:
                log_path = self.orchestrator.process_manager.get_client_log_path(client_id)
                if log_path:
                    print(f"  {client_id}: tail -f {log_path}")

            print("\n🎯 All clients running. Press Ctrl+C to stop all.")

            # Wait for shutdown signal
            self._setup_signal_handlers()
            self.running = True

            try:
                while self.running:
                    await asyncio.sleep(5)

                    # Periodic health check
                    running_clients = self.orchestrator.process_manager.get_running_client_ids()
                    if not running_clients:
                        print("⚠️ All clients have stopped")
                        break

            except KeyboardInterrupt:
                pass

            print("\n🛑 Stopping all clients...")
            stopped = await self.orchestrator.stop_all_clients()
            if stopped:
                print(f"✅ Stopped {len(stopped)} clients")
            else:
                print("ℹ️ No clients were running")
        else:
            print("❌ No clients were started")
            print("💡 Check client configurations or create clients first")

    async def show_status(self) -> None:
        """Show platform status with enhanced logging information."""
        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        print("📊 MultiCord Platform Status")
        print("=" * 50)

        # Platform summary
        total_clients = len(self.orchestrator.config_manager.client_configs)
        running_clients = len(self.orchestrator.process_manager.get_running_client_ids())
        print(f"Clients: {running_clients} running / {total_clients} configured")

        # Show enabled/disabled breakdown
        enabled_count = sum(1 for config in self.orchestrator.config_manager.client_configs.values()
                          if getattr(config, 'enabled', True))
        disabled_count = total_clients - enabled_count
        print(f"Status: {enabled_count} enabled / {disabled_count} {'disabled' if disabled_count else 'Disabled'}")
        print()

        # Detailed client information with log file locations
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
                        log_file = process_info.get('log_file', 'unknown')

                        print(f"{status_icon} {client_id}: RUNNING (PID: {pid}) • Uptime: {uptime:.1f}h • Source: {source}")
                        print(f"   💾 Memory: {memory:.1f} MB • ⚡ CPU: {cpu:.1f}% • 🔄 Restarts: {restart_count}")
                        if log_file and log_file != 'unknown':
                            print(f"   📁 Logs: {log_file}")
                    else:
                        print(f"{status_icon} {client_id}: RUNNING (process info unavailable)")
                else:
                    status_icon = "🔴"
                    status_reason = "Not running"
                    enabled_status = "Enabled" if getattr(config, 'enabled', True) else "Disabled"
                    print(f"{status_icon} {client_id}: STOPPED ({status_reason}) • {enabled_status}")

                # Show health indicator
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
        print("💡 Management commands:")
        print("  python platform_main.py --interactive  # Interactive management")
        print("  python -m bot_platform.deployment_tools new-client  # Create client")

    async def interactive_mode(self) -> None:
        """Run interactive management console."""
        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        print("🎮 MultiCord Interactive Platform Management")
        print("=" * 50)

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
            print("  9. View client logs")
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
                    await self._view_client_logs_interactive()
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

    async def _create_client_interactive(self) -> None:
        """
        FIXED: Use existing ClientOnboardingTool instead of duplicate implementation.
        This eliminates code duplication and uses the sophisticated existing system.
        """
        print("\n" + "=" * 50)

        # Use the existing, sophisticated ClientOnboardingTool
        tool = ClientOnboardingTool()

        # Auto-detect template support and use appropriate workflow
        use_templates = tool.template_manager is not None
        success = tool.interactive_onboarding(use_templates=use_templates)

        if success:
            # Refresh orchestrator to pick up new client
            self.orchestrator.config_manager.discover_clients()

        print("=" * 50)
        input("Press Enter to continue...")

    async def _view_client_logs_interactive(self) -> None:
        """View client logs interactively."""
        clients = list(self.orchestrator.config_manager.client_configs.keys())
        if not clients:
            print("❌ No clients configured.")
            return

        print("\nConfigured Clients:")
        for i, client_id in enumerate(clients, 1):
            status = "🟢 Running" if client_id in self.orchestrator.process_manager.get_running_client_ids() else "🔴 Stopped"
            print(f"  {i}. {client_id} ({status})")

        try:
            choice = int(input(f"Select client to view logs (1-{len(clients)}): "))
            if 1 <= choice <= len(clients):
                client_id = clients[choice - 1]
                log_path = self.orchestrator.process_manager.get_client_log_path(client_id)

                if log_path and Path(log_path).exists():
                    print(f"\n📁 Log file: {log_path}")
                    print("💡 View live logs: tail -f " + log_path)
                    print("💡 View recent logs: tail -n 50 " + log_path)

                    # Show last few lines
                    try:
                        with open(log_path, 'r') as f:
                            lines = f.readlines()
                            if lines:
                                print(f"\n📋 Last 10 lines from {client_id}:")
                                print("-" * 40)
                                for line in lines[-10:]:
                                    print(line.rstrip())
                    except Exception as e:
                        print(f"❌ Could not read log file: {e}")
                else:
                    print(f"❌ No log file found for {client_id}")
                    print("💡 Client may not have been started yet")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a valid number.")

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
                    log_path = self.orchestrator.process_manager.get_client_log_path(client_id)
                    print(f"✅ {client_id} started successfully")
                    if log_path:
                        print(f"📁 View logs: tail -f {log_path}")
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
                    log_path = self.orchestrator.process_manager.get_client_log_path(client_id)
                    print(f"✅ {client_id} restarted successfully")
                    if log_path:
                        print(f"📁 View logs: tail -f {log_path}")
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
            print("\n📁 View logs:")
            for client_id in started:
                log_path = self.orchestrator.process_manager.get_client_log_path(client_id)
                if log_path:
                    print(f"  {client_id}: tail -f {log_path}")
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

                confirm = input(f"⚠️ Delete client '{client_id}' permanently? (yes/no): ").strip().lower()
                if confirm == "yes":
                    # Stop client first if running
                    if client_id in self.orchestrator.process_manager.get_running_client_ids():
                        print(f"🛑 Stopping {client_id} first...")
                        self.orchestrator.stop_client(client_id)

                    # Delete using orchestrator's delete method
                    success = self.orchestrator.delete_client(client_id)
                    if success:
                        print(f"✅ Client '{client_id}' deleted successfully")
                        # Refresh config manager
                        self.orchestrator.config_manager.discover_clients()
                    else:
                        print(f"❌ Failed to delete client '{client_id}'")
                else:
                    print("❌ Deletion cancelled")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a valid number.")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="MultiCord - Multi-Node Discord Management Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python platform_main.py --status                # Show platform status
  python platform_main.py --interactive          # Interactive management
  python platform_main.py --client alpha         # Run specific client
  python platform_main.py                        # Start all enabled clients
        """
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true", help="Show platform status")
    group.add_argument("--interactive", action="store_true", help="Interactive management console")
    group.add_argument("--client", type=str, help="Run specific client")

    args = parser.parse_args()

    manager = PlatformManager()

    try:
        if args.status:
            await manager.show_status()
        elif args.interactive:
            await manager.interactive_mode()
        elif args.client:
            await manager.run_single_client(args.client)
        else:
            await manager.start_all_clients()
    except KeyboardInterrupt:
        print("\n🛑 Operation cancelled")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
    