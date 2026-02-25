"""
Auto-generation of manifests for Discord.py bots.

Enables importing any Discord.py bot by automatically detecting structure
and generating appropriate bot.json and cog.json manifests.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import ast


class BotStructureAnalyzer:
    """
    Analyzes Discord.py bot structure and generates metadata.

    Detects:
    - Main bot file (bot.py, main.py, __main__.py)
    - Cogs directory and individual cogs
    - requirements.txt dependencies
    - Discord.py version
    - Python version (from code hints or requirements.txt)
    """

    def __init__(self, bot_path: Path):
        """
        Initialize analyzer.

        Args:
            bot_path: Path to Discord.py bot directory
        """
        self.bot_path = Path(bot_path)

    def find_main_file(self) -> Optional[Path]:
        """
        Find the main bot file.

        Looks for (in order):
        1. bot.py
        2. main.py
        3. __main__.py
        4. First .py file with Bot/AutoShardedBot class

        Returns:
            Path to main file, or None if not found
        """
        # Try common names first
        for name in ["bot.py", "main.py", "__main__.py"]:
            path = self.bot_path / name
            if path.exists():
                return path

        # Search for file with Bot class
        for py_file in self.bot_path.glob("*.py"):
            if self._contains_bot_class(py_file):
                return py_file

        return None

    def _contains_bot_class(self, file_path: Path) -> bool:
        """
        Check if file contains discord Bot/AutoShardedBot class.

        Args:
            file_path: Path to Python file

        Returns:
            True if file contains Bot class instantiation
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Look for Bot/AutoShardedBot instantiation
            patterns = [
                r'commands\.Bot\(',
                r'commands\.AutoShardedBot\(',
                r'Bot\(',
                r'AutoShardedBot\(',
            ]

            return any(re.search(pattern, content) for pattern in patterns)

        except Exception:
            return False

    def find_cogs_directory(self) -> Optional[Path]:
        """
        Find the cogs directory.

        Returns:
            Path to cogs directory, or None if not found
        """
        cogs_dir = self.bot_path / "cogs"
        if cogs_dir.exists() and cogs_dir.is_dir():
            return cogs_dir

        # Check for alternative names
        for name in ["extensions", "ext", "plugins"]:
            alt_dir = self.bot_path / name
            if alt_dir.exists() and alt_dir.is_dir():
                return alt_dir

        return None

    def detect_cogs(self) -> List[str]:
        """
        Detect individual cogs in cogs directory.

        Returns:
            List of cog names (directory or file names without .py)
        """
        cogs_dir = self.find_cogs_directory()
        if not cogs_dir:
            return []

        cogs = []

        # Check for cog directories (with __init__.py)
        for item in cogs_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                cogs.append(item.name)

        # Check for standalone cog files
        for py_file in cogs_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            if self._is_cog_file(py_file):
                cogs.append(py_file.stem)

        return sorted(cogs)

    def _is_cog_file(self, file_path: Path) -> bool:
        """
        Check if file is a Discord.py cog.

        Args:
            file_path: Path to Python file

        Returns:
            True if file contains Cog class
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Look for Cog class definition
            patterns = [
                r'class\s+\w+\(commands\.Cog\)',
                r'class\s+\w+\(Cog\)',
            ]

            return any(re.search(pattern, content) for pattern in patterns)

        except Exception:
            return False

    def parse_requirements_txt(self) -> Dict[str, Any]:
        """
        Parse requirements.txt for dependency information.

        Returns:
            Dict with discord_py_version, python_version, and other dependencies
        """
        req_path = self.bot_path / "requirements.txt"
        if not req_path.exists():
            return {
                "discord_py_version": ">=2.0.0",
                "python_version": ">=3.9",
                "dependencies": []
            }

        try:
            with open(req_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            discord_version = ">=2.0.0"
            python_version = ">=3.9"
            dependencies = []

            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Extract discord.py version
                if line.startswith('discord.py') or line.startswith('discord'):
                    match = re.search(r'[><=~]+[\d.]+', line)
                    if match:
                        discord_version = match.group()

                # Extract Python version from comments
                if 'python_requires' in line.lower():
                    match = re.search(r'[><=~]+[\d.]+', line)
                    if match:
                        python_version = match.group()

                dependencies.append(line)

            return {
                "discord_py_version": discord_version,
                "python_version": python_version,
                "dependencies": dependencies
            }

        except Exception:
            return {
                "discord_py_version": ">=2.0.0",
                "python_version": ">=3.9",
                "dependencies": []
            }

    def detect_features(self) -> Dict[str, bool]:
        """
        Detect bot features from code analysis.

        Returns:
            Dict of feature flags
        """
        features = {
            "slash_commands": False,
            "prefix_commands": False,
            "voice_support": False,
            "database": False,
        }

        main_file = self.find_main_file()
        if not main_file:
            return features

        try:
            with open(main_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Detect slash commands
            if 'app_commands' in content or '@tree.command' in content:
                features["slash_commands"] = True

            # Detect prefix commands
            if '@bot.command' in content or '@commands.command' in content:
                features["prefix_commands"] = True

            # Detect voice support
            if 'VoiceClient' in content or 'voice_client' in content:
                features["voice_support"] = True

            # Detect database usage
            db_patterns = ['sqlite3', 'psycopg', 'pymongo', 'aiosqlite', 'motor']
            if any(pattern in content for pattern in db_patterns):
                features["database"] = True

        except Exception:
            pass

        return features


class ManifestGenerator:
    """
    Generates manifests for Discord.py bots.

    Creates bot.json and cog.json files based on bot structure analysis.
    """

    def __init__(self):
        """Initialize manifest generator."""
        self.analyzer_class = BotStructureAnalyzer

    def generate_template_manifest(
        self,
        bot_path: Path,
        template_id: Optional[str] = None,
        **overrides
    ) -> Dict[str, Any]:
        """
        Generate bot.json manifest for a Discord.py bot.

        Args:
            bot_path: Path to bot directory
            template_id: Custom bot ID (defaults to directory name)
            **overrides: Manual overrides for manifest fields

        Returns:
            Generated template manifest dict
        """
        analyzer = self.analyzer_class(bot_path)

        # Generate template ID
        if template_id is None:
            template_id = bot_path.name.lower().replace(' ', '-')

        # Analyze structure
        main_file = analyzer.find_main_file()
        cogs_dir = analyzer.find_cogs_directory()
        req_info = analyzer.parse_requirements_txt()
        features = analyzer.detect_features()

        # Detect files
        files = []
        for pattern in ["*.py", "*.toml", "*.txt", ".env.example", ".gitignore", "README.md"]:
            for file in bot_path.glob(pattern):
                if file.is_file():
                    files.append(file.name)

        if cogs_dir:
            files.append("cogs/")

        # Build manifest
        manifest = {
            "$schema": "https://multicord.io/schemas/template.schema.json",
            "type": "template",
            "id": template_id,
            "name": overrides.get("name", bot_path.name.title()),
            "description": overrides.get(
                "description",
                f"Imported Discord.py bot: {bot_path.name}"
            ),
            "version": overrides.get("version", "1.0.0"),
            "author": overrides.get("author", "Unknown"),
            "category": overrides.get("category", "general"),
            "tags": overrides.get("tags", ["imported", "discord.py"]),
            "discord_py_version": req_info["discord_py_version"],
            "python_version": req_info["python_version"],
            "files": sorted(files),
            "features": features,
            "compatibility": {
                "multicord_version": ">=3.0.0",
                "platforms": ["windows", "linux", "macos"]
            }
        }

        # Add cog dependencies if cogs detected
        cogs = analyzer.detect_cogs()
        if cogs:
            manifest["requires_cogs"] = [
                f"{cog}@>=1.0.0" for cog in cogs
            ]

        # Apply manual overrides
        manifest.update(overrides)

        return manifest

    def generate_cog_manifest(
        self,
        cog_path: Path,
        cog_id: Optional[str] = None,
        **overrides
    ) -> Dict[str, Any]:
        """
        Generate cog.json manifest for a Discord.py cog.

        Args:
            cog_path: Path to cog directory (or file)
            cog_id: Custom cog ID (defaults to directory/file name)
            **overrides: Manual overrides for manifest fields

        Returns:
            Generated cog manifest dict
        """
        # Generate cog ID
        if cog_id is None:
            cog_id = cog_path.stem if cog_path.is_file() else cog_path.name
            cog_id = cog_id.lower().replace(' ', '-')

        # Detect files
        files = []
        if cog_path.is_dir():
            for pattern in ["*.py", "*.txt", "*.md", "*.json"]:
                for file in cog_path.glob(pattern):
                    if file.is_file():
                        files.append(file.name)
        else:
            files.append(cog_path.name)

        # Build manifest
        manifest = {
            "$schema": "https://multicord.io/schemas/cog.schema.json",
            "type": "cog",
            "id": cog_id,
            "name": overrides.get("name", cog_id.replace('-', ' ').title()),
            "description": overrides.get(
                "description",
                f"Imported Discord.py cog: {cog_id}"
            ),
            "version": overrides.get("version", "1.0.0"),
            "author": overrides.get("author", "Unknown"),
            "category": overrides.get("category", "utility"),
            "tags": overrides.get("tags", ["imported", "cog"]),
            "discord_py_version": ">=2.0.0",
            "python_version": ">=3.9",
            "database_required": False,
            "database_optional": False,
            "files": sorted(files),
            "dependencies": {},
            "optional_dependencies": {},
            "compatibility": {
                "multicord_version": ">=3.0.0",
                "platforms": ["windows", "linux", "macos"]
            }
        }

        # Apply manual overrides
        manifest.update(overrides)

        return manifest

    def save_manifest(
        self,
        manifest: Dict[str, Any],
        output_path: Path
    ) -> None:
        """
        Save manifest to JSON file.

        Args:
            manifest: Manifest dict
            output_path: Path to output file (bot.json or cog.json)
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
