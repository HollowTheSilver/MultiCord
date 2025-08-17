"""
Platform Launcher
================================================
"""

import asyncio
import os
import sys
import signal
import subprocess
import psutil
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.utils.loguruConfig import configure_logger


@dataclass
class ClientProcess:
    """Information about a running client bot instance."""
    client_id: str
    process: subprocess.Popen = None
    started_at: datetime = None
    restart_count: int = 0
    last_restart: Optional[datetime] = None
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    status: str = "running"
    health_check_failures: int = 0
    pid: Optional[int] = None

    def __post_init__(self):
        if self.process and not self.pid:
            self.pid = self.process.pid
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc)


@dataclass
class ClientConfig:
    """Basic client configuration for launcher."""
    client_id: str
    display_name: str
    enabled: bool = True
    auto_restart: bool = True
    max_restarts: int = 5
    restart_delay: int = 30
    memory_limit_mb: int = 512
    custom_env: Dict[str, str] = field(default_factory=dict)


class PlatformLauncher:
    """Multi-client Discord bot launcher with corrected directory paths."""

    def __init__(self, config_path: str = "platform_config.json"):
        """Initialize the platform launcher."""
        self.config_path = Path(config_path)
        self.clients_dir = Path("clients")
        self.core_dir = Path("core")

        # Process tracking files - FIXED PATHS
        self.runtime_dir = Path("bot_platform/runtime")
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.process_registry = self.runtime_dir / "client_processes.json"

        # Client manager database for synchronization - FIXED PATH
        self.client_manager_db = Path("bot_platform/clients.json")

        # Process management
        self.client_processes: Dict[str, ClientProcess] = {}
        self.client_configs: Dict[str, ClientConfig] = {}
        self.shutdown_requested = False

        # Monitoring
        self.start_time = datetime.now(timezone.utc)
        self.total_restarts = 0
        self.last_health_check = None

        # Setup logging - FIXED PATH
        self.logger = configure_logger(
            log_dir="bot_platform/logs",
            level="INFO",
            format_extra=True,
            discord_compat=True
        )

        # Load configuration with synchronization
        self._load_synchronized_config()
        self._discover_running_clients()
        self._setup_signal_handlers()

    def _load_synchronized_config(self) -> None:
        """Load platform configuration synchronized with client manager database."""
        # First, discover all clients from multiple sources
        discovered_clients = {}

        # Source 1: Directory scanning
        discovered_clients.update(self._scan_client_directories())

        # Source 2: Client manager database
        discovered_clients.update(self._load_from_client_manager_db())

        # Source 3: Existing platform config
        discovered_clients.update(self._load_existing_platform_config())

        # Update client configs with discovered clients
        self.client_configs = discovered_clients

        # Save updated platform config
        self._save_platform_config()

        self.logger.info(f"Loaded configuration for {len(self.client_configs)} clients")

    def _scan_client_directories(self) -> Dict[str, ClientConfig]:
        """Scan client directories and create configurations."""
        configs = {}

        if not self.clients_dir.exists():
            self.logger.debug("Clients directory not found")
            return configs

        for client_dir in self.clients_dir.iterdir():
            if client_dir.is_dir() and not client_dir.name.startswith("_"):
                client_id = client_dir.name
                configs[client_id] = ClientConfig(
                    client_id=client_id,
                    display_name=client_id.title().replace('_', ' ')
                )

        if configs:
            self.logger.debug(f"Found {len(configs)} clients from directory scan")
        return configs

    def _load_from_client_manager_db(self) -> Dict[str, ClientConfig]:
        """Load clients from client manager database for synchronization."""
        configs = {}

        if not self.client_manager_db.exists():
            self.logger.debug("Client manager database not found")
            return configs

        try:
            with open(self.client_manager_db, 'r', encoding='utf-8') as f:
                client_data = json.load(f)

            for client_id, info in client_data.items():
                configs[client_id] = ClientConfig(
                    client_id=client_id,
                    display_name=info.get('display_name', client_id.title()),
                    enabled=info.get('status', 'active') == 'active'
                )

            if configs:
                self.logger.debug(f"Loaded {len(configs)} clients from client manager database")

        except Exception as e:
            self.logger.debug(f"Could not load client manager database: {e}")

        return configs

    def _load_existing_platform_config(self) -> Dict[str, ClientConfig]:
        """Load existing platform configuration."""
        configs = {}

        if not self.config_path.exists():
            return configs

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            for client_data in config_data.get("clients", []):
                client_config = ClientConfig(**client_data)
                configs[client_config.client_id] = client_config

            if configs:
                self.logger.debug(f"Loaded {len(configs)} clients from existing platform config")

        except Exception as e:
            self.logger.debug(f"Could not load existing platform config: {e}")

        return configs

    def _save_platform_config(self) -> None:
        """Save current platform configuration."""
        try:
            config_data = {
                "platform": {
                    "name": "Multi-Client Discord Bot Platform",
                    "version": "2.0.1",
                    "last_updated": datetime.now().isoformat()
                },
                "clients": [
                    {
                        "client_id": config.client_id,
                        "display_name": config.display_name,
                        "enabled": config.enabled,
                        "auto_restart": config.auto_restart,
                        "max_restarts": config.max_restarts,
                        "restart_delay": config.restart_delay,
                        "memory_limit_mb": config.memory_limit_mb,
                        "custom_env": config.custom_env
                    }
                    for config in self.client_configs.values()
                ]
            }

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            self.logger.debug(f"Saved platform config with {len(self.client_configs)} clients")

        except Exception as e:
            self.logger.error(f"Failed to save platform config: {e}")

    def _discover_running_clients(self) -> None:
        """Discover and track already running client processes."""
        discovered_count = 0

        try:
            # Method 1: Check process registry file
            if self.process_registry.exists():
                discovered_count += self._load_from_process_registry()

            # Method 2: Scan running processes
            discovered_count += self._scan_running_processes()

            if discovered_count > 0:
                self.logger.info(f"Discovered {discovered_count} running client processes")
            else:
                self.logger.debug("No running client processes discovered")

        except Exception as e:
            self.logger.error(f"Error during process discovery: {e}")

    def _load_from_process_registry(self) -> int:
        """Load process info from registry file."""
        try:
            with open(self.process_registry, 'r', encoding='utf-8') as f:
                registry_data = json.load(f)

            discovered = 0
            for client_id, process_data in registry_data.items():
                pid = process_data.get('pid')
                if pid and psutil.pid_exists(pid):
                    try:
                        proc = psutil.Process(pid)
                        # Verify it's actually our client process
                        cmdline = ' '.join(proc.cmdline())
                        if 'bot_platform.client_runner' in cmdline and f'--client-id {client_id}' in cmdline:
                            # Reconstruct ClientProcess info
                            started_at = datetime.fromisoformat(process_data['started_at'])
                            client_process = ClientProcess(
                                client_id=client_id,
                                started_at=started_at,
                                restart_count=process_data.get('restart_count', 0),
                                pid=pid
                            )
                            self.client_processes[client_id] = client_process
                            discovered += 1
                            self.logger.debug(f"Discovered registered client {client_id} (PID: {pid})")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

            return discovered

        except Exception as e:
            self.logger.debug(f"Could not load process registry: {e}")
            return 0

    def _scan_running_processes(self) -> int:
        """Scan all running processes to find our clients."""
        discovered = 0

        try:
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if not cmdline:
                        continue

                    cmdline_str = ' '.join(cmdline)

                    # Look for our client runner processes
                    if 'bot_platform.client_runner' in cmdline_str and '--client-id' in cmdline_str:
                        # Extract client ID from command line
                        for i, arg in enumerate(cmdline):
                            if arg == '--client-id' and i + 1 < len(cmdline):
                                client_id = cmdline[i + 1]

                                # Skip if we already know about this process
                                if client_id in self.client_processes:
                                    continue

                                # Verify client_id is configured (or add it if missing)
                                if client_id not in self.client_configs:
                                    # Auto-add discovered client to configuration
                                    self.client_configs[client_id] = ClientConfig(
                                        client_id=client_id,
                                        display_name=client_id.title().replace('_', ' ')
                                    )
                                    self.logger.info(f"Auto-discovered new client: {client_id}")

                                # Create ClientProcess entry
                                proc_obj = psutil.Process(proc.info['pid'])
                                create_time = datetime.fromtimestamp(proc_obj.create_time(), tz=timezone.utc)

                                client_process = ClientProcess(
                                    client_id=client_id,
                                    started_at=create_time,
                                    pid=proc.info['pid']
                                )
                                self.client_processes[client_id] = client_process
                                discovered += 1
                                self.logger.debug(f"Discovered running client {client_id} (PID: {proc.info['pid']})")
                                break

                except (psutil.NoSuchProcess, psutil.AccessDenied, IndexError):
                    continue

        except Exception as e:
            self.logger.debug(f"Error scanning processes: {e}")

        return discovered

    def _save_process_registry(self) -> None:
        """Save current process information to registry file."""
        try:
            registry_data = {}
            for client_id, process_info in self.client_processes.items():
                registry_data[client_id] = {
                    'pid': process_info.pid,
                    'started_at': process_info.started_at.isoformat(),
                    'restart_count': process_info.restart_count,
                    'last_updated': datetime.now().isoformat()
                }

            with open(self.process_registry, 'w', encoding='utf-8') as f:
                json.dump(registry_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.debug(f"Could not save process registry: {e}")

    def _cleanup_process_registry(self) -> None:
        """Remove dead processes from registry."""
        if self.process_registry.exists():
            try:
                self.process_registry.unlink()
                self.logger.debug("Cleaned up process registry")
            except Exception as e:
                self.logger.debug(f"Could not cleanup process registry: {e}")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def start_client(self, client_id: str) -> bool:
        """Start a specific client bot instance."""
        if client_id not in self.client_configs:
            self.logger.error(f"Client {client_id} not found in configuration")
            return False

        config = self.client_configs[client_id]
        if not config.enabled:
            self.logger.info(f"Client {client_id} is disabled, skipping")
            return False

        # Check if client is already running
        if client_id in self.client_processes:
            process_info = self.client_processes[client_id]
            if process_info.pid and psutil.pid_exists(process_info.pid):
                self.logger.warning(f"Client {client_id} is already running (PID: {process_info.pid})")
                return True

        # Verify client directory exists
        client_dir = self.clients_dir / client_id
        if not client_dir.exists():
            self.logger.error(f"Client directory not found: {client_dir}")
            return False

        try:
            # Build command to run client
            cmd = [
                sys.executable, "-m", "bot_platform.client_runner",
                "--client-id", client_id
            ]

            # Setup environment
            env = os.environ.copy()
            env.update(config.custom_env)
            env["CLIENT_ID"] = client_id

            # Start the client process
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Store process info
            self.client_processes[client_id] = ClientProcess(
                client_id=client_id,
                process=process,
                started_at=datetime.now(timezone.utc),
                pid=process.pid
            )

            # Update process registry
            self._save_process_registry()

            self.logger.info(f"Started client {client_id} (PID: {process.pid})")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start client {client_id}: {e}")
            return False

    async def stop_client(self, client_id: str, force: bool = False) -> bool:
        """Stop a specific client bot instance."""
        if client_id not in self.client_processes:
            self.logger.warning(f"Client {client_id} is not running")
            return True

        process_info = self.client_processes[client_id]

        try:
            if process_info.pid and psutil.pid_exists(process_info.pid):
                proc = psutil.Process(process_info.pid)

                if force:
                    proc.kill()
                    self.logger.info(f"Force killed client {client_id}")
                else:
                    proc.terminate()
                    self.logger.info(f"Terminated client {client_id}")

                # Wait for process to die
                try:
                    proc.wait(timeout=10)
                except psutil.TimeoutExpired:
                    proc.kill()
                    self.logger.warning(f"Had to force kill client {client_id}")

            # Remove from tracking
            del self.client_processes[client_id]
            self._save_process_registry()

            return True

        except Exception as e:
            self.logger.error(f"Failed to stop client {client_id}: {e}")
            return False

    async def restart_client(self, client_id: str) -> bool:
        """Restart a specific client bot instance."""
        self.logger.info(f"Restarting client {client_id}")

        # Stop the client
        if not await self.stop_client(client_id):
            return False

        # Wait a moment
        await asyncio.sleep(2)

        # Start the client
        success = await self.start_client(client_id)
        if success and client_id in self.client_processes:
            self.client_processes[client_id].restart_count += 1
            self.total_restarts += 1
            self._save_process_registry()

        return success

    def _update_resource_usage(self) -> None:
        """Update memory and CPU usage for all tracked processes."""
        for client_id, process_info in list(self.client_processes.items()):
            try:
                if process_info.pid and psutil.pid_exists(process_info.pid):
                    proc = psutil.Process(process_info.pid)

                    # Update memory and CPU usage
                    process_info.memory_usage = proc.memory_info().rss / 1024 / 1024  # MB
                    process_info.cpu_usage = proc.cpu_percent()

                    # Check memory limits
                    config = self.client_configs.get(client_id)
                    if config and process_info.memory_usage > config.memory_limit_mb:
                        self.logger.warning(
                            f"Client {client_id} exceeding memory limit: "
                            f"{process_info.memory_usage:.1f}MB > {config.memory_limit_mb}MB"
                        )
                else:
                    # Process died, remove from tracking
                    self.logger.warning(f"Client {client_id} process no longer exists, removing from tracking")
                    del self.client_processes[client_id]
                    self._save_process_registry()

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process died, remove from tracking
                self.logger.warning(f"Client {client_id} process died, removing from tracking")
                if client_id in self.client_processes:
                    del self.client_processes[client_id]
                    self._save_process_registry()
            except Exception as e:
                self.logger.error(f"Error updating resources for client {client_id}: {e}")

    def get_platform_stats(self) -> Dict[str, Any]:
        """Get comprehensive platform statistics."""
        # Update resource usage before getting stats
        self._update_resource_usage()

        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        stats = {
            "platform": {
                "uptime_seconds": uptime,
                "uptime_hours": uptime / 3600,
                "total_restarts": self.total_restarts,
                "total_clients": len(self.client_configs),
                "running_clients": len(self.client_processes),
                "enabled_clients": sum(1 for config in self.client_configs.values() if config.enabled)
            },
            "clients": {}
        }

        # Add individual client stats
        for client_id, config in self.client_configs.items():
            client_stats = {
                "enabled": config.enabled,
                "running": client_id in self.client_processes,
                "restart_count": 0,
                "memory_mb": 0.0,
                "cpu_percent": 0.0,
                "uptime_seconds": 0
            }

            # Add runtime stats if running
            if client_id in self.client_processes:
                process_info = self.client_processes[client_id]
                client_stats.update({
                    "restart_count": process_info.restart_count,
                    "memory_mb": process_info.memory_usage,
                    "cpu_percent": process_info.cpu_usage,
                    "uptime_seconds": (datetime.now(timezone.utc) - process_info.started_at).total_seconds()
                })

            stats["clients"][client_id] = client_stats

        return stats

    async def run(self) -> None:
        """Main run loop for the platform launcher."""
        self.logger.info("Platform launcher started")

        try:
            # Start enabled clients
            started_clients = []
            for client_id, config in self.client_configs.items():
                if config.enabled:
                    if await self.start_client(client_id):
                        started_clients.append(client_id)

            if started_clients:
                self.logger.info(f"Started {len(started_clients)} clients: {', '.join(started_clients)}")
            else:
                self.logger.warning("No clients were started")
                return

            # Main monitoring loop
            while not self.shutdown_requested:
                self._update_resource_usage()
                await asyncio.sleep(30)  # Check every 30 seconds

        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Shutdown all clients and cleanup."""
        self.logger.info("Shutting down platform...")

        # Stop all running clients
        for client_id in list(self.client_processes.keys()):
            await self.stop_client(client_id)

        # Cleanup process registry
        self._cleanup_process_registry()

        self.logger.info("Platform shutdown complete")
