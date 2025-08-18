#!/usr/bin/env python3
"""
Platform Main Entry Point
=========================

Multi-client Discord bot platform launcher and management interface.
Enhanced with auto-detection and smart logging capabilities.

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
import signal
import sys
from pathlib import Path
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from bot_platform.launcher import PlatformLauncher
from bot_platform.client_manager import ClientManager


import subprocess


def diagnose_client_startup():
    """Diagnose common client startup issues."""
    issues = []

    # Check if client_runner.py exists
    client_runner = Path("bot_platform/client_runner.py")
    if not client_runner.exists():
        issues.append("❌ client_runner.py not found")

    # Check if clients directory exists
    clients_dir = Path("clients")
    if not clients_dir.exists():
        issues.append("❌ clients/ directory not found")

    # Check specific client directories
    for client_name in ["default", "client_two"]:
        client_dir = clients_dir / client_name
        if not client_dir.exists():
            issues.append(f"❌ {client_name} directory missing")
        else:
            config_file = client_dir / "config.json"
            if not config_file.exists():
                issues.append(f"❌ {client_name}/config.json missing")

    # Try running client_runner.py with --help to see if it works
    try:
        result = subprocess.run([
            sys.executable,
            str(client_runner.resolve()),
            "--help"
        ], capture_output=True, text=True, timeout=5)

        if result.returncode != 0:
            issues.append(f"❌ client_runner.py failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        issues.append("❌ client_runner.py hangs on startup")
    except Exception as e:
        issues.append(f"❌ client_runner.py error: {e}")

    return issues


class PlatformMain:
    """Main platform controller."""

    def __init__(self, launcher: PlatformLauncher):
        """Initialize with pre-configured launcher."""
        self.launcher = launcher
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
                    success = self.launcher.start_client(client_filter)  # Removed await - this is sync
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
        """Enhanced status display with health information."""

        # DEBUG: Check auto-healing state before getting stats
        print(f"🔍 DEBUG: Auto-healing config = {self.launcher.auto_healing_config['enabled']}")

        print("📊 Enhanced Multi-Client Platform Status")
        print("=" * 50)

        # Get enhanced stats from launcher
        stats = self.launcher.get_enhanced_platform_stats()
        platform_stats = stats["platform"]
        health_stats = stats["health"]

        # DEBUG: Check what stats returned
        print(f"🔍 DEBUG: Stats auto_healing_enabled = {health_stats['auto_healing_enabled']}")

        # Platform overview
        print(f"🕐 Platform Uptime: {platform_stats['uptime_hours']:.1f} hours")
        print(f"🔄 Total Restarts: {platform_stats['total_restarts']}")
        print(f"📊 Total Clients: {platform_stats['total_clients']}")
        print(f"✅ Healthy Clients: {health_stats['healthy_clients']}")
        print(f"⚠️ Clients with Issues: {health_stats['clients_with_issues']}")
        print(f"🔧 Auto-fixes Applied: {health_stats['total_auto_fixes']}")
        print(f"🤖 Auto-healing: {'Enabled' if health_stats['auto_healing_enabled'] else 'Disabled'}")
        print()

        # Enhanced client details
        if stats["clients"]:
            print("Detailed Client Status:")
            print("-" * 50)

            for client_id, client_stats in stats["clients"].items():
                status_icon = "🟢" if client_stats["running"] else "🔴"
                health_icon = "✅" if client_stats["health_status"].get("config_health") == "healthy" else "⚠️"

                print(f"{status_icon} {client_id} {health_icon}")

                # Show health information
                health_status = client_stats["health_status"]
                config_health = health_status.get("config_health", "unknown")
                print(f"   🏥 Config Health: {config_health}")

                # Show issues if any
                issues = client_stats.get("config_issues", [])
                if issues:
                    print(f"   ⚠️ Issues: {len(issues)}")
                    for issue in issues[:3]:  # Show first 3 issues
                        print(f"      • {issue}")
                    if len(issues) > 3:
                        print(f"      • ... and {len(issues) - 3} more")

                # Show auto-fixes applied
                auto_fixes = client_stats.get("auto_fixes_applied", 0)
                if auto_fixes > 0:
                    print(f"   🔧 Auto-fixes applied: {auto_fixes}")

                # Show runtime stats if running
                if client_stats["running"]:
                    uptime_hours = client_stats["uptime_seconds"] / 3600
                    print(f"   ⏱️ Uptime: {uptime_hours:.1f} hours")
                    print(f"   💾 Memory: {client_stats['memory_mb']:.1f} MB")
                    print(f"   ⚡ CPU: {client_stats['cpu_percent']:.1f}%")
                    print(f"   🔄 Restarts: {client_stats['restart_count']}")

                print()

            # Show recent auto-fix log
            auto_fix_log = stats.get("auto_fix_log", [])
            if auto_fix_log:
                print("Recent Auto-fixes:")
                print("-" * 20)
                for fix in auto_fix_log[-5:]:  # Show last 5
                    timestamp = fix.get("timestamp", "Unknown")[:19]  # Remove microseconds

                    # Handle different log entry formats
                    action = fix.get("action") or fix.get("fix_applied") or fix.get("description") or "Unknown action"

                    print(f"   {timestamp}: {action}")
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
            print("  7. Run diagnostics")
            print("  8. Quit")

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
                    await self.diagnose_platform()
                elif choice == "8":
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
                success = self.launcher.start_client(client_id)  # Removed await - this is sync
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
                success = self.launcher.stop_client(client_id)  # This one IS async
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
                success = self.launcher.restart_client(client_id)  # This one IS async
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
        print("  For detailed logs, check: bot_platform/logs/")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(sig, frame):
            print(f"\n🛑 Received signal {sig}, shutting down...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def diagnose_platform(self) -> None:
        """Diagnose platform issues."""
        print("🔍 Platform Diagnostics")
        print("=" * 30)

        issues = diagnose_client_startup()
        if issues:
            print("❌ Issues found:")
            for issue in issues:
                print(f"   {issue}")
        else:
            print("✅ Basic checks passed")

        # Check auto-healing status
        print(f"\n🤖 Auto-healing: {'Enabled' if self.launcher.auto_healing_config['enabled'] else 'Disabled'}")

        # Check client configs
        print(f"\n📊 Configured clients: {len(self.launcher.client_configs)}")
        for client_id, config in self.launcher.client_configs.items():
            status = "🟢" if config.enabled else "🔴"
            print(f"   {status} {client_id}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Multi-Client Discord Bot Platform")
    parser.add_argument("--client", help="Start specific client only")
    parser.add_argument("--status", action="store_true", help="Show platform status")
    parser.add_argument("--interactive", action="store_true", help="Interactive management mode")

    # Enhanced arguments (removed duplicates)
    parser.add_argument("--no-auto-heal", action="store_true",
                        help="Disable auto-healing features")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be auto-fixed without making changes")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")

    args = parser.parse_args()

    # Create and configure launcher with enhanced arguments
    launcher = PlatformLauncher()

    # Handle enhanced arguments BEFORE discovery
    if args.no_auto_heal:
        launcher.auto_healing_config["enabled"] = False
        launcher.logger.info("🚫 Auto-healing disabled via command line")

    if args.dry_run:
        launcher.auto_healing_config["enabled"] = False
        launcher.logger.info("🔍 Dry-run mode: Auto-healing disabled")

    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
        launcher.logger.info("🔍 Verbose logging enabled")

    # Create platform manager with configured launcher
    platform = PlatformMain(launcher)

    # Handle command-line arguments
    if args.status:
        await platform.show_status()
    elif args.interactive:
        await platform.interactive_mode()
    else:
        await platform.start_platform(args.client)


if __name__ == "__main__":
    asyncio.run(main())
