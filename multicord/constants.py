"""
MultiCord CLI Constants.

Central registry for official built-in bots and cogs,
plus other configuration constants.
"""

import os
from typing import Dict

# Official built-in sources - always available without import
# These are auto-fetched on first use (lazy-fetch pattern)
OFFICIAL_REPOS: Dict[str, str] = {
    # Bot Sources
    'basic': 'https://github.com/HollowTheSilver/MultiCord-BasicTemplate',
    'advanced': 'https://github.com/HollowTheSilver/MultiCord-AdvancedTemplate',

    # Standalone Cogs
    'permissions': 'https://github.com/HollowTheSilver/MultiCord-PermissionsCog',
    'moderation': 'https://github.com/HollowTheSilver/MultiCord-ModerationCog',
    'music': 'https://github.com/HollowTheSilver/MultiCord-MusicCog',
}

# Categorize official sources by type for display purposes
OFFICIAL_BOTS = ['basic', 'advanced']
OFFICIAL_COGS = ['permissions', 'moderation', 'music']

# Directory structure
USER_REPOS_DIR = 'repos'         # ~/.multicord/repos/ (includes built-ins)
BOTS_DIR = 'bots'                # ~/.multicord/bots/

# Git operation defaults
DEFAULT_BRANCH = 'main'
CACHE_TTL_SECONDS = 3600  # 1 hour

# Manifest filenames
COLLECTION_MANIFEST = 'multicord.json'
BOT_MANIFEST = 'bot.json'
COG_MANIFEST = 'cog.json'
# Port configuration (with environment variable support)
DEFAULT_API_URL = os.getenv('MULTICORD_API_URL', 'http://localhost:8000')
OAUTH_CALLBACK_PORT = int(os.getenv('MULTICORD_OAUTH_PORT', '8899'))
BOT_PORT_START = int(os.getenv('MULTICORD_BOT_PORT_START', '8100'))
BOT_PORT_END = int(os.getenv('MULTICORD_BOT_PORT_END', '8200'))

# Standard bot file structure
BOT_ENTRY_FILE = 'bot.py'              # Main bot entry point
REQUIREMENTS_FILE = 'requirements.txt'  # Python dependencies
ENV_FILE = '.env'                       # Environment variables (runtime)
ENV_EXAMPLE_FILE = '.env.example'      # Environment template
CONFIG_FILE = 'config.toml'            # Bot configuration
META_FILE = '.multicord_meta.json'     # Bot metadata
LOG_DIR = 'logs'                        # Log directory
LOG_FILE = 'bot.log'                    # Default log filename
