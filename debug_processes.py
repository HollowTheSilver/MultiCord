#!/usr/bin/env python3
"""
Process Debugging Utility
=========================

Utility script to debug and fix process tracking issues in the Discord bot platform.
This script helps identify duplicate processes, orphaned processes, and synchronization issues.

Usage:
    python debug_processes.py --check           # Check for issues
    python debug_processes.py --cleanup         # Clean up orphaned processes
    python debug_processes.py --status          # Show detailed process status
    python debug_processes.py --kill-all        # Emergency: kill all client processes
"""

import argparse
import sys
import json
import psutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from bot_platform.launcher import PlatformLauncher
except ImportError:
    print("❌ Could not import PlatformLauncher. Run from project root directory.")
    sys.exit(1)


class ProcessDebugger:
    """Debug and fix process tracking issues."""

    def __init__(self):
        self.launcher = None

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
                        'memory_mb': proc.memory_info().rss / 1024 / 1024 if proc.is_running() else 0
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        return processes

    def check_process_issues(self) -> Dict[str, Any]:
        """Check for various process-related issues."""
        print("🔍 Analyzing process status...")

        # Find all system processes
        system_processes = self.find_all_client_processes()

        # Try to load launcher state
        launcher_processes = {}
        try:
            self.launcher = PlatformLauncher()
            launcher_processes = {
                client_id: {
                    'pid': info.pid,
                    'started_at': info.started_at.timestamp() if info.started_at else None,
                    'process_exists': info.process is not None,
                    'process_poll': info.process.poll() if info.process else 'no_process'
                }
                for client_id, info in self.launcher.client_processes.items()
            }
        except Exception as e:
            print(f"⚠️ Could not load launcher state: {e}")

        # Analyze issues
        issues = {
            'duplicate_processes': [],
            'orphaned_processes': [],
            'missing_processes': [],
            'zombie_processes': [],
            'platform_sync_issues': []
        }

        # Check for duplicates (same client_id, multiple PIDs)
        client_pids = {}
        for proc in system_processes:
            client_id = proc['client_id']
            if client_id:
                if client_id not in client_pids:
                    client_pids[client_id] = []
                client_pids[client_id].append(proc)

        for client_id, proc_list in client_pids.items():
            if len(proc_list) > 1:
                issues['duplicate_processes'].append({
                    'client_id': client_id,
                    'processes': proc_list
                })

        # Check for zombies
        for proc in system_processes:
            if proc['status'] == psutil.STATUS_ZOMBIE:
                issues['zombie_processes'].append(proc)

        # Check platform sync issues
        for client_id, launcher_info in launcher_processes.items():
            # Find corresponding system process
            system_proc = None
            for proc in system_processes:
                if proc['client_id'] == client_id and proc['pid'] == launcher_info['pid']:
                    system_proc = proc
                    break

            if not system_proc:
                issues['missing_processes'].append({
                    'client_id': client_id,
                    'launcher_pid': launcher_info['pid'],
                    'issue': 'Platform thinks process exists but not found in system'
                })
            elif not system_proc['is_running']:
                issues['platform_sync_issues'].append({
                    'client_id': client_id,
                    'pid': launcher_info['pid'],
                    'issue': 'Platform tracking dead process'
                })

        # Check for orphaned processes
        for proc in system_processes:
            client_id = proc['client_id']
            if client_id and client_id not in launcher_processes:
                issues['orphaned_processes'].append(proc)

        return {
            'system_processes': system_processes,
            'launcher_processes': launcher_processes,
            'issues': issues,
            'summary': {
                'total_system_processes': len(system_processes),
                'total_launcher_tracked': len(launcher_processes),
                'total_issues': sum(len(issue_list) for issue_list in issues.values())
            }
        }

    def print_status_report(self, analysis: Dict[str, Any]) -> None:
        """Print a detailed status report."""
        print("\n📊 PROCESS STATUS REPORT")
        print("=" * 60)

        summary = analysis['summary']
        print(f"🔍 System Processes Found: {summary['total_system_processes']}")
        print(f"🎮 Platform Tracked: {summary['total_launcher_tracked']}")
        print(f"⚠️ Total Issues: {summary['total_issues']}")
        print()

        # Show system processes
        if analysis['system_processes']:
            print("🖥️ SYSTEM PROCESSES:")
            print("-" * 40)
            for proc in analysis['system_processes']:
                status_icon = "🟢" if proc['is_running'] else "🔴"
                created = datetime.fromtimestamp(proc['create_time']).strftime("%H:%M:%S")
                print(
                    f"{status_icon} PID {proc['pid']}: {proc['client_id']} (started {created}, {proc['memory_mb']:.1f}MB)")

        # Show platform tracked
        if analysis['launcher_processes']:
            print(f"\n🎮 PLATFORM TRACKED:")
            print("-" * 40)
            for client_id, info in analysis['launcher_processes'].items():
                poll_status = "running" if info['process_poll'] is None else f"exited({info['process_poll']})"
                print(f"📝 {client_id}: PID {info['pid']} ({poll_status})")

        # Show issues
        issues = analysis['issues']
        if any(issues.values()):
            print(f"\n⚠️ ISSUES DETECTED:")
            print("-" * 40)

            if issues['duplicate_processes']:
                print("🚨 DUPLICATE PROCESSES:")
                for dup in issues['duplicate_processes']:
                    print(f"   Client '{dup['client_id']}' has {len(dup['processes'])} processes:")
                    for proc in dup['processes']:
                        print(f"      - PID {proc['pid']} ({proc['status']})")

            if issues['orphaned_processes']:
                print("👻 ORPHANED PROCESSES (not tracked by platform):")
                for proc in issues['orphaned_processes']:
                    print(f"   - PID {proc['pid']}: {proc['client_id']}")

            if issues['missing_processes']:
                print("❓ MISSING PROCESSES (platform expects but not found):")
                for missing in issues['missing_processes']:
                    print(f"   - {missing['client_id']}: {missing['issue']}")

            if issues['platform_sync_issues']:
                print("🔄 SYNC ISSUES (platform tracking problems):")
                for sync in issues['platform_sync_issues']:
                    print(f"   - {sync['client_id']} PID {sync['pid']}: {sync['issue']}")

            if issues['zombie_processes']:
                print("🧟 ZOMBIE PROCESSES:")
                for zombie in issues['zombie_processes']:
                    print(f"   - PID {zombie['pid']}: {zombie['client_id']}")
        else:
            print(f"\n✅ NO ISSUES DETECTED")

    def cleanup_processes(self, analysis: Dict[str, Any], dry_run: bool = False) -> None:
        """Clean up problematic processes."""
        issues = analysis['issues']
        actions = []

        # Handle duplicates (keep newest, kill older)
        for dup in issues['duplicate_processes']:
            processes = sorted(dup['processes'], key=lambda p: p['create_time'], reverse=True)
            keep_proc = processes[0]
            kill_procs = processes[1:]

            actions.append(f"Keep newest {dup['client_id']} process (PID {keep_proc['pid']})")
            for proc in kill_procs:
                actions.append(f"Kill duplicate {dup['client_id']} process (PID {proc['pid']})")
                if not dry_run:
                    try:
                        psutil.Process(proc['pid']).terminate()
                        print(f"🔪 Terminated duplicate process PID {proc['pid']}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        print(f"❌ Could not terminate PID {proc['pid']}: {e}")

        # Handle zombies
        for zombie in issues['zombie_processes']:
            actions.append(f"Clean up zombie process (PID {zombie['pid']})")
            if not dry_run:
                try:
                    psutil.Process(zombie['pid']).kill()
                    print(f"🧟 Killed zombie process PID {zombie['pid']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    print(f"❌ Could not kill zombie PID {zombie['pid']}: {e}")

        if dry_run:
            print(f"\n🔍 DRY RUN - Would perform {len(actions)} actions:")
            for action in actions:
                print(f"   • {action}")
        elif not actions:
            print("✅ No cleanup actions needed")

    def kill_all_client_processes(self, confirm: bool = False) -> None:
        """Emergency function to kill all client processes."""
        if not confirm:
            response = input("⚠️ This will kill ALL client processes. Are you sure? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cancelled")
                return

        processes = self.find_all_client_processes()
        killed = 0

        for proc in processes:
            try:
                psutil.Process(proc['pid']).terminate()
                print(f"🔪 Terminated {proc['client_id']} (PID {proc['pid']})")
                killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                print(f"❌ Could not terminate PID {proc['pid']}: {e}")

        print(f"\n✅ Terminated {killed} processes")


def main():
    parser = argparse.ArgumentParser(description="Debug platform process issues")
    parser.add_argument("--check", action="store_true", help="Check for process issues")
    parser.add_argument("--cleanup", action="store_true", help="Clean up problematic processes")
    parser.add_argument("--status", action="store_true", help="Show detailed process status")
    parser.add_argument("--kill-all", action="store_true", help="Kill all client processes (emergency)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")

    args = parser.parse_args()

    debugger = ProcessDebugger()

    if args.check or args.status or not any([args.cleanup, args.kill_all]):
        # Default action: analyze and report
        analysis = debugger.check_process_issues()
        debugger.print_status_report(analysis)

        if analysis['summary']['total_issues'] > 0:
            print(f"\n💡 Run with --cleanup to fix issues automatically")

    if args.cleanup:
        analysis = debugger.check_process_issues()
        debugger.cleanup_processes(analysis, dry_run=args.dry_run)

    if args.kill_all:
        debugger.kill_all_client_processes()


if __name__ == "__main__":
    main()
