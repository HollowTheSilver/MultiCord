"""
Config Manager - Unified Configuration Management
===============================================

Handles all configuration operations:
- Client discovery from all sources
- Configuration synchronization
- Health checks and validation
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from datetime import datetime

from core.utils.loguruConfig import configure_logger


@dataclass
class ClientConfig:
    """Clean client configuration."""
    client_id: str
    display_name: str
    enabled: bool = True
    auto_restart: bool = True
    max_restarts: int = 5
    restart_delay: int = 30
    memory_limit_mb: int = 512
    custom_env: Dict[str, str] = None
    plan: str = "basic"
    created_at: Optional[str] = None

    def __post_init__(self):
        if self.custom_env is None:
            self.custom_env = {}
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


@dataclass
class DiscoveryResults:
    """Results from client discovery."""
    directories: Dict[str, Dict] = None
    database: Dict[str, Dict] = None
    platform_config: Dict[str, Dict] = None

    def __post_init__(self):
        if self.directories is None:
            self.directories = {}
        if self.database is None:
            self.database = {}
        if self.platform_config is None:
            self.platform_config = {}


class ConfigManager:
    """Unified configuration management."""

    def __init__(self, config_path: str = "platform_config.json"):
        """Initialize configuration manager."""
        self.config_path = Path(config_path)
        self.clients_dir = Path("clients")
        self.client_manager_db = Path("bot_platform/clients.json")

        self.logger = configure_logger(
            log_dir="bot_platform/logs",
            level="INFO",
            format_extra=True,
            discord_compat=True
        )

        # Configuration state
        self.client_configs: Dict[str, ClientConfig] = {}
        self.platform_config: Dict[str, Any] = {}

        # Load initial configuration
        self.load_platform_config()

    def discover_all_clients(self) -> DiscoveryResults:
        """Discover clients from all sources."""
        self.logger.info("🔍 Discovering clients from all sources...")

        results = DiscoveryResults()

        # 1. Discover from directories
        results.directories = self._discover_from_directories()

        # 2. Discover from client manager database
        results.database = self._discover_from_database()

        # 3. Discover from platform config
        results.platform_config = self._discover_from_platform_config()

        total_found = len(set(
            list(results.directories.keys()) +
            list(results.database.keys()) +
            list(results.platform_config.keys())
        ))

        self.logger.info(f"📊 Discovery complete: {len(results.directories)} directories, "
                         f"{len(results.database)} in database, "
                         f"{len(results.platform_config)} in platform config, "
                         f"{total_found} unique clients")

        return results

    def _discover_from_directories(self) -> Dict[str, Dict]:
        """Discover clients from filesystem directories."""
        clients = {}

        if not self.clients_dir.exists():
            return clients

        for client_dir in self.clients_dir.iterdir():
            if not client_dir.is_dir() or client_dir.name.startswith('_'):
                continue

            client_id = client_dir.name

            # Check for required files
            required_files = ['config.json', '.env']
            existing_files = []
            missing_files = []

            for file_name in required_files:
                file_path = client_dir / file_name
                if file_path.exists():
                    existing_files.append(file_name)
                else:
                    missing_files.append(file_name)

            # Load directory config if it exists
            config_data = {}
            config_file = client_dir / 'config.json'
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        file_config = json.load(f)

                    # Extract client info from config structure
                    if 'client_info' in file_config:
                        config_data.update(file_config['client_info'])
                    if 'bot_config' in file_config:
                        config_data.update(file_config['bot_config'])

                except Exception as e:
                    self.logger.debug(f"Could not read config for {client_id}: {e}")

            clients[client_id] = {
                'source': 'directory',
                'path': str(client_dir),
                'is_complete': len(missing_files) == 0,
                'existing_files': existing_files,
                'missing_files': missing_files,
                'config': config_data
            }

        return clients

    def _discover_from_database(self) -> Dict[str, Dict]:
        """Discover clients from client manager database."""
        clients = {}

        if not self.client_manager_db.exists():
            return clients

        try:
            with open(self.client_manager_db, 'r', encoding='utf-8') as f:
                db_data = json.load(f)

            for client_id, client_data in db_data.items():
                clients[client_id] = {
                    'source': 'database',
                    'data': client_data,
                    'last_updated': client_data.get('last_updated')
                }

        except Exception as e:
            self.logger.debug(f"Could not read client database: {e}")

        return clients

    def _discover_from_platform_config(self) -> Dict[str, Dict]:
        """Discover clients from platform configuration."""
        clients = {}

        if not self.config_path.exists():
            return clients

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                platform_data = json.load(f)

            for client_data in platform_data.get('clients', []):
                client_id = client_data.get('client_id')
                if client_id:
                    clients[client_id] = {
                        'source': 'platform_config',
                        'data': client_data
                    }

        except Exception as e:
            self.logger.debug(f"Could not read platform config: {e}")

        return clients

    def merge_client_configs(self, discovery_results: DiscoveryResults) -> Dict[str, ClientConfig]:
        """Merge configuration from all sources with priority."""
        merged_configs = {}

        # Get all unique client IDs
        all_client_ids = set()
        all_client_ids.update(discovery_results.directories.keys())
        all_client_ids.update(discovery_results.database.keys())
        all_client_ids.update(discovery_results.platform_config.keys())

        for client_id in all_client_ids:
            # Start with defaults
            config_data = {
                'client_id': client_id,
                'display_name': client_id.replace('_', ' ').title(),
                'enabled': True,
                'auto_restart': True,
                'max_restarts': 5,
                'restart_delay': 30,
                'memory_limit_mb': 512,
                'custom_env': {},
                'plan': 'basic'
            }

            # Merge data with priority: database > platform_config > directory
            if client_id in discovery_results.directories:
                dir_config = discovery_results.directories[client_id].get('config', {})
                config_data.update(dir_config)

            if client_id in discovery_results.platform_config:
                platform_config = discovery_results.platform_config[client_id].get('data', {})
                config_data.update(platform_config)

            if client_id in discovery_results.database:
                db_config = discovery_results.database[client_id].get('data', {})
                config_data.update(db_config)

            # Create ClientConfig object
            try:
                merged_configs[client_id] = ClientConfig(**{
                    k: v for k, v in config_data.items()
                    if k in ['client_id', 'display_name', 'enabled', 'auto_restart',
                             'max_restarts', 'restart_delay', 'memory_limit_mb',
                             'custom_env', 'plan', 'created_at']
                })
            except Exception as e:
                self.logger.warning(f"Error creating config for {client_id}: {e}")
                # Create minimal config
                merged_configs[client_id] = ClientConfig(
                    client_id=client_id,
                    display_name=client_id.replace('_', ' ').title()
                )

        return merged_configs

    def load_client_configs(self) -> Dict[str, ClientConfig]:
        """Load and merge all client configurations."""
        discovery_results = self.discover_all_clients()
        self.client_configs = self.merge_client_configs(discovery_results)
        return self.client_configs

    def save_client_configs(self) -> bool:
        """Save client configurations back to database and platform config."""
        try:
            # Save to client manager database
            if self.client_manager_db.parent.exists():
                db_data = {}
                for client_id, config in self.client_configs.items():
                    config_dict = asdict(config)
                    config_dict['last_updated'] = datetime.now().isoformat()
                    db_data[client_id] = config_dict

                with open(self.client_manager_db, 'w', encoding='utf-8') as f:
                    json.dump(db_data, f, indent=2, ensure_ascii=False)

            # Save to platform config
            self.save_platform_config()

            return True

        except Exception as e:
            self.logger.error(f"Failed to save client configs: {e}")
            return False

    def load_platform_config(self) -> Dict[str, Any]:
        """Load platform configuration."""
        default_config = {
            'platform': {
                'name': 'Multi-Client Discord Bot Platform',
                'version': '3.0.0',
                'last_updated': datetime.now().isoformat()
            },
            'auto_healing': {
                'enabled': True,
                'fix_missing_files': True,
                'sync_configurations': True,
                'validate_tokens': False
            },
            'logging': {
                'level': 'INFO',
                'show_startup_details': True,
                'show_auto_healing': True
            },
            'clients': []
        }

        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)

                # Merge with defaults
                self.platform_config = {**default_config, **loaded_config}

            except Exception as e:
                self.logger.warning(f"Could not load platform config: {e}")
                self.platform_config = default_config
        else:
            self.platform_config = default_config

        return self.platform_config

    def save_platform_config(self) -> bool:
        """Save platform configuration."""
        try:
            # Update clients list
            self.platform_config['clients'] = [
                asdict(config) for config in self.client_configs.values()
            ]

            # Update timestamp
            self.platform_config['platform']['last_updated'] = datetime.now().isoformat()

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.platform_config, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            self.logger.error(f"Failed to save platform config: {e}")
            return False

    def get_client_config(self, client_id: str) -> Optional[ClientConfig]:
        """Get configuration for a specific client."""
        return self.client_configs.get(client_id)

    def add_client_config(self, config: ClientConfig) -> bool:
        """Add a new client configuration."""
        try:
            self.client_configs[config.client_id] = config
            return self.save_client_configs()
        except Exception as e:
            self.logger.error(f"Failed to add client config: {e}")
            return False

    def remove_client_config(self, client_id: str) -> bool:
        """Remove a client configuration."""
        try:
            if client_id in self.client_configs:
                del self.client_configs[client_id]
                return self.save_client_configs()
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove client config: {e}")
            return False

    def validate_client_health(self, client_id: str) -> Dict[str, Any]:
        """Validate health of a specific client."""
        health_info = {
            'client_id': client_id,
            'config_health': 'unknown',
            'issues': [],
            'last_check': datetime.now().isoformat()
        }

        # Check if client exists in configs
        if client_id not in self.client_configs:
            health_info['config_health'] = 'missing'
            health_info['issues'].append('Client not found in configuration')
            return health_info

        # Check directory structure
        client_dir = self.clients_dir / client_id
        if not client_dir.exists():
            health_info['config_health'] = 'unhealthy'
            health_info['issues'].append('Client directory missing')
            return health_info

        # Check required files
        required_files = ['config.json', '.env']
        missing_files = []

        for file_name in required_files:
            if not (client_dir / file_name).exists():
                missing_files.append(file_name)

        if missing_files:
            health_info['config_health'] = 'unhealthy'
            health_info['issues'].extend([f'Missing file: {f}' for f in missing_files])
        else:
            health_info['config_health'] = 'healthy'

        return health_info

    def get_auto_healing_config(self) -> Dict[str, Any]:
        """Get auto-healing configuration."""
        return self.platform_config.get('auto_healing', {
            'enabled': True,
            'fix_missing_files': True,
            'sync_configurations': True,
            'validate_tokens': False
        })
