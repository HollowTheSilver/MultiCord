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
import logging

# Add core modules to path
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from utils.loguruConfig import configure_logger


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
    """
    Multi-client Discord bot launcher and process manager.
    """

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
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)

                for client_data in config_data.get("clients", []):
                    config = ClientConfig(**client_data)
                    self.client_configs[config.client_id] = config

                self.logger.info(f"Loaded configuration for {len(self.client_configs)} clients")
            else:
                self.logger.warning("No platform config found, scanning for clients...")
                self._discover_clients()

        except Exception as e:
            self.logger.error(f"Failed to load platform config: {e}")
            self._discover_clients()

    def _discover_clients(self) -> None:
        """Discover clients by scanning the clients directory."""
        if not self.clients_dir.exists():
            self.logger.error("Clients directory not found!")
            return

        for client_dir in self.clients_dir.iterdir():
            if client_dir.is_dir() and not client_dir.name.startswith("_"):
                # Check if client has required files
                if (client_dir / ".env").exists():
                    client_id = client_dir.name
                    self.client_configs[client_id] = ClientConfig(
                        client_id=client_id,
                        display_name=client_id.replace("_", " ").title()
                    )
                    self.logger.info(f"Discovered client: {client_id}")

        # Save discovered configuration
        self._save_platform_config()

    def _save_platform_config(self) -> None:
        """Save current configuration to file."""
        try:
            config_data = {
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

            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=2)

        except Exception as e:
            self.logger.error(f"Failed to save platform config: {e}")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            self.logger.warning(f"Received signal {sig}, initiating graceful shutdown...")
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def start_client(self, client_id: str) -> bool:
        """Start a specific client bot."""
        if client_id not in self.client_configs:
            self.logger.error(f"Client {client_id} not found in configuration")
            return False

        if client_id in self.client_processes:
            self.logger.warning(f"Client {client_id} is already running")
            return False

        config = self.client_configs[client_id]
        if not config.enabled:
            self.logger.info(f"Client {client_id} is disabled, skipping")
            return False

        try:
            # Setup environment
            env = os.environ.copy()
            env["CLIENT_ID"] = client_id
            env["CLIENT_PATH"] = str(self.clients_dir / client_id)
            env.update(config.custom_env)

            # Start the bot process
            cmd = [
                sys.executable, "-m", "platform.client_runner",
                "--client-id", client_id
            ]

            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path.cwd()
            )

            # Track the process
            client_process = ClientProcess(
                client_id=client_id,
                process=process,
                started_at=datetime.now(timezone.utc)
            )

            self.client_processes[client_id] = client_process

            self.logger.info(f"Started client {client_id} with PID {process.pid}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start client {client_id}: {e}")
            return False

    async def stop_client(self, client_id: str, graceful: bool = True) -> bool:
        """Stop a specific client bot."""
        if client_id not in self.client_processes:
            self.logger.warning(f"Client {client_id} is not running")
            return False

        client_process = self.client_processes[client_id]
        process = client_process.process

        try:
            if graceful:
                # Try graceful shutdown first
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    self.logger.warning(f"Client {client_id} didn't shutdown gracefully, forcing...")
                    process.kill()
                    process.wait()
            else:
                process.kill()
                process.wait()

            del self.client_processes[client_id]
            self.logger.info(f"Stopped client {client_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to stop client {client_id}: {e}")
            return False

    async def restart_client(self, client_id: str) -> bool:
        """Restart a specific client bot."""
        self.logger.info(f"Restarting client {client_id}")

        # Stop the client
        if client_id in self.client_processes:
            await self.stop_client(client_id)

        # Wait before restart
        config = self.client_configs.get(client_id)
        if config:
            await asyncio.sleep(config.restart_delay)

        # Start again
        return await self.start_client(client_id)

    async def start_all_clients(self) -> None:
        """Start all enabled clients."""
        self.logger.info("Starting all enabled clients...")

        for client_id, config in self.client_configs.items():
            if config.enabled:
                await self.start_client(client_id)
                await asyncio.sleep(2)  # Stagger startup

    async def stop_all_clients(self) -> None:
        """Stop all running clients."""
        self.logger.info("Stopping all clients...")

        # Stop all clients concurrently
        tasks = []
        for client_id in list(self.client_processes.keys()):
            tasks.append(self.stop_client(client_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def health_check_loop(self) -> None:
        """Continuous health monitoring loop."""
        while not self.shutdown_requested:
            try:
                await self._perform_health_checks()
                self.last_health_check = datetime.now(timezone.utc)
                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                self.logger.error(f"Health check failed: {e}")
                await asyncio.sleep(30)

    async def _perform_health_checks(self) -> None:
        """Perform health checks on all running clients."""
        for client_id, client_process in list(self.client_processes.items()):
            try:
                process = client_process.process

                # Check if process is still running
                if process.poll() is not None:
                    self.logger.warning(f"Client {client_id} process has died")
                    client_process.status = "crashed"
                    await self._handle_client_crash(client_id)
                    continue

                # Get resource usage
                try:
                    psutil_process = psutil.Process(process.pid)
                    client_process.memory_usage = psutil_process.memory_info().rss / 1024 / 1024  # MB
                    client_process.cpu_usage = psutil_process.cpu_percent()

                    # Check memory limits
                    config = self.client_configs.get(client_id)
                    if config and client_process.memory_usage > config.memory_limit_mb:
                        self.logger.warning(f"Client {client_id} exceeds memory limit: {client_process.memory_usage:.1f}MB")

                except psutil.NoSuchProcess:
                    self.logger.warning(f"Client {client_id} process no longer exists")
                    client_process.status = "missing"
                    await self._handle_client_crash(client_id)

                client_process.status = "healthy"
                client_process.health_check_failures = 0

            except Exception as e:
                self.logger.error(f"Health check failed for client {client_id}: {e}")
                client_process.health_check_failures += 1

                if client_process.health_check_failures >= 3:
                    await self._handle_client_crash(client_id)

    async def _handle_client_crash(self, client_id: str) -> None:
        """Handle a crashed client with auto-restart logic."""
        client_process = self.client_processes.get(client_id)
        config = self.client_configs.get(client_id)

        if not client_process or not config:
            return

        # Clean up the process
        if client_id in self.client_processes:
            del self.client_processes[client_id]

        # Check restart policy
        if config.auto_restart and client_process.restart_count < config.max_restarts:
            self.logger.info(f"Auto-restarting client {client_id} (attempt {client_process.restart_count + 1})")

            # Wait before restart
            await asyncio.sleep(config.restart_delay)

            # Update restart tracking
            self.total_restarts += 1

            # Restart the client
            await self.start_client(client_id)

            # Update restart count
            if client_id in self.client_processes:
                self.client_processes[client_id].restart_count = client_process.restart_count + 1
                self.client_processes[client_id].last_restart = datetime.now(timezone.utc)
        else:
            self.logger.error(f"Client {client_id} has exceeded max restarts or auto-restart is disabled")

    def get_platform_status(self) -> Dict[str, Any]:
        """Get comprehensive platform status."""
        running_clients = len(self.client_processes)
        total_clients = len(self.client_configs)
        enabled_clients = sum(1 for config in self.client_configs.values() if config.enabled)

        total_memory = sum(cp.memory_usage for cp in self.client_processes.values())
        avg_cpu = sum(cp.cpu_usage for cp in self.client_processes.values()) / max(running_clients, 1)

        uptime = datetime.now(timezone.utc) - self.start_time

        return {
            "platform": {
                "uptime_seconds": uptime.total_seconds(),
                "total_restarts": self.total_restarts,
                "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None
            },
            "clients": {
                "total": total_clients,
                "enabled": enabled_clients,
                "running": running_clients,
                "crashed": sum(1 for cp in self.client_processes.values() if cp.status == "crashed")
            },
            "resources": {
                "total_memory_mb": round(total_memory, 1),
                "avg_cpu_percent": round(avg_cpu, 1)
            },
            "client_details": {
                client_id: {
                    "status": cp.status,
                    "uptime_seconds": (datetime.now(timezone.utc) - cp.started_at).total_seconds(),
                    "restart_count": cp.restart_count,
                    "memory_mb": round(cp.memory_usage, 1),
                    "cpu_percent": round(cp.cpu_usage, 1)
                }
                for client_id, cp in self.client_processes.items()
            }
        }

    async def run(self) -> None:
        """Main platform run loop."""
        self.logger.info("🚀 Starting Discord Bot Platform")

        try:
            # Start health monitoring
            health_task = asyncio.create_task(self.health_check_loop())

            # Start all clients
            await self.start_all_clients()

            self.logger.info(f"Platform started with {len(self.client_processes)} clients")

            # Main loop
            while not self.shutdown_requested:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Platform error: {e}")
        finally:
            # Cleanup
            self.logger.info("Shutting down platform...")

            # Cancel health monitoring
            if 'health_task' in locals():
                health_task.cancel()

            # Stop all clients
            await self.stop_all_clients()

            self.logger.info("Platform shutdown complete")


async def main():
    """Main entry point for the platform launcher."""
    launcher = PlatformLauncher()
    await launcher.run()


if __name__ == "__main__":
    asyncio.run(main())
