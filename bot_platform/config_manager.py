"""
Config Manager
=====================================================

Reads all client data from ClientManager (single source of truth).
Provides ClientConfig objects for platform operations.
No separate client storage - eliminates dual database complexity.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from core.utils.loguruConfig import configure_logger


@dataclass
class ClientConfig:
    """Clean client configuration for platform operations."""
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


class ConfigManager:
    """Configuration management - reads from ClientManager single source of truth."""

    def __init__(self, config_path: str = "platform_config.json"):
        """Initialize configuration manager."""
        self.config_path = Path(config_path)
        self.clients_dir = Path("clients")

        self.logger = configure_logger(
            log_dir="bot_platform/logs",
            level="INFO",
            format_extra=True,
            discord_compat=True
        )

        # Configuration state
        self.client_configs: Dict[str, ClientConfig] = {}
        self.platform_config: Dict[str, Any] = {}

        # Load platform configuration (not client data)
        self.load_platform_config()

    def load_client_configs(self) -> Dict[str, ClientConfig]:
        """Load client configurations from ClientManager (single source of truth)."""
        self.logger.info("🔍 Loading clients from ClientManager...")

        try:
            # Import here to avoid circular imports
            from .client_manager import ClientManager

            client_manager = ClientManager()
            client_manager_clients = client_manager.list_clients()

            # Convert ClientInfo objects to ClientConfig objects
            converted_configs = {}
            for client_id, client_info in client_manager_clients.items():
                config = ClientConfig(
                    client_id=client_info.client_id,
                    display_name=client_info.display_name,
                    plan=client_info.plan,
                    created_at=client_info.created_at,
                    enabled=True  # Default operational setting
                )
                converted_configs[client_id] = config

            self.client_configs = converted_configs

            # Log discovery results
            directory_count = self._count_client_directories()
            total_clients = len(self.client_configs)

            self.logger.info(f"📊 Discovery complete: {directory_count} directories, "
                           f"{total_clients} in ClientManager database, "
                           f"{total_clients} unique clients")

            return self.client_configs

        except Exception as e:
            self.logger.error(f"Failed to load client configs from ClientManager: {e}")
            # Fallback to directory discovery only
            return self._fallback_directory_discovery()

    def _count_client_directories(self) -> int:
        """Count client directories for logging."""
        if not self.clients_dir.exists():
            return 0

        count = 0
        for client_dir in self.clients_dir.iterdir():
            if client_dir.is_dir() and not client_dir.name.startswith('_'):
                count += 1
        return count

    def _fallback_directory_discovery(self) -> Dict[str, ClientConfig]:
        """Fallback: discover clients from directories if ClientManager fails."""
        self.logger.warning("Using fallback directory discovery")

        fallback_configs = {}

        if not self.clients_dir.exists():
            return fallback_configs

        for client_dir in self.clients_dir.iterdir():
            if not client_dir.is_dir() or client_dir.name.startswith('_'):
                continue

            client_id = client_dir.name

            # Basic config from directory name
            config = ClientConfig(
                client_id=client_id,
                display_name=client_id.replace('_', ' ').replace('-', ' ').title(),
                plan="basic"  # Default
            )

            fallback_configs[client_id] = config

        self.client_configs = fallback_configs
        self.logger.warning(f"Fallback discovery found {len(fallback_configs)} clients")
        return fallback_configs

    def get_client_config(self, client_id: str) -> Optional[ClientConfig]:
        """Get configuration for a specific client."""
        return self.client_configs.get(client_id)

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

    def load_platform_config(self) -> Dict[str, Any]:
        """Load platform configuration (not client data)."""
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
            }
        }

        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)

                # Merge with defaults, remove any client data
                merged_config = {**default_config, **loaded_config}
                # Ensure no client data in platform config
                merged_config.pop('clients', None)

                self.platform_config = merged_config

            except Exception as e:
                self.logger.warning(f"Could not load platform config: {e}")
                self.platform_config = default_config
        else:
            self.platform_config = default_config

        return self.platform_config

    def save_platform_config(self) -> bool:
        """Save platform configuration (not client data)."""
        try:
            # Update timestamp
            self.platform_config['platform']['last_updated'] = datetime.now().isoformat()

            # Ensure no client data
            config_to_save = {k: v for k, v in self.platform_config.items() if k != 'clients'}

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            self.logger.error(f"Failed to save platform config: {e}")
            return False

    def get_auto_healing_config(self) -> Dict[str, Any]:
        """Get auto-healing configuration."""
        return self.platform_config.get('auto_healing', {
            'enabled': True,
            'fix_missing_files': True,
            'sync_configurations': True,
            'validate_tokens': False
        })
