"""
Bot backup and restore system for safe source updates.
Provides automatic backups before updates with compression and rotation.
"""

import json
import shutil
import tarfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import threading


@dataclass
class BackupMetadata:
    """Metadata about a bot backup."""
    bot_name: str
    timestamp: str
    template: str
    template_version: str
    reason: str  # "pre_update", "manual", "automatic"
    files_count: int
    backup_size_mb: float
    backup_file: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BackupMetadata':
        """Create from dictionary."""
        return cls(**data)


class BackupManager:
    """Manages bot backups with compression, rotation, and restoration."""

    # Files/directories to exclude from backups
    EXCLUDE_PATTERNS = {
        '__pycache__',
        '*.pyc',
        '*.pyo',
        '.venv',
        'venv',
        '.git',
        'logs',  # Exclude logs - they can be large and aren't needed
        '.multicord_meta.json'  # Will be handled separately
    }

    def __init__(self, bots_dir: Optional[Path] = None, backups_dir: Optional[Path] = None,
                 max_backups: int = 5):
        """
        Initialize backup manager.

        Args:
            bots_dir: Directory containing bot instances
            backups_dir: Directory to store backups
            max_backups: Maximum number of backups to keep per bot (default: 5)
        """
        self.bots_dir = bots_dir or (Path.home() / ".multicord" / "bots")
        self.backups_dir = backups_dir or (Path.home() / ".multicord" / "backups")
        self.max_backups = max_backups

        # Ensure backup directory exists
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        # Lock for thread-safe operations
        self._lock = threading.Lock()

    def create_backup(
        self,
        bot_name: str,
        reason: str = "manual"
    ) -> Optional[BackupMetadata]:
        """
        Create a compressed backup of a bot.

        Args:
            bot_name: Name of the bot to backup
            reason: Reason for backup (pre_update, manual, automatic)

        Returns:
            BackupMetadata or None if failed
        """
        with self._lock:
            bot_path = self.bots_dir / bot_name
            if not bot_path.exists():
                return None

            # Read bot metadata for version tracking
            meta_file = bot_path / ".multicord_meta.json"
            template = "unknown"
            template_version = "unknown"

            if meta_file.exists():
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                        template = meta.get("source", "unknown")
                        template_version = meta.get("source_version", "unknown")
                except Exception:
                    pass

            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            backup_name = f"backup_{timestamp}"

            # Create bot-specific backup directory
            bot_backup_dir = self.backups_dir / bot_name
            bot_backup_dir.mkdir(exist_ok=True)

            backup_file = bot_backup_dir / f"{backup_name}.tar.gz"
            metadata_file = bot_backup_dir / f"{backup_name}.json"

            try:
                # Create compressed backup
                files_count = 0
                with tarfile.open(backup_file, "w:gz") as tar:
                    for item in bot_path.iterdir():
                        # Skip excluded patterns
                        if self._should_exclude(item):
                            continue

                        # Add to archive
                        tar.add(item, arcname=item.name)
                        if item.is_file():
                            files_count += 1
                        else:
                            files_count += sum(1 for _ in item.rglob('*') if _.is_file())

                # Calculate backup size
                backup_size_mb = backup_file.stat().st_size / (1024 * 1024)

                # Create metadata
                metadata = BackupMetadata(
                    bot_name=bot_name,
                    timestamp=datetime.now().isoformat(),
                    template=template,
                    template_version=template_version,
                    reason=reason,
                    files_count=files_count,
                    backup_size_mb=round(backup_size_mb, 2),
                    backup_file=backup_file.name
                )

                # Save metadata
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata.to_dict(), f, indent=2)

                # Rotate old backups
                self._rotate_backups(bot_name)

                return metadata

            except Exception as e:
                # Clean up on failure
                if backup_file.exists():
                    backup_file.unlink()
                if metadata_file.exists():
                    metadata_file.unlink()
                raise RuntimeError(f"Failed to create backup: {e}")

    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded from backup."""
        name = path.name

        # Check exact matches
        if name in self.EXCLUDE_PATTERNS:
            return True

        # Check wildcard patterns
        for pattern in self.EXCLUDE_PATTERNS:
            if '*' in pattern:
                # Simple wildcard matching
                if pattern.startswith('*'):
                    if name.endswith(pattern[1:]):
                        return True
                if pattern.endswith('*'):
                    if name.startswith(pattern[:-1]):
                        return True

        return False

    def _rotate_backups(self, bot_name: str) -> None:
        """Remove old backups exceeding max_backups limit."""
        bot_backup_dir = self.backups_dir / bot_name
        if not bot_backup_dir.exists():
            return

        # Get all backup files sorted by timestamp (oldest first)
        backups = sorted(
            bot_backup_dir.glob("backup_*.tar.gz"),
            key=lambda p: p.stat().st_mtime
        )

        # Remove oldest backups if exceeding limit
        while len(backups) > self.max_backups:
            old_backup = backups.pop(0)
            old_metadata = bot_backup_dir / f"{old_backup.stem}.json"

            # Remove both backup and metadata
            old_backup.unlink()
            if old_metadata.exists():
                old_metadata.unlink()

    def list_backups(self, bot_name: str) -> List[BackupMetadata]:
        """
        List all available backups for a bot.

        Args:
            bot_name: Name of the bot

        Returns:
            List of BackupMetadata sorted by timestamp (newest first)
        """
        bot_backup_dir = self.backups_dir / bot_name
        if not bot_backup_dir.exists():
            return []

        backups = []
        for metadata_file in bot_backup_dir.glob("backup_*.json"):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    backups.append(BackupMetadata.from_dict(data))
            except Exception:
                # Skip corrupted metadata files
                continue

        # Sort by timestamp (newest first)
        backups.sort(key=lambda b: b.timestamp, reverse=True)
        return backups

    def get_latest_backup(self, bot_name: str) -> Optional[BackupMetadata]:
        """
        Get the most recent backup for a bot.

        Args:
            bot_name: Name of the bot

        Returns:
            BackupMetadata or None if no backups exist
        """
        backups = self.list_backups(bot_name)
        return backups[0] if backups else None

    def restore_backup(
        self,
        bot_name: str,
        backup_file: Optional[str] = None,
        create_safety_backup: bool = True
    ) -> bool:
        """
        Restore a bot from backup.

        Args:
            bot_name: Name of the bot to restore
            backup_file: Specific backup file to restore (default: latest)
            create_safety_backup: Create a backup before restoring (default: True)

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            bot_path = self.bots_dir / bot_name
            bot_backup_dir = self.backups_dir / bot_name

            if not bot_backup_dir.exists():
                raise FileNotFoundError(f"No backups found for bot '{bot_name}'")

            # Determine which backup to restore
            if backup_file is None:
                latest = self.get_latest_backup(bot_name)
                if not latest:
                    raise FileNotFoundError(f"No backups available for '{bot_name}'")
                backup_file = latest.backup_file

            backup_path = bot_backup_dir / backup_file
            if not backup_path.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_file}")

            # Create safety backup before restore (if bot exists)
            if create_safety_backup and bot_path.exists():
                try:
                    self.create_backup(bot_name, reason="pre_restore")
                except Exception as e:
                    raise RuntimeError(f"Failed to create safety backup: {e}")

            try:
                # Remove current bot directory (if exists)
                if bot_path.exists():
                    shutil.rmtree(bot_path)

                # Create fresh bot directory
                bot_path.mkdir(parents=True, exist_ok=True)

                # Extract backup
                with tarfile.open(backup_path, "r:gz") as tar:
                    tar.extractall(path=bot_path)

                return True

            except Exception as e:
                raise RuntimeError(f"Failed to restore backup: {e}")

    def delete_backup(self, bot_name: str, backup_file: str) -> bool:
        """
        Delete a specific backup.

        Args:
            bot_name: Name of the bot
            backup_file: Backup file to delete

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            bot_backup_dir = self.backups_dir / bot_name
            if not bot_backup_dir.exists():
                return False

            backup_path = bot_backup_dir / backup_file
            metadata_path = bot_backup_dir / f"{Path(backup_file).stem}.json"

            try:
                if backup_path.exists():
                    backup_path.unlink()
                if metadata_path.exists():
                    metadata_path.unlink()
                return True
            except Exception:
                return False

    def delete_all_backups(self, bot_name: str) -> int:
        """
        Delete all backups for a bot.

        Args:
            bot_name: Name of the bot

        Returns:
            Number of backups deleted
        """
        with self._lock:
            bot_backup_dir = self.backups_dir / bot_name
            if not bot_backup_dir.exists():
                return 0

            count = 0
            for backup_file in bot_backup_dir.glob("backup_*.tar.gz"):
                metadata_file = bot_backup_dir / f"{backup_file.stem}.json"

                backup_file.unlink()
                if metadata_file.exists():
                    metadata_file.unlink()
                count += 1

            # Remove empty directory
            if not list(bot_backup_dir.iterdir()):
                bot_backup_dir.rmdir()

            return count

    def get_backup_stats(self, bot_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about backups.

        Args:
            bot_name: Specific bot or None for all bots

        Returns:
            Dictionary with backup statistics
        """
        if bot_name:
            backups = self.list_backups(bot_name)
            total_size = sum(b.backup_size_mb for b in backups)
            return {
                "bot_name": bot_name,
                "backup_count": len(backups),
                "total_size_mb": round(total_size, 2),
                "oldest_backup": backups[-1].timestamp if backups else None,
                "newest_backup": backups[0].timestamp if backups else None
            }
        else:
            # Get stats for all bots
            all_bots = [d.name for d in self.backups_dir.iterdir() if d.is_dir()]
            stats = {
                "total_bots": len(all_bots),
                "total_backups": 0,
                "total_size_mb": 0,
                "bots": {}
            }

            for bot in all_bots:
                bot_stats = self.get_backup_stats(bot)
                stats["total_backups"] += bot_stats["backup_count"]
                stats["total_size_mb"] += bot_stats["total_size_mb"]
                stats["bots"][bot] = bot_stats

            stats["total_size_mb"] = round(stats["total_size_mb"], 2)
            return stats
