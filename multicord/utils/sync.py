"""
Configuration synchronization between local and cloud bots.
Handles conflict resolution and version tracking.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from enum import Enum


class MergeStrategy(Enum):
    """Strategies for resolving configuration conflicts."""
    LOCAL_FIRST = "local_first"
    CLOUD_FIRST = "cloud_first"
    MANUAL = "manual"
    NEWEST = "newest"


class ConfigSync:
    """Manages configuration synchronization between local and cloud."""

    def __init__(self, bots_dir: Optional[Path] = None):
        """Initialize sync manager."""
        self.bots_dir = bots_dir or (Path.home() / ".multicord" / "bots")
        self.sync_meta_dir = Path.home() / ".multicord" / "sync"
        self.sync_meta_dir.mkdir(parents=True, exist_ok=True)

    def get_config_hash(self, config: Dict[str, Any]) -> str:
        """Generate hash of configuration for comparison."""
        # Sort keys for consistent hashing
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()

    def get_local_config(self, bot_name: str) -> Optional[Dict[str, Any]]:
        """Get local bot configuration."""
        bot_dir = self.bots_dir / bot_name
        config_file = bot_dir / "config.toml"

        if not config_file.exists():
            config_file = bot_dir / "config.json"
            if not config_file.exists():
                return None

        try:
            if config_file.suffix == ".toml":
                import toml
                with open(config_file, 'r') as f:
                    return toml.load(f)
            else:
                with open(config_file, 'r') as f:
                    return json.load(f)
        except Exception:
            return None

    def save_local_config(self, bot_name: str, config: Dict[str, Any]) -> bool:
        """Save configuration to local bot."""
        bot_dir = self.bots_dir / bot_name
        if not bot_dir.exists():
            return False

        # Prefer TOML if it exists, otherwise JSON
        config_file = bot_dir / "config.toml"
        if not config_file.exists():
            config_file = bot_dir / "config.json"

        try:
            if config_file.suffix == ".toml":
                import toml
                with open(config_file, 'w') as f:
                    toml.dump(config, f)
            else:
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)

            # Update sync metadata
            self._update_sync_metadata(bot_name, config)
            return True
        except Exception:
            return False

    def detect_conflicts(
        self,
        local_config: Dict[str, Any],
        cloud_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Detect configuration conflicts between local and cloud."""
        conflicts = []

        # Get all unique keys
        all_keys = set(local_config.keys()) | set(cloud_config.keys())

        for key in all_keys:
            local_value = local_config.get(key)
            cloud_value = cloud_config.get(key)

            if local_value != cloud_value:
                conflicts.append({
                    "key": key,
                    "local_value": local_value,
                    "cloud_value": cloud_value,
                    "type": self._classify_conflict(key, local_value, cloud_value)
                })

        return conflicts

    def merge_configs(
        self,
        local_config: Dict[str, Any],
        cloud_config: Dict[str, Any],
        strategy: MergeStrategy = MergeStrategy.NEWEST,
        local_timestamp: Optional[float] = None,
        cloud_timestamp: Optional[float] = None
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Merge configurations based on strategy.
        Returns merged config and list of changes made.
        """
        merged = {}
        changes = []

        # Get all unique keys
        all_keys = set(local_config.keys()) | set(cloud_config.keys())

        for key in all_keys:
            local_value = local_config.get(key)
            cloud_value = cloud_config.get(key)

            if local_value == cloud_value:
                # No conflict
                merged[key] = local_value
            elif strategy == MergeStrategy.LOCAL_FIRST:
                merged[key] = local_value if local_value is not None else cloud_value
                if local_value != cloud_value:
                    changes.append(f"Kept local value for '{key}'")
            elif strategy == MergeStrategy.CLOUD_FIRST:
                merged[key] = cloud_value if cloud_value is not None else local_value
                if local_value != cloud_value:
                    changes.append(f"Used cloud value for '{key}'")
            elif strategy == MergeStrategy.NEWEST:
                # Use timestamps if available
                if local_timestamp and cloud_timestamp:
                    if local_timestamp > cloud_timestamp:
                        merged[key] = local_value if local_value is not None else cloud_value
                        changes.append(f"Used newer local value for '{key}'")
                    else:
                        merged[key] = cloud_value if cloud_value is not None else local_value
                        changes.append(f"Used newer cloud value for '{key}'")
                else:
                    # Fall back to cloud first if no timestamps
                    merged[key] = cloud_value if cloud_value is not None else local_value
                    if local_value != cloud_value:
                        changes.append(f"Used cloud value for '{key}' (no timestamp)")
            else:
                # Manual strategy - include both values for user decision
                merged[key] = {
                    "conflict": True,
                    "local": local_value,
                    "cloud": cloud_value
                }
                changes.append(f"Manual resolution needed for '{key}'")

        return merged, changes

    def sync_bot(
        self,
        bot_name: str,
        cloud_config: Dict[str, Any],
        strategy: MergeStrategy = MergeStrategy.NEWEST,
        cloud_timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Sync a bot's configuration with cloud.
        Returns sync result with status and changes.
        """
        result = {
            "success": False,
            "bot_name": bot_name,
            "strategy": strategy.value,
            "conflicts": [],
            "changes": [],
            "merged_config": None
        }

        # Get local config
        local_config = self.get_local_config(bot_name)
        if not local_config:
            # No local config, use cloud config
            if self.save_local_config(bot_name, cloud_config):
                result["success"] = True
                result["changes"] = ["Created local config from cloud"]
                result["merged_config"] = cloud_config
            return result

        # Get local timestamp from metadata
        local_timestamp = self._get_sync_timestamp(bot_name)

        # Detect conflicts
        conflicts = self.detect_conflicts(local_config, cloud_config)
        result["conflicts"] = conflicts

        if not conflicts:
            # No conflicts, configs are identical
            result["success"] = True
            result["merged_config"] = local_config
            return result

        # Merge configurations
        merged_config, changes = self.merge_configs(
            local_config,
            cloud_config,
            strategy,
            local_timestamp,
            cloud_timestamp
        )

        result["changes"] = changes
        result["merged_config"] = merged_config

        # Save merged config if not manual strategy
        if strategy != MergeStrategy.MANUAL:
            if self.save_local_config(bot_name, merged_config):
                result["success"] = True
            else:
                result["success"] = False
                result["error"] = "Failed to save merged configuration"
        else:
            # Manual strategy requires user intervention
            result["success"] = False
            result["requires_manual"] = True

        return result

    def export_config_for_deploy(self, bot_name: str) -> Optional[Dict[str, Any]]:
        """
        Export bot configuration for deployment to cloud.
        Sanitizes sensitive data and adds metadata.
        """
        config = self.get_local_config(bot_name)
        if not config:
            return None

        # Add metadata
        export_config = {
            "config": config,
            "metadata": {
                "bot_name": bot_name,
                "exported_at": datetime.utcnow().isoformat(),
                "config_hash": self.get_config_hash(config),
                "source": "local"
            }
        }

        # Sanitize sensitive data (don't include tokens in export)
        if "token" in export_config["config"]:
            export_config["config"]["token"] = ""
            export_config["metadata"]["token_removed"] = True

        return export_config

    def _classify_conflict(
        self,
        key: str,
        local_value: Any,
        cloud_value: Any
    ) -> str:
        """Classify the type of conflict."""
        if local_value is None:
            return "added_in_cloud"
        elif cloud_value is None:
            return "added_locally"
        elif type(local_value) != type(cloud_value):
            return "type_mismatch"
        else:
            return "value_difference"

    def _get_sync_timestamp(self, bot_name: str) -> Optional[float]:
        """Get last sync timestamp for a bot."""
        meta_file = self.sync_meta_dir / f"{bot_name}_sync.json"
        if not meta_file.exists():
            return None

        try:
            with open(meta_file, 'r') as f:
                meta = json.load(f)
                return meta.get("timestamp")
        except Exception:
            return None

    def _update_sync_metadata(self, bot_name: str, config: Dict[str, Any]) -> None:
        """Update sync metadata for a bot."""
        meta_file = self.sync_meta_dir / f"{bot_name}_sync.json"
        meta = {
            "timestamp": datetime.utcnow().timestamp(),
            "config_hash": self.get_config_hash(config),
            "last_sync": datetime.utcnow().isoformat()
        }

        try:
            with open(meta_file, 'w') as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass