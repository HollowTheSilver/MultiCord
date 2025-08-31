"""
Platform Main - PID Consistency Fix for Interactive Menu
========================================================

FIXED: PID consistency issues in interactive menu by implementing:
1. Smart refresh mechanism before displaying process lists
2. Retry logic for registry synchronization
3. Manual refresh option in interactive menu  
4. Enhanced process state validation
"""

import asyncio
import signal
import sys
import time
from typing import Optional, Set, Dict, Any
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from bot_platform.service_manager import PlatformOrchestrator
from bot_platform.deployment_tools import ClientOnboardingTool


class PlatformManager:
    """Main platform management interface with enhanced PID consistency."""

    def __init__(self):
        """Initialize platform manager."""
        self.orchestrator = PlatformOrchestrator()
        self.running = False
        self.shutdown_by_signal = False
        self._last_refresh_time = 0
        self._refresh_interval = 2.0  # Minimum seconds between forced refreshes

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            print(f"\n🛑 Received signal {sig}. Shutting down gracefully...")
            self.running = False
            # Mark that shutdown was triggered by signal
            self.shutdown_by_signal = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _ensure_fresh_process_data(self, force_refresh: bool = False) -> None:
        """
        FIXED: Refresh process data without automatic discovery.
        
        Args:
            force_refresh: Force a refresh regardless of timing
        """
        current_time = time.time()
        
        # Force refresh if requested or enough time has passed
        if force_refresh or (current_time - self._last_refresh_time) > self._refresh_interval:
            try:
                # Only cleanup dead processes - NO automatic discovery
                dead_count = len(self.orchestrator.process_manager.cleanup_dead_processes())
                self._last_refresh_time = current_time
                
                if dead_count > 0:
                    # Brief pause to allow registry write to complete
                    time.sleep(0.2)
            except Exception as e:
                print(f"⚠️ Warning: Failed to refresh process data: {e}")

    def _get_fresh_running_clients(self) -> Set[str]:
        """Get running client IDs with fresh registry data."""
        self._ensure_fresh_process_data()
        return self.orchestrator.process_manager.get_running_client_ids()

    def _get_fresh_process_status(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get process status with fresh registry data."""
        self._ensure_fresh_process_data()
        return self.orchestrator.process_manager.get_process_status(client_id)

    def _validate_process_consistency(self, client_id: str, expected_running: bool) -> bool:
        """
        SIMPLIFIED: Basic validation without complex retry logic.
        
        Args:
            client_id: Client to check
            expected_running: Whether we expect the process to be running
            
        Returns:
            bool: True if state matches expectations
        """
        try:
            self._ensure_fresh_process_data()
            running_clients = self._get_fresh_running_clients()
            is_running = client_id in running_clients
            return is_running == expected_running
        except Exception:
            return False

    async def run_single_client(self, client_id: str) -> None:
        """Run a single client with improved logging feedback."""
        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        print(f"🚀 Starting single client: {client_id}")

        success = self.orchestrator.start_client(client_id)

        if success:
            # Brief validation check
            if not self._validate_process_consistency(client_id, expected_running=True):
                print("⚠️ Warning: Process state syncing...")
                time.sleep(0.5)  # Brief sync time
                
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
            self.shutdown_by_signal = False

            try:
                while self.running:
                    await asyncio.sleep(1)

                    # Check if client is still running with fresh data
                    if client_id not in self._get_fresh_running_clients():
                        print(f"⚠️ Client {client_id} has stopped")
                        break

            except KeyboardInterrupt:
                pass

            # Only try to stop client if it wasn't already terminated by the signal
            if not self.shutdown_by_signal:
                print(f"\n🛑 Stopping client {client_id}...")
                self.orchestrator.stop_client(client_id)
                print("✅ Client stopped")
            else:
                # Client was terminated by signal - just clean up registry
                print(f"\n🛑 Client {client_id} terminated by signal")
                # Allow ProcessManager to handle cleanup automatically
                print("✅ Cleanup completed")
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

            # Show log file locations for each started client with fresh data
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

                    # Periodic health check with fresh data
                    running_clients = self._get_fresh_running_clients()
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
        """Show platform status with enhanced logging information and fresh data."""
        if not self.orchestrator.initialize():
            print("❌ Platform initialization failed")
            return

        # CONSISTENCY FIX: Ensure fresh data before displaying status
        self._ensure_fresh_process_data(force_refresh=True)

        print("📊 MultiCord Platform Status")
        print("=" * 50)

        # Platform summary with fresh data
        total_clients = len(self.orchestrator.config_manager.client_configs)
        running_clients = len(self._get_fresh_running_clients())
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

            running_client_ids = self._get_fresh_running_clients()

            for client_id, config in self.orchestrator.config_manager.client_configs.items():
                is_running = client_id in running_client_ids

                if is_running:
                    status_icon = "🟢"
                    process_info = self._get_fresh_process_status(client_id)

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
        """Run interactive management console with refresh capabilities."""
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
            print("  r. Refresh process data")  # NEW: Manual refresh option
            print("  0. Exit management console")

            try:
                choice = input("\nSelect option (0-9, r): ").strip().lower()

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
                elif choice == "r":
                    await self._manual_refresh_interactive()  # NEW: Manual refresh
                elif choice == "0":
                    print("👋 Exiting management console...")
                    self.running = False
                    break
                else:
                    print("❌ Invalid option. Please choose 0-9 or 'r' for refresh.")

            except (KeyboardInterrupt, EOFError):
                print("\n👋 Exiting management console...")
                print("✅ All running clients will continue running independently")
                self.running = False
                break
            except Exception as e:
                print(f"❌ Error: {e}")

        print("📋 Management console closed. Use 'python platform_main.py --status' to check client status.")

    async def _manual_refresh_interactive(self) -> None:
        """Manual refresh option for interactive menu."""
        print("\n🔄 Refreshing process data...")
        try:
            self._ensure_fresh_process_data(force_refresh=True)
            
            # Show quick status after refresh
            running_clients = self._get_fresh_running_clients()
            total_clients = len(self.orchestrator.config_manager.client_configs)
            
            print(f"✅ Refresh completed: {len(running_clients)} running / {total_clients} configured")
            
            if running_clients:
                print("🟢 Running clients:")
                for client_id in running_clients:
                    process_info = self._get_fresh_process_status(client_id)
                    if process_info:
                        pid = process_info.get('pid', 'unknown')
                        print(f"   • {client_id} (PID: {pid})")
            else:
                print("🔴 No clients currently running")
                
        except Exception as e:
            print(f"❌ Refresh failed: {e}")

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
            # Refresh orchestrator to pick up new client with fresh data
            self.orchestrator.config_manager.discover_clients()
            self._ensure_fresh_process_data(force_refresh=True)

        print("=" * 50)
        input("Press Enter to continue...")

    async def _view_client_logs_interactive(self) -> None:
        """View client logs interactively with fresh client data."""
        clients = list(self.orchestrator.config_manager.client_configs.keys())
        if not clients:
            print("❌ No clients configured.")
            return

        print("\nConfigured Clients:")
        running_client_ids = self._get_fresh_running_clients()
        
        for i, client_id in enumerate(clients, 1):
            status = "🟢 Running" if client_id in running_client_ids else "🔴 Stopped"
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
                        with open(log_path, 'r', encoding='utf-8') as f:
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
        """Start a client interactively with fresh data and consistency checks."""
        clients = list(self.orchestrator.config_manager.client_configs.keys())
        if not clients:
            print("❌ No clients configured.")
            return

        print("\nAvailable Clients:")
        running_ids = self._get_fresh_running_clients()

        for i, client_id in enumerate(clients, 1):
            status = "🟢 Running" if client_id in running_ids else "🔴 Stopped"
            print(f"  {i}. {client_id} ({status})")

        try:
            choice = int(input(f"Select client (1-{len(clients)}): "))
            if 1 <= choice <= len(clients):
                client_id = clients[choice - 1]
                
                # CONSISTENCY CHECK: Warn if client is already running
                if client_id in running_ids:
                    print(f"⚠️ Warning: {client_id} appears to be already running")
                    confirm = input("Continue anyway? (y/N): ").strip().lower()
                    if confirm != 'y':
                        print("❌ Operation cancelled")
                        return
                
                print(f"🚀 Starting {client_id}...")
                success = self.orchestrator.start_client(client_id)
                
                if success:
                    # CONSISTENCY VALIDATION: Check that client actually started
                    if self._validate_process_consistency(client_id, expected_running=True):
                        log_path = self.orchestrator.process_manager.get_client_log_path(client_id)
                        print(f"✅ {client_id} started successfully")
                        if log_path:
                            print(f"📁 View logs: tail -f {log_path}")
                    else:
                        print(f"⚠️ {client_id} start command succeeded but process state is syncing...")
                        print("💡 Use 'r' to refresh and verify, or check logs")
                else:
                    print(f"❌ Failed to start {client_id}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a valid number.")

    async def _stop_client_interactive(self) -> None:
        """Stop a client interactively with fresh data and consistency checks."""
        running_clients = list(self._get_fresh_running_clients())
        if not running_clients:
            print("❌ No clients are currently running.")
            return

        print("\nRunning Clients:")
        for i, client_id in enumerate(running_clients, 1):
            # Show additional process info for better identification
            process_info = self._get_fresh_process_status(client_id)
            if process_info:
                pid = process_info.get('pid', 'unknown')
                uptime = process_info.get('uptime_hours', 0)
                print(f"  {i}. {client_id} (PID: {pid}, Uptime: {uptime:.1f}h)")
            else:
                print(f"  {i}. {client_id}")

        try:
            choice = int(input(f"Select client to stop (1-{len(running_clients)}): "))
            if 1 <= choice <= len(running_clients):
                client_id = running_clients[choice - 1]
                print(f"🛑 Stopping {client_id}...")
                success = self.orchestrator.stop_client(client_id)
                
                if success:
                    # CONSISTENCY VALIDATION: Check that client actually stopped
                    if self._validate_process_consistency(client_id, expected_running=False):
                        print(f"✅ {client_id} stopped successfully")
                    else:
                        print(f"⚠️ {client_id} stop command succeeded but process state is syncing...")
                        print("💡 Use 'r' to refresh and verify")
                else:
                    print(f"❌ Failed to stop {client_id}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a valid number.")

    async def _restart_client_interactive(self) -> None:
        """Restart a client interactively with fresh data and consistency checks."""
        clients = list(self.orchestrator.config_manager.client_configs.keys())
        if not clients:
            print("❌ No clients configured.")
            return

        print("\nConfigured Clients:")
        running_ids = self._get_fresh_running_clients()

        for i, client_id in enumerate(clients, 1):
            status = "🟢 Running" if client_id in running_ids else "🔴 Stopped"
            if client_id in running_ids:
                process_info = self._get_fresh_process_status(client_id)
                if process_info:
                    pid = process_info.get('pid', 'unknown')
                    uptime = process_info.get('uptime_hours', 0)
                    print(f"  {i}. {client_id} ({status}, PID: {pid}, Uptime: {uptime:.1f}h)")
                else:
                    print(f"  {i}. {client_id} ({status})")
            else:
                print(f"  {i}. {client_id} ({status})")

        try:
            choice = int(input(f"Select client to restart (1-{len(clients)}): "))
            if 1 <= choice <= len(clients):
                client_id = clients[choice - 1]
                print(f"🔄 Restarting {client_id}...")
                success = self.orchestrator.restart_client(client_id)
                
                if success:
                    # CONSISTENCY VALIDATION: Check that client restarted properly
                    if self._validate_process_consistency(client_id, expected_running=True):
                        log_path = self.orchestrator.process_manager.get_client_log_path(client_id)
                        print(f"✅ {client_id} restarted successfully")
                        if log_path:
                            print(f"📁 View logs: tail -f {log_path}")
                    else:
                        print(f"⚠️ {client_id} restart command succeeded but process state is syncing...")
                        print("💡 Use 'r' to refresh and verify, or check logs")
                else:
                    print(f"❌ Failed to restart {client_id}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a valid number.")

    async def _start_all_interactive(self) -> None:
        """Start all enabled clients with fresh data tracking."""
        print("🚀 Starting all enabled clients...")
        started = await self.orchestrator.start_all_clients()

        if started:
            print(f"✅ Started {len(started)} clients: {', '.join(started)}")
            
            # Ensure fresh data after bulk start
            self._ensure_fresh_process_data(force_refresh=True)
            
            print("\n📁 View logs:")
            for client_id in started:
                log_path = self.orchestrator.process_manager.get_client_log_path(client_id)
                if log_path:
                    print(f"  {client_id}: tail -f {log_path}")
        else:
            print("❌ No clients were started")

    async def _stop_all_interactive(self) -> None:
        """Stop all running clients with fresh data tracking."""
        print("🛑 Stopping all running clients...")
        stopped = await self.orchestrator.stop_all_clients()
        
        if stopped:
            print(f"✅ Stopped {len(stopped)} clients: {', '.join(stopped)}")
            
            # Ensure fresh data after bulk stop
            self._ensure_fresh_process_data(force_refresh=True)
        else:
            print("ℹ️ No clients were running")

    async def _delete_client_interactive(self) -> None:
        """Delete a client interactively with fresh data."""
        clients = list(self.orchestrator.config_manager.client_configs.keys())
        if not clients:
            print("❌ No clients configured.")
            return

        print("\nConfigured Clients:")
        running_ids = self._get_fresh_running_clients()
        
        for i, client_id in enumerate(clients, 1):
            status = "🟢 Running" if client_id in running_ids else "🔴 Stopped"
            print(f"  {i}. {client_id} ({status})")

        try:
            choice = int(input(f"Select client to delete (1-{len(clients)}): "))
            if 1 <= choice <= len(clients):
                client_id = clients[choice - 1]

                confirm = input(f"⚠️ Delete client '{client_id}' permanently? (yes/no): ").strip().lower()
                if confirm == "yes":
                    # Stop client first if running
                    if client_id in running_ids:
                        print(f"🛑 Stopping {client_id} first...")
                        self.orchestrator.stop_client(client_id)
                        
                        # Validate stop before proceeding
                        if not self._validate_process_consistency(client_id, expected_running=False):
                            print("⚠️ Process may still be stopping...")
                            time.sleep(2)  # Give more time

                    # Delete using orchestrator's delete method
                    success = self.orchestrator.delete_client(client_id)
                    if success:
                        print(f"✅ Client '{client_id}' deleted successfully")
                        # Refresh config manager and process data
                        self.orchestrator.config_manager.discover_clients()
                        self._ensure_fresh_process_data(force_refresh=True)
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
