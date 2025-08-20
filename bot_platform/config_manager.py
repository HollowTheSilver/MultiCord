"""
Config Manager - Unified Configuration Management
===============================================

Integrates with ClientManager FLAGS system for unified client discovery.
Handles all configuration operations and client lifecycle management.
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
    """Unified configuration management integrated with ClientManager."""

    def __init__(self, config_path: str = "platform_config.json"):
        """Initialize configuration manager."""
        self.config_path = Path(config_path)
        self.clients_dir = Path("clients")
        # Updated to match ClientManager database file
        self.client_manager_db = Path("bot_platform/clients_db.json")

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

        # 2. Discover from ClientManager database (flags system)
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

            # Check for FLAGS system files (new) or features system files (old)
            flags_file = client_dir / 'flags.py'
            features_file = client_dir / 'features.py'
            config_file = client_dir / 'config.py'
            env_file = client_dir / '.env'

            # Determine system type and completeness
            has_flags = flags_file.exists()
            has_features = features_file.exists()
            has_config = config_file.exists()
            has_env = env_file.exists()

            system_type = "FLAGS" if has_flags else ("FEATURES" if has_features else "INCOMPLETE")
            is_complete = has_env and (has_flags or has_features)

            # Load directory config if it exists
            config_data = {}
            if config_file.exists():
                try:
                    spec = {}
                    with open(config_file, 'r', encoding='utf-8') as f:
                        exec(f.read(), spec)

                    if 'CLIENT_CONFIG' in spec:
                        client_config = spec['CLIENT_CONFIG']
                        if 'client_info' in client_config:
                            config_data.update(client_config['client_info'])
                        if 'bot_config' in client_config:
                            config_data.update(client_config['bot_config'])

                except Exception as e:
                    self.logger.debug(f"Could not read config for {client_id}: {e}")

            clients[client_id] = {
                'source': 'directory',
                'path': str(client_dir),
                'system_type': system_type,
                'is_complete': is_complete,
                'has_flags': has_flags,
                'has_features': has_features,
                'config': config_data
            }

        return clients

    def _discover_from_database(self) -> Dict[str, Dict]:
        """Discover clients from ClientManager database (FLAGS system)."""
        clients = {}

        if not self.client_manager_db.exists():
            return clients

        try:
            with open(self.client_manager_db, 'r', encoding='utf-8') as f:
                db_data = json.load(f)

            for client_id, client_data in db_data.items():
                # Convert ClientManager's ClientInfo to ConfigManager format
                clients[client_id] = {
                    'source': 'database',
                    'data': {
                        'client_id': client_data.get('client_id', client_id),
                        'display_name': client_data.get('display_name', client_id),
                        'plan': client_data.get('plan', 'basic'),
                        'enabled': True,  # Default for ClientManager clients
                        'created_at': client_data.get('created_at'),
                        'last_updated': client_data.get('last_updated'),
                        'status': client_data.get('status', 'active'),
                        'monthly_fee': client_data.get('monthly_fee', 0.0),
                        'discord_token': client_data.get('discord_token'),
                        'owner_ids': client_data.get('owner_ids'),
                        'branding': client_data.get('branding', {}),
                        'notes': client_data.get('notes', '')
                    },
                    'system_type': 'FLAGS',
                    'last_updated': client_data.get('last_updated')
                }

        except Exception as e:
            self.logger.debug(f"Could not read ClientManager database: {e}")

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
        """Merge configuration from all sources with priority: database > platform_config > directory."""
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
                'display_name': client_id.replace('_', ' ').replace('-', ' ').title(),
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
                # Filter to only include valid ClientConfig fields
                valid_fields = {
                    k: v for k, v in config_data.items()
                    if k in ['client_id', 'display_name', 'enabled', 'auto_restart',
                             'max_restarts', 'restart_delay', 'memory_limit_mb',
                             'custom_env', 'plan', 'created_at']
                }

                merged_configs[client_id] = ClientConfig(**valid_fields)

            except Exception as e:
                self.logger.warning(f"Error creating config for {client_id}: {e}")
                # Create minimal config
                merged_configs[client_id] = ClientConfig(
                    client_id=client_id,
                    display_name=config_data.get('display_name', client_id.replace('_', ' ').title()),
                    plan=config_data.get('plan', 'basic')
                )

        return merged_configs

    def load_client_configs(self) -> Dict[str, ClientConfig]:
        """Load and merge all client configurations."""
        discovery_results = self.discover_all_clients()
        self.client_configs = self.merge_client_configs(discovery_results)
        return self.client_configs

    def save_client_configs(self) -> bool:
        """Save client configurations back to platform config."""
        try:
            # Update platform config with current client list
            self.platform_config['clients'] = [
                asdict(config) for config in self.client_configs.values()
            ]

            # Update timestamp
            self.platform_config['platform']['last_updated'] = datetime.now().isoformat()

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.platform_config, f, indent=2, ensure_ascii=False)

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
        health_data = {
            'client_id': client_id,
            'config_health': 'unknown',
            'issues': [],
            'last_checked': datetime.now().isoformat()
        }

        try:
            client_dir = self.clients_dir / client_id

            if not client_dir.exists():
                health_data['config_health'] = 'missing'
                health_data['issues'].append('Client directory does not exist')
                return health_data

            # Check for FLAGS or FEATURES system
            flags_file = client_dir / 'flags.py'
            features_file = client_dir / 'features.py'
            config_file = client_dir / 'config.py'
            env_file = client_dir / '.env'
            branding_file = client_dir / 'branding.py'

            issues = []

            # Check required files
            if not env_file.exists():
                issues.append('Missing .env file')

            if not config_file.exists():
                issues.append('Missing config.py file')

            if not branding_file.exists():
                issues.append('Missing branding.py file')

            # Check configuration system
            if not flags_file.exists() and not features_file.exists():
                issues.append('Missing flags.py or features.py file')
            elif flags_file.exists() and features_file.exists():
                issues.append('Both flags.py and features.py exist (should migrate to flags.py only)')

            # Check custom_cogs directory
            custom_cogs_dir = client_dir / 'custom_cogs'
            if not custom_cogs_dir.exists():
                issues.append('Missing custom_cogs directory')

            health_data['issues'] = issues
            health_data['config_health'] = 'healthy' if len(issues) == 0 else 'issues'

        except Exception as e:
            health_data['config_health'] = 'error'
            health_data['issues'] = [f'Health check failed: {str(e)}']

        return health_data

    def get_auto_healing_config(self) -> Dict[str, Any]:
        """Get auto-healing configuration."""
        return self.platform_config.get('auto_healing', {
            'enabled': True,
            'fix_missing_files': True,
            'sync_configurations': True,
            'validate_tokens': False
        })

    def sync_with_client_manager(self) -> bool:
        """Synchronize with ClientManager database."""
        try:
            # Import ClientManager to get latest data
            from bot_platform.client_manager import ClientManager

            client_manager = ClientManager()
            client_manager_clients = client_manager.list_clients()

            # Update our configs with ClientManager data
            for client_id, client_info in client_manager_clients.items():
                config = ClientConfig(
                    client_id=client_info.client_id,
                    display_name=client_info.display_name,
                    plan=client_info.plan,
                    created_at=client_info.created_at,
                    enabled=True  # Default for ClientManager clients
                )
                self.client_configs[client_id] = config

            # Save updated configs
            return self.save_client_configs()

        except Exception as e:
            self.logger.error(f"Failed to sync with ClientManager: {e}")
            return False

    def get_flags_system_clients(self) -> List[str]:
        """Get list of clients using FLAGS system."""
        flags_clients = []

        for client_id in self.client_configs:
            client_dir = self.clients_dir / client_id
            if (client_dir / 'flags.py').exists():
                flags_clients.append(client_id)

        return flags_clients

    def get_features_system_clients(self) -> List[str]:
        """Get list of clients using old FEATURES system."""
        features_clients = []

        for client_id in self.client_configs:
            client_dir = self.clients_dir / client_id
            flags_file = client_dir / 'flags.py'
            features_file = client_dir / 'features.py'

            if features_file.exists() and not flags_file.exists():
                features_clients.append(client_id)

        return features_clients
