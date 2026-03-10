"""
Bot structure detection and validation.

Resolves Discord.py bot entry points using a manifest-first strategy:
manifest/metadata declaration → convention-based scanning → error.
"""

import json
from pathlib import Path
from typing import Optional, Tuple, List
from multicord.constants import BOT_ENTRY_FILE, META_FILE, BOT_MANIFEST

# Standard entry point filenames in priority order
ENTRY_POINT_CANDIDATES = [
    BOT_ENTRY_FILE,  # bot.py (standard)
    'main.py',       # Common alternative
    'run.py',        # Another common pattern
    '__main__.py',   # Python module pattern
]


def detect_entry_point(bot_path: Path) -> str:
    """
    Detect the bot's entry point file.

    Resolution order (manifest-first, like package.json → main):
    1. Stored metadata (.multicord_meta.json entry_point field)
    2. Bot manifest (bot.json entry_point field)
    3. Convention-based scanning of known filenames with Discord.py validation

    Args:
        bot_path: Path to bot directory

    Returns:
        Entry point filename (e.g., 'bot.py', 'main.py')

    Raises:
        ValueError: If no valid entry point found
    """
    # 1. Check stored metadata (already-detected entry point)
    entry = _read_manifest_entry_point(bot_path / META_FILE)
    if entry and (bot_path / entry).exists():
        return entry

    # 2. Check bot manifest declaration
    entry = _read_manifest_entry_point(bot_path / BOT_MANIFEST)
    if entry and (bot_path / entry).exists():
        return entry

    # 3. Convention-based fallback with Discord.py content validation
    for candidate in ENTRY_POINT_CANDIDATES:
        entry_file = bot_path / candidate
        if entry_file.exists() and _is_valid_entry_point(entry_file):
            return candidate

    raise ValueError(
        f"No recognized Discord bot entry point found in {bot_path}.\n"
        f"Expected one of: {', '.join(ENTRY_POINT_CANDIDATES)}\n"
        f"Each file should contain Discord.py bot initialization code.\n"
        f"Tip: declare 'entry_point' in bot.json to use a custom filename."
    )


def _read_manifest_entry_point(manifest_path: Path) -> Optional[str]:
    """Read entry_point field from a JSON manifest file."""
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, encoding='utf-8') as f:
            data = json.load(f)
        return data.get("entry_point")
    except (json.JSONDecodeError, IOError, KeyError):
        return None


def _is_valid_entry_point(file_path: Path) -> bool:
    """
    Check if file looks like a valid Discord bot entry point.

    Args:
        file_path: Path to potential entry point file

    Returns:
        True if file contains Discord bot indicators
    """
    try:
        content = file_path.read_text(encoding='utf-8')
    except (IOError, UnicodeDecodeError):
        return False

    # Look for Discord.py indicators
    discord_indicators = [
        'discord.Client',
        'commands.Bot',
        'discord.ext',
        'from discord',
        'import discord',
        '@bot.',
        '@client.',
        'client.run(',
        'bot.run(',
    ]

    return any(indicator in content for indicator in discord_indicators)


def validate_bot_structure(bot_path: Path) -> Tuple[bool, List[str]]:
    """
    Validate bot directory has minimum required structure.

    Args:
        bot_path: Path to bot directory

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    from multicord.constants import REQUIREMENTS_FILE

    issues = []

    # Check if directory exists
    if not bot_path.exists():
        return False, ["Directory does not exist"]

    if not bot_path.is_dir():
        return False, ["Path is not a directory"]

    # Check for entry point
    try:
        detect_entry_point(bot_path)
    except ValueError as e:
        issues.append(str(e))

    # Check for requirements.txt (warning, not error)
    if not (bot_path / REQUIREMENTS_FILE).exists():
        issues.append(f"Warning: No {REQUIREMENTS_FILE} found (dependencies may not install)")

    return (len(issues) == 0, issues)


def get_bot_info(bot_path: Path) -> dict:
    """
    Extract basic information about a bot.

    Args:
        bot_path: Path to bot directory

    Returns:
        Dictionary with bot information
    """
    from multicord.constants import REQUIREMENTS_FILE, CONFIG_FILE, ENV_FILE

    info = {
        'path': str(bot_path),
        'name': bot_path.name,
        'has_entry_point': False,
        'entry_point': None,
        'has_requirements': False,
        'has_config': False,
        'has_env': False,
    }

    try:
        info['entry_point'] = detect_entry_point(bot_path)
        info['has_entry_point'] = True
    except ValueError:
        pass

    info['has_requirements'] = (bot_path / REQUIREMENTS_FILE).exists()
    info['has_config'] = (bot_path / CONFIG_FILE).exists()
    info['has_env'] = (bot_path / ENV_FILE).exists()

    return info
