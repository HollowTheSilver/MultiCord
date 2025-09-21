"""
Offline cache management for cloud bot data.
Provides transparent caching with TTL and invalidation.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import threading


class CacheManager:
    """Manages offline cache for API responses."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize cache manager with directory and lock."""
        self.cache_dir = cache_dir or (Path.home() / ".multicord" / "cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache files
        self.bots_cache = self.cache_dir / "bots.json"
        self.templates_cache = self.cache_dir / "templates.json"
        self.metadata_cache = self.cache_dir / "metadata.json"

        # Default TTL in seconds (1 hour)
        self.default_ttl = 3600

        # Thread lock for concurrent access
        self._lock = threading.Lock()

        # Initialize metadata if not exists
        if not self.metadata_cache.exists():
            self._save_metadata({})

    def get_bots(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached bot list if valid."""
        with self._lock:
            if not self.bots_cache.exists():
                return None

            if not self._is_cache_valid("bots"):
                return None

            try:
                with open(self.bots_cache, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None

    def set_bots(self, bots: List[Dict[str, Any]], ttl: Optional[int] = None) -> None:
        """Cache bot list with TTL."""
        with self._lock:
            try:
                with open(self.bots_cache, 'w') as f:
                    json.dump(bots, f, indent=2)

                self._update_metadata("bots", ttl or self.default_ttl)
            except IOError as e:
                # Silently fail - cache is optional
                pass

    def get_templates(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached templates if valid."""
        with self._lock:
            if not self.templates_cache.exists():
                return None

            if not self._is_cache_valid("templates"):
                return None

            try:
                with open(self.templates_cache, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None

    def set_templates(self, templates: List[Dict[str, Any]], ttl: Optional[int] = None) -> None:
        """Cache template list with TTL."""
        with self._lock:
            try:
                with open(self.templates_cache, 'w') as f:
                    json.dump(templates, f, indent=2)

                self._update_metadata("templates", ttl or self.default_ttl)
            except IOError:
                pass

    def get_bot_config(self, bot_name: str) -> Optional[Dict[str, Any]]:
        """Get cached configuration for a specific bot."""
        config_file = self.cache_dir / f"bot_{bot_name}_config.json"

        with self._lock:
            if not config_file.exists():
                return None

            if not self._is_cache_valid(f"bot_{bot_name}_config"):
                return None

            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None

    def set_bot_config(self, bot_name: str, config: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Cache bot configuration with TTL."""
        config_file = self.cache_dir / f"bot_{bot_name}_config.json"

        with self._lock:
            try:
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)

                self._update_metadata(f"bot_{bot_name}_config", ttl or self.default_ttl)
            except IOError:
                pass

    def invalidate(self, key: Optional[str] = None) -> None:
        """Invalidate specific cache or all caches."""
        with self._lock:
            metadata = self._load_metadata()

            if key:
                # Invalidate specific cache
                if key in metadata:
                    del metadata[key]

                    # Delete corresponding file if it's a bot config
                    if key.startswith("bot_") and key.endswith("_config"):
                        config_file = self.cache_dir / f"{key}.json"
                        if config_file.exists():
                            config_file.unlink()
            else:
                # Invalidate all caches
                metadata = {}

                # Delete all cache files
                for cache_file in self.cache_dir.glob("*.json"):
                    if cache_file.name != "metadata.json":
                        cache_file.unlink()

            self._save_metadata(metadata)

    def get_cache_status(self) -> Dict[str, Any]:
        """Get status of all caches including age and validity."""
        with self._lock:
            metadata = self._load_metadata()
            status = {
                "cache_dir": str(self.cache_dir),
                "caches": {}
            }

            for key, info in metadata.items():
                timestamp = info.get("timestamp", 0)
                ttl = info.get("ttl", self.default_ttl)
                age = int(time.time() - timestamp)
                expires_in = max(0, ttl - age)

                status["caches"][key] = {
                    "timestamp": datetime.fromtimestamp(timestamp).isoformat(),
                    "age_seconds": age,
                    "ttl_seconds": ttl,
                    "expires_in_seconds": expires_in,
                    "is_valid": expires_in > 0
                }

            return status

    def clear_expired(self) -> int:
        """Clear all expired cache entries. Returns number cleared."""
        with self._lock:
            metadata = self._load_metadata()
            cleared = 0

            for key in list(metadata.keys()):
                if not self._is_cache_valid(key, metadata):
                    del metadata[key]
                    cleared += 1

                    # Delete corresponding file if it's a bot config
                    if key.startswith("bot_") and key.endswith("_config"):
                        config_file = self.cache_dir / f"{key}.json"
                        if config_file.exists():
                            config_file.unlink()

            self._save_metadata(metadata)
            return cleared

    def _is_cache_valid(self, key: str, metadata: Optional[Dict] = None) -> bool:
        """Check if a cache entry is still valid based on TTL."""
        if metadata is None:
            metadata = self._load_metadata()

        if key not in metadata:
            return False

        info = metadata[key]
        timestamp = info.get("timestamp", 0)
        ttl = info.get("ttl", self.default_ttl)

        return (time.time() - timestamp) < ttl

    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata."""
        try:
            if self.metadata_cache.exists():
                with open(self.metadata_cache, 'r') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

        return {}

    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        """Save cache metadata."""
        try:
            with open(self.metadata_cache, 'w') as f:
                json.dump(metadata, f, indent=2)
        except IOError:
            pass

    def _update_metadata(self, key: str, ttl: int) -> None:
        """Update metadata for a cache entry."""
        metadata = self._load_metadata()
        metadata[key] = {
            "timestamp": time.time(),
            "ttl": ttl
        }
        self._save_metadata(metadata)