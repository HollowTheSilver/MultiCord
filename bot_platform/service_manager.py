"""
Service Manager & Platform Orchestrator
======================================

ServiceManager: High-level business operations
PlatformOrchestrator: Coordinates all components with dependency injection
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from pathlib import Path

from .process_manager import ProcessManager
from .config_manager import ConfigManager, ClientConfig
from core.utils.loguruConfig import configure_logger


class ServiceManager:
    """High-level business operations and platform services."""

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

    def get_platform_status(self) -> Dict[str, Any]:
        """Get comprehensive platform status."""
        current_time = datetime.now(timezone.utc)
        uptime_hours = (current_time - self.start_time).total_seconds() / 3600

        # Get process status for all clients
        all_processes = self.process_manager.get_all_processes()

        # Get health status for all clients
        health_summary = {
            'healthy_clients': 0,
            'clients_with_issues': 0,
            'total_auto_fixes': len(self.auto_fix_log),
            'auto_healing_enabled': self.config_manager.get_auto_healing_config().get('enabled', True)
        }

        # Combine process and config info
        client_details = {}
        for client_id, config in self.config_manager.client_configs.items():
            # Get process status
            process_status = all_processes.get(client_id, {
                'running': False,
                'status': 'stopped',
                'restart_count': 0
            })

            # Get health status
            health_status = self.config_manager.validate_client_health(client_id)

            # Track health summary
            if health_status['config_health'] == 'healthy':
                health_summary['healthy_clients'] += 1
            else:
                health_summary['clients_with_issues'] += 1

            # Combine all information
            client_details[client_id] = {
                **process_status,
                'health_status': health_status,
                'config_issues': health_status.get('issues', []),
                'auto_fixes_applied': len([fix for fix in self.auto_fix_log if client_id in str(fix)])
            }

        return {
            'platform': {
                'uptime_hours': round(uptime_hours, 1),
                'total_clients': len(self.config_manager.client_configs),
                'running_clients': len([c for c in all_processes.values() if c.get('running')]),
                'total_restarts': self.total_restarts,
                'last_health_check': current_time.isoformat()
            },
            'health': health_summary,
            'clients': client_details,
            'auto_fix_log': self.auto_fix_log[-10:]  # Last 10 auto-fixes
        }

    def start_client(self, client_id: str) -> bool:
        """Start a specific client with business logic."""
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
            # Could add auto-healing here if enabled

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
                      plan: str = "basic", **kwargs) -> bool:
        """Create a new client with business validation."""
        if client_id in self.config_manager.client_configs:
            self.logger.error(f"Client {client_id} already exists")
            return False

        # Validate client_id format
        if not client_id.replace('_', '').replace('-', '').isalnum():
            self.logger.error(f"Invalid client_id format: {client_id}")
            return False

        # Create config
        config = ClientConfig(
            client_id=client_id,
            display_name=display_name or client_id.replace('_', ' ').title(),
            plan=plan,
            **kwargs
        )

        # Add to configuration
        success = self.config_manager.add_client_config(config)
        if success:
            self.logger.info(f"✅ Created client: {client_id}")
            self.auto_fix_log.append({
                'timestamp': datetime.now().isoformat(),
                'action': f'Created client {client_id}',
                'type': 'client_creation'
            })

        return success

    def delete_client(self, client_id: str, backup: bool = True) -> bool:
        """Delete a client with optional backup."""
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

        # Remove from configuration
        success = self.config_manager.remove_client_config(client_id)
        if success:
            self.logger.info(f"🗑️ Deleted client: {client_id}")
            self.auto_fix_log.append({
                'timestamp': datetime.now().isoformat(),
                'action': f'Deleted client {client_id}',
                'type': 'client_deletion'
            })

        return success

    def _backup_client(self, client_id: str) -> bool:
        """Create backup of client data."""
        try:
            import shutil
            from datetime import datetime

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
                # Could add more auto-healing logic here
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

            # Load configuration
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
        """Create a new client."""
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

        # Save configurations
        self.config_manager.save_client_configs()

        self.logger.info("✅ Platform shutdown complete")
        self.initialized = False
