#!/usr/bin/env python3
"""
Process Debugging Utility
=====================================================

Utility for debugging process issues with the platform's architecture.

Usage:
    python debug_processes.py --check           # Check for issues
    python debug_processes.py --cleanup         # Clean up orphaned processes
    python debug_processes.py --status          # Show detailed process status
    python debug_processes.py --kill-all        # Emergency: kill all client processes
"""

import argparse
import sys
import psutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from bot_platform.service_manager import PlatformOrchestrator
except ImportError:
    print("❌ Could not import new architecture. Make sure you've implemented the clean architecture.")
    sys.exit(1)


class ProcessDebuggerV2:
    """Debug and analyze processes for the new clean architecture."""

    def __init__(self):
        self.orchestrator = None

    def find_all_client_processes(self) -> List[Dict[str, Any]]:
        """Find all client_runner.py processes in the system."""
        processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'status']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and 'client_runner.py' in ' '.join(cmdline):
                    client_id = None
                    for arg in cmdline:
                        if arg.startswith('--client-id='):
                            client_id = arg.split('=', 1)[1]
                            break

                    processes.append({
                        'pid': proc.info['pid'],
                        'client_id': client_id,
                        'cmdline': cmdline,
                        'create_time': proc.info['create_time'],
                        'status': proc.info['status'],
                        'is_running': proc.is_running(),
                        'memory_mb': proc.memory_info().rss / 1024 / 1024 if proc.is_running() else 0,
                        'process_type': 'runner'
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        return processes

    def find_all_python_processes(self) -> List[Dict[str, Any]]:
        """Find all Python processes that might be Discord bots."""
        processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'status']):
            try:
                cmdline = proc.info['cmdline']
                if (cmdline and
                        ('python' in proc.info['name'].lower() or 'python' in str(cmdline[0]).lower()) and
                        len(cmdline) > 1 and
                        'client_runner.py' in ' '.join(cmdline)):

                    # Determine if this is a runner or bot process
                    if any('--client-id=' in arg for arg in cmdline):
                        process_type = 'runner'
                        client_id = None
                        for arg in cmdline:
                            if arg.startswith('--client-id='):
                                client_id = arg.split('=', 1)[1]
                                break
                    else:
                        # This might be a spawned bot process
                        process_type = 'bot'
                        client_id = 'unknown'

                    processes.append({
                        'pid': proc.info['pid'],
                        'client_id': client_id,
                        'cmdline': cmdline,
                        'create_time': proc.info['create_time'],
                        'status': proc.info['status'],
                        'is_running': proc.is_running(),
                        'memory_mb': proc.memory_info().rss / 1024 / 1024 if proc.is_running() else 0,
                        'process_type': process_type
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        return processes

    def analyze_architecture_status(self) -> Dict[str, Any]:
        """Analyze process status using new architecture."""
        print("🔍 Analyzing new architecture process status...")

        # Find all related processes
        runner_processes = self.find_all_client_processes()

        # Try to load new architecture state
        platform_processes = {}
        try:
            self.orchestrator = PlatformOrchestrator()
            if self.orchestrator.initialize():
                platform_processes = self.orchestrator.process_manager.get_all_processes()
        except Exception as e:
            print(f"⚠️ Could not load new architecture state: {e}")

        # Analyze the situation
        analysis = {
            'runner_processes': runner_processes,
            'platform_tracked': platform_processes,
            'architecture_status': 'new' if platform_processes else 'unknown',
            'summary': {
                'total_runner_processes': len(runner_processes),
                'platform_tracked': len(platform_processes),
                'architecture_working': len(platform_processes) > 0
            }
        }

        # Group processes by client
        client_processes = {}
        for proc in runner_processes:
            client_id = proc['client_id']
            if client_id:
                if client_id not in client_processes:
                    client_processes[client_id] = []
                client_processes[client_id].append(proc)

        analysis['client_processes'] = client_processes

        return analysis

    def print_architecture_status(self, analysis: Dict[str, Any]) -> None:
        """Print status report for new architecture."""
        print("\n📊 NEW ARCHITECTURE PROCESS STATUS")
        print("=" * 60)

        summary = analysis['summary']
        print(f"🔍 Runner Processes Found: {summary['total_runner_processes']}")
        print(f"🎮 Platform Tracked: {summary['platform_tracked']}")
        print(
            f"🏗️ Architecture Status: {'✅ New Clean Architecture' if summary['architecture_working'] else '❌ Old/Unknown'}")
        print()

        # Show platform tracked processes
        if analysis['platform_tracked']:
            print("🎮 PLATFORM MANAGED PROCESSES:")
            print("-" * 40)
            for client_id, process_info in analysis['platform_tracked'].items():
                status_icon = "🟢" if process_info.get('running') else "🔴"
                pid = process_info.get('pid', 'unknown')
                memory = process_info.get('memory_mb', 0)
                source = process_info.get('source', 'unknown')
                print(f"{status_icon} {client_id}: PID {pid} ({memory:.1f}MB) • Source: {source}")

        # Show system processes by client
        client_processes = analysis['client_processes']
        if client_processes:
            print(f"\n🖥️ SYSTEM PROCESSES BY CLIENT:")
            print("-" * 40)
            for client_id, processes in client_processes.items():
                print(f"\n📁 Client: {client_id}")
                for proc in processes:
                    status_icon = "🟢" if proc['is_running'] else "🔴"
                    created = datetime.fromtimestamp(proc['create_time']).strftime("%H:%M:%S")
                    print(
                        f"  {status_icon} PID {proc['pid']}: {proc['process_type']} (started {created}, {proc['memory_mb']:.1f}MB)")

        # Analysis
        if summary['architecture_working']:
            print(f"\n✅ NEW ARCHITECTURE STATUS: WORKING CORRECTLY")
            print("   • Platform is tracking processes properly")
            print("   • ProcessManager is functioning")
            print("   • Clean architecture successfully implemented")

            # Check if this is normal behavior
            total_clients = len(client_processes)
            total_processes = summary['total_runner_processes']
            if total_processes == total_clients:
                print("   • Process count is normal (1 runner per client)")
            elif total_processes == total_clients * 2:
                print("   • Process count shows runner + bot processes (normal)")
            else:
                print(f"   • Unusual process count: {total_processes} processes for {total_clients} clients")
        else:
            print(f"\n⚠️ ARCHITECTURE STATUS: UNKNOWN")
            print("   • Could not connect to new architecture")
            print("   • Platform might not be initialized")
            print("   • Check if new architecture files are in place")

    def cleanup_architecture_processes(self, analysis: Dict[str, Any], dry_run: bool = False) -> None:
        """Clean up processes using new architecture knowledge."""
        if not analysis['summary']['architecture_working']:
            print("❌ Cannot perform intelligent cleanup - new architecture not detected")
            print("💡 Use --kill-all for emergency cleanup")
            return

        print("🔧 Performing intelligent cleanup using new architecture...")

        # Use the platform's process manager for cleanup
        if self.orchestrator:
            try:
                dead_processes = self.orchestrator.process_manager.cleanup_dead_processes()
                if dead_processes:
                    print(f"🧹 Cleaned up {len(dead_processes)} dead processes: {', '.join(dead_processes)}")
                else:
                    print("✅ No cleanup needed - all processes healthy")
            except Exception as e:
                print(f"❌ Cleanup error: {e}")

    def emergency_kill_all(self, confirm: bool = False) -> None:
        """Emergency function to kill all client processes."""
        if not confirm:
            response = input("⚠️ This will kill ALL client processes. Are you sure? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cancelled")
                return

        runner_processes = self.find_all_client_processes()
        killed = 0

        for proc in runner_processes:
            try:
                psutil.Process(proc['pid']).terminate()
                print(f"🔪 Terminated {proc['client_id']} runner (PID {proc['pid']})")
                killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                print(f"❌ Could not terminate PID {proc['pid']}: {e}")

        print(f"\n✅ Terminated {killed} runner processes")
        print("💡 Bot processes should stop automatically when runners terminate")


def main():
    parser = argparse.ArgumentParser(description="Debug new architecture process issues")
    parser.add_argument("--check", action="store_true", help="Check for process issues")
    parser.add_argument("--cleanup", action="store_true", help="Clean up problematic processes")
    parser.add_argument("--status", action="store_true", help="Show detailed process status")
    parser.add_argument("--kill-all", action="store_true", help="Kill all client processes (emergency)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")

    args = parser.parse_args()

    debugger = ProcessDebuggerV2()

    if args.check or args.status or not any([args.cleanup, args.kill_all]):
        # Default action: analyze and report
        analysis = debugger.analyze_architecture_status()
        debugger.print_architecture_status(analysis)

    if args.cleanup:
        analysis = debugger.analyze_architecture_status()
        debugger.cleanup_architecture_processes(analysis, dry_run=args.dry_run)

    if args.kill_all:
        debugger.emergency_kill_all()


if __name__ == "__main__":
    main()
