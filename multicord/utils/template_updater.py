"""
Template update system with multiple update strategies.
Handles safe bot template updates with backup, rollback, and conflict resolution.
"""

import shutil
import json
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import filecmp

from .template_repository import TemplateRepository
from .backup_manager import BackupManager
from .version import SemanticVersion
from .config_merger import ConfigMerger


class UpdateStrategy(Enum):
    """Update strategy determines which files are modified."""
    CORE_ONLY = "core-only"          # Only bot.py, requirements.txt
    SAFE_MERGE = "safe-merge"        # Core + merge configs (recommended)
    FULL_REPLACE = "full-replace"    # Replace all files (aggressive)


@dataclass
class UpdateResult:
    """Result of a template update operation."""
    success: bool
    strategy: str
    bot_name: str
    old_version: str
    new_version: str
    files_updated: List[str]
    files_merged: List[str]
    files_skipped: List[str]
    conflicts: List[str]
    backup_created: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class TemplateUpdater:
    """Manages template updates with multiple strategies and safety features."""

    # Core files that should always be updated
    CORE_FILES = {
        "bot.py",
        "requirements.txt"
    }

    # Configuration files that can be merged
    CONFIG_FILES = {
        "config.toml",
        ".env.example",
        "README.md"
    }

    # Files that should never be modified (user data)
    PROTECTED_FILES = {
        ".env",
        "data",
        "logs",
        ".multicord_meta.json"
    }

    def __init__(
        self,
        bots_dir: Optional[Path] = None,
        template_repo: Optional[TemplateRepository] = None,
        backup_manager: Optional[BackupManager] = None
    ):
        """
        Initialize template updater.

        Args:
            bots_dir: Directory containing bot instances
            template_repo: Template repository manager
            backup_manager: Backup manager instance
        """
        self.bots_dir = bots_dir or (Path.home() / ".multicord" / "bots")
        self.template_repo = template_repo or TemplateRepository()
        self.backup_manager = backup_manager or BackupManager(bots_dir=self.bots_dir)
        self.config_merger = ConfigMerger()

    def update_bot(
        self,
        bot_name: str,
        strategy: UpdateStrategy = UpdateStrategy.SAFE_MERGE,
        target_version: Optional[str] = None,
        create_backup: bool = True,
        dry_run: bool = False
    ) -> UpdateResult:
        """
        Update a bot to the latest (or specified) template version.

        Args:
            bot_name: Name of the bot to update
            strategy: Update strategy to use
            target_version: Specific version to update to (default: latest)
            create_backup: Create backup before updating (default: True)
            dry_run: Preview changes without applying (default: False)

        Returns:
            UpdateResult with details of the update operation
        """
        bot_path = self.bots_dir / bot_name
        if not bot_path.exists():
            return UpdateResult(
                success=False,
                strategy=strategy.value,
                bot_name=bot_name,
                old_version="unknown",
                new_version="unknown",
                files_updated=[],
                files_merged=[],
                files_skipped=[],
                conflicts=[],
                error_message=f"Bot '{bot_name}' not found"
            )

        # Read bot metadata
        meta_file = bot_path / ".multicord_meta.json"
        if not meta_file.exists():
            return UpdateResult(
                success=False,
                strategy=strategy.value,
                bot_name=bot_name,
                old_version="unknown",
                new_version="unknown",
                files_updated=[],
                files_merged=[],
                files_skipped=[],
                conflicts=[],
                error_message="Bot metadata not found (not a template-based bot)"
            )

        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except Exception as e:
            return UpdateResult(
                success=False,
                strategy=strategy.value,
                bot_name=bot_name,
                old_version="unknown",
                new_version="unknown",
                files_updated=[],
                files_merged=[],
                files_skipped=[],
                conflicts=[],
                error_message=f"Failed to read metadata: {e}"
            )

        template_name = metadata.get("template")
        repo_name = metadata.get("repository", "official")
        current_version = metadata.get("template_version", "unknown")

        # Get template info from repository
        try:
            template_info = self.template_repo.get_template_info(template_name, repo_name)
            if not template_info:
                return UpdateResult(
                    success=False,
                    strategy=strategy.value,
                    bot_name=bot_name,
                    old_version=current_version,
                    new_version="unknown",
                    files_updated=[],
                    files_merged=[],
                    files_skipped=[],
                    conflicts=[],
                    error_message=f"Template '{template_name}' not found in repository '{repo_name}'"
                )

            latest_version = template_info.get("version", "unknown")

            # Use target_version if specified
            update_version = target_version or latest_version

            # Get template path
            template_path = self.template_repo.get_template_path(template_name, repo_name)

        except Exception as e:
            return UpdateResult(
                success=False,
                strategy=strategy.value,
                bot_name=bot_name,
                old_version=current_version,
                new_version="unknown",
                files_updated=[],
                files_merged=[],
                files_skipped=[],
                conflicts=[],
                error_message=f"Failed to fetch template: {e}"
            )

        # Create backup before update (unless dry run)
        backup_name = None
        if create_backup and not dry_run:
            try:
                backup = self.backup_manager.create_backup(bot_name, reason="pre_update")
                if backup:
                    backup_name = backup.backup_file
            except Exception as e:
                return UpdateResult(
                    success=False,
                    strategy=strategy.value,
                    bot_name=bot_name,
                    old_version=current_version,
                    new_version=update_version,
                    files_updated=[],
                    files_merged=[],
                    files_skipped=[],
                    conflicts=[],
                    error_message=f"Failed to create backup: {e}"
                )

        # Apply update based on strategy
        try:
            if strategy == UpdateStrategy.CORE_ONLY:
                result = self._update_core_only(bot_path, template_path, dry_run)
            elif strategy == UpdateStrategy.SAFE_MERGE:
                result = self._update_safe_merge(bot_path, template_path, dry_run)
            elif strategy == UpdateStrategy.FULL_REPLACE:
                result = self._update_full_replace(bot_path, template_path, dry_run)
            else:
                return UpdateResult(
                    success=False,
                    strategy=strategy.value,
                    bot_name=bot_name,
                    old_version=current_version,
                    new_version=update_version,
                    files_updated=[],
                    files_merged=[],
                    files_skipped=[],
                    conflicts=[],
                    error_message=f"Unknown strategy: {strategy}"
                )

            files_updated, files_merged, files_skipped, conflicts = result

            # Update metadata (unless dry run)
            if not dry_run:
                metadata["template_version"] = update_version
                metadata["last_updated"] = __import__('datetime').datetime.now().isoformat()
                with open(meta_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2)

            return UpdateResult(
                success=True,
                strategy=strategy.value,
                bot_name=bot_name,
                old_version=current_version,
                new_version=update_version,
                files_updated=files_updated,
                files_merged=files_merged,
                files_skipped=files_skipped,
                conflicts=conflicts,
                backup_created=backup_name
            )

        except Exception as e:
            return UpdateResult(
                success=False,
                strategy=strategy.value,
                bot_name=bot_name,
                old_version=current_version,
                new_version=update_version,
                files_updated=[],
                files_merged=[],
                files_skipped=[],
                conflicts=[],
                backup_created=backup_name,
                error_message=f"Update failed: {e}"
            )

    def _update_core_only(
        self,
        bot_path: Path,
        template_path: Path,
        dry_run: bool
    ) -> Tuple[List[str], List[str], List[str], List[str]]:
        """
        Update only core files (bot.py, requirements.txt).
        Safest strategy - no configuration changes.

        Returns:
            Tuple of (files_updated, files_merged, files_skipped, conflicts)
        """
        files_updated = []
        files_merged = []
        files_skipped = []
        conflicts = []

        for core_file in self.CORE_FILES:
            source = template_path / core_file
            target = bot_path / core_file

            if not source.exists():
                files_skipped.append(core_file)
                continue

            # Check if file was modified by user
            if target.exists() and not filecmp.cmp(source, target, shallow=False):
                # For bot.py, this is a conflict (user may have customized)
                if core_file == "bot.py":
                    conflicts.append(f"{core_file} (modified by user)")
                    files_skipped.append(core_file)
                    continue

            # Copy file
            if not dry_run:
                shutil.copy2(source, target)
            files_updated.append(core_file)

        return files_updated, files_merged, files_skipped, conflicts

    def _update_safe_merge(
        self,
        bot_path: Path,
        template_path: Path,
        dry_run: bool
    ) -> Tuple[List[str], List[str], List[str], List[str]]:
        """
        Update core files + merge configuration files.
        Recommended strategy - balances safety and features.

        Returns:
            Tuple of (files_updated, files_merged, files_skipped, conflicts)
        """
        files_updated = []
        files_merged = []
        files_skipped = []
        conflicts = []

        # Update core files
        for core_file in self.CORE_FILES:
            source = template_path / core_file
            target = bot_path / core_file

            if not source.exists():
                files_skipped.append(core_file)
                continue

            if not dry_run:
                shutil.copy2(source, target)
            files_updated.append(core_file)

        # Merge configuration files
        for config_file in self.CONFIG_FILES:
            source = template_path / config_file
            target = bot_path / config_file

            if not source.exists():
                continue

            if not target.exists():
                # New config file - just copy it
                if not dry_run:
                    shutil.copy2(source, target)
                files_updated.append(config_file)
            else:
                # Config file exists - attempt merge
                if config_file.endswith('.toml'):
                    # Merge TOML files intelligently
                    if not dry_run:
                        merge_result = self.config_merger.merge_toml_files(
                            user_file=target,
                            template_file=source,
                            create_backup=True
                        )
                        if merge_result.success:
                            files_merged.append(config_file)
                            conflicts.extend(merge_result.conflicts)
                        else:
                            conflicts.append(f"{config_file} (merge failed: {merge_result.error_message})")
                            files_skipped.append(config_file)
                    else:
                        # Dry run - just preview
                        files_merged.append(config_file)
                elif config_file == 'README.md':
                    # README - backup old, install new
                    if not dry_run:
                        shutil.copy2(target, bot_path / "README.old.md")
                        shutil.copy2(source, target)
                    files_merged.append(config_file)
                else:
                    # Default: skip modified config files
                    files_skipped.append(config_file)

        return files_updated, files_merged, files_skipped, conflicts

    def _update_full_replace(
        self,
        bot_path: Path,
        template_path: Path,
        dry_run: bool
    ) -> Tuple[List[str], List[str], List[str], List[str]]:
        """
        Replace all files except protected user data.
        Aggressive strategy - use with caution.

        Returns:
            Tuple of (files_updated, files_merged, files_skipped, conflicts)
        """
        files_updated = []
        files_merged = []
        files_skipped = []
        conflicts = []

        # Copy all template files
        for item in template_path.iterdir():
            # Skip protected files
            if item.name in self.PROTECTED_FILES:
                files_skipped.append(item.name)
                continue

            target = bot_path / item.name

            if item.is_file():
                if not dry_run:
                    shutil.copy2(item, target)
                files_updated.append(item.name)
            elif item.is_dir() and item.name not in {'__pycache__', '.git'}:
                if not dry_run:
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.copytree(item, target)
                files_updated.append(f"{item.name}/ (directory)")

        return files_updated, files_merged, files_skipped, conflicts

    def preview_update(
        self,
        bot_name: str,
        strategy: UpdateStrategy = UpdateStrategy.SAFE_MERGE,
        target_version: Optional[str] = None
    ) -> UpdateResult:
        """
        Preview what would be updated without applying changes.

        Args:
            bot_name: Name of the bot
            strategy: Update strategy to preview
            target_version: Specific version to preview

        Returns:
            UpdateResult with dry_run=True
        """
        return self.update_bot(
            bot_name=bot_name,
            strategy=strategy,
            target_version=target_version,
            create_backup=False,
            dry_run=True
        )

    def rollback_update(self, bot_name: str, backup_file: Optional[str] = None) -> bool:
        """
        Rollback a bot to a previous backup.

        Args:
            bot_name: Name of the bot
            backup_file: Specific backup to restore (default: latest)

        Returns:
            True if successful
        """
        try:
            return self.backup_manager.restore_backup(
                bot_name=bot_name,
                backup_file=backup_file,
                create_safety_backup=True
            )
        except Exception:
            return False

    def get_update_plan(
        self,
        bot_name: str,
        strategy: UpdateStrategy,
        target_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get detailed update plan without executing.

        Args:
            bot_name: Name of the bot
            strategy: Update strategy
            target_version: Specific version to plan for

        Returns:
            Dictionary with update plan details
        """
        preview = self.preview_update(bot_name, strategy, target_version)

        return {
            "bot_name": bot_name,
            "strategy": strategy.value,
            "current_version": preview.old_version,
            "target_version": preview.new_version,
            "will_update": preview.files_updated,
            "will_merge": preview.files_merged,
            "will_skip": preview.files_skipped,
            "conflicts": preview.conflicts,
            "safe_to_proceed": len(preview.conflicts) == 0,
            "requires_backup": True,
            "can_rollback": self.backup_manager.get_latest_backup(bot_name) is not None
        }
