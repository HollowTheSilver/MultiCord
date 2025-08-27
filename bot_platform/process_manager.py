"""
Process Manager - Unified Process Management with Proper I/O Redirection
==========================================

Root cause fix for process logging issue: Redirect client process stdout/stderr
to appropriate log files instead of inheriting parent terminal.
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
    log_file_path: Optional[str] = None  # Track where logs are redirected

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

        # Ensure platform logs directory exists
        platform_logs = Path("bot_platform/logs")
        platform_logs.mkdir(parents=True, exist_ok=True)

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
                                source=ProcessSource.DISCOVERED,
                                log_file_path=f"clients/{client_id}/logs/client_output.log"
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
        """Start a new client process with proper I/O redirection."""
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

            # Set up environment with UTF-8 encoding
            import os
            env = os.environ.copy()
            if hasattr(config, 'custom_env'):
                env.update(config.custom_env)

            # Force UTF-8 encoding for subprocess output
            env['PYTHONIOENCODING'] = 'utf-8'
            if os.name == 'nt':  # Windows
                env['PYTHONLEGACYWINDOWSSTDIO'] = '1'

            # Set up dedicated logging for client process
            client_logs_dir = Path(f"clients/{client_id}/logs")
            client_logs_dir.mkdir(parents=True, exist_ok=True)

            # Create unique log file for this process instance
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file_path = client_logs_dir / f"client_output_{timestamp}.log"

            # Open log file with proper UTF-8 encoding and error handling
            log_file = open(log_file_path, 'w', encoding='utf-8', errors='replace', buffering=1)

            # Start process with proper encoding and output redirection
            try:
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    cwd=Path.cwd(),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,  # Handle text encoding properly
                    encoding='utf-8',  # Force UTF-8 encoding
                    errors='replace',  # Replace problematic characters instead of failing
                    bufsize=1  # Line buffered
                )
            except Exception as encoding_error:
                # Fallback: try without explicit encoding if UTF-8 fails
                log_file.close()
                log_file = open(log_file_path, 'w', encoding='utf-8', errors='replace', buffering=1)

                process = subprocess.Popen(
                    cmd,
                    env=env,
                    cwd=Path.cwd(),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    bufsize=1
                )

            # Register process
            with self._lock:
                process_info = ProcessInfo(
                    client_id=client_id,
                    pid=process.pid,
                    started_at=datetime.now(timezone.utc),
                    source=ProcessSource.LAUNCHED,
                    subprocess_handle=process,
                    log_file_path=str(log_file_path)
                )
                self._processes[client_id] = process_info

            self.logger.info(f"🚀 Started client {client_id} (PID: {process.pid}, Logs: {log_file_path})")

            print(f"✅ Client {client_id} started with dedicated logging")
            print(f"📁 View real-time logs: tail -f {log_file_path}")

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

                # Close log file if we have the subprocess handle
                if process_info.subprocess_handle and process_info.subprocess_handle.stdout:
                    try:
                        process_info.subprocess_handle.stdout.close()
                    except:
                        pass

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

            status = {
                "running": process_info.is_running,
                "pid": process_info.pid,
                "source": process_info.source.value,
                "uptime_hours": round(uptime, 1),
                "memory_mb": round(process_info.memory_mb, 1),
                "cpu_percent": round(process_info.cpu_percent, 1),
                "restart_count": process_info.restart_count,
                "last_restart": process_info.last_restart.isoformat() if process_info.last_restart else None,
                "status": "running" if process_info.is_running else "stopped",
                "log_file": process_info.log_file_path
            }

            return status

    def get_all_processes(self) -> Dict[str, Dict]:
        """Get status of all processes."""
        with self._lock:
            return {
                client_id: self.get_process_status(client_id)
                for client_id in self._processes
            }

    def cleanup_dead_processes(self) -> List[str]:
        """Remove dead processes from registry and return their IDs."""
        cleaned_up = []

        with self._lock:
            dead_processes = []

            for client_id, process_info in self._processes.items():
                if not process_info.is_running:
                    dead_processes.append(client_id)

            for client_id in dead_processes:
                # Close any open file handles before removing
                process_info = self._processes[client_id]
                if process_info.subprocess_handle and process_info.subprocess_handle.stdout:
                    try:
                        process_info.subprocess_handle.stdout.close()
                    except:
                        pass

                del self._processes[client_id]
                cleaned_up.append(client_id)
                self.logger.info(f"🧹 Cleaned up dead process: {client_id}")

        return cleaned_up

    def get_running_client_ids(self) -> Set[str]:
        """Get set of currently running client IDs."""
        with self._lock:
            return {
                client_id for client_id, process_info in self._processes.items()
                if process_info.is_running
            }

    def get_client_log_path(self, client_id: str) -> Optional[str]:
        """Get the current log file path for a client."""
        with self._lock:
            if client_id in self._processes:
                return self._processes[client_id].log_file_path
            return None
