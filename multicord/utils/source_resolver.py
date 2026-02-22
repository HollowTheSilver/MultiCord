"""
Source Resolver for MultiCord CLI.

Implements the lazy-fetch pattern for official built-in sources
and resolution of user-imported Git repositories.
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from multicord.constants import (
    OFFICIAL_REPOS,
    OFFICIAL_TEMPLATES,
    OFFICIAL_COGS,
    OFFICIAL_CACHE_DIR,
    USER_REPOS_DIR,
    DEFAULT_BRANCH,
    CACHE_TTL_SECONDS,
    TEMPLATE_MANIFEST,
    COG_MANIFEST,
    LEGACY_MANIFEST,
)
from multicord.utils.display import Display
from multicord.utils.validation import validate_git_url

display = Display()


class SourceResolver:
    """
    Resolves source names to local paths, auto-fetching official sources on first use.

    Sources can be:
    1. Official built-ins (auto-fetched from GitHub on first use)
    2. User-imported Git repos (tracked in repos.json)
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path.home() / '.multicord'
        self.official_dir = self.base_dir / OFFICIAL_CACHE_DIR
        self.repos_dir = self.base_dir / USER_REPOS_DIR
        self.repos_config_file = self.base_dir / 'config' / 'repos.json'

        # Ensure directories exist
        self.official_dir.mkdir(parents=True, exist_ok=True)
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        self.repos_config_file.parent.mkdir(parents=True, exist_ok=True)

    def resolve_source(self, name: str, force_update: bool = False) -> Path:
        """
        Resolve a source name to a local path, fetching if needed.

        Args:
            name: Source name (e.g., 'basic', 'permissions', 'my-custom-repo')
            force_update: Force Git pull even if cache is fresh

        Returns:
            Path to the local source directory

        Raises:
            SystemExit: If source not found
        """
        # 1. Check official built-ins (always available)
        if name in OFFICIAL_REPOS:
            return self._ensure_official_source(name, force_update)

        # 2. Check user's imported Git repos
        user_repos = self._load_user_repos()
        if name in user_repos:
            repo_info = user_repos[name]
            return Path(repo_info['path'])

        # 3. Not found - show helpful error
        self._show_not_found_error(name)
        sys.exit(1)

    def _ensure_official_source(self, name: str, force_update: bool = False) -> Path:
        """Ensure official source is available locally, fetching if needed."""
        cache_path = self.official_dir / name
        git_url = OFFICIAL_REPOS[name]

        if not cache_path.exists():
            # First use - auto-fetch
            display.info(f"Fetching official '{name}'...")
            self._git_clone(git_url, cache_path)
            self._update_cache_timestamp(name)
            display.success(f"Official '{name}' ready")
        elif force_update or self._is_cache_stale(name):
            # Update if stale or forced
            display.info(f"Updating official '{name}'...")
            self._git_pull(cache_path)
            self._update_cache_timestamp(name)

        return cache_path

    def _git_clone(self, url: str, dest: Path):
        """Clone a Git repository."""
        from multicord.utils.git_operations import GitRepository, GitOperationConfig

        config = GitOperationConfig.from_env()
        git_repo = GitRepository(url, dest, DEFAULT_BRANCH, config)
        git_repo.ensure_repository(force_update=False)

    def _git_pull(self, repo_path: Path):
        """Pull latest changes for a repository."""
        from multicord.utils.git_operations import GitRepository, GitOperationConfig

        # Determine the remote URL from git config
        import subprocess
        result = subprocess.run(
            ['git', 'config', '--get', 'remote.origin.url'],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        url = result.stdout.strip() if result.returncode == 0 else ''

        config = GitOperationConfig.from_env()
        git_repo = GitRepository(url, repo_path, DEFAULT_BRANCH, config)
        git_repo.ensure_repository(force_update=True)

    def _is_cache_stale(self, name: str) -> bool:
        """Check if cached source needs updating based on TTL."""
        cache_info = self._load_cache_info()
        if name not in cache_info:
            return True

        last_updated = cache_info[name].get('last_updated')
        if not last_updated:
            return True

        try:
            updated_dt = datetime.fromisoformat(last_updated)
            age_seconds = (datetime.now() - updated_dt).total_seconds()
            return age_seconds > CACHE_TTL_SECONDS
        except (ValueError, TypeError):
            return True

    def _update_cache_timestamp(self, name: str):
        """Update the cache timestamp for a source."""
        cache_info = self._load_cache_info()
        cache_info[name] = {
            'last_updated': datetime.now().isoformat(),
            'url': OFFICIAL_REPOS.get(name, '')
        }
        self._save_cache_info(cache_info)

    def _load_cache_info(self) -> Dict[str, Any]:
        """Load official cache metadata."""
        cache_file = self.base_dir / 'config' / 'official_cache.json'
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache_info(self, cache_info: Dict[str, Any]):
        """Save official cache metadata."""
        cache_file = self.base_dir / 'config' / 'official_cache.json'
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache_info, indent=2))

    def _load_user_repos(self) -> Dict[str, Any]:
        """Load user-imported repository configuration."""
        if self.repos_config_file.exists():
            try:
                return json.loads(self.repos_config_file.read_text())
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_user_repos(self, repos: Dict[str, Any]):
        """Save user-imported repository configuration."""
        self.repos_config_file.parent.mkdir(parents=True, exist_ok=True)
        self.repos_config_file.write_text(json.dumps(repos, indent=2))

    def _show_not_found_error(self, name: str):
        """Show helpful error message when source not found."""
        display.error(f"Unknown source: '{name}'")

        # Show available built-ins
        display.info("Available built-in templates: " + ", ".join(OFFICIAL_TEMPLATES))
        display.info("Available built-in cogs: " + ", ".join(OFFICIAL_COGS))

        # Show user repos if any
        user_repos = self._load_user_repos()
        if user_repos:
            display.info("Your imported repos: " + ", ".join(user_repos.keys()))

        display.info("To import a Git repo: multicord repo import <git-url> --as <name>")

    def import_repo(self, git_url: str, name: str, description: str = "") -> Path:
        """
        Import a Git repository as a reusable source.

        Args:
            git_url: Git repository URL
            name: Local name for the repository
            description: Optional description

        Returns:
            Path to the cloned repository
        """
        # Validate Git URL
        is_valid, error = validate_git_url(git_url)
        if not is_valid:
            raise ValueError(f"Invalid Git URL: {error}")

        # Validate not overwriting built-in
        if name in OFFICIAL_REPOS:
            raise ValueError(f"Cannot use name '{name}' - it's a built-in source")

        # Check if already exists
        user_repos = self._load_user_repos()
        if name in user_repos:
            raise ValueError(f"Repository '{name}' already exists. Use 'repo remove' first.")

        # Clone to repos directory
        repo_path = self.repos_dir / name
        display.info(f"Cloning '{git_url}' as '{name}'...")
        self._git_clone(git_url, repo_path)

        # Detect type
        source_type = self._detect_source_type(repo_path)

        # Save to config
        user_repos[name] = {
            'url': git_url,
            'path': str(repo_path),
            'type': source_type,
            'description': description,
            'imported_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat()
        }
        self._save_user_repos(user_repos)

        display.success(f"Imported '{name}' ({source_type})")
        return repo_path

    def _detect_source_type(self, path: Path) -> str:
        """Detect whether a source is a template or cog."""
        # Check for cog.json (v3.0 cog)
        if (path / COG_MANIFEST).exists():
            return 'cog'

        # Check for template.json (v3.0 template)
        if (path / TEMPLATE_MANIFEST).exists():
            return 'template'

        # Check legacy manifest.json
        legacy_manifest = path / LEGACY_MANIFEST
        if legacy_manifest.exists():
            try:
                data = json.loads(legacy_manifest.read_text())
                return data.get('type', 'template')
            except (json.JSONDecodeError, IOError):
                pass

        # Check for bot.py (template indicator)
        if (path / 'bot.py').exists():
            return 'template'

        # Check for __init__.py with setup function (cog indicator)
        init_file = path / '__init__.py'
        if init_file.exists():
            content = init_file.read_text()
            if 'async def setup' in content or 'def setup' in content:
                return 'cog'

        return 'unknown'

    def remove_repo(self, name: str) -> bool:
        """
        Remove an imported repository.

        Args:
            name: Repository name to remove

        Returns:
            True if removed successfully
        """
        # Cannot remove built-ins
        if name in OFFICIAL_REPOS:
            raise ValueError(f"Cannot remove built-in source '{name}'")

        user_repos = self._load_user_repos()
        if name not in user_repos:
            raise ValueError(f"Repository '{name}' not found")

        # Remove from disk
        repo_path = Path(user_repos[name]['path'])
        if repo_path.exists():
            import shutil
            shutil.rmtree(repo_path)

        # Remove from config
        del user_repos[name]
        self._save_user_repos(user_repos)

        display.success(f"Removed repository '{name}'")
        return True

    def update_repo(self, name: str) -> bool:
        """
        Update a repository (git pull).

        Args:
            name: Repository name to update

        Returns:
            True if updated successfully
        """
        # Handle official sources
        if name in OFFICIAL_REPOS:
            self._ensure_official_source(name, force_update=True)
            return True

        # Handle user repos
        user_repos = self._load_user_repos()
        if name not in user_repos:
            raise ValueError(f"Repository '{name}' not found")

        repo_path = Path(user_repos[name]['path'])
        display.info(f"Updating '{name}'...")
        self._git_pull(repo_path)

        # Update timestamp
        user_repos[name]['last_updated'] = datetime.now().isoformat()
        self._save_user_repos(user_repos)

        display.success(f"Updated '{name}'")
        return True

    def list_sources(self, include_disabled: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        List all available sources (built-ins + user repos).

        Returns:
            Dictionary of source name -> source info
        """
        sources = {}

        # Add built-ins
        for name in OFFICIAL_TEMPLATES:
            sources[name] = {
                'type': 'template',
                'source': 'built-in',
                'url': OFFICIAL_REPOS[name],
                'description': self._get_builtin_description(name),
                'cached': (self.official_dir / name).exists()
            }

        for name in OFFICIAL_COGS:
            sources[name] = {
                'type': 'cog',
                'source': 'built-in',
                'url': OFFICIAL_REPOS[name],
                'description': self._get_builtin_description(name),
                'cached': (self.official_dir / name).exists()
            }

        # Add user repos
        user_repos = self._load_user_repos()
        for name, info in user_repos.items():
            sources[name] = {
                'type': info.get('type', 'unknown'),
                'source': 'imported',
                'url': info.get('url', ''),
                'description': info.get('description', ''),
                'last_updated': info.get('last_updated', ''),
                'cached': True
            }

        return sources

    def _get_builtin_description(self, name: str) -> str:
        """Get description for a built-in source."""
        descriptions = {
            'basic': 'Simple beginner-friendly Discord bot template',
            'advanced': 'Production-ready template with sharding support',
            'permissions': '9-level hierarchical permission system',
            'moderation': 'Kick, ban, mute, warn, auto-moderation',
            'music': 'YouTube playback with queue management',
        }
        return descriptions.get(name, 'Official MultiCord source')

    def get_source_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a source.

        Args:
            name: Source name

        Returns:
            Source info dictionary or None
        """
        sources = self.list_sources()
        return sources.get(name)

    def is_template(self, name: str) -> bool:
        """Check if a source is a template."""
        if name in OFFICIAL_TEMPLATES:
            return True
        user_repos = self._load_user_repos()
        if name in user_repos:
            return user_repos[name].get('type') == 'template'
        return False

    def is_cog(self, name: str) -> bool:
        """Check if a source is a cog."""
        if name in OFFICIAL_COGS:
            return True
        user_repos = self._load_user_repos()
        if name in user_repos:
            return user_repos[name].get('type') == 'cog'
        return False

    # ── Source Operations ─────────────────────────────────────────────

    def get_source_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Read the manifest (template.json or cog.json) from a resolved source.

        Args:
            name: Source name

        Returns:
            Parsed manifest dictionary, or None if no manifest found
        """
        path = self.resolve_source(name)

        # Try template.json first, then cog.json, then legacy manifest.json
        for manifest_name in (TEMPLATE_MANIFEST, COG_MANIFEST, LEGACY_MANIFEST):
            manifest_path = path / manifest_name
            if manifest_path.exists():
                try:
                    return json.loads(manifest_path.read_text(encoding='utf-8'))
                except (json.JSONDecodeError, IOError):
                    continue

        return None

    def get_source_version(self, name: str) -> str:
        """Get the version string from a source's manifest."""
        metadata = self.get_source_metadata(name)
        if metadata:
            return metadata.get('version', 'unknown')
        return 'unknown'

    def install_source(self, name: str, dest: Path) -> bool:
        """
        Copy source files to a destination directory (for bot creation).

        Excludes .git and __pycache__ directories.

        Args:
            name: Source name to install from
            dest: Destination directory (will be created if needed)

        Returns:
            True if successful
        """
        source_path = self.resolve_source(name)

        if not source_path.exists():
            raise FileNotFoundError(f"Source '{name}' not found at {source_path}")

        dest.mkdir(parents=True, exist_ok=True)

        exclude_dirs = {'.git', '__pycache__', '.venv', 'node_modules'}

        for item in source_path.iterdir():
            if item.name in exclude_dirs:
                continue
            if item.is_file():
                shutil.copy2(item, dest / item.name)
            elif item.is_dir():
                shutil.copytree(item, dest / item.name, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns('.git', '__pycache__'))

        return True

    def validate_source(self, name: str) -> Tuple[bool, List[str]]:
        """
        Validate that a source has the minimum required files for a bot template.

        Args:
            name: Source name to validate

        Returns:
            Tuple of (is_valid, list of missing files)
        """
        path = self.resolve_source(name)
        required_files = ['bot.py', 'requirements.txt']
        missing = [f for f in required_files if not (path / f).exists()]
        return (len(missing) == 0, missing)

    def clear_cache(self, name: Optional[str] = None) -> bool:
        """
        Clear cached source data from disk.

        Args:
            name: Specific source to clear, or None for all official caches

        Returns:
            True if successful
        """
        if name:
            if name in OFFICIAL_REPOS:
                cache_path = self.official_dir / name
                if cache_path.exists():
                    shutil.rmtree(cache_path)
                # Clear timestamp
                cache_info = self._load_cache_info()
                cache_info.pop(name, None)
                self._save_cache_info(cache_info)
            else:
                raise ValueError(f"Cannot clear cache for non-official source '{name}'. Use 'repo remove' instead.")
        else:
            # Clear all official caches
            if self.official_dir.exists():
                shutil.rmtree(self.official_dir)
                self.official_dir.mkdir(parents=True, exist_ok=True)
            self._save_cache_info({})

        return True
