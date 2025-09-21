"""
Process orchestration for local multi-bot management.
Adapted from OLD/MultiCordRewrite1 with PostgreSQL dependencies removed.
"""

import asyncio
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

import psutil

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


@dataclass
class ProcessInfo:
    """Information about a running bot process."""
    process_id: str
    bot_name: str
    pid: int
    status: str  # running, stopped, error
    started_at: datetime
    port: Optional[int] = None
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    restart_count: int = 0
    last_heartbeat: Optional[datetime] = None
    log_path: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'process_id': self.process_id,
            'bot_name': self.bot_name,
            'pid': self.pid,
            'status': self.status,
            'started_at': self.started_at.isoformat(),
            'port': self.port,
            'memory_mb': self.memory_mb,
            'cpu_percent': self.cpu_percent,
            'restart_count': self.restart_count,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'log_path': self.log_path
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ProcessInfo':
        """Create from dictionary."""
        data['started_at'] = datetime.fromisoformat(data['started_at'])
        if data.get('last_heartbeat'):
            data['last_heartbeat'] = datetime.fromisoformat(data['last_heartbeat'])
        return cls(**data)


@dataclass
class HealthStatus:
    """Health status of a bot process."""
    is_running: bool
    memory_mb: float
    cpu_percent: float
    uptime_seconds: float
    last_check: datetime
    error_message: Optional[str] = None
    
    @property
    def is_healthy(self) -> bool:
        """Check if process is healthy based on thresholds."""
        if not self.is_running:
            return False
        if self.memory_mb > 1024:  # 1GB limit
            return False
        if self.cpu_percent > 95:  # 95% CPU limit
            return False
        return True


class ProcessStatus(Enum):
    """Process status enumeration."""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    STARTING = "starting"
    STOPPING = "stopping"


class FileLockingManager:
    """Cross-platform file locking for process registry."""
    
    @staticmethod
    def acquire_lock(file_handle, exclusive: bool = True) -> bool:
        """Acquire file lock with cross-platform support."""
        try:
            if HAS_FCNTL:
                lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                fcntl.flock(file_handle.fileno(), lock_type | fcntl.LOCK_NB)
                return True
            elif HAS_MSVCRT and exclusive:
                msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            return True  # No locking available, proceed anyway
        except (IOError, OSError):
            return False
    
    @staticmethod
    def release_lock(file_handle) -> bool:
        """Release file lock."""
        try:
            if HAS_FCNTL:
                fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
            elif HAS_MSVCRT:
                msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
            return True
        except:
            return False


class ProcessRegistry:
    """Local file-based process registry with thread safety."""
    
    def __init__(self, registry_path: Optional[Path] = None):
        """Initialize process registry."""
        self.registry_path = registry_path or (Path.home() / ".multicord" / "process_registry.json")
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_registry_exists()
    
    def _ensure_registry_exists(self):
        """Ensure registry file exists."""
        if not self.registry_path.exists():
            self.registry_path.write_text("{}")
    
    def register_process(self, process_info: ProcessInfo) -> bool:
        """Register a new process."""
        try:
            with open(self.registry_path, 'r+') as f:
                if not FileLockingManager.acquire_lock(f):
                    return False
                
                try:
                    registry = json.load(f)
                    registry[process_info.bot_name] = process_info.to_dict()
                    
                    f.seek(0)
                    json.dump(registry, f, indent=2)
                    f.truncate()
                    return True
                finally:
                    FileLockingManager.release_lock(f)
        except Exception as e:
            logging.error(f"Failed to register process: {e}")
            return False
    
    def get_process(self, bot_name: str) -> Optional[ProcessInfo]:
        """Get process info by bot name."""
        try:
            with open(self.registry_path, 'r') as f:
                if not FileLockingManager.acquire_lock(f, exclusive=False):
                    return None
                
                try:
                    registry = json.load(f)
                    if bot_name in registry:
                        return ProcessInfo.from_dict(registry[bot_name])
                    return None
                finally:
                    FileLockingManager.release_lock(f)
        except:
            return None
    
    def list_processes(self) -> List[ProcessInfo]:
        """List all registered processes."""
        try:
            with open(self.registry_path, 'r') as f:
                if not FileLockingManager.acquire_lock(f, exclusive=False):
                    return []
                
                try:
                    registry = json.load(f)
                    return [ProcessInfo.from_dict(data) for data in registry.values()]
                finally:
                    FileLockingManager.release_lock(f)
        except:
            return []
    
    def remove_process(self, bot_name: str) -> bool:
        """Remove process from registry."""
        try:
            with open(self.registry_path, 'r+') as f:
                if not FileLockingManager.acquire_lock(f):
                    return False
                
                try:
                    registry = json.load(f)
                    if bot_name in registry:
                        del registry[bot_name]
                        
                        f.seek(0)
                        json.dump(registry, f, indent=2)
                        f.truncate()
                        return True
                    return False
                finally:
                    FileLockingManager.release_lock(f)
        except:
            return False
    
    def cleanup_dead_processes(self) -> int:
        """Remove dead processes from registry."""
        cleaned = 0
        for process_info in self.list_processes():
            try:
                if not psutil.pid_exists(process_info.pid):
                    if self.remove_process(process_info.bot_name):
                        cleaned += 1
            except:
                pass
        return cleaned


class PortManager:
    """Manages port allocation for bot processes."""
    
    def __init__(self, start_port: int = 8100, end_port: int = 8200):
        """Initialize port manager."""
        self.start_port = start_port
        self.end_port = end_port
        self.allocated_ports: Set[int] = set()
    
    def allocate_port(self) -> Optional[int]:
        """Allocate an available port."""
        import socket
        
        for port in range(self.start_port, self.end_port):
            if port in self.allocated_ports:
                continue
                
            # Test if port is available
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', port))
                    self.allocated_ports.add(port)
                    return port
            except OSError:
                continue
        
        return None
    
    def release_port(self, port: int):
        """Release an allocated port."""
        self.allocated_ports.discard(port)


class ProcessOrchestrator:
    """Orchestrates bot process lifecycle with health monitoring."""
    
    def __init__(self, 
                 bots_dir: Optional[Path] = None,
                 logs_dir: Optional[Path] = None):
        """Initialize process orchestrator."""
        self.bots_dir = bots_dir or (Path.home() / ".multicord" / "bots")
        self.logs_dir = logs_dir or (Path.home() / ".multicord" / "logs")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        self.registry = ProcessRegistry()
        self.port_manager = PortManager()
        self.processes: Dict[str, subprocess.Popen] = {}
        self.logger = logging.getLogger(__name__)
    
    def start_bot(self, bot_name: str) -> Tuple[bool, str]:
        """
        Start a bot process with conflict resolution and monitoring.
        
        Returns:
            Tuple of (success, message)
        """
        # Check for conflicts
        existing = self.registry.get_process(bot_name)
        if existing and psutil.pid_exists(existing.pid):
            return False, f"Bot '{bot_name}' is already running (PID: {existing.pid})"
        
        # Clean up dead registry entry if exists
        if existing:
            self.registry.remove_process(bot_name)
        
        # Get bot path
        bot_path = self.bots_dir / bot_name
        if not bot_path.exists():
            return False, f"Bot '{bot_name}' not found"
        
        bot_file = bot_path / "bot.py"
        if not bot_file.exists():
            return False, f"Bot file not found: {bot_file}"
        
        # Allocate port
        port = self.port_manager.allocate_port()
        if not port:
            return False, "No available ports for bot"
        
        # Prepare environment
        env = os.environ.copy()
        env['BOT_NAME'] = bot_name
        env['BOT_PORT'] = str(port)
        env['BOT_CONFIG'] = str(bot_path / "config.toml")
        
        # Create log file
        log_file = self.logs_dir / f"{bot_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        try:
            # Start process
            with open(log_file, 'w') as log_handle:
                process = subprocess.Popen(
                    [sys.executable, str(bot_file)],
                    cwd=str(bot_path),
                    env=env,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
                )
            
            # Register process
            process_info = ProcessInfo(
                process_id=str(uuid4()),
                bot_name=bot_name,
                pid=process.pid,
                status=ProcessStatus.RUNNING.value,
                started_at=datetime.now(),
                port=port,
                log_path=str(log_file)
            )
            
            if self.registry.register_process(process_info):
                self.processes[bot_name] = process
                return True, f"Bot '{bot_name}' started successfully (PID: {process.pid}, Port: {port})"
            else:
                process.terminate()
                return False, "Failed to register process"
                
        except Exception as e:
            self.port_manager.release_port(port)
            return False, f"Failed to start bot: {e}"
    
    def stop_bot(self, bot_name: str, force: bool = False) -> Tuple[bool, str]:
        """
        Stop a bot process gracefully.
        
        Returns:
            Tuple of (success, message)
        """
        process_info = self.registry.get_process(bot_name)
        if not process_info:
            return False, f"Bot '{bot_name}' is not registered"
        
        try:
            if process_info.pid and psutil.pid_exists(process_info.pid):
                proc = psutil.Process(process_info.pid)
                
                # Try graceful termination first
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except psutil.TimeoutExpired:
                    if force:
                        proc.kill()
                        proc.wait()
                    else:
                        return False, "Bot did not stop gracefully. Use --force to kill."
            
            # Clean up registry
            self.registry.remove_process(bot_name)
            
            # Release port
            if process_info.port:
                self.port_manager.release_port(process_info.port)
            
            # Remove from local tracking
            if bot_name in self.processes:
                del self.processes[bot_name]
            
            return True, f"Bot '{bot_name}' stopped successfully"
            
        except Exception as e:
            return False, f"Failed to stop bot: {e}"
    
    def get_bot_health(self, bot_name: str) -> Optional[HealthStatus]:
        """Get health status of a bot."""
        process_info = self.registry.get_process(bot_name)
        if not process_info:
            return None
        
        try:
            if not psutil.pid_exists(process_info.pid):
                return HealthStatus(
                    is_running=False,
                    memory_mb=0,
                    cpu_percent=0,
                    uptime_seconds=0,
                    last_check=datetime.now(),
                    error_message="Process not found"
                )
            
            proc = psutil.Process(process_info.pid)
            memory_info = proc.memory_info()
            
            return HealthStatus(
                is_running=proc.is_running(),
                memory_mb=memory_info.rss / 1024 / 1024,
                cpu_percent=proc.cpu_percent(interval=0.1),
                uptime_seconds=(datetime.now() - process_info.started_at).total_seconds(),
                last_check=datetime.now()
            )
            
        except Exception as e:
            return HealthStatus(
                is_running=False,
                memory_mb=0,
                cpu_percent=0,
                uptime_seconds=0,
                last_check=datetime.now(),
                error_message=str(e)
            )
    
    def list_running_bots(self) -> List[Dict[str, Any]]:
        """List all running bots with health info."""
        running_bots = []
        
        # Clean up dead processes first
        self.registry.cleanup_dead_processes()
        
        for process_info in self.registry.list_processes():
            health = self.get_bot_health(process_info.bot_name)
            if health and health.is_running:
                running_bots.append({
                    'name': process_info.bot_name,
                    'pid': process_info.pid,
                    'port': process_info.port,
                    'status': 'healthy' if health.is_healthy else 'unhealthy',
                    'memory_mb': round(health.memory_mb, 2),
                    'cpu_percent': round(health.cpu_percent, 2),
                    'uptime_seconds': round(health.uptime_seconds),
                    'started_at': process_info.started_at.isoformat()
                })
        
        return running_bots
    
    def restart_bot(self, bot_name: str) -> Tuple[bool, str]:
        """Restart a bot process."""
        # Stop if running
        if self.registry.get_process(bot_name):
            success, message = self.stop_bot(bot_name, force=True)
            if not success:
                return False, f"Failed to stop bot for restart: {message}"
            
            # Wait for process to fully terminate
            time.sleep(1)
        
        # Start bot
        return self.start_bot(bot_name)


# Import os at the top level for environment variables
import os