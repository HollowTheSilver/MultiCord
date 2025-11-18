"""
Template repository management for MultiCord CLI.
Handles downloading and managing bot templates from Git repositories with
multi-repository support, priority system, and version tracking.
"""

import json
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class RepositoryConfig:
    """Configuration for a template repository."""
    name: str
    url: str
    type: str = "custom"  # "official" or "custom"
    enabled: bool = True
    priority: int = 0  # Higher priority = checked first
    auto_update: bool = False
    last_synced: Optional[str] = None
    branch: str = "main"
    auth_required: bool = False
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RepositoryConfig':
        """Create from dictionary."""
        return cls(**data)


class TemplateRepository:
    """Manages template repositories with multi-repo support and priority system."""

    DEFAULT_REPO_URL = "https://github.com/HollowTheSilver/MultiCord-Templates.git"
    CONFIG_VERSION = "2.0"  # Enhanced config version

    def __init__(self):
        self.cache_dir = Path.home() / ".multicord" / "templates"
        self.repos_dir = Path.home() / ".multicord" / "repositories"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.repos_dir.mkdir(parents=True, exist_ok=True)

        # Repository configuration
        self.repos_config_file = self.repos_dir / "repositories.json"
        self.config = self._load_configuration()
        self.repositories = self.config.get('repositories', {})

    def _load_configuration(self) -> Dict[str, Any]:
        """Load repository configuration with backwards compatibility."""
        if not self.repos_config_file.exists():
            # Create default enhanced configuration
            return self._create_default_config()

        with open(self.repos_config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Check if old format (v1.0) - just {name: url} dict
        if 'version' not in config and 'repositories' not in config:
            # Migrate from v1.0 to v2.0
            config = self._migrate_v1_to_v2(config)
            self._save_configuration(config)

        return config

    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration with official repository."""
        config = {
            "version": self.CONFIG_VERSION,
            "repositories": {
                "official": {
                    "name": "MultiCord Official",
                    "url": self.DEFAULT_REPO_URL,
                    "type": "official",
                    "enabled": True,
                    "priority": 0,
                    "auto_update": True,
                    "last_synced": None,
                    "branch": "main",
                    "auth_required": False,
                    "description": "Official MultiCord templates and cogs"
                }
            },
            "settings": {
                "default_repository": "official",
                "auto_update_interval_hours": 24,
                "cache_ttl_hours": 168
            }
        }
        self._save_configuration(config)
        return config

    def _migrate_v1_to_v2(self, old_config: Dict[str, str]) -> Dict[str, Any]:
        """Migrate v1.0 config (name: url) to v2.0 enhanced format."""
        new_config = {
            "version": self.CONFIG_VERSION,
            "repositories": {},
            "settings": {
                "default_repository": "official",
                "auto_update_interval_hours": 24,
                "cache_ttl_hours": 168
            }
        }

        # Convert each repository
        for name, url in old_config.items():
            new_config["repositories"][name] = {
                "name": name.replace('_', ' ').title(),
                "url": url,
                "type": "official" if name == "official" else "custom",
                "enabled": True,
                "priority": 0 if name == "official" else 10,  # Custom repos higher priority
                "auto_update": name == "official",  # Only auto-update official
                "last_synced": None,
                "branch": "main",
                "auth_required": False,
                "description": f"Migrated from v1.0: {name}"
            }

        return new_config

    def _save_configuration(self, config: Dict[str, Any]) -> None:
        """Save enhanced configuration."""
        with open(self.repos_config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

    def add_repository(
        self,
        name: str,
        url: str,
        priority: int = 10,
        auto_update: bool = False,
        branch: str = "main",
        description: str = ""
    ) -> bool:
        """
        Add a new template repository.

        Args:
            name: Repository identifier
            url: Git repository URL
            priority: Priority (higher = checked first), default 10 for custom repos
            auto_update: Whether to auto-update this repo
            branch: Git branch to use
            description: Human-readable description

        Returns:
            True if successfully added
        """
        if name in self.repositories:
            raise ValueError(f"Repository '{name}' already exists")

        self.repositories[name] = {
            "name": name.replace('_', ' ').replace('-', ' ').title(),
            "url": url,
            "type": "custom",
            "enabled": True,
            "priority": priority,
            "auto_update": auto_update,
            "last_synced": None,
            "branch": branch,
            "auth_required": False,
            "description": description or f"Custom repository: {name}"
        }

        self.config['repositories'] = self.repositories
        self._save_configuration(self.config)
        return True

    def remove_repository(self, name: str) -> bool:
        """
        Remove a template repository.

        Args:
            name: Repository identifier

        Returns:
            True if successfully removed
        """
        if name == "official":
            raise ValueError("Cannot remove official repository")

        if name in self.repositories:
            del self.repositories[name]
            self.config['repositories'] = self.repositories
            self._save_configuration(self.config)

            # Clean up cached repository
            repo_path = self.repos_dir / name
            if repo_path.exists():
                shutil.rmtree(repo_path)
            return True
        return False

    def list_repositories(self, enabled_only: bool = False) -> Dict[str, Dict]:
        """
        List all configured repositories.

        Args:
            enabled_only: Only return enabled repositories

        Returns:
            Dictionary of repository configurations
        """
        if enabled_only:
            return {
                name: config
                for name, config in self.repositories.items()
                if config.get('enabled', True)
            }
        return self.repositories.copy()

    def get_repository_config(self, name: str) -> Optional[Dict]:
        """Get configuration for a specific repository."""
        return self.repositories.get(name)

    def update_repository_config(self, name: str, **kwargs) -> bool:
        """
        Update repository configuration.

        Args:
            name: Repository identifier
            **kwargs: Fields to update (priority, enabled, auto_update, etc.)

        Returns:
            True if successfully updated
        """
        if name not in self.repositories:
            raise ValueError(f"Repository '{name}' not found")

        repo = self.repositories[name]
        for key, value in kwargs.items():
            if key in repo:
                repo[key] = value

        self.config['repositories'] = self.repositories
        self._save_configuration(self.config)
        return True

    def set_repository_priority(self, name: str, priority: int) -> bool:
        """Set priority for a repository."""
        return self.update_repository_config(name, priority=priority)

    def enable_repository(self, name: str) -> bool:
        """Enable a repository."""
        return self.update_repository_config(name, enabled=True)

    def disable_repository(self, name: str) -> bool:
        """Disable a repository."""
        if name == "official":
            raise ValueError("Cannot disable official repository")
        return self.update_repository_config(name, enabled=False)

    def get_enabled_repositories_by_priority(self) -> List[Tuple[str, Dict]]:
        """
        Get enabled repositories sorted by priority (highest first).

        Returns:
            List of (name, config) tuples sorted by priority
        """
        repos = [
            (name, config)
            for name, config in self.repositories.items()
            if config.get('enabled', True)
        ]
        # Sort by priority (descending)
        return sorted(repos, key=lambda x: x[1].get('priority', 0), reverse=True)

    def clone_repository(self, name: str, force_update: bool = False) -> Path:
        """
        Clone or update a template repository.

        Args:
            name: Repository identifier
            force_update: Force git pull even if recently synced

        Returns:
            Path to repository directory
        """
        if name not in self.repositories:
            raise ValueError(f"Repository '{name}' not found")

        repo_config = self.repositories[name]
        repo_url = repo_config['url']
        repo_path = self.repos_dir / name
        branch = repo_config.get('branch', 'main')

        try:
            if repo_path.exists():
                # Update existing repository
                subprocess.run(
                    ["git", "checkout", branch],
                    cwd=repo_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
                subprocess.run(
                    ["git", "pull"],
                    cwd=repo_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
            else:
                # Clone new repository
                subprocess.run(
                    ["git", "clone", "-b", branch, repo_url, str(repo_path)],
                    check=True,
                    capture_output=True,
                    text=True
                )

            # Update last_synced timestamp
            self.update_repository_config(name, last_synced=datetime.now().isoformat())

            return repo_path

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to clone/update repository '{name}': {e.stderr}")

    # // ========================================( Multi-Repo Template Discovery )======================================== // #

    def list_all_templates(self, enabled_only: bool = True) -> Dict[str, List[Tuple[str, Dict]]]:
        """
        List templates from ALL repositories grouped by template name.

        Args:
            enabled_only: Only search enabled repositories

        Returns:
            Dict mapping template names to list of (repo_name, template_info) tuples
            Sorted by repository priority
        """
        all_templates = {}
        repos = self.get_enabled_repositories_by_priority() if enabled_only else list(self.repositories.items())

        for repo_name, repo_config in repos:
            try:
                templates = self.list_templates(repo_name)
                for template_name, template_info in templates.items():
                    if template_name not in all_templates:
                        all_templates[template_name] = []
                    all_templates[template_name].append((repo_name, template_info))
            except Exception:
                # Skip repositories that fail to load
                continue

        return all_templates

    def find_template(self, template_name: str, repo_name: Optional[str] = None) -> Optional[Tuple[str, Dict]]:
        """
        Find a template across all repositories using priority system.

        Args:
            template_name: Name of template to find
            repo_name: Specific repository to search (optional)

        Returns:
            Tuple of (repo_name, template_info) or None if not found
        """
        if repo_name:
            # Search specific repository
            template_info = self.get_template_info(template_name, repo_name)
            if template_info:
                return (repo_name, template_info)
            return None

        # Search all enabled repos by priority
        for repo_name, repo_config in self.get_enabled_repositories_by_priority():
            try:
                template_info = self.get_template_info(template_name, repo_name)
                if template_info:
                    return (repo_name, template_info)
            except Exception:
                continue

        return None

    def get_template_path(self, template_name: str, repo_name: str) -> Path:
        """Get path to template directory in repository."""
        repo_path = self.repos_dir / repo_name
        if not repo_path.exists():
            repo_path = self.clone_repository(repo_name)
        return repo_path / template_name

    # // ========================================( Single-Repo Methods )======================================== // #

    def get_manifest(self, repo_name: str = "official") -> Dict[str, Any]:
        """Get the manifest from a repository."""
        repo_path = self.repos_dir / repo_name

        # Clone or update repository if not exists
        if not repo_path.exists():
            repo_path = self.clone_repository(repo_name)

        manifest_path = repo_path / "manifest.json"

        if not manifest_path.exists():
            raise FileNotFoundError(f"No manifest.json found in repository '{repo_name}'")

        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def list_templates(self, repo_name: str = "official") -> Dict[str, Dict]:
        """List available templates from a repository."""
        manifest = self.get_manifest(repo_name)
        return manifest.get("templates", {})

    def get_template_info(self, template_name: str, repo_name: str = "official") -> Optional[Dict]:
        """Get information about a specific template."""
        templates = self.list_templates(repo_name)
        return templates.get(template_name)

    def install_template(self, template_name: str, dest_dir: Path, repo_name: str = "official") -> bool:
        """Install a template to the destination directory."""
        # Ensure repository is cloned/updated
        repo_path = self.repos_dir / repo_name
        if not repo_path.exists():
            repo_path = self.clone_repository(repo_name)

        # Verify template exists
        template_info = self.get_template_info(template_name, repo_name)
        if not template_info:
            raise ValueError(f"Template '{template_name}' not found in repository '{repo_name}'")

        # Copy template files
        template_source = repo_path / template_name
        if not template_source.exists():
            raise FileNotFoundError(f"Template directory not found: {template_source}")

        try:
            # Create destination directory
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Copy all template files
            for item in template_source.iterdir():
                if item.is_file():
                    shutil.copy2(item, dest_dir / item.name)
                elif item.is_dir() and item.name not in ['.git', '__pycache__']:
                    shutil.copytree(item, dest_dir / item.name, dirs_exist_ok=True)

            return True

        except Exception as e:
            raise RuntimeError(f"Failed to install template: {e}")

    def update_template(self, template_name: str, dest_dir: Path, repo_name: str = "official") -> bool:
        """Update an existing template installation."""
        # Update the repository first
        self.clone_repository(repo_name)

        # Re-install the template (overwrite existing files)
        return self.install_template(template_name, dest_dir, repo_name)

    def search_templates(self, query: str, repo_name: str = "official") -> Dict[str, Dict]:
        """Search templates by name, tags, or category."""
        templates = self.list_templates(repo_name)
        query_lower = query.lower()

        results = {}
        for name, info in templates.items():
            # Search in name
            if query_lower in name.lower():
                results[name] = info
                continue

            # Search in description
            if query_lower in info.get("description", "").lower():
                results[name] = info
                continue

            # Search in tags
            tags = info.get("tags", [])
            if any(query_lower in tag.lower() for tag in tags):
                results[name] = info
                continue

            # Search in category
            if query_lower in info.get("category", "").lower():
                results[name] = info

        return results

    def get_template_categories(self, repo_name: str = "official") -> Dict[str, Dict]:
        """Get all template categories from a repository."""
        manifest = self.get_manifest(repo_name)
        return manifest.get("categories", {})

    def get_repository_info(self, repo_name: str = "official") -> Dict[str, Any]:
        """Get repository metadata."""
        manifest = self.get_manifest(repo_name)
        return manifest.get("repository", {})

    def clear_cache(self, repo_name: Optional[str] = None) -> bool:
        """Clear cached repository data."""
        try:
            if repo_name:
                # Clear specific repository
                repo_path = self.repos_dir / repo_name
                if repo_path.exists():
                    shutil.rmtree(repo_path)
            else:
                # Clear all repositories
                if self.repos_dir.exists():
                    shutil.rmtree(self.repos_dir)
                    self.repos_dir.mkdir(parents=True, exist_ok=True)

            return True

        except Exception as e:
            raise RuntimeError(f"Failed to clear cache: {e}")

    def validate_template(self, template_path: Path) -> bool:
        """Validate a template has required files."""
        required_files = ["bot.py", "config.toml", "requirements.txt"]

        for file in required_files:
            if not (template_path / file).exists():
                return False

        return True
