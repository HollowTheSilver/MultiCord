"""
MultiCord CLI Constants.

Central registry for official built-in templates and cogs,
plus other configuration constants.
"""

from typing import Dict

# Official built-in sources - always available without import
# These are auto-fetched on first use (lazy-fetch pattern)
OFFICIAL_REPOS: Dict[str, str] = {
    # Templates
    'basic': 'https://github.com/HollowTheSilver/MultiCord-BasicTemplate',
    'advanced': 'https://github.com/HollowTheSilver/MultiCord-AdvancedTemplate',

    # Standalone Cogs
    'permissions': 'https://github.com/HollowTheSilver/MultiCord-PermissionsCog',
    'moderation': 'https://github.com/HollowTheSilver/MultiCord-ModerationCog',
    'music': 'https://github.com/HollowTheSilver/MultiCord-MusicCog',
}

# Categorize official sources by type for display purposes
OFFICIAL_TEMPLATES = ['basic', 'advanced']
OFFICIAL_COGS = ['permissions', 'moderation', 'music']

# Cache directory structure
OFFICIAL_CACHE_DIR = 'official'  # ~/.multicord/official/
USER_REPOS_DIR = 'repos'         # ~/.multicord/repos/
BOTS_DIR = 'bots'                # ~/.multicord/bots/

# Git operation defaults
DEFAULT_BRANCH = 'main'
CACHE_TTL_SECONDS = 3600  # 1 hour

# Manifest filenames (v3.0)
COLLECTION_MANIFEST = 'multicord.json'
TEMPLATE_MANIFEST = 'template.json'
COG_MANIFEST = 'cog.json'
LEGACY_MANIFEST = 'manifest.json'
