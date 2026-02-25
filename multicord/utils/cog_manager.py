"""
Cog management for MultiCord CLI.
Handles installing and managing optional bot cogs from source repositories.
Includes dependency resolution for cog-to-cog dependencies.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple

from multicord.utils.venv_manager import VenvManager
from multicord.utils.validation import validate_path_containment


class DependencyError(Exception):
    """Raised when cog dependency resolution fails."""
    pass


class CircularDependencyError(DependencyError):
    """Raised when a circular dependency is detected."""
    pass


class VersionMismatchError(DependencyError):
    """Raised when a dependency version requirement cannot be satisfied."""
    pass


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """Parse a semver version string into tuple (major, minor, patch)."""
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)', version_str)
    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return (0, 0, 0)


def version_satisfies(installed_version: str, requirement: str) -> bool:
    """
    Check if an installed version satisfies a version requirement.

    Supports: >=1.0.0, ^1.0.0 (1.x.x), ~1.0.0 (1.0.x), exact match (1.0.0)
    """
    installed = parse_version(installed_version)

    if requirement.startswith('>='):
        required = parse_version(requirement[2:])
        return installed >= required
    elif requirement.startswith('^'):
        required = parse_version(requirement[1:])
        return installed[0] == required[0] and installed >= required
    elif requirement.startswith('~'):
        required = parse_version(requirement[1:])
        return installed[0] == required[0] and installed[1] == required[1] and installed >= required
    else:
        required = parse_version(requirement)
        return installed == required


class CogManager:
    """Manages cog installations and updates."""

    def __init__(self, source_path: Path):
        """
        Initialize cog manager.

        Args:
            source_path: Path to the source repository containing cogs
        """
        self.source_path = source_path
        self.cogs_dir = source_path / "cogs"
        self.venv_manager = VenvManager()

    def list_available_cogs(self) -> Dict[str, Dict[str, Any]]:
        """
        List all available cogs from the repository.

        Returns:
            Dictionary of cog metadata keyed by cog ID
        """
        manifest_path = self.source_path / "multicord.json"
        if not manifest_path.exists():
            return {}

        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        cogs = {}

        # Parse items array for cog entries like "cogs/permissions/"
        for item_path in manifest.get("items", []):
            if not item_path.startswith("cogs/"):
                continue  # Skip non-cog items

            # Extract cog name from path
            cog_name = item_path.replace("cogs/", "").rstrip("/")
            cog_dir = self.source_path / "cogs" / cog_name
            cog_manifest_path = cog_dir / "cog.json"

            if cog_manifest_path.exists():
                with open(cog_manifest_path, 'r', encoding='utf-8') as f:
                    cog_info = json.load(f)
                    cog_id = cog_info.get("id", cog_name)
                    cogs[cog_id] = cog_info

        return cogs

    def get_cog_metadata(self, cog_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific cog.

        Args:
            cog_name: Name of the cog

        Returns:
            Cog metadata dictionary or None if not found
        """
        available_cogs = self.list_available_cogs()
        return available_cogs.get(cog_name)

    def get_cog_path(self, cog_name: str) -> Optional[Path]:
        """
        Get the path to a cog in the repository.

        Args:
            cog_name: Name of the cog

        Returns:
            Path to the cog directory or None if not found
        """
        cog_path = self.cogs_dir / cog_name
        is_contained, error = validate_path_containment(cog_path, self.cogs_dir)
        if not is_contained:
            raise ValueError(f"Invalid cog name: {error}")

        if cog_path.exists() and cog_path.is_dir():
            return cog_path

        return None

    def get_cog_dependencies(self, cog_name: str) -> Dict[str, str]:
        """
        Get dependencies for a cog from its cog.json manifest.

        Args:
            cog_name: Name of the cog

        Returns:
            Dictionary of {dependency_name: version_requirement}
        """
        cog_path = self.get_cog_path(cog_name)
        if not cog_path:
            return {}

        manifest_file = cog_path / "cog.json"
        if not manifest_file.exists():
            return {}

        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        return manifest.get('dependencies', {})

    def get_cog_optional_dependencies(self, cog_name: str) -> Dict[str, str]:
        """Get optional dependencies for a cog from its cog.json manifest."""
        cog_path = self.get_cog_path(cog_name)
        if not cog_path:
            return {}

        manifest_file = cog_path / "cog.json"
        if not manifest_file.exists():
            return {}

        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        return manifest.get('optional_dependencies', {})

    def resolve_dependencies(
        self,
        cog_name: str,
        bot_path: Path,
        visited: Optional[Set[str]] = None,
        chain: Optional[List[str]] = None
    ) -> List[str]:
        """
        Resolve all dependencies for a cog recursively.

        Args:
            cog_name: Name of the cog to resolve dependencies for
            bot_path: Path to the bot directory
            visited: Set of already processed cogs (for circular detection)
            chain: Current dependency chain (for error reporting)

        Returns:
            Ordered list of cogs to install (dependencies first)

        Raises:
            CircularDependencyError: If circular dependency detected
            DependencyError: If a required dependency cannot be found
        """
        if visited is None:
            visited = set()
        if chain is None:
            chain = []

        if cog_name in visited:
            if cog_name in chain:
                cycle = chain[chain.index(cog_name):] + [cog_name]
                raise CircularDependencyError(
                    f"Circular dependency detected: {' → '.join(cycle)}"
                )
            return []

        visited.add(cog_name)
        chain.append(cog_name)

        install_order = []
        dependencies = self.get_cog_dependencies(cog_name)

        for dep_name, version_req in dependencies.items():
            if not self.get_cog_path(dep_name):
                raise DependencyError(
                    f"Required dependency '{dep_name}' for cog '{cog_name}' not found in repository"
                )

            installed_cogs = self.list_installed_cogs(bot_path)
            if dep_name not in installed_cogs:
                dep_order = self.resolve_dependencies(dep_name, bot_path, visited, chain.copy())
                for dep in dep_order:
                    if dep not in install_order:
                        install_order.append(dep)
                if dep_name not in install_order:
                    install_order.append(dep_name)
            else:
                installed_info = self.get_installed_cog_info(bot_path, dep_name)
                installed_version = installed_info.get('version', '0.0.0') if installed_info else '0.0.0'
                if not version_satisfies(installed_version, version_req):
                    raise VersionMismatchError(
                        f"Cog '{cog_name}' requires {dep_name} {version_req}, "
                        f"but {installed_version} is installed"
                    )

        chain.pop()
        return install_order

    def check_missing_dependencies(self, bot_path: Path, cog_name: str) -> List[Tuple[str, str]]:
        """
        Check which dependencies are missing for a cog.

        Returns:
            List of (dependency_name, version_requirement) tuples for missing deps
        """
        dependencies = self.get_cog_dependencies(cog_name)
        installed_cogs = self.list_installed_cogs(bot_path)
        missing = []

        for dep_name, version_req in dependencies.items():
            if dep_name not in installed_cogs:
                missing.append((dep_name, version_req))

        return missing

    def install_cog(
        self,
        bot_path: Path,
        cog_name: str,
        auto_install_deps: bool = True,
        _installing_chain: Optional[Set[str]] = None
    ) -> bool:
        """
        Install a cog into a bot's cogs directory with dependency resolution.

        Args:
            bot_path: Path to the bot directory
            cog_name: Name of the cog to install
            auto_install_deps: If True, automatically install missing dependencies
            _installing_chain: Internal tracking for dependency installation

        Returns:
            True if successful, False otherwise
        """
        if _installing_chain is None:
            _installing_chain = set()

        # Get cog source path
        cog_source = self.get_cog_path(cog_name)
        if not cog_source:
            raise ValueError(f"Cog '{cog_name}' not found in repository")

        # Check if already installed
        bot_cogs_dir = bot_path / "cogs"
        cog_dest = bot_cogs_dir / cog_name
        if cog_dest.exists():
            if cog_name in _installing_chain:
                return True
            raise ValueError(f"Cog '{cog_name}' is already installed")

        # Resolve and install dependencies first
        if auto_install_deps:
            try:
                deps_to_install = self.resolve_dependencies(cog_name, bot_path)
                _installing_chain.add(cog_name)

                for dep_name in deps_to_install:
                    if dep_name not in self.list_installed_cogs(bot_path):
                        self.install_cog(bot_path, dep_name, auto_install_deps=True,
                                        _installing_chain=_installing_chain)
            except CircularDependencyError:
                raise
            except DependencyError as e:
                raise ValueError(str(e))

        # Ensure bot has cogs directory
        bot_cogs_dir.mkdir(exist_ok=True)

        # Create __init__.py in cogs directory if it doesn't exist
        cogs_init = bot_cogs_dir / "__init__.py"
        if not cogs_init.exists():
            cogs_init.write_text("# Cogs directory\n")

        # Discover cog structure and copy intelligently
        from multicord.utils.source_resolver import SourceResolver, discover_cog_structure

        cog_package_path, cog_metadata_path = discover_cog_structure(cog_source, cog_name)

        # Copy cog package
        SourceResolver.copy_source_files(cog_package_path, cog_dest)

        # Copy metadata if found
        if cog_metadata_path:
            import shutil
            shutil.copy2(cog_metadata_path, cog_dest / cog_metadata_path.name)

        # Install cog requirements if they exist
        requirements_file = cog_dest / "requirements.txt"
        if requirements_file.exists():
            self._install_requirements(requirements_file, bot_path)

        # Update bot's config if it exists
        self._update_bot_config(bot_path, cog_name, action='add')

        return True

    def remove_cog(self, bot_path: Path, cog_name: str) -> bool:
        """
        Remove a cog from a bot.

        Args:
            bot_path: Path to the bot directory
            cog_name: Name of the cog to remove

        Returns:
            True if successful, False otherwise
        """
        bot_cogs_dir = bot_path / "cogs"
        cog_path = bot_cogs_dir / cog_name

        if not cog_path.exists():
            raise ValueError(f"Cog '{cog_name}' is not installed")

        # Remove cog directory
        shutil.rmtree(cog_path)

        # Update bot's config
        self._update_bot_config(bot_path, cog_name, action='remove')

        return True

    def list_installed_cogs(self, bot_path: Path) -> List[str]:
        """
        List cogs installed in a bot.

        Args:
            bot_path: Path to the bot directory

        Returns:
            List of installed cog names
        """
        bot_cogs_dir = bot_path / "cogs"

        if not bot_cogs_dir.exists():
            return []

        installed = []
        for item in bot_cogs_dir.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                # Check if it has __init__.py (is a valid cog)
                if (item / "__init__.py").exists():
                    installed.append(item.name)

        return installed

    def get_installed_cog_info(self, bot_path: Path, cog_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an installed cog from its cog.json manifest.

        Args:
            bot_path: Path to the bot directory
            cog_name: Name of the cog

        Returns:
            Dictionary with cog information or None
        """
        bot_cogs_dir = bot_path / "cogs"
        cog_path = bot_cogs_dir / cog_name

        if not cog_path.exists():
            return None

        manifest_file = cog_path / "cog.json"
        if manifest_file.exists():
            with open(manifest_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        # No manifest found, return basic info
        return {
            "name": cog_name,
            "path": str(cog_path),
            "installed": True
        }

    def update_cog(self, bot_path: Path, cog_name: str) -> bool:
        """
        Update an installed cog to the latest version from repository.

        Args:
            bot_path: Path to the bot directory
            cog_name: Name of the cog to update

        Returns:
            True if successful, False otherwise
        """
        # Remove old version
        self.remove_cog(bot_path, cog_name)

        # Install new version
        self.install_cog(bot_path, cog_name)

        return True

    def _install_requirements(self, requirements_file: Path, bot_path: Path) -> None:
        """
        Install cog requirements into bot's isolated virtual environment.

        Args:
            requirements_file: Path to requirements.txt
            bot_path: Path to the bot directory

        Raises:
            RuntimeError: If venv is invalid or installation fails
        """
        # Validate bot's venv exists
        is_valid, venv_msg = self.venv_manager.validate_venv(bot_path)
        if not is_valid:
            raise RuntimeError(
                f"Bot venv invalid: {venv_msg}. "
                f"Create with: multicord venv install {bot_path.name}"
            )

        # Get bot's venv Python executable
        venv_python = self.venv_manager.get_venv_python(bot_path)

        # Get shared pip cache directory
        pip_cache_dir = self.venv_manager.pip_cache_dir

        try:
            # Install cog requirements into bot's isolated venv
            # Stream pip output in real-time so users see progress
            subprocess.run(
                [str(venv_python), "-m", "pip", "install",
                 "-r", str(requirements_file),
                 "--cache-dir", str(pip_cache_dir)],
                check=True,
                timeout=300,  # 5 minute safety timeout
                cwd=bot_path
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "Package installation timed out after 5 minutes. "
                f"Check network connection and try: multicord venv clean {bot_path.name}"
            )
        except subprocess.CalledProcessError:
            raise RuntimeError("Failed to install cog requirements. Check pip output above.")

    def _update_bot_config(self, bot_path: Path, cog_name: str, action: str) -> None:
        """
        Update bot's configuration to track installed cogs.

        Args:
            bot_path: Path to the bot directory
            cog_name: Name of the cog
            action: 'add' or 'remove'
        """
        config_file = bot_path / "config.toml"

        if not config_file.exists():
            return

        try:
            import tomli
            import tomli_w

            # Read current config
            with open(config_file, 'rb') as f:
                config = tomli.load(f)

            # Update cogs section
            if 'cogs' not in config:
                config['cogs'] = {'installed': []}

            if action == 'add':
                if cog_name not in config['cogs']['installed']:
                    config['cogs']['installed'].append(cog_name)
            elif action == 'remove':
                if cog_name in config['cogs']['installed']:
                    config['cogs']['installed'].remove(cog_name)

            # Write updated config
            with open(config_file, 'wb') as f:
                tomli_w.dump(config, f)

        except ImportError:
            # TOML libraries not available, skip config update
            pass
        except Exception:
            # Don't fail on config update errors
            pass
