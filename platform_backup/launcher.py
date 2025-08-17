"""
Platform Launcher System
========================

Smart launcher that manages multiple Discord bot instances for different clients.
Handles process management, health monitoring, and resource tracking.
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
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.utils.loguruConfig import configure_logger


@dataclass
class ClientProcess:
    """Information about a running client bot instance."""
    client_id: str
    process: subprocess.Popen
    started_at: datetime
    restart_count: int = 0
    last_restart: Optional[datetime] = None
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    status: str = "running"
    health_check_failures: int = 0


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
    """Multi-client Discord bot launcher and process manager."""

    def __init__(self, config_path: str = "platform_config.json"):
        """Initialize the platform launcher."""
        self.config_path = Path(config_path)
        self.clients_dir = Path("clients")
        self.core_dir = Path("core")

        # Process management
        self.client_processes: Dict[str, ClientProcess] = {}
        self.client_configs: Dict[str, ClientConfig] = {}
        self.shutdown_requested = False

        # Monitoring
        self.start_time = datetime.now(timezone.utc)
        self.total_restarts = 0
        self.last_health_check = None

        # Setup logging
        self.logger = configure_logger(
            log_dir="platform/logs",
            level="INFO",
            format_extra=True,
            discord_compat=True
        )

        # Load configuration
        self._load_platform_config()
        self._setup_signal_handlers()

    def _load_platform_config(self) -> None:
        """Load platform and client configurations."""
        if not self.config_path.exists():
            self._create_default_config()

        try:
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)

            for client_data in config_data.get("clients", []):
                client_config = ClientConfig(**client_data)
                self.client_configs[client_config.client_id] = client_config

            self.logger.info(f"Loaded configuration for {len(self.client_configs)} clients")

        except Exception as e:
            self.logger.error(f"Failed to load platform config: {e}")
            self._create_default_config()

    def _create_default_config(self) -> None:
        """Create default platform configuration."""
        default_config = {
            "clients": [
                {
                    "client_id": "default",
                    "display_name": "Default Client",
                    "enabled": True,
                    "auto_restart": True,
                    "max_restarts": 5,
                    "restart_delay": 30,
                    "memory_limit_mb": 512,
                    "custom_env": {}
                }
            ]
        }

        with open(self.config_path, 'w') as f:
            json.dump(default_config, f, indent=2)

        self.logger.info("Created default platform configuration")

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
            if process_info.process.poll() is None:  # Still running
                self.logger.warning(f"Client {client_id} is already running")
                return True

        # Verify client directory exists
        client_dir = self.clients_dir / client_id
        if not client_dir.exists():
            self.logger.error(f"Client directory not found: {client_dir}")
            return False

        try:
            # Build command to run client
            cmd = [
                sys.executable, "-m", "platform.client_runner",
                "--client-id", client_id
            ]

            # Setup environment
            env = os.environ.copy()
            env.update(config.custom_env)
            env["CLIENT_ID"] = client_id

            # Start the client process
            process = subprocess.Popen(
                cmd,
                cwd=client_dir,
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
                started_at=datetime.now(timezone.utc)
            )

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
        process = process_info.process

        try:
            if process.poll() is None:  # Process is still running
                if force:
                    process.kill()
                    self.logger.info(f"Force killed client {client_id}")
                else:
                    process.terminate()
                    self.logger.info(f"Sent terminate signal to client {client_id}")

                # Wait for process to exit
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    if not force:
                        process.kill()
                        process.wait(timeout=5)
                        self.logger.warning(f"Force killed client {client_id} after timeout")

            # Remove from active processes
            del self.client_processes[client_id]
            self.logger.info(f"Stopped client {client_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to stop client {client_id}: {e}")
            return False

    async def restart_client(self, client_id: str) -> bool:
        """Restart a specific client bot instance."""
        self.logger.info(f"Restarting client {client_id}")

        # Stop the client first
        await self.stop_client(client_id)

        # Wait a moment
        await asyncio.sleep(2)

        # Start it again
        return await self.start_client(client_id)

    async def start_all_clients(self) -> None:
        """Start all enabled clients."""
        self.logger.info("Starting all enabled clients...")

        for client_id, config in self.client_configs.items():
            if config.enabled:
                await self.start_client(client_id)
                await asyncio.sleep(1)  # Stagger starts

    async def stop_all_clients(self) -> None:
        """Stop all running clients."""
        self.logger.info("Stopping all clients...")

        stop_tasks = []
        for client_id in list(self.client_processes.keys()):
            task = asyncio.create_task(self.stop_client(client_id))
            stop_tasks.append(task)

        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

    async def monitor_clients(self) -> None:
        """Monitor client health and resource usage."""
        while not self.shutdown_requested:
            try:
                await self._check_client_health()
                await self._update_resource_usage()
                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                self.logger.error(f"Error in client monitoring: {e}")
                await asyncio.sleep(5)

    async def _check_client_health(self) -> None:
        """Check health of all running clients."""
        for client_id, process_info in list(self.client_processes.items()):
            try:
                # Check if process is still alive
                if process_info.process.poll() is not None:
                    # Process has died
                    self.logger.warning(f"Client {client_id} process has died")
                    del self.client_processes[client_id]

                    # Handle auto-restart
                    config = self.client_configs.get(client_id)
                    if config and config.auto_restart:
                        if process_info.restart_count < config.max_restarts:
                            self.logger.info(f"Auto-restarting client {client_id}")
                            process_info.restart_count += 1
                            process_info.last_restart = datetime.now(timezone.utc)
                            self.total_restarts += 1

                            await asyncio.sleep(config.restart_delay)
                            await self.start_client(client_id)
                        else:
                            self.logger.error(f"Client {client_id} exceeded max restarts")

            except Exception as e:
                self.logger.error(f"Error checking health of client {client_id}: {e}")

    async def _update_resource_usage(self) -> None:
        """Update resource usage statistics for all clients."""
        for client_id, process_info in self.client_processes.items():
            try:
                pid = process_info.process.pid
                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)

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

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass  # Process might have just died
            except Exception as e:
                self.logger.error(f"Error updating resources for client {client_id}: {e}")

    def get_platform_stats(self) -> Dict[str, Any]:
        """Get comprehensive platform statistics."""
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
        self.logger.info("Starting Multi-Client Discord Bot Platform")

        # Setup signal handlers
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            # Start all enabled clients
            await self.start_all_clients()

            # Start monitoring task
            monitor_task = asyncio.create_task(self.monitor_clients())

            # Main loop
            while not self.shutdown_requested:
                await asyncio.sleep(1)

        except Exception as e:
            self.logger.error(f"Platform error: {e}")
        finally:
            # Cleanup
            self.logger.info("Shutting down platform...")
            await self.stop_all_clients()
            if 'monitor_task' in locals():
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
            self.logger.info("Platform shutdown complete")


if __name__ == "__main__":
    import asyncio
    launcher = PlatformLauncher()
    asyncio.run(launcher.run())
