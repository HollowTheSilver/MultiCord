"""
Virtual environment management for per-bot dependency isolation.
Provides centralized venv lifecycle operations including creation, validation,
and dependency installation with shared pip caching.
"""

import os
import sys
import venv
import subprocess
import shutil
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime


class VenvManager:
    """Manages isolated virtual environments for Discord bots."""

    def __init__(self, bots_dir: Optional[Path] = None):
        """
        Initialize venv manager with optional bots directory.

        Args:
            bots_dir: Path to bots directory. Defaults to ~/.multicord/bots
        """
        if bots_dir is None:
            bots_dir = Path.home() / ".multicord" / "bots"

        self.bots_dir = Path(bots_dir)
        self.pip_cache_dir = Path.home() / ".multicord" / "pip-cache"

        # Ensure directories exist
        self.bots_dir.mkdir(parents=True, exist_ok=True)
        self.pip_cache_dir.mkdir(parents=True, exist_ok=True)

    def create_venv(self, bot_dir: Path) -> Tuple[bool, str]:
        """
        Create isolated virtual environment for a bot.

        Args:
            bot_dir: Path to bot directory

        Returns:
            Tuple of (success, message)
        """
        venv_dir = bot_dir / ".venv"

        if venv_dir.exists():
            return False, f"Virtual environment already exists at {venv_dir}"

        try:
            # Create venv with pip
            venv.create(venv_dir, with_pip=True, clear=False)

            # Upgrade pip to latest version
            venv_python = self.get_venv_python(bot_dir)
            if not venv_python.exists():
                return False, f"Failed to create venv: Python executable not found"

            # Upgrade pip, setuptools, and wheel
            # Stream output so users see progress
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "--upgrade",
                 "pip", "setuptools", "wheel"],
                check=True,
                timeout=300  # 5 minute safety timeout
            )

            return True, f"Created virtual environment at {venv_dir}"

        except subprocess.TimeoutExpired:
            return False, "Pip upgrade timed out after 5 minutes. Check network connection."
        except subprocess.CalledProcessError:
            return False, "Failed to upgrade pip. Check output above."
        except Exception as e:
            return False, f"Failed to create virtual environment: {str(e)}"

    def validate_venv(self, bot_dir: Path) -> Tuple[bool, str]:
        """
        Validate that a bot's virtual environment exists and is functional.

        Args:
            bot_dir: Path to bot directory

        Returns:
            Tuple of (is_valid, message)
        """
        venv_dir = bot_dir / ".venv"

        if not venv_dir.exists():
            return False, f"Virtual environment not found at {venv_dir}"

        # Check for Python executable
        venv_python = self.get_venv_python(bot_dir)
        if not venv_python.exists():
            return False, f"Python executable not found at {venv_python}"

        # Test Python executable
        try:
            result = subprocess.run(
                [str(venv_python), "--version"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            python_version = result.stdout.strip()
            return True, f"Valid venv with {python_version}"

        except subprocess.CalledProcessError:
            return False, "Python executable exists but is not functional"
        except subprocess.TimeoutExpired:
            return False, "Python executable check timed out"
        except Exception as e:
            return False, f"Validation failed: {str(e)}"

    def get_venv_python(self, bot_dir: Path) -> Path:
        """
        Get path to bot's venv Python executable (cross-platform).

        Args:
            bot_dir: Path to bot directory

        Returns:
            Path to Python executable in bot's venv
        """
        venv_dir = bot_dir / ".venv"

        if os.name == 'nt':
            # Windows: .venv/Scripts/python.exe
            return venv_dir / "Scripts" / "python.exe"
        else:
            # Unix-like (Linux, macOS): .venv/bin/python
            return venv_dir / "bin" / "python"

    def get_venv_pip(self, bot_dir: Path) -> Path:
        """
        Get path to bot's venv pip executable (cross-platform).

        Args:
            bot_dir: Path to bot directory

        Returns:
            Path to pip executable in bot's venv
        """
        venv_dir = bot_dir / ".venv"

        if os.name == 'nt':
            # Windows: .venv/Scripts/pip.exe
            return venv_dir / "Scripts" / "pip.exe"
        else:
            # Unix-like: .venv/bin/pip
            return venv_dir / "bin" / "pip"

    def install_requirements(self, bot_dir: Path, upgrade: bool = False) -> Tuple[bool, str]:
        """
        Install requirements.txt into bot's virtual environment.

        Args:
            bot_dir: Path to bot directory
            upgrade: Whether to upgrade existing packages

        Returns:
            Tuple of (success, message)
        """
        requirements_file = bot_dir / "requirements.txt"

        if not requirements_file.exists():
            return False, f"requirements.txt not found at {requirements_file}"

        # Validate venv exists
        is_valid, msg = self.validate_venv(bot_dir)
        if not is_valid:
            return False, f"Invalid venv: {msg}"

        venv_python = self.get_venv_python(bot_dir)

        try:
            # Build pip install command
            cmd = [
                str(venv_python), "-m", "pip", "install",
                "-r", str(requirements_file),
                "--cache-dir", str(self.pip_cache_dir)
            ]

            if upgrade:
                cmd.append("--upgrade")

            # Install dependencies
            # Stream output so users see progress
            result = subprocess.run(
                cmd,
                check=True,
                timeout=300,  # 5 minute safety timeout
                cwd=bot_dir
            )

            return True, "Successfully installed requirements"

        except subprocess.TimeoutExpired:
            return False, "Installation timed out after 5 minutes. Check network connection."
        except subprocess.CalledProcessError:
            return False, "Failed to install requirements. Check pip output above."
        except Exception as e:
            return False, f"Installation failed: {str(e)}"

    def clean_venv(self, bot_dir: Path) -> Tuple[bool, str]:
        """
        Remove and recreate bot's virtual environment from scratch.

        Args:
            bot_dir: Path to bot directory

        Returns:
            Tuple of (success, message)
        """
        venv_dir = bot_dir / ".venv"

        if not venv_dir.exists():
            return False, f"No virtual environment found at {venv_dir}"

        try:
            # Remove existing venv
            shutil.rmtree(venv_dir)

            # Recreate venv
            success, msg = self.create_venv(bot_dir)
            if not success:
                return False, f"Failed to recreate venv: {msg}"

            # Reinstall requirements if they exist
            requirements_file = bot_dir / "requirements.txt"
            if requirements_file.exists():
                success, msg = self.install_requirements(bot_dir)
                if not success:
                    return False, f"Venv recreated but requirements installation failed: {msg}"
                return True, "Virtual environment cleaned and requirements reinstalled"

            return True, "Virtual environment cleaned successfully"

        except Exception as e:
            return False, f"Failed to clean venv: {str(e)}"

    def update_venv(self, bot_dir: Path) -> Tuple[bool, str]:
        """
        Upgrade all packages in bot's virtual environment to latest versions.

        Args:
            bot_dir: Path to bot directory

        Returns:
            Tuple of (success, message)
        """
        # Validate venv exists
        is_valid, msg = self.validate_venv(bot_dir)
        if not is_valid:
            return False, f"Invalid venv: {msg}"

        venv_python = self.get_venv_python(bot_dir)

        try:
            # Get list of installed packages
            result = subprocess.run(
                [str(venv_python), "-m", "pip", "list", "--format=json"],
                check=True,
                capture_output=True,
                text=True
            )

            packages = json.loads(result.stdout)
            package_names = [pkg['name'] for pkg in packages
                           if pkg['name'] not in ['pip', 'setuptools', 'wheel']]

            if not package_names:
                return True, "No packages to update"

            # Update all packages
            # Stream output so users see progress
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "--upgrade",
                 "--cache-dir", str(self.pip_cache_dir)] + package_names,
                check=True,
                timeout=300  # 5 minute safety timeout
            )

            return True, f"Updated {len(package_names)} packages"

        except subprocess.TimeoutExpired:
            return False, "Package update timed out after 5 minutes. Check network connection."
        except subprocess.CalledProcessError:
            return False, "Failed to update packages. Check pip output above."
        except json.JSONDecodeError:
            return False, "Failed to parse package list"
        except Exception as e:
            return False, f"Update failed: {str(e)}"

    def get_venv_info(self, bot_dir: Path) -> Optional[Dict]:
        """
        Get information about bot's virtual environment.

        Args:
            bot_dir: Path to bot directory

        Returns:
            Dictionary with venv info, or None if invalid
        """
        is_valid, msg = self.validate_venv(bot_dir)
        if not is_valid:
            return None

        venv_dir = bot_dir / ".venv"
        venv_python = self.get_venv_python(bot_dir)

        info = {
            'bot_name': bot_dir.name,
            'venv_path': str(venv_dir),
            'python_path': str(venv_python),
            'exists': True,
            'valid': True
        }

        try:
            # Get Python version
            result = subprocess.run(
                [str(venv_python), "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            info['python_version'] = result.stdout.strip()

            # Get installed packages
            result = subprocess.run(
                [str(venv_python), "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                check=True
            )
            packages = json.loads(result.stdout)
            info['package_count'] = len(packages)
            info['packages'] = packages

            # Get disk usage
            total_size = sum(
                f.stat().st_size for f in venv_dir.rglob('*') if f.is_file()
            )
            info['disk_usage_mb'] = round(total_size / (1024 * 1024), 2)

        except Exception as e:
            info['error'] = str(e)

        return info

    def list_all_venvs(self) -> List[Dict]:
        """
        List all bot virtual environments.

        Returns:
            List of venv info dictionaries
        """
        venvs = []

        if not self.bots_dir.exists():
            return venvs

        for bot_dir in self.bots_dir.iterdir():
            if not bot_dir.is_dir():
                continue

            venv_dir = bot_dir / ".venv"
            is_valid, msg = self.validate_venv(bot_dir)

            venv_info = {
                'bot_name': bot_dir.name,
                'venv_path': str(venv_dir),
                'exists': venv_dir.exists(),
                'valid': is_valid,
                'message': msg
            }

            if is_valid:
                detailed_info = self.get_venv_info(bot_dir)
                if detailed_info:
                    venv_info.update(detailed_info)

            venvs.append(venv_info)

        return venvs

    def get_cache_info(self) -> Dict:
        """
        Get information about shared pip cache.

        Returns:
            Dictionary with cache statistics
        """
        if not self.pip_cache_dir.exists():
            return {
                'cache_dir': str(self.pip_cache_dir),
                'exists': False,
                'size_mb': 0,
                'file_count': 0
            }

        try:
            # Calculate total cache size
            total_size = sum(
                f.stat().st_size for f in self.pip_cache_dir.rglob('*') if f.is_file()
            )

            # Count files
            file_count = sum(1 for f in self.pip_cache_dir.rglob('*') if f.is_file())

            return {
                'cache_dir': str(self.pip_cache_dir),
                'exists': True,
                'size_mb': round(total_size / (1024 * 1024), 2),
                'file_count': file_count
            }

        except Exception as e:
            return {
                'cache_dir': str(self.pip_cache_dir),
                'exists': True,
                'error': str(e)
            }

    def clear_cache(self) -> Tuple[bool, str]:
        """
        Clear shared pip cache directory.

        Returns:
            Tuple of (success, message)
        """
        if not self.pip_cache_dir.exists():
            return True, "Cache directory does not exist"

        try:
            shutil.rmtree(self.pip_cache_dir)
            self.pip_cache_dir.mkdir(parents=True, exist_ok=True)
            return True, "Cache cleared successfully"

        except Exception as e:
            return False, f"Failed to clear cache: {str(e)}"
