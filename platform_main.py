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
"""

import asyncio
import argparse
import sys
import signal
from pathlib import Path
from typing import Optional

# Add platform modules to path
sys.path.insert(0, str(Path(__file__).parent / "platform"))
sys.path.insert(0, str(Path(__file__).parent / "core"))

from platform.launcher import PlatformLauncher
from platform.client_manager import ClientManager


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
        print("📊 Multi-Client Discord Bot Platform Status")
        print("=" * 45)
        
        try:
            # Client information
            clients = self.client_manager.list_clients()
            print(f"\n📋 Configured Clients: {len(clients)}")
            
            for client in clients:
                status_emoji = "🟢" if client.status == "active" else "🔴"
                print(f"   {status_emoji} {client.display_name} ({client.client_id})")
                print(f"      Plan: {client.plan.title()} - ${client.monthly_fee}/month")
                
            # Billing summary
            billing = self.client_manager.get_billing_summary()
            print(f"\n💰 Revenue: ${billing['total_monthly_revenue']}/month")
            print(f"📦 Plans: Basic({billing['plans']['basic']}) Premium({billing['plans']['premium']}) Enterprise({billing['plans']['enterprise']})")
            
            # Try to get runtime status
            try:
                status = self.launcher.get_platform_status()
                print(f"\n🚀 Runtime Status:")
                print(f"   Running Clients: {status['clients']['running']}/{status['clients']['total']}")
                print(f"   Total Memory: {status['resources']['total_memory_mb']:.1f} MB")
                print(f"   Average CPU: {status['resources']['avg_cpu_percent']:.1f}%")
                print(f"   Platform Uptime: {status['platform']['uptime_seconds']/3600:.1f} hours")
                
                if status['client_details']:
                    print(f"\n🤖 Individual Client Status:")
                    for client_id, details in status['client_details'].items():
                        uptime_hours = details['uptime_seconds'] / 3600
                        memory_mb = details['memory_mb']
                        cpu_percent = details['cpu_percent']
                        
                        health_emoji = "🟢" if details['status'] == "healthy" else "🟡" if details['status'] == "running" else "🔴"
                        print(f"   {health_emoji} {client_id}: {details['status']}")
                        print(f"      Uptime: {uptime_hours:.1f}h | Memory: {memory_mb:.1f}MB | CPU: {cpu_percent:.1f}%")
                        
                        if details['restart_count'] > 0:
                            print(f"      Restarts: {details['restart_count']}")
                            
            except Exception as e:
                print(f"⚠️  Could not connect to running platform: {e}")
                print("   Platform may not be running or accessible")
                
        except Exception as e:
            print(f"❌ Failed to get status: {e}")

    async def interactive_mode(self) -> None:
        """Interactive platform management mode."""
        print("🔧 Interactive Platform Management")
        print("=" * 35)
        
        while True:
            print("\nAvailable Commands:")
            print("  1. Show Status")
            print("  2. List Clients")
            print("  3. Start Client")
            print("  4. Stop Client")
            print("  5. Restart Client")
            print("  6. Create New Client")
            print("  7. Platform Logs")
            print("  0. Exit")
            
            try:
                choice = input("\nSelect option (0-7): ").strip()
                
                if choice == '0':
                    print("👋 Goodbye!")
                    break
                elif choice == '1':
                    await self.show_status()
                elif choice == '2':
                    await self._list_clients_interactive()
                elif choice == '3':
                    await self._start_client_interactive()
                elif choice == '4':
                    await self._stop_client_interactive()
                elif choice == '5':
                    await self._restart_client_interactive()
                elif choice == '6':
                    await self._create_client_interactive()
                elif choice == '7':
                    await self._show_logs_interactive()
                else:
                    print("❌ Invalid option. Please select 0-7.")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

    async def _list_clients_interactive(self) -> None:
        """List clients in interactive mode."""
        clients = self.client_manager.list_clients()
        
        if not clients:
            print("📋 No clients configured.")
            return
            
        print(f"\n📋 Configured Clients ({len(clients)}):")
        for i, client in enumerate(clients, 1):
            status_emoji = "🟢" if client.status == "active" else "🔴"
            print(f"  {i}. {status_emoji} {client.display_name} ({client.client_id})")
            print(f"     Plan: {client.plan.title()} | Fee: ${client.monthly_fee}/month")

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
        print("For detailed client creation, use: python -m platform.deployment_tools new-client")
        
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
        print(f"  python -m platform.deployment_tools new-client")

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
    parser = argparse.ArgumentParser(
        description="Multi-Client Discord Bot Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python platform_main.py                    # Start all enabled clients
  python platform_main.py --client alpha     # Start specific client only
  python platform_main.py --status          # Show platform status
  python platform_main.py --interactive     # Interactive management mode
        """
    )
    
    parser.add_argument(
        '--client', '-c',
        help='Start specific client only'
    )
    parser.add_argument(
        '--status', '-s',
        action='store_true',
        help='Show platform status and exit'
    )
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Interactive management mode'
    )
    
    args = parser.parse_args()
    
    platform = PlatformMain()
    platform._setup_signal_handlers()
    
    try:
        if args.status:
            await platform.show_status()
        elif args.interactive:
            await platform.interactive_mode()
        else:
            await platform.start_platform(client_filter=args.client)
            
    except KeyboardInterrupt:
        print("\n🛑 Platform stopped by user")
    except Exception as e:
        print(f"❌ Platform error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
