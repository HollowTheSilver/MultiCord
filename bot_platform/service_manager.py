"""
Service Manager & Platform Orchestrator
======================================

ServiceManager: High-level business operations using ClientManager as single source of truth
PlatformOrchestrator: Coordinates all components with dependency injection

Simplified - no database synchronization complexity.
"""

import asyncio
import shutil
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from pathlib import Path

from .process_manager import ProcessManager
from .config_manager import ConfigManager, ClientConfig
from core.utils.loguruConfig import configure_logger


class ServiceManager:
    """High-level business operations using ClientManager as single source of truth."""

    def __init__(self, process_manager: ProcessManager, config_manager: ConfigManager):
        """Initialize with dependency injection."""
        self.process_manager = process_manager
        self.config_manager = config_manager

        self.logger = configure_logger(
            log_dir="bot_platform/logs",
            level="INFO",
            format_extra=True,
            discord_compat=True
        )

        # Platform statistics
        self.start_time = datetime.now(timezone.utc)
        self.total_restarts = 0
        self.auto_fix_log = []

        # Initialize ClientManager for FLAGS system
        self._client_manager = None

    def _get_client_manager(self):
        """Lazy initialize ClientManager to avoid circular imports."""
        if self._client_manager is None:
            from .client_manager import ClientManager
            self._client_manager = ClientManager()
        return self._client_manager

    def get_platform_status(self) -> Dict[str, Any]:
        """Get comprehensive platform status."""
        # Calculate uptime
        uptime_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        uptime_hours = uptime_seconds / 3600

        # Get client information
        total_clients = len(self.config_manager.client_configs)
        running_clients = len(self.process_manager.get_running_client_ids())
        enabled_clients = len([
            c for c in self.config_manager.client_configs.values() if c.enabled
        ])

        # Get FLAGS system statistics
        flags_clients = len(self.config_manager.get_flags_system_clients())
        features_clients = len(self.config_manager.get_features_system_clients())

        return {
            'platform': {
                'uptime_hours': round(uptime_hours, 2),
                'total_restarts': self.total_restarts,
                'auto_fixes_applied': len(self.auto_fix_log),
                'last_auto_fix': self.auto_fix_log[-1] if self.auto_fix_log else None
            },
            'clients': {
                'total': total_clients,
                'running': running_clients,
                'enabled': enabled_clients,
                'stopped': total_clients - running_clients,
                'flags_system': flags_clients,
                'features_system': features_clients
            },
            'health': {
                'platform_healthy': True,
                'auto_healing_enabled': self.config_manager.get_auto_healing_config().get('enabled', True)
            }
        }

    def start_client(self, client_id: str) -> bool:
        """Start a specific client."""
        if client_id not in self.config_manager.client_configs:
            self.logger.error(f"Client {client_id} not found")
            return False

        config = self.config_manager.client_configs[client_id]
        if not config.enabled:
            self.logger.warning(f"Client {client_id} is disabled")
            return False

        # Validate client health first
        health = self.config_manager.validate_client_health(client_id)
        if health['config_health'] != 'healthy':
            self.logger.warning(f"Client {client_id} has health issues: {health['issues']}")

        return self.process_manager.start_process(client_id, self.config_manager.client_configs)

    def stop_client(self, client_id: str) -> bool:
        """Stop a specific client."""
        return self.process_manager.stop_process(client_id)

    def restart_client(self, client_id: str) -> bool:
        """Restart a specific client."""
        self.total_restarts += 1
        return self.process_manager.restart_process(client_id, self.config_manager.client_configs)

    async def start_all_enabled_clients(self) -> List[str]:
        """Start all enabled clients."""
        enabled_clients = [
            client_id for client_id, config in self.config_manager.client_configs.items()
            if config.enabled
        ]

        if not enabled_clients:
            self.logger.warning("No enabled clients found")
            return []

        self.logger.info(f"Starting {len(enabled_clients)} enabled clients...")

        started_clients = []
        for client_id in enabled_clients:
            if self.start_client(client_id):
                started_clients.append(client_id)

            # Brief pause between starts
            await asyncio.sleep(0.5)

        self.logger.info(f"Started {len(started_clients)}/{len(enabled_clients)} clients")
        return started_clients

    async def stop_all_clients(self) -> List[str]:
        """Stop all running clients."""
        running_clients = list(self.process_manager.get_running_client_ids())

        if not running_clients:
            self.logger.info("No clients are currently running")
            return []

        self.logger.info(f"Stopping {len(running_clients)} clients...")

        stopped_clients = []
        for client_id in running_clients:
            if self.stop_client(client_id):
                stopped_clients.append(client_id)

        self.logger.info(f"Stopped {len(stopped_clients)}/{len(running_clients)} clients")
        return stopped_clients

    def create_client(self, client_id: str, display_name: str = None,
                      plan: str = "basic", database_backend: str = "sqlite", **kwargs) -> bool:
        """Create a new client using ClientManager FLAGS system."""
        try:
            client_manager = self._get_client_manager()

            success = client_manager.create_client(
                client_id=client_id,
                display_name=display_name or client_id.replace('_', ' ').replace('-', ' ').title(),
                plan=plan,
                database_backend=database_backend,
                **kwargs
            )

            if success:
                # Reload ConfigManager to pick up new client from ClientManager
                self.config_manager.load_client_configs()

                self.logger.info(f"✅ Created client: {client_id} using FLAGS system")
                self.auto_fix_log.append({
                    'timestamp': datetime.now().isoformat(),
                    'action': f'Created client {client_id} with FLAGS system',
                    'type': 'client_creation'
                })

            return success

        except Exception as e:
            self.logger.error(f"Failed to create client {client_id}: {e}")
            return False

    def delete_client(self, client_id: str, backup: bool = True) -> bool:
        """Delete a client with optional backup using ClientManager."""
        try:
            if client_id not in self.config_manager.client_configs:
                self.logger.error(f"Client {client_id} not found")
                return False

            # Stop client if running
            if client_id in self.process_manager.get_running_client_ids():
                self.logger.info(f"Stopping {client_id} before deletion...")
                self.stop_client(client_id)

            # Create backup if requested
            if backup:
                backup_success = self._backup_client(client_id)
                if not backup_success:
                    self.logger.warning(f"Backup failed for {client_id}, continuing with deletion...")

            # Use ClientManager to delete
            client_manager = self._get_client_manager()
            success = client_manager.delete_client(client_id)

            if success:
                # Reload ConfigManager to reflect deletion
                self.config_manager.load_client_configs()

                self.logger.info(f"🗑️ Deleted client: {client_id}")
                self.auto_fix_log.append({
                    'timestamp': datetime.now().isoformat(),
                    'action': f'Deleted client {client_id}',
                    'type': 'client_deletion'
                })

            return success

        except Exception as e:
            self.logger.error(f"Failed to delete client {client_id}: {e}")
            return False

    def _backup_client(self, client_id: str) -> bool:
        """Create backup of client data."""
        try:
            client_dir = Path("clients") / client_id
            if not client_dir.exists():
                return True  # Nothing to backup

            backup_dir = Path("backups") / f"{client_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_dir.parent.mkdir(exist_ok=True)

            shutil.copytree(client_dir, backup_dir)
            self.logger.info(f"📦 Backed up {client_id} to {backup_dir}")
            return True

        except Exception as e:
            self.logger.error(f"Backup failed for {client_id}: {e}")
            return False

    def auto_heal_platform(self) -> int:
        """Perform auto-healing operations."""
        if not self.config_manager.get_auto_healing_config().get('enabled', True):
            return 0

        fixes_applied = 0

        # Clean up dead processes
        dead_processes = self.process_manager.cleanup_dead_processes()
        fixes_applied += len(dead_processes)

        for client_id in dead_processes:
            self.auto_fix_log.append({
                'timestamp': datetime.now().isoformat(),
                'action': f'Cleaned up dead process for {client_id}',
                'type': 'process_cleanup'
            })

        # Validate all client health
        for client_id in self.config_manager.client_configs:
            health = self.config_manager.validate_client_health(client_id)
            if health['config_health'] != 'healthy':
                self.logger.info(f"Client {client_id} needs attention: {health['issues']}")

        if fixes_applied > 0:
            self.logger.info(f"🔧 Auto-healing applied {fixes_applied} fixes")

        return fixes_applied

    async def health_check_loop(self) -> None:
        """Continuous health monitoring."""
        while True:
            try:
                self.auto_heal_platform()
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
                await asyncio.sleep(60)  # Retry in 1 minute


class PlatformOrchestrator:
    """Main orchestrator that coordinates all components."""

    def __init__(self, config_path: str = "platform_config.json"):
        """Initialize platform with dependency injection."""
        self.logger = configure_logger(
            log_dir="bot_platform/logs",
            level="INFO",
            format_extra=True,
            discord_compat=True
        )

        # Initialize components
        self.config_manager = ConfigManager(config_path)
        self.process_manager = ProcessManager()
        self.service_manager = ServiceManager(self.process_manager, self.config_manager)

        # Platform state
        self.initialized = False

    def initialize(self) -> bool:
        """Initialize the platform."""
        try:
            self.logger.info("🚀 Initializing Multi-Client Discord Bot Platform")

            # Load configuration from ClientManager
            self.config_manager.load_client_configs()

            # Log summary
            total_clients = len(self.config_manager.client_configs)
            running_clients = len(self.process_manager.get_running_client_ids())

            self.logger.info(f"✅ Platform ready with {total_clients} clients ({running_clients} running)")

            self.initialized = True
            return True

        except Exception as e:
            self.logger.error(f"Platform initialization failed: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get platform status."""
        if not self.initialized:
            return {'error': 'Platform not initialized'}

        return self.service_manager.get_platform_status()

    def start_client(self, client_id: str) -> bool:
        """Start a client."""
        if not self.initialized:
            self.logger.error("Platform not initialized")
            return False

        return self.service_manager.start_client(client_id)

    def stop_client(self, client_id: str) -> bool:
        """Stop a client."""
        if not self.initialized:
            self.logger.error("Platform not initialized")
            return False

        return self.service_manager.stop_client(client_id)

    def restart_client(self, client_id: str) -> bool:
        """Restart a client."""
        if not self.initialized:
            self.logger.error("Platform not initialized")
            return False

        return self.service_manager.restart_client(client_id)

    async def start_all_clients(self) -> List[str]:
        """Start all enabled clients."""
        if not self.initialized:
            self.logger.error("Platform not initialized")
            return []

        return await self.service_manager.start_all_enabled_clients()

    async def stop_all_clients(self) -> List[str]:
        """Stop all clients."""
        if not self.initialized:
            self.logger.error("Platform not initialized")
            return []

        return await self.service_manager.stop_all_clients()

    def create_client(self, client_id: str, **kwargs) -> bool:
        """Create a new client using FLAGS system."""
        if not self.initialized:
            self.logger.error("Platform not initialized")
            return False

        return self.service_manager.create_client(client_id, **kwargs)

    def delete_client(self, client_id: str, backup: bool = True) -> bool:
        """Delete a client."""
        if not self.initialized:
            self.logger.error("Platform not initialized")
            return False

        return self.service_manager.delete_client(client_id, backup)

    async def run_health_monitoring(self) -> None:
        """Start health monitoring loop."""
        if not self.initialized:
            self.logger.error("Platform not initialized")
            return

        await self.service_manager.health_check_loop()

    async def shutdown(self) -> None:
        """Graceful platform shutdown."""
        if not self.initialized:
            return

        self.logger.info("🛑 Shutting down platform...")

        # Stop all clients
        await self.stop_all_clients()

        # Save platform configuration (not client data)
        self.config_manager.save_platform_config()

        self.logger.info("✅ Platform shutdown complete")
        self.initialized = False
