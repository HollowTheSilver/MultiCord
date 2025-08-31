"""
Process Manager - Fixed Architecture
====================================

CORE FIXES:
1. Separate discovery from launch operations
2. Check for conflicts BEFORE starting, not after
3. No automatic discovery after launch
4. Clean process lifecycle management
"""

import sys
import json
import subprocess
import psutil
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
    try:
        import msvcrt
        HAS_MSVCRT = True
    except ImportError:
        HAS_MSVCRT = False

from core.utils.loguruConfig import configure_logger


class ProcessSource(Enum):
    """Source of process information."""
    DISCOVERED = "discovered"
    LAUNCHED = "launched"


@dataclass
class ProcessInfo:
    """Process information without architectural confusion."""
    client_id: str
    pid: int
    started_at: datetime
    source: ProcessSource
    subprocess_handle: Optional[subprocess.Popen] = None
    restart_count: int = 0
    last_restart: Optional[datetime] = None
    log_file_path: Optional[str] = None
    terminal_instance: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['started_at'] = self.started_at.isoformat()
        if self.last_restart:
            data['last_restart'] = self.last_restart.isoformat()
        data.pop('subprocess_handle', None)
        data['source'] = self.source.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ProcessInfo':
        """Create ProcessInfo from dictionary."""
        data['started_at'] = datetime.fromisoformat(data['started_at'])
        if data.get('last_restart'):
            data['last_restart'] = datetime.fromisoformat(data['last_restart'])
        data['source'] = ProcessSource(data['source'])
        return cls(**data)

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


class ProcessRegistry:
    """Thread-safe persistent process registry."""
    
    def __init__(self, registry_path: str = "bot_platform/runtime/client_processes.json"):
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        
        if not self.registry_path.exists():
            self._write_registry({})
    
    def _lock_file(self, file_handle, exclusive=False):
        """Cross-platform file locking."""
        if HAS_FCNTL:
            lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(file_handle.fileno(), lock_type)
        elif HAS_MSVCRT and exclusive:
            msvcrt.locking(file_handle.fileno(), msvcrt.LK_LOCK, 1)
    
    def _unlock_file(self, file_handle):
        """Cross-platform file unlocking."""
        if HAS_FCNTL:
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
        elif HAS_MSVCRT:
            msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
    
    def _read_registry(self) -> Dict[str, Dict]:
        """Read process registry with locking."""
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                try:
                    self._lock_file(f, exclusive=False)
                    return json.load(f)
                finally:
                    try:
                        self._unlock_file(f)
                    except:
                        pass
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        except Exception:
            return {}
    
    def _write_registry(self, data: Dict[str, Dict]) -> bool:
        """Write process registry with locking."""
        try:
            with open(self.registry_path, 'w', encoding='utf-8') as f:
                try:
                    self._lock_file(f, exclusive=True)
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    return True
                finally:
                    try:
                        self._unlock_file(f)
                    except:
                        pass
        except Exception:
            return False
    
    def get_all_processes(self) -> Dict[str, ProcessInfo]:
        """Get all processes from registry."""
        with self._lock:
            data = self._read_registry()
            processes = {}
            for client_id, process_dict in data.items():
                try:
                    processes[client_id] = ProcessInfo.from_dict(process_dict)
                except Exception:
                    pass
            return processes
    
    def get_process(self, client_id: str) -> Optional[ProcessInfo]:
        """Get specific process from registry."""
        processes = self.get_all_processes()
        return processes.get(client_id)
    
    def add_process(self, process_info: ProcessInfo) -> bool:
        """Add process to registry."""
        with self._lock:
            data = self._read_registry()
            data[process_info.client_id] = process_info.to_dict()
            return self._write_registry(data)
    
    def remove_process(self, client_id: str) -> bool:
        """Remove process from registry."""
        with self._lock:
            data = self._read_registry()
            if client_id in data:
                del data[client_id]
                return self._write_registry(data)
            return True
    
    def cleanup_dead_processes(self) -> List[str]:
        """Remove dead processes and return their IDs."""
        with self._lock:
            processes = self.get_all_processes()
            dead_processes = []
            
            for client_id, process_info in processes.items():
                if not process_info.is_running:
                    dead_processes.append(client_id)
            
            if dead_processes:
                data = self._read_registry()
                for client_id in dead_processes:
                    data.pop(client_id, None)
                self._write_registry(data)
            
            return dead_processes


class ProcessManager:
    """Fixed process manager with clean separation of concerns."""

    def __init__(self):
        """Initialize with clean architecture."""
        self.logger = configure_logger(
            log_dir="bot_platform/logs",
            level="INFO",
            format_extra=True,
            discord_compat=True
        )

        self.registry = ProcessRegistry()
        self._subprocess_handles: Dict[str, subprocess.Popen] = {}
        self._lock = threading.RLock()
        
        import uuid
        self.terminal_id = str(uuid.uuid4())[:8]

        # Clean up only dead processes on startup - NO discovery
        self._cleanup_dead_only()

    def _cleanup_dead_only(self) -> None:
        """Clean up only dead processes - no discovery."""
        dead_processes = self.registry.cleanup_dead_processes()
        if dead_processes:
            self.logger.info(f"Cleaned up {len(dead_processes)} dead processes")

    def start_process(self, client_id: str, client_configs: Dict) -> bool:
        """
        FIXED: Start process with proper conflict resolution.
        
        NEW LOGIC:
        1. Check for existing processes FIRST
        2. Handle conflicts before starting
        3. Start new process
        4. Register it
        5. NO AUTOMATIC DISCOVERY
        """
        if client_id not in client_configs:
            self.logger.error(f"Client {client_id} not found in configuration")
            return False

        # STEP 1: Check for existing processes BEFORE starting
        existing_processes = self._find_running_processes_for_client(client_id)
        
        if existing_processes:
            self.logger.warning(f"Found {len(existing_processes)} existing processes for {client_id}")
            
            # Handle conflicts BEFORE starting new process
            conflict_resolved = self._handle_existing_process_conflict(client_id, existing_processes)
            if not conflict_resolved:
                self.logger.error(f"Could not resolve process conflict for {client_id}")
                return False

        # STEP 2: Verify configuration
        config = client_configs[client_id]
        if not getattr(config, 'enabled', True):
            self.logger.warning(f"Client {client_id} is disabled")
            return False

        # STEP 3: Start new process
        try:
            process_info = self._launch_new_process(client_id, config)
            if not process_info:
                return False

            # STEP 4: Register the launched process
            if self.registry.add_process(process_info):
                self.logger.info(f"Started client {client_id} (PID: {process_info.pid}, Terminal: {self.terminal_id})")
                print(f"✅ Client {client_id} started (PID: {process_info.pid})")
                if process_info.log_file_path:
                    print(f"📁 View logs: tail -f {process_info.log_file_path}")
                return True
            else:
                self.logger.error(f"Failed to register process {client_id}")
                self._terminate_process_info(process_info)
                return False

        except Exception as e:
            self.logger.error(f"Failed to start client {client_id}: {e}")
            return False

    def _find_running_processes_for_client(self, client_id: str) -> List[Dict]:
        """Find all running processes for a specific client."""
        running_processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    cmdline = proc.info['cmdline']
                    if not cmdline:
                        continue

                    # Look for client runner processes
                    if 'client_runner.py' not in ' '.join(cmdline):
                        continue

                    # Extract client ID
                    found_client_id = None
                    for arg in cmdline:
                        if arg.startswith('--client-id='):
                            found_client_id = arg.split('=', 1)[1]
                            break

                    if found_client_id == client_id:
                        running_processes.append({
                            'pid': proc.info['pid'],
                            'create_time': proc.info['create_time'],
                            'cmdline': cmdline
                        })

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        except Exception as e:
            self.logger.error(f"Error finding processes for {client_id}: {e}")

        return running_processes

    def _handle_existing_process_conflict(self, client_id: str, existing_processes: List[Dict]) -> bool:
        """Handle conflicts with existing processes."""
        try:
            if len(existing_processes) == 1:
                # Single existing process - check if it's in registry
                process = existing_processes[0]
                registry_process = self.registry.get_process(client_id)
                
                if registry_process and registry_process.pid == process['pid']:
                    self.logger.warning(f"Client {client_id} is already running (PID: {process['pid']})")
                    return False  # Don't start duplicate
                else:
                    # Orphaned process - terminate it
                    self.logger.info(f"Terminating orphaned process {client_id} (PID: {process['pid']})")
                    try:
                        psutil.Process(process['pid']).terminate()
                        import time
                        time.sleep(1)  # Give it time to stop
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    return True
            
            else:
                # Multiple processes - terminate all (this shouldn't happen)
                self.logger.error(f"Multiple processes found for {client_id} - terminating all")
                for process in existing_processes:
                    try:
                        self.logger.info(f"Terminating duplicate process {client_id} (PID: {process['pid']})")
                        psutil.Process(process['pid']).terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                import time
                time.sleep(1)  # Give them time to stop
                return True

        except Exception as e:
            self.logger.error(f"Error handling process conflict for {client_id}: {e}")
            return False

    def _launch_new_process(self, client_id: str, config) -> Optional[ProcessInfo]:
        """Launch a new process and return ProcessInfo."""
        try:
            cmd = [
                sys.executable,
                str(Path("bot_platform/client_runner.py").resolve()),
                f"--client-id={client_id}"
            ]

            # Set up environment
            import os
            env = os.environ.copy()
            if hasattr(config, 'custom_env'):
                env.update(config.custom_env)
            env['PYTHONIOENCODING'] = 'utf-8'
            if os.name == 'nt':
                env['PYTHONLEGACYWINDOWSSTDIO'] = '1'

            # Set up logging
            client_logs_dir = Path(f"clients/{client_id}/logs")
            client_logs_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file_path = client_logs_dir / f"client_output_{timestamp}.log"

            with open(log_file_path, 'w', encoding='utf-8', errors='replace', buffering=1) as log_file:
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    cwd=Path.cwd(),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1
                )

            # Store subprocess handle locally
            with self._lock:
                self._subprocess_handles[client_id] = process

            # Create ProcessInfo
            process_info = ProcessInfo(
                client_id=client_id,
                pid=process.pid,
                started_at=datetime.now(timezone.utc),
                source=ProcessSource.LAUNCHED,
                log_file_path=str(log_file_path),
                terminal_instance=self.terminal_id
            )

            return process_info

        except Exception as e:
            self.logger.error(f"Failed to launch process for {client_id}: {e}")
            return None

    def _terminate_process_info(self, process_info: ProcessInfo) -> bool:
        """Terminate a process using ProcessInfo."""
        try:
            # Try subprocess handle first if available
            with self._lock:
                subprocess_handle = self._subprocess_handles.get(process_info.client_id)
            
            if subprocess_handle:
                subprocess_handle.terminate()
                try:
                    subprocess_handle.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    subprocess_handle.kill()
                    subprocess_handle.wait()
                return True
            else:
                # Use psutil
                proc = psutil.Process(process_info.pid)
                proc.terminate()
                proc.wait(timeout=10)
                return True
        except Exception:
            try:
                if subprocess_handle:
                    subprocess_handle.kill()
                else:
                    psutil.Process(process_info.pid).kill()
                return True
            except:
                return False

    def stop_process(self, client_id: str) -> bool:
        """Stop a client process."""
        process_info = self.registry.get_process(client_id)
        if not process_info:
            return True  # Already stopped

        try:
            if not process_info.is_running:
                # Clean up registry silently
                self.registry.remove_process(client_id)
                with self._lock:
                    self._subprocess_handles.pop(client_id, None)
                return True

            self.logger.info(f"Stopping client {client_id} (PID: {process_info.pid})")
            
            # Try subprocess handle first
            subprocess_handle = None
            with self._lock:
                subprocess_handle = self._subprocess_handles.get(client_id)
            
            if subprocess_handle:
                success = self._terminate_subprocess(subprocess_handle)
            else:
                success = self._terminate_process_info(process_info)
            
            # Clean up
            with self._lock:
                self._subprocess_handles.pop(client_id, None)
            self.registry.remove_process(client_id)
            
            if success:
                self.logger.info(f"✅ Stopped client {client_id}")
            else:
                self.logger.warning(f"⚠️ Force stopped client {client_id}")
            
            return success

        except Exception as e:
            self.logger.error(f"Error stopping client {client_id}: {e}")
            return False

    def _terminate_subprocess(self, process: subprocess.Popen) -> bool:
        """Terminate subprocess handle."""
        try:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return True
        except Exception:
            try:
                process.kill()
                return True
            except:
                return False

    def restart_process(self, client_id: str, client_configs: Dict) -> bool:
        """Restart a client process."""
        self.logger.info(f"🔄 Restarting client {client_id}")
        
        if self.stop_process(client_id):
            import time
            time.sleep(2)
            return self.start_process(client_id, client_configs)
        return False

    def get_running_client_ids(self) -> Set[str]:
        """Get running client IDs."""
        processes = self.registry.get_all_processes()
        return {
            client_id for client_id, process_info in processes.items()
            if process_info.is_running
        }

    def get_process_status(self, client_id: str) -> Optional[Dict]:
        """Get process status."""
        process_info = self.registry.get_process(client_id)
        if not process_info:
            return None

        uptime = (datetime.now(timezone.utc) - process_info.started_at).total_seconds() / 3600

        return {
            "running": process_info.is_running,
            "pid": process_info.pid,
            "source": process_info.source.value,
            "uptime_hours": round(uptime, 1),
            "memory_mb": round(process_info.memory_mb, 1),
            "cpu_percent": round(process_info.cpu_percent, 1),
            "restart_count": process_info.restart_count,
            "status": "running" if process_info.is_running else "stopped",
            "log_file": process_info.log_file_path,
            "terminal_instance": process_info.terminal_instance
        }

    def get_all_processes(self) -> Dict[str, Dict]:
        """Get status of all processes."""
        processes = self.registry.get_all_processes()
        return {
            client_id: self.get_process_status(client_id)
            for client_id in processes.keys()
        }

    def cleanup_dead_processes(self) -> List[str]:
        """Remove dead processes from registry."""
        return self.registry.cleanup_dead_processes()

    def get_client_log_path(self, client_id: str) -> Optional[str]:
        """Get log file path for a client."""
        process_info = self.registry.get_process(client_id)
        return process_info.log_file_path if process_info else None

    # DISCOVERY METHODS - NOW SEPARATE FROM LAUNCH OPERATIONS
    
    def manual_discovery(self) -> int:
        """Manual discovery - only call when needed."""
        self.logger.info("Running manual process discovery")
        return self._discover_orphaned_processes()

    def _discover_orphaned_processes(self) -> int:
        """Discover and register orphaned processes."""
        discovered_count = 0
        existing_processes = self.registry.get_all_processes()
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    cmdline = proc.info['cmdline']
                    if not cmdline or 'client_runner.py' not in ' '.join(cmdline):
                        continue

                    client_id = None
                    for arg in cmdline:
                        if arg.startswith('--client-id='):
                            client_id = arg.split('=', 1)[1]
                            break

                    if not client_id:
                        continue

                    # Check if already registered correctly
                    if client_id in existing_processes:
                        existing = existing_processes[client_id]
                        if existing.pid == proc.info['pid'] and existing.is_running:
                            continue  # Already registered correctly

                    # Register discovered process
                    process_info = ProcessInfo(
                        client_id=client_id,
                        pid=proc.info['pid'],
                        started_at=datetime.fromtimestamp(proc.info['create_time'], tz=timezone.utc),
                        source=ProcessSource.DISCOVERED,
                        log_file_path=f"clients/{client_id}/logs/client_output.log",
                        terminal_instance="discovered"
                    )
                    
                    if self.registry.add_process(process_info):
                        discovered_count += 1
                        self.logger.info(f"🔗 Discovered orphaned process: {client_id} (PID: {proc.info['pid']})")

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception as e:
            self.logger.error(f"Error during discovery: {e}")

        if discovered_count > 0:
            self.logger.info(f"✅ Discovered {discovered_count} orphaned processes")

        return discovered_count

    # Compatibility methods for existing code
    def cleanup_and_discover(self) -> int:
        """
        DEPRECATED: Compatibility method.
        
        This method previously caused the bug by running discovery after launch.
        Now it only cleans up dead processes and does NOT run discovery.
        """
        dead_count = len(self.cleanup_dead_processes())
        if dead_count > 0:
            self.logger.info(f"🧹 Cleaned up {dead_count} dead processes")
        return dead_count

    def discover_and_register_new(self) -> int:
        """
        DEPRECATED: Compatibility method.
        
        This method previously caused conflicts with freshly launched processes.
        Now redirects to manual_discovery() which should only be called explicitly.
        """
        self.logger.warning("discover_and_register_new() is deprecated - use manual_discovery() explicitly")
        return self.manual_discovery()
