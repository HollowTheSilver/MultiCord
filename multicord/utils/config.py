"""
Configuration management for MultiCord CLI.
"""

import toml
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """Manages MultiCord configuration."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".multicord"
        self.config_file = self.config_dir / "config.toml"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or create default config
        if not self.config_file.exists():
            self._create_default_config()
        
        self.config = self._load_config()
    
    def _create_default_config(self) -> None:
        """Create default configuration file."""
        default_config = {
            "general": {
                "default_template": "basic",
                "log_level": "INFO",
                "max_bots": 10
            },
            "api": {
                "url": "https://api.multicord.io",
                "timeout": 30
            }
        }
        
        with open(self.config_file, "w") as f:
            toml.dump(default_config, f)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        with open(self.config_file, "r") as f:
            return toml.load(f)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        keys = key.split(".")
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        keys = key.split(".")
        config = self.config
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
        
        # Save to file
        with open(self.config_file, "w") as f:
            toml.dump(self.config, f)
    
    def get_local_config(self) -> Dict[str, Any]:
        """Get local configuration section."""
        return self.config.get("general", {})
    
    def get_api_url(self) -> str:
        """Get API URL."""
        return self.config.get("api", {}).get("url", "https://api.multicord.io")