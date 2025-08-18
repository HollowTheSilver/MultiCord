#!/usr/bin/env python3
"""
Multi-Client Discord Bot Platform
=================================

Main entry point for the multi-client Discord bot platform.
Manages multiple client bot instances with shared core functionality.

Usage:
    python platform_main.py                    # Start all enabled clients
    python platform_main.py --client alpha     # Start specific client only
    python platform_main.py --status          # Show platform status
    python platform_main.py --interactive     # Interactive management mode

Author: HollowTheSilver
Version: 2.0.2
"""

import asyncio
import argparse
import sys
import signal
from pathlib import Path
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from bot_platform.launcher import PlatformLauncher
from bot_platform.client_manager import ClientManager


class PlatformMain:
    """Main platform controller."""

    def __init__(self):
        self.launcher = PlatformLauncher()
        self.client_manager = ClientManager()
        self.running = False

    async def start_platform(self, client_filter: Optional[str] = None) -> None:
        """Start the platform with optional client filtering."""
        print("🚀 Starting Multi-Client Discord Bot Platform")
        print("=" * 50)

        try:
            if client_filter:
                # Start specific client only
                if client_filter in self.launcher.client_configs:
                    print(f"🤖 Starting client: {client_filter}")
                    success = await self.launcher.start_client(client_filter)
                    if success:
                        print(f"✅ Client {client_filter} started successfully")
                        # Keep running
                        self.running = True
                        while self.running:
                            await asyncio.sleep(1)
                    else:
                        print(f"❌ Failed to start client {client_filter}")
                        return
                else:
                    print(f"❌ Client '{client_filter}' not found")
                    print("Available clients:")
                    for client_id in self.launcher.client_configs:
                        print(f"  - {client_id}")
                    return
            else:
                # Start all clients
                await self.launcher.run()

        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested by user")
        except Exception as e:
            print(f"❌ Platform error: {e}")
        finally:
            self.running = False
            print("🔌 Platform shutdown complete")

    async def show_status(self) -> None:
        """Show platform status."""
        print("📊 Multi-Client Platform Status")
        print("=" * 40)

        # Platform stats
        stats = self.launcher.get_platform_stats()
        print(f"🕐 Uptime: {stats['platform']['uptime_hours']:.1f} hours")
        print(f"🔄 Total restarts: {stats['platform']['total_restarts']}")
        print(f"📊 Configured clients: {stats['platform']['total_clients']}")
        print(f"🟢 Running clients: {stats['platform']['running_clients']}")
        print()

        # Client details
        if stats['clients']:
            print("Client Details:")
            print("-" * 40)
            for client_id, client_stats in stats['clients'].items():
                status = "🟢 Running" if client_stats['running'] else "🔴 Stopped"
                print(f"{status} {client_id}")
                if client_stats['running']:
                    print(f"  📈 Memory: {client_stats['memory_mb']:.1f}MB")
                    print(f"  ⚡ CPU: {client_stats['cpu_percent']:.1f}%")
                    print(f"  🔄 Restarts: {client_stats['restart_count']}")
                print()
        else:
            print("❌ No clients configured")

    async def interactive_mode(self) -> None:
        """Run interactive management console."""
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
            print("  5. Create new client")
            print("  6. View logs")
            print("  7. Quit")

            try:
                choice = input("\nSelect option (1-7): ").strip()

                if choice == "1":
                    await self.show_status()
                elif choice == "2":
                    await self._start_client_interactive()
                elif choice == "3":
                    await self._stop_client_interactive()
                elif choice == "4":
                    await self._restart_client_interactive()
                elif choice == "5":
                    await self._create_client_interactive()
                elif choice == "6":
                    await self._show_logs_interactive()
                elif choice == "7":
                    print("👋 Goodbye!")
                    self.running = False
                else:
                    print("❌ Invalid option. Please choose 1-7.")

            except (KeyboardInterrupt, EOFError):
                print("\n👋 Goodbye!")
                self.running = False
            except Exception as e:
                print(f"❌ Error: {e}")

    async def _start_client_interactive(self) -> None:
        """Start a client interactively."""
        clients = list(self.launcher.client_configs.keys())
        if not clients:
            print("❌ No clients configured.")
            return

        print("\nAvailable Clients:")
        for i, client_id in enumerate(clients, 1):
            status = "🟢 Running" if client_id in self.launcher.client_processes else "🔴 Stopped"
            print(f"  {i}. {client_id} ({status})")

        try:
            choice = int(input(f"Select client (1-{len(clients)}): "))
            if 1 <= choice <= len(clients):
                client_id = clients[choice - 1]
                print(f"🚀 Starting {client_id}...")
                success = await self.launcher.start_client(client_id)
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
        running_clients = list(self.launcher.client_processes.keys())
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
                success = await self.launcher.stop_client(client_id)
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
        clients = list(self.launcher.client_configs.keys())
        if not clients:
            print("❌ No clients configured.")
            return

        print("\nConfigured Clients:")
        for i, client_id in enumerate(clients, 1):
            status = "🟢 Running" if client_id in self.launcher.client_processes else "🔴 Stopped"
            print(f"  {i}. {client_id} ({status})")

        try:
            choice = int(input(f"Select client to restart (1-{len(clients)}): "))
            if 1 <= choice <= len(clients):
                client_id = clients[choice - 1]
                print(f"🔄 Restarting {client_id}...")
                success = await self.launcher.restart_client(client_id)
                if success:
                    print(f"✅ {client_id} restarted successfully")
                else:
                    print(f"❌ Failed to restart {client_id}")
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a valid number.")

    async def _create_client_interactive(self) -> None:
        """Create a new client interactively."""
        print("🆕 Creating a new client...")
        print("For detailed client creation, use: python -m bot_platform.deployment_tools new-client")

        # Quick creation
        client_id = input("Client ID: ").strip().lower()
        if not client_id or client_id in self.client_manager.clients:
            print("❌ Invalid or existing client ID.")
            return

        display_name = input("Display Name: ").strip()
        if not display_name:
            print("❌ Display name is required.")
            return

        # Use deployment tools for full creation
        print("Please use the full onboarding tool for complete setup:")
        print(f"  python -m bot_platform.deployment_tools new-client")

    async def _show_logs_interactive(self) -> None:
        """Show platform logs."""
        print("📄 Recent Platform Logs:")
        print("  (This would show recent log entries)")
        print("  For detailed logs, check: platform/logs/")

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

    args = parser.parse_args()

    platform = PlatformMain()

    if args.status:
        await platform.show_status()
    elif args.interactive:
        await platform.interactive_mode()
    else:
        await platform.start_platform(args.client)


if __name__ == "__main__":
    asyncio.run(main())
