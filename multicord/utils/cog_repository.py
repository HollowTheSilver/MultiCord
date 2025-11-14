"""
Cog repository management for MultiCord CLI.
Handles downloading and managing optional bot cogs from Git repositories.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any


class CogRepository:
    """Manages cog repositories and installations."""

    def __init__(self, template_repo_path: Path):
        """
        Initialize cog repository manager.

        Args:
            template_repo_path: Path to the cloned template repository
        """
        self.template_repo_path = template_repo_path
        self.cogs_dir = template_repo_path / "cogs"
        self.manifest_path = template_repo_path / "manifest.json"

    def list_available_cogs(self) -> Dict[str, Dict[str, Any]]:
        """
        List all available cogs from the repository.

        Returns:
            Dictionary of cog metadata keyed by cog ID
        """
        if not self.manifest_path.exists():
            return {}

        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        return manifest.get('cogs', {})

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

        if cog_path.exists() and cog_path.is_dir():
            return cog_path

        return None

    def install_cog(self, bot_path: Path, cog_name: str) -> bool:
        """
        Install a cog into a bot's cogs directory.

        Args:
            bot_path: Path to the bot directory
            cog_name: Name of the cog to install

        Returns:
            True if successful, False otherwise
        """
        # Get cog source path
        cog_source = self.get_cog_path(cog_name)
        if not cog_source:
            raise ValueError(f"Cog '{cog_name}' not found in repository")

        # Ensure bot has cogs directory
        bot_cogs_dir = bot_path / "cogs"
        bot_cogs_dir.mkdir(exist_ok=True)

        # Create __init__.py in cogs directory if it doesn't exist
        cogs_init = bot_cogs_dir / "__init__.py"
        if not cogs_init.exists():
            cogs_init.write_text("# Cogs directory\n")

        # Copy cog to bot's cogs directory
        cog_dest = bot_cogs_dir / cog_name

        if cog_dest.exists():
            raise ValueError(f"Cog '{cog_name}' is already installed")

        shutil.copytree(cog_source, cog_dest)

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
        Get information about an installed cog.

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

        # Try to load manifest from installed cog
        manifest_file = cog_path / "manifest.json"
        if manifest_file.exists():
            with open(manifest_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Fallback to basic info
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
        Install cog requirements using pip.

        Args:
            requirements_file: Path to requirements.txt
            bot_path: Path to the bot directory
        """
        try:
            # Use the virtual environment if it exists
            venv_python = bot_path / ".venv" / "Scripts" / "python.exe"
            if not venv_python.exists():
                venv_python = bot_path / ".venv" / "bin" / "python"

            if venv_python.exists():
                python_cmd = str(venv_python)
            else:
                python_cmd = "python"

            subprocess.run(
                [python_cmd, "-m", "pip", "install", "-r", str(requirements_file)],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            # Log warning but don't fail the installation
            print(f"Warning: Failed to install cog requirements: {e.stderr}")

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
