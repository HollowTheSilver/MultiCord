"""
Process Manager - Unified Process Management
==========================================

Single source of truth for all client process operations.
Eliminates the competing discovery vs launch systems.
"""

import sys
import subprocess
import psutil
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from core.utils.loguruConfig import configure_logger


class ProcessSource(Enum):
    """Source of process information."""
    DISCOVERED = "discovered"  # Found via system scan
    LAUNCHED = "launched"  # Started by us


@dataclass
class ProcessInfo:
    """Clean process information without wrappers."""
    client_id: str
    pid: int
    started_at: datetime
    source: ProcessSource
    subprocess_handle: Optional[subprocess.Popen] = None  # Only for launched processes
    restart_count: int = 0
    last_restart: Optional[datetime] = None

    @property
    def is_running(self) -> bool:
        """Check if process is actually running."""
        try:
            proc = psutil.Process(self.pid)
            return proc.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    @property
    def memory_mb(self) -> float:
        """Get memory usage in MB."""
        try:
            proc = psutil.Process(self.pid)
            return proc.memory_info().rss / 1024 / 1024
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    @property
    def cpu_percent(self) -> float:
        """Get CPU usage percentage."""
        try:
            proc = psutil.Process(self.pid)
            return proc.cpu_percent(interval=0.1)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    def terminate(self) -> bool:
        """Terminate the process gracefully."""
        try:
            if self.subprocess_handle:
                # Use subprocess handle if available
                self.subprocess_handle.terminate()
                try:
                    self.subprocess_handle.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.subprocess_handle.kill()
                    self.subprocess_handle.wait()
                return True
            else:
                # Use psutil for discovered processes
                proc = psutil.Process(self.pid)
                proc.terminate()
                proc.wait(timeout=10)
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
            # Force kill if graceful termination fails
            try:
                if self.subprocess_handle:
                    self.subprocess_handle.kill()
                else:
                    psutil.Process(self.pid).kill()
                return True
            except:
                return False


class ProcessManager:
    """Unified process management - single source of truth."""

    def __init__(self):
        """Initialize process manager."""
        self.logger = configure_logger(
            log_dir="bot_platform/logs",
            level="INFO",
            format_extra=True,
            discord_compat=True
        )

        # Thread-safe process registry
        self._processes: Dict[str, ProcessInfo] = {}
        self._lock = threading.RLock()

        # Discover existing processes on startup
        self.discover_and_register_existing()

    def discover_and_register_existing(self) -> int:
        """Discover and register existing client processes."""
        discovered_count = 0

        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    cmdline = proc.info['cmdline']
                    if not cmdline or len(cmdline) < 2:
                        continue

                    # Look for client runner processes
                    if 'client_runner.py' not in ' '.join(cmdline):
                        continue

                    # Extract client ID
                    client_id = None
                    for arg in cmdline:
                        if arg.startswith('--client-id='):
                            client_id = arg.split('=', 1)[1]
                            break

                    if not client_id:
                        continue

                    # Register discovered process
                    with self._lock:
                        if client_id not in self._processes:
                            process_info = ProcessInfo(
                                client_id=client_id,
                                pid=proc.info['pid'],
                                started_at=datetime.fromtimestamp(proc.info['create_time'], tz=timezone.utc),
                                source=ProcessSource.DISCOVERED
                            )
                            self._processes[client_id] = process_info
                            discovered_count += 1
                            self.logger.info(f"🔗 Discovered existing process: {client_id} (PID: {proc.info['pid']})")

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception as e:
            self.logger.error(f"Error during process discovery: {e}")

        if discovered_count > 0:
            self.logger.info(f"✅ Discovered and registered {discovered_count} existing processes")

        return discovered_count

    def start_process(self, client_id: str, client_configs: Dict) -> bool:
        """Start a new client process."""
        if client_id not in client_configs:
            self.logger.error(f"Client {client_id} not found in configuration")
            return False

        # Check if already running
        with self._lock:
            if client_id in self._processes:
                process_info = self._processes[client_id]
                if process_info.is_running:
                    self.logger.warning(f"Client {client_id} is already running (PID: {process_info.pid})")
                    return True
                else:
                    # Clean up dead process entry
                    self.logger.info(f"Cleaning up dead process entry for {client_id}")
                    del self._processes[client_id]

        config = client_configs[client_id]
        if not getattr(config, 'enabled', True):
            self.logger.warning(f"Client {client_id} is disabled")
            return False

        try:
            # Build command
            cmd = [
                sys.executable,  # This ensures we use the same Python interpreter
                str(Path("bot_platform/client_runner.py").resolve()),
                f"--client-id={client_id}"
            ]

            # Set up environment
            import os
            env = os.environ.copy()
            if hasattr(config, 'custom_env'):
                env.update(config.custom_env)

            # Start process
            process = subprocess.Popen(
                cmd,
                env=env,
                cwd=Path.cwd()
            )

            # Register process
            with self._lock:
                process_info = ProcessInfo(
                    client_id=client_id,
                    pid=process.pid,
                    started_at=datetime.now(timezone.utc),
                    source=ProcessSource.LAUNCHED,
                    subprocess_handle=process
                )
                self._processes[client_id] = process_info

            self.logger.info(f"🚀 Started client {client_id} (PID: {process.pid})")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start client {client_id}: {e}")
            return False

    def stop_process(self, client_id: str) -> bool:
        """Stop a client process."""
        with self._lock:
            if client_id not in self._processes:
                self.logger.warning(f"Client {client_id} is not running")
                return True

            process_info = self._processes[client_id]

            try:
                if process_info.is_running:
                    self.logger.info(f"Stopping client {client_id}...")
                    success = process_info.terminate()
                    if success:
                        self.logger.info(f"✅ Stopped client {client_id}")
                    else:
                        self.logger.warning(f"⚠️ Force stopped client {client_id}")
                else:
                    self.logger.info(f"Client {client_id} was already stopped")

                # Remove from registry
                del self._processes[client_id]
                return True

            except Exception as e:
                self.logger.error(f"Error stopping client {client_id}: {e}")
                return False

    def restart_process(self, client_id: str, client_configs: Dict) -> bool:
        """Restart a client process."""
        self.logger.info(f"🔄 Restarting client {client_id}")

        # Update restart count
        with self._lock:
            if client_id in self._processes:
                self._processes[client_id].restart_count += 1
                self._processes[client_id].last_restart = datetime.now(timezone.utc)

        if self.stop_process(client_id):
            import time
            time.sleep(2)  # Brief pause
            return self.start_process(client_id, client_configs)
        return False

    def get_process_status(self, client_id: str) -> Optional[Dict]:
        """Get status of a specific process."""
        with self._lock:
            if client_id not in self._processes:
                return None

            process_info = self._processes[client_id]
            uptime = (datetime.now(timezone.utc) - process_info.started_at).total_seconds() / 3600

            return {
                "running": process_info.is_running,
                "pid": process_info.pid,
                "source": process_info.source.value,
                "uptime_hours": round(uptime, 1),
                "memory_mb": round(process_info.memory_mb, 1),
                "cpu_percent": round(process_info.cpu_percent, 1),
                "restart_count": process_info.restart_count,
                "last_restart": process_info.last_restart.isoformat() if process_info.last_restart else None,
                "status": "running" if process_info.is_running else "stopped"
            }

    def get_all_processes(self) -> Dict[str, Dict]:
        """Get status of all processes."""
        with self._lock:
            return {
                client_id: self.get_process_status(client_id)
                for client_id in self._processes
            }

    def cleanup_dead_processes(self) -> List[str]:
        """Remove dead processes from registry and return their IDs."""
        dead_processes = []

        with self._lock:
            for client_id in list(self._processes.keys()):
                process_info = self._processes[client_id]
                if not process_info.is_running:
                    dead_processes.append(client_id)
                    del self._processes[client_id]
                    self.logger.info(f"🧹 Cleaned up dead process: {client_id}")

        return dead_processes

    def get_running_client_ids(self) -> Set[str]:
        """Get set of currently running client IDs."""
        with self._lock:
            return {
                client_id for client_id, process_info in self._processes.items()
                if process_info.is_running
            }

    def force_kill_all(self) -> List[str]:
        """Emergency function to kill all client processes."""
        killed_processes = []

        with self._lock:
            for client_id in list(self._processes.keys()):
                try:
                    process_info = self._processes[client_id]
                    if process_info.is_running:
                        process_info.terminate()
                        killed_processes.append(client_id)
                        self.logger.info(f"🔪 Force killed client {client_id}")
                    del self._processes[client_id]
                except Exception as e:
                    self.logger.error(f"Error force killing {client_id}: {e}")

        return killed_processes
