"""
Process Orchestrator Service
===========================

Extracted and adapted from MultiCordOG ProcessManager.
Provides process lifecycle management with PostgreSQL integration
and strategy-independent operation.

Key Patterns Extracted:
- Thread-safe process registry with file locking
- Process conflict resolution before starting
- Health monitoring with psutil integration
- Cross-platform file locking
- Clean subprocess lifecycle management
"""

import asyncio
import logging
import threading
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4, UUID

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

# Platform imports
from ..entities.process_info import ProcessInfo, ProcessSource, HealthStatus
from ..strategies.bot_execution_strategy import ProcessHandle, BotConfiguration
from ..repositories.process_repository import ProcessRepository
from ..infrastructure.postgresql_pool import PostgreSQLConnectionPool


@dataclass
class ProcessConflictResult:
    """Result of process conflict resolution."""
    success: bool
    message: str
    conflicting_processes: List[int] = None
    action_taken: str = None


class FileLockingManager:
    """
    Cross-platform file locking utility extracted from MultiCordOG.
    
    Provides Windows and Unix compatible file locking for log files
    and other shared resources.
    """
    
    @staticmethod
    def lock_file(file_handle, exclusive: bool = False) -> bool:
        """
        Lock a file with cross-platform compatibility.
        
        Args:
            file_handle: Open file handle
            exclusive: Whether to acquire exclusive lock
            
        Returns:
            True if lock acquired successfully
        """
        try:
            if HAS_FCNTL:
                lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                fcntl.flock(file_handle.fileno(), lock_type)
                return True
            elif HAS_MSVCRT and exclusive:
                msvcrt.locking(file_handle.fileno(), msvcrt.LK_LOCK, 1)
                return True
            return True  # No locking available but continue
        except Exception:
            return False
    
    @staticmethod
    def unlock_file(file_handle) -> bool:
        """
        Unlock a file with cross-platform compatibility.
        
        Args:
            file_handle: Open file handle
            
        Returns:
            True if unlock successful
        """
        try:
            if HAS_FCNTL:
                fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
            elif HAS_MSVCRT:
                msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
            return True
        except Exception:
            return False


class ProcessConflictResolver:
    """
    Process conflict resolution extracted from MultiCordOG.
    
    Handles detection and resolution of conflicting bot processes
    before starting new instances.
    """
    
    def __init__(self, logger: logging.Logger = None):
        """Initialize conflict resolver."""
        self.logger = logger or logging.getLogger(__name__)
    
    async def resolve_conflicts(self, 
                              client_id: str, 
                              process_repository: ProcessRepository) -> ProcessConflictResult:
        """
        Resolve process conflicts before starting a bot.
        
        Args:
            client_id: Bot client identifier
            process_repository: Process data access
            
        Returns:
            ProcessConflictResult indicating success/failure and actions taken
        """
        try:
            # Step 1: Check for existing processes in registry
            existing_process = await process_repository.find_by_client_id(client_id)
            
            # Step 2: Check for running system processes
            running_processes = self._find_system_processes_for_client(client_id)
            
            # Step 3: Resolve conflicts
            if existing_process and existing_process.is_running:
                return ProcessConflictResult(
                    success=False,
                    message=f"Bot {client_id} is already running (PID: {existing_process.pid})",
                    conflicting_processes=[existing_process.pid],
                    action_taken="none"
                )
            
            if existing_process and not existing_process.is_running:
                # Clean up dead registry entry
                await process_repository.remove_process(existing_process.process_id)
                self.logger.info(f"Cleaned up dead process registry entry for {client_id}")
            
            if running_processes:
                # Terminate orphaned processes not in registry
                terminated_count = self._terminate_orphaned_processes(client_id, running_processes)
                if terminated_count > 0:
                    self.logger.info(f"Terminated {terminated_count} orphaned processes for {client_id}")
                    # Wait for processes to fully terminate
                    await asyncio.sleep(1)
                
                return ProcessConflictResult(
                    success=True,
                    message=f"Resolved conflicts by terminating {terminated_count} orphaned processes",
                    conflicting_processes=[p['pid'] for p in running_processes],
                    action_taken="terminated_orphaned"
                )
            
            return ProcessConflictResult(
                success=True,
                message="No conflicts found",
                action_taken="none"
            )
            
        except Exception as e:
            self.logger.error(f"Error resolving conflicts for {client_id}: {e}")
            return ProcessConflictResult(
                success=False,
                message=f"Error during conflict resolution: {e}",
                action_taken="error"
            )
    
    def _find_system_processes_for_client(self, client_id: str) -> List[Dict[str, Any]]:
        """
        Find system processes for a client (adapted from MultiCordOG).
        
        Args:
            client_id: Bot client identifier
            
        Returns:
            List of process information dictionaries
        """
        running_processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    cmdline = proc.info['cmdline']
                    if not cmdline:
                        continue
                    
                    # Look for MultiCord bot processes
                    cmdline_str = ' '.join(cmdline)
                    
                    # Check for various bot execution patterns
                    is_bot_process = (
                        'discord.py' in cmdline_str or
                        'bot.py' in cmdline_str or
                        f'{client_id}' in cmdline_str or
                        'client_runner.py' in cmdline_str
                    )
                    
                    if not is_bot_process:
                        continue
                    
                    # Try to extract client ID from command line
                    found_client_id = self._extract_client_id_from_cmdline(cmdline, client_id)
                    
                    if found_client_id == client_id:
                        running_processes.append({
                            'pid': proc.info['pid'],
                            'create_time': proc.info['create_time'],
                            'cmdline': cmdline,
                            'name': proc.info['name']
                        })
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        except Exception as e:
            self.logger.error(f"Error finding system processes for {client_id}: {e}")
        
        return running_processes
    
    def _extract_client_id_from_cmdline(self, cmdline: List[str], target_client_id: str) -> Optional[str]:
        """Extract client ID from command line arguments."""
        # Look for --client-id= parameter
        for arg in cmdline:
            if arg.startswith('--client-id='):
                return arg.split('=', 1)[1]
        
        # Look for client ID in file paths
        for arg in cmdline:
            if target_client_id in arg:
                return target_client_id
        
        return None
    
    def _terminate_orphaned_processes(self, client_id: str, processes: List[Dict[str, Any]]) -> int:
        """
        Terminate orphaned processes (adapted from MultiCordOG).
        
        Args:
            client_id: Bot client identifier
            processes: List of process information
            
        Returns:
            Number of processes terminated
        """
        terminated_count = 0
        
        for process_info in processes:
            try:
                pid = process_info['pid']
                self.logger.info(f"Terminating orphaned process for {client_id} (PID: {pid})")
                
                proc = psutil.Process(pid)
                proc.terminate()
                
                # Wait for graceful termination
                try:
                    proc.wait(timeout=5)
                    terminated_count += 1
                except psutil.TimeoutExpired:
                    # Force kill if graceful termination fails
                    try:
                        proc.kill()
                        terminated_count += 1
                        self.logger.warning(f"Force killed process {pid} for {client_id}")
                    except psutil.NoSuchProcess:
                        terminated_count += 1  # Already dead
                
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                # Process already dead or no permission
                self.logger.debug(f"Could not terminate process {process_info['pid']}: {e}")
                terminated_count += 1  # Count as handled
            except Exception as e:
                self.logger.error(f"Error terminating process {process_info['pid']}: {e}")
        
        return terminated_count


class ProcessOrchestrator:
    """
    Process orchestrator service extracted from MultiCordOG ProcessManager.
    
    Provides strategy-independent process lifecycle management with
    PostgreSQL integration and comprehensive health monitoring.
    """
    
    def __init__(self, 
                 db_pool: PostgreSQLConnectionPool,
                 process_repository: ProcessRepository,
                 logger: logging.Logger = None):
        """
        Initialize process orchestrator.
        
        Args:
            db_pool: PostgreSQL connection pool
            process_repository: Process data access
            logger: Logger instance
        """
        self.db_pool = db_pool
        self.process_repository = process_repository
        self.logger = logger or logging.getLogger(__name__)
        
        # Process management
        self._subprocess_handles: Dict[str, subprocess.Popen] = {}
        self._lock = threading.RLock()
        
        # Conflict resolution
        self.conflict_resolver = ProcessConflictResolver(logger)
        
        # Terminal instance identifier
        self.terminal_id = str(uuid4())[:8]
        
        # Initialize with cleanup
        self._startup_cleanup()
    
    def _startup_cleanup(self) -> None:
        """Clean up dead processes on startup (extracted pattern)."""
        try:
            # This will be handled by the cleanup_dead_processes method
            self.logger.info("ProcessOrchestrator initialized")
        except Exception as e:
            self.logger.error(f"Error during startup cleanup: {e}")
    
    async def start_process(self, 
                          client_id: str,
                          config: BotConfiguration,
                          execution_command: List[str]) -> Optional[ProcessHandle]:
        """
        Start a bot process with comprehensive lifecycle management.
        
        Args:
            client_id: Bot client identifier
            config: Bot configuration
            execution_command: Command to execute
            
        Returns:
            ProcessHandle if successful, None otherwise
        """
        try:
            self.logger.info(f"Starting process for {client_id}")
            
            # Step 1: Resolve process conflicts
            conflict_result = await self.conflict_resolver.resolve_conflicts(
                client_id, self.process_repository
            )
            
            if not conflict_result.success:
                self.logger.error(f"Process conflict resolution failed: {conflict_result.message}")
                return None
            
            if conflict_result.action_taken != "none":
                self.logger.info(f"Conflict resolution: {conflict_result.message}")
            
            # Step 2: Prepare execution environment
            env = self._prepare_environment(config)
            log_file_path = self._setup_logging(client_id, config)
            
            # Step 3: Start subprocess
            with open(log_file_path, 'w', encoding='utf-8', errors='replace', buffering=1) as log_file:
                process = subprocess.Popen(
                    execution_command,
                    env=env,
                    cwd=config.log_directory.parent if config.log_directory else Path.cwd(),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1
                )
            
            # Step 4: Store subprocess handle
            with self._lock:
                self._subprocess_handles[client_id] = process
            
            # Step 5: Create ProcessInfo
            process_info = ProcessInfo(
                process_id=uuid4(),
                instance_id=config.instance_id,
                client_id=client_id,
                pid=process.pid,
                started_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                source=ProcessSource.LAUNCHED,
                log_file_path=str(log_file_path),
                terminal_instance=self.terminal_id
            )
            
            # Step 6: Save to PostgreSQL
            await self.process_repository.save_process(process_info)
            
            # Step 7: Create and return process handle
            handle = ProcessHandle(
                process_info=process_info,
                subprocess_handle=process
            )
            
            self.logger.info(f"Successfully started process {client_id} (PID: {process.pid})")
            return handle
            
        except Exception as e:
            self.logger.error(f"Failed to start process for {client_id}: {e}")
            # Clean up on failure
            with self._lock:
                if client_id in self._subprocess_handles:
                    try:
                        self._subprocess_handles[client_id].terminate()
                        del self._subprocess_handles[client_id]
                    except:
                        pass
            return None
    
    async def stop_process(self, handle: ProcessHandle, force: bool = False) -> bool:
        """
        Stop a bot process with graceful shutdown.
        
        Args:
            handle: Process handle to stop
            force: Force kill if graceful shutdown fails
            
        Returns:
            True if stopped successfully
        """
        try:
            client_id = handle.process_info.client_id
            self.logger.info(f"Stopping process {client_id} (PID: {handle.process_info.pid})")
            
            if not handle.is_running:
                self.logger.info(f"Process {client_id} already stopped")
                await self._cleanup_process_resources(client_id, handle.process_info.process_id)
                return True
            
            # Try graceful shutdown first
            success = await self._terminate_process(handle, force)
            
            # Clean up resources
            await self._cleanup_process_resources(client_id, handle.process_info.process_id)
            
            if success:
                self.logger.info(f"Successfully stopped process {client_id}")
            else:
                self.logger.warning(f"Process {client_id} required force termination")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error stopping process {handle.process_info.client_id}: {e}")
            return False
    
    async def restart_process(self, 
                            handle: ProcessHandle, 
                            config: BotConfiguration,
                            execution_command: List[str]) -> Optional[ProcessHandle]:
        """
        Restart a bot process.
        
        Args:
            handle: Current process handle
            config: Bot configuration
            execution_command: Command to execute
            
        Returns:
            New ProcessHandle if successful
        """
        client_id = handle.process_info.client_id
        self.logger.info(f"Restarting process {client_id}")
        
        # Stop current process
        stop_success = await self.stop_process(handle, force=False)
        if not stop_success:
            self.logger.warning(f"Failed to cleanly stop {client_id}, continuing with restart")
        
        # Wait for cleanup
        await asyncio.sleep(1)
        
        # Start new process
        new_handle = await self.start_process(client_id, config, execution_command)
        
        if new_handle:
            # Update restart count
            new_handle.process_info.restart_count = handle.process_info.restart_count + 1
            new_handle.process_info.last_restart = datetime.now(timezone.utc)
            
            # Update in database
            await self.process_repository.update_process(new_handle.process_info)
            
            self.logger.info(f"Successfully restarted {client_id} (new PID: {new_handle.process_info.pid})")
        
        return new_handle
    
    async def get_process_health(self, handle: ProcessHandle) -> HealthStatus:
        """
        Get comprehensive health status for a process.
        
        Args:
            handle: Process handle
            
        Returns:
            HealthStatus with current metrics
        """
        return handle.process_info.get_current_health_status()
    
    async def cleanup_dead_processes(self) -> List[str]:
        """
        Clean up dead processes from registry and memory.
        
        Returns:
            List of cleaned up client IDs
        """
        try:
            # Get all processes from repository
            all_processes = await self.process_repository.get_all_processes()
            
            dead_client_ids = []
            
            for process_info in all_processes:
                if not process_info.is_running:
                    dead_client_ids.append(process_info.client_id)
                    
                    # Remove from repository
                    await self.process_repository.remove_process(process_info.process_id)
                    
                    # Clean up subprocess handles
                    with self._lock:
                        self._subprocess_handles.pop(process_info.client_id, None)
            
            if dead_client_ids:
                self.logger.info(f"Cleaned up {len(dead_client_ids)} dead processes: {dead_client_ids}")
            
            return dead_client_ids
            
        except Exception as e:
            self.logger.error(f"Error cleaning up dead processes: {e}")
            return []
    
    def _prepare_environment(self, config: BotConfiguration) -> Dict[str, str]:
        """Prepare environment variables for process execution."""
        import os
        env = os.environ.copy()
        
        # Add bot configuration
        env.update(config.environment_config)
        
        # Ensure proper encoding
        env['PYTHONIOENCODING'] = 'utf-8'
        if os.name == 'nt':
            env['PYTHONLEGACYWINDOWSSTDIO'] = '1'
        
        return env
    
    def _setup_logging(self, client_id: str, config: BotConfiguration) -> Path:
        """Set up logging for bot process."""
        # Create log directory
        log_dir = config.log_directory or Path(f"bots/{client_id}/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file_path = log_dir / f"bot_output_{timestamp}.log"
        
        return log_file_path
    
    async def _terminate_process(self, handle: ProcessHandle, force: bool = False) -> bool:
        """Terminate process with graceful/force options."""
        try:
            subprocess_handle = handle.subprocess_handle
            client_id = handle.process_info.client_id
            
            if subprocess_handle:
                # Use subprocess handle
                subprocess_handle.terminate()
                try:
                    subprocess_handle.wait(timeout=10)
                    return True
                except subprocess.TimeoutExpired:
                    if force:
                        subprocess_handle.kill()
                        subprocess_handle.wait()
                        return True
                    return False
            else:
                # Use psutil
                proc = psutil.Process(handle.process_info.pid)
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                    return True
                except psutil.TimeoutExpired:
                    if force:
                        proc.kill()
                        return True
                    return False
                    
        except (psutil.NoSuchProcess, subprocess.ProcessLookupError):
            # Already dead
            return True
        except Exception as e:
            self.logger.error(f"Error terminating process: {e}")
            return False
    
    async def _cleanup_process_resources(self, client_id: str, process_id: UUID) -> None:
        """Clean up process resources."""
        # Remove subprocess handle
        with self._lock:
            self._subprocess_handles.pop(client_id, None)
        
        # Remove from repository
        try:
            await self.process_repository.remove_process(process_id)
        except Exception as e:
            self.logger.error(f"Error removing process {client_id} from repository: {e}")
    
    async def get_running_processes(self) -> List[ProcessInfo]:
        """Get all running processes."""
        return await self.process_repository.get_running_processes()
    
    async def get_all_processes(self) -> List[ProcessInfo]:
        """Get all processes (running and stopped)."""
        return await self.process_repository.get_all_processes()