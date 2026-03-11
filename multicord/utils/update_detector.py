"""
Source update detection for MultiCord CLI.
Detects available updates for bot sources by comparing versions.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from .version import SemanticVersion, is_newer_version, get_update_type, has_breaking_changes
from .source_resolver import SourceResolver


@dataclass
class UpdateInfo:
    """Information about an available source update."""
    available: bool
    current_version: Optional[str] = None
    latest_version: Optional[str] = None
    update_type: Optional[str] = None  # "breaking", "feature", "patch", "none"
    breaking_changes: bool = False
    changelog: Optional[Dict[str, str]] = None
    source_name: Optional[str] = None

    def __str__(self) -> str:
        if not self.available:
            return "No updates available"

        update_emoji = {
            "breaking": "⚠️",
            "feature": "✨",
            "patch": "🔧",
            "none": "✓"
        }
        emoji = update_emoji.get(self.update_type, "📦")

        return (f"{emoji} Update available: {self.current_version} → {self.latest_version} "
                f"({self.update_type} update)")


class UpdateDetector:
    """Detects source updates by comparing bot metadata with source manifests."""

    def __init__(self, bots_dir: Optional[Path] = None):
        """
        Initialize update detector.

        Args:
            bots_dir: Directory containing bot instances (default: ~/.multicord/bots)
        """
        self.bots_dir = bots_dir or (Path.home() / ".multicord" / "bots")
        self.resolver = SourceResolver()

    def check_bot_updates(self, bot_name: str) -> Optional[UpdateInfo]:
        """
        Check if updates are available for a specific bot.

        Args:
            bot_name: Name of the bot to check

        Returns:
            UpdateInfo instance or None if bot not found
        """
        bot_path = self.bots_dir / bot_name
        if not bot_path.exists():
            return None

        # Read bot metadata
        meta_file = bot_path / ".multicord_meta.json"
        if not meta_file.exists():
            return UpdateInfo(
                available=False,
                source_name=bot_name
            )

        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except Exception:
            return UpdateInfo(available=False)

        source_name = metadata.get('source')
        current_version = metadata.get('source_version', 'unknown')

        if not source_name or current_version == 'unknown':
            return UpdateInfo(available=False)

        # Get latest source info via resolver
        try:
            source_metadata = self.resolver.get_source_metadata(source_name)
            if not source_metadata:
                return UpdateInfo(available=False)

            latest_version = source_metadata.get('version', 'unknown')

            # Compare versions
            if latest_version == 'unknown' or current_version == 'unknown':
                return UpdateInfo(available=False)

            if is_newer_version(current_version, latest_version):
                update_type = get_update_type(current_version, latest_version)
                breaking = has_breaking_changes(current_version, latest_version)

                return UpdateInfo(
                    available=True,
                    current_version=current_version,
                    latest_version=latest_version,
                    update_type=update_type,
                    breaking_changes=breaking,
                    changelog=source_metadata.get('changelog'),
                    source_name=source_name
                )
            else:
                return UpdateInfo(
                    available=False,
                    current_version=current_version,
                    latest_version=latest_version,
                    source_name=source_name
                )

        except Exception as e:
            # Repository access failed, return no update
            return UpdateInfo(available=False)

    def check_all_bots_updates(self) -> Dict[str, UpdateInfo]:
        """
        Check for updates across all bots.

        Returns:
            Dictionary mapping bot names to UpdateInfo
        """
        updates = {}

        if not self.bots_dir.exists():
            return updates

        for bot_dir in self.bots_dir.iterdir():
            if bot_dir.is_dir() and not bot_dir.name.startswith('.'):
                update_info = self.check_bot_updates(bot_dir.name)
                if update_info:
                    updates[bot_dir.name] = update_info

        return updates

    def get_bots_with_updates(self) -> List[str]:
        """
        Get list of bot names that have updates available.

        Returns:
            List of bot names with available updates
        """
        all_updates = self.check_all_bots_updates()
        return [
            bot_name
            for bot_name, update_info in all_updates.items()
            if update_info.available
        ]

    def get_update_summary(self) -> Dict[str, int]:
        """
        Get summary of updates by type.

        Returns:
            Dictionary with counts: {
                'total': 5,
                'breaking': 1,
                'feature': 2,
                'patch': 2,
                'up_to_date': 10
            }
        """
        all_updates = self.check_all_bots_updates()

        summary = {
            'total': 0,
            'breaking': 0,
            'feature': 0,
            'patch': 0,
            'up_to_date': 0
        }

        for update_info in all_updates.values():
            if update_info.available:
                summary['total'] += 1
                if update_info.update_type:
                    summary[update_info.update_type] = summary.get(update_info.update_type, 0) + 1
            else:
                summary['up_to_date'] += 1

        return summary

    def get_changelog_for_bot(self, bot_name: str) -> Optional[Dict[str, str]]:
        """
        Get changelog for a bot's template.

        Args:
            bot_name: Name of the bot

        Returns:
            Changelog dictionary mapping versions to changes, or None
        """
        update_info = self.check_bot_updates(bot_name)
        if update_info and update_info.changelog:
            return update_info.changelog
        return None

    def get_changes_between_versions(
        self,
        bot_name: str,
        from_version: Optional[str] = None
    ) -> List[str]:
        """
        Get list of changes between bot's current version and latest.

        Args:
            bot_name: Name of the bot
            from_version: Version to compare from (default: bot's current version)

        Returns:
            List of change descriptions
        """
        update_info = self.check_bot_updates(bot_name)
        if not update_info or not update_info.available or not update_info.changelog:
            return []

        current = from_version or update_info.current_version
        latest = update_info.latest_version

        if not current or not latest:
            return []

        # Parse versions
        current_ver = SemanticVersion.parse(current)
        latest_ver = SemanticVersion.parse(latest)

        if not current_ver or not latest_ver:
            return []

        # Collect all changes between versions
        changes = []
        for version, description in update_info.changelog.items():
            ver = SemanticVersion.parse(version)
            if ver and current_ver < ver <= latest_ver:
                changes.append(f"[{version}] {description}")

        return changes
