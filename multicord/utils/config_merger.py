"""
Configuration file merging for safe template updates.
Intelligently merges TOML and ENV files while preserving user customizations.
"""

import toml
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MergeResult:
    """Result of a configuration merge operation."""
    success: bool
    added_fields: List[str]
    updated_fields: List[str]
    preserved_fields: List[str]
    conflicts: List[str]
    backup_created: Optional[str] = None
    error_message: Optional[str] = None


class ConfigMerger:
    """Merges configuration files while preserving user customizations."""

    def __init__(self):
        """Initialize configuration merger."""
        pass

    def merge_toml_files(
        self,
        user_file: Path,
        template_file: Path,
        output_file: Optional[Path] = None,
        create_backup: bool = True
    ) -> MergeResult:
        """
        Merge TOML configuration files intelligently.

        Strategy:
        - Preserve all user values
        - Add new fields from template
        - Keep user's field order where possible
        - Add comments for new fields

        Args:
            user_file: Existing user configuration
            template_file: New template configuration
            output_file: Output path (default: overwrite user_file)
            create_backup: Create .old backup (default: True)

        Returns:
            MergeResult with merge details
        """
        if output_file is None:
            output_file = user_file

        # Create backup if requested
        backup_path = None
        if create_backup and user_file.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = user_file.parent / f"{user_file.stem}.{timestamp}.old{user_file.suffix}"
            shutil.copy2(user_file, backup_path)

        try:
            # Load both files
            user_config = self._load_toml(user_file) if user_file.exists() else {}
            template_config = self._load_toml(template_file)

            # Merge configurations
            merged_config, merge_info = self._merge_dicts(
                user_config,
                template_config,
                path=""
            )

            # Write merged configuration
            with open(output_file, 'w', encoding='utf-8') as f:
                toml.dump(merged_config, f)

            added, updated, preserved, conflicts = merge_info

            return MergeResult(
                success=True,
                added_fields=added,
                updated_fields=updated,
                preserved_fields=preserved,
                conflicts=conflicts,
                backup_created=str(backup_path) if backup_path else None
            )

        except Exception as e:
            return MergeResult(
                success=False,
                added_fields=[],
                updated_fields=[],
                preserved_fields=[],
                conflicts=[],
                backup_created=str(backup_path) if backup_path else None,
                error_message=f"Failed to merge TOML: {e}"
            )

    def _load_toml(self, file_path: Path) -> Dict[str, Any]:
        """Load TOML file with error handling."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return toml.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load TOML file {file_path}: {e}")

    def _merge_dicts(
        self,
        user: Dict[str, Any],
        template: Dict[str, Any],
        path: str = ""
    ) -> Tuple[Dict[str, Any], Tuple[List[str], List[str], List[str], List[str]]]:
        """
        Recursively merge dictionaries.

        Priority: user values > template values
        New fields from template are added

        Returns:
            Tuple of (merged_dict, (added, updated, preserved, conflicts))
        """
        merged = {}
        added = []
        updated = []
        preserved = []
        conflicts = []

        # Start with all user keys (preserve user values)
        for key, user_value in user.items():
            full_path = f"{path}.{key}" if path else key

            if key in template:
                template_value = template[key]

                # Both are dicts - recurse
                if isinstance(user_value, dict) and isinstance(template_value, dict):
                    merged[key], sub_info = self._merge_dicts(
                        user_value,
                        template_value,
                        full_path
                    )
                    sub_added, sub_updated, sub_preserved, sub_conflicts = sub_info
                    added.extend(sub_added)
                    updated.extend(sub_updated)
                    preserved.extend(sub_preserved)
                    conflicts.extend(sub_conflicts)

                # Type mismatch or different values
                elif user_value != template_value:
                    # Preserve user value but note the conflict
                    merged[key] = user_value
                    preserved.append(full_path)

                    # If types differ, it's a conflict
                    if type(user_value) != type(template_value):
                        conflicts.append(
                            f"{full_path} (user type: {type(user_value).__name__}, "
                            f"template type: {type(template_value).__name__})"
                        )

                # Same value - just preserve
                else:
                    merged[key] = user_value
                    preserved.append(full_path)
            else:
                # Key only in user config - preserve it
                merged[key] = user_value
                preserved.append(full_path)

        # Add new keys from template
        for key, template_value in template.items():
            if key not in user:
                full_path = f"{path}.{key}" if path else key
                merged[key] = template_value
                added.append(full_path)

        return merged, (added, updated, preserved, conflicts)

    def merge_env_files(
        self,
        user_file: Path,
        template_file: Path,
        output_file: Optional[Path] = None,
        create_backup: bool = True
    ) -> MergeResult:
        """
        Merge ENV files intelligently.

        Strategy:
        - Preserve all user values (including secrets)
        - Add new keys from template with template values
        - Maintain comments and structure
        - Mark new additions with comments

        Args:
            user_file: Existing user .env file
            template_file: New template .env.example file
            output_file: Output path (default: overwrite user_file)
            create_backup: Create .old backup (default: True)

        Returns:
            MergeResult with merge details
        """
        if output_file is None:
            output_file = user_file

        # Create backup if requested
        backup_path = None
        if create_backup and user_file.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = user_file.parent / f"{user_file.stem}.{timestamp}.old"
            shutil.copy2(user_file, backup_path)

        try:
            # Parse both files
            user_vars = self._parse_env_file(user_file) if user_file.exists() else {}
            template_vars = self._parse_env_file(template_file)

            added = []
            preserved = []

            # Build merged content
            lines = []

            # Header
            lines.append("# MultiCord Bot Configuration")
            lines.append(f"# Merged: {datetime.now().isoformat()}")
            lines.append("")

            # First, write all existing user variables (preserved)
            if user_vars:
                lines.append("# Existing Configuration")
                for key, value in user_vars.items():
                    lines.append(f"{key}={value}")
                    preserved.append(key)
                lines.append("")

            # Then, add new variables from template
            new_vars = {k: v for k, v in template_vars.items() if k not in user_vars}
            if new_vars:
                lines.append("# New Fields from Template Update")
                for key, value in new_vars.items():
                    lines.append(f"{key}={value}")
                    added.append(key)
                lines.append("")

            # Write merged file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            return MergeResult(
                success=True,
                added_fields=added,
                updated_fields=[],
                preserved_fields=preserved,
                conflicts=[],
                backup_created=str(backup_path) if backup_path else None
            )

        except Exception as e:
            return MergeResult(
                success=False,
                added_fields=[],
                updated_fields=[],
                preserved_fields=[],
                conflicts=[],
                backup_created=str(backup_path) if backup_path else None,
                error_message=f"Failed to merge ENV: {e}"
            )

    def _parse_env_file(self, file_path: Path) -> Dict[str, str]:
        """
        Parse ENV file into key-value pairs.

        Args:
            file_path: Path to .env file

        Returns:
            Dictionary of environment variables
        """
        env_vars = {}

        if not file_path.exists():
            return env_vars

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                # Parse KEY=VALUE
                if '=' in line:
                    key, _, value = line.partition('=')
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    env_vars[key] = value

        return env_vars

    def merge_config_directory(
        self,
        user_dir: Path,
        template_dir: Path,
        create_backups: bool = True
    ) -> Dict[str, MergeResult]:
        """
        Merge all configuration files in a directory.

        Args:
            user_dir: User's configuration directory
            template_dir: Template configuration directory
            create_backups: Create backups before merging

        Returns:
            Dictionary mapping filenames to MergeResults
        """
        results = {}

        # Merge TOML files
        for toml_file in template_dir.glob("*.toml"):
            user_file = user_dir / toml_file.name
            result = self.merge_toml_files(
                user_file,
                toml_file,
                create_backup=create_backups
            )
            results[toml_file.name] = result

        # Merge ENV files
        for env_file in template_dir.glob(".env*"):
            # Skip .env (user secrets), only merge .env.example
            if env_file.name == ".env":
                continue

            user_file = user_dir / ".env"
            result = self.merge_env_files(
                user_file,
                env_file,
                create_backup=create_backups
            )
            results[env_file.name] = result

        return results

    def preview_merge(
        self,
        user_file: Path,
        template_file: Path
    ) -> MergeResult:
        """
        Preview merge without writing files.

        Args:
            user_file: Existing user configuration
            template_file: New template configuration

        Returns:
            MergeResult showing what would change
        """
        if user_file.suffix == '.toml':
            # For preview, don't write or backup
            user_config = self._load_toml(user_file) if user_file.exists() else {}
            template_config = self._load_toml(template_file)

            _, merge_info = self._merge_dicts(user_config, template_config)
            added, updated, preserved, conflicts = merge_info

            return MergeResult(
                success=True,
                added_fields=added,
                updated_fields=updated,
                preserved_fields=preserved,
                conflicts=conflicts
            )

        elif user_file.suffix == '.env' or user_file.name.startswith('.env'):
            user_vars = self._parse_env_file(user_file) if user_file.exists() else {}
            template_vars = self._parse_env_file(template_file)

            added = [k for k in template_vars if k not in user_vars]
            preserved = list(user_vars.keys())

            return MergeResult(
                success=True,
                added_fields=added,
                updated_fields=[],
                preserved_fields=preserved,
                conflicts=[]
            )

        else:
            return MergeResult(
                success=False,
                added_fields=[],
                updated_fields=[],
                preserved_fields=[],
                conflicts=[],
                error_message=f"Unsupported file type: {user_file.suffix}"
            )
