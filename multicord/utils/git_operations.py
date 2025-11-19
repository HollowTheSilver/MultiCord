"""
Professional Git repository management for MultiCord CLI.

Implements industry-standard practices from npm, pip, cargo, and homebrew:
- Configurable timeouts (default 60s, no infinite hangs)
- Real-time progress streaming (users see Git output)
- Retry logic with exponential backoff (handles transient failures)
- Smart caching with TTL (reduces unnecessary network calls)
- Offline fallback (uses cached templates when network fails)
- Comprehensive error handling with actionable messages
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, TypeVar, List, Dict, Any
import json
import os
import subprocess
import sys
import time
import random


T = TypeVar('T')


class GitErrorType(Enum):
    """Classification of Git errors for retry logic."""
    TRANSIENT = "transient"  # Network issues, should retry
    PERMANENT = "permanent"  # Auth failures, don't retry
    TIMEOUT = "timeout"      # Operation timed out


class GitOperationError(Exception):
    """Base exception for Git operations with context and suggestions."""

    def __init__(
        self,
        message: str,
        error_type: GitErrorType,
        output: Optional[str] = None,
        suggestions: Optional[List[str]] = None
    ):
        super().__init__(message)
        self.error_type = error_type
        self.output = output
        self.suggestions = suggestions or []

    def format_user_message(self) -> str:
        """Format error message with suggestions for user display."""
        msg = str(self)

        if self.suggestions:
            msg += "\n\nSuggestions:\n"
            for suggestion in self.suggestions:
                msg += f"  • {suggestion}\n"

        if self.output and len(self.output) < 500:
            msg += f"\nCommand output:\n{self.output}"

        return msg


@dataclass
class GitOperationConfig:
    """Configuration for Git operations."""
    clone_timeout: int = 120      # 2 minutes for initial clone
    fetch_timeout: int = 60       # 1 minute for updates
    checkout_timeout: int = 10    # 10 seconds for local checkout
    max_retries: int = 3          # Retry transient failures 3 times
    base_retry_delay: float = 1.0  # Start with 1 second delay
    max_retry_delay: float = 30.0  # Cap at 30 seconds
    cache_ttl: int = 3600         # 1 hour cache lifetime
    offline_mode: bool = False    # Prefer cached data
    shallow_clone: bool = True    # Use --depth 1 for faster clones
    show_progress: bool = True    # Stream Git output to user

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'GitOperationConfig':
        """Create configuration from dictionary (e.g., TOML file)."""
        return cls(
            clone_timeout=config_dict.get('clone_timeout', 120),
            fetch_timeout=config_dict.get('fetch_timeout', 60),
            checkout_timeout=config_dict.get('checkout_timeout', 10),
            max_retries=config_dict.get('max_retries', 3),
            base_retry_delay=config_dict.get('base_retry_delay', 1.0),
            max_retry_delay=config_dict.get('max_retry_delay', 30.0),
            cache_ttl=config_dict.get('cache_ttl', 3600),
            offline_mode=config_dict.get('offline_mode', False),
            shallow_clone=config_dict.get('shallow_clone', True),
            show_progress=config_dict.get('show_progress', True),
        )

    @classmethod
    def from_env(cls) -> 'GitOperationConfig':
        """Create configuration from environment variables."""
        return cls(
            clone_timeout=int(os.getenv('MULTICORD_CLONE_TIMEOUT', '120')),
            fetch_timeout=int(os.getenv('MULTICORD_FETCH_TIMEOUT', '60')),
            checkout_timeout=int(os.getenv('MULTICORD_CHECKOUT_TIMEOUT', '10')),
            max_retries=int(os.getenv('MULTICORD_MAX_RETRIES', '3')),
            offline_mode=os.getenv('MULTICORD_OFFLINE', '').lower() in ('1', 'true', 'yes'),
            show_progress=os.getenv('MULTICORD_SHOW_PROGRESS', '1') == '1',
        )


class GitRepository:
    """
    Professional Git repository manager with industry-standard practices.

    Features:
    - Real-time progress streaming (no silent operations)
    - Configurable timeouts (no infinite hangs)
    - Retry with exponential backoff (handles network issues)
    - Smart caching (reduces unnecessary updates)
    - Offline fallback (graceful degradation)
    - Comprehensive error handling (actionable messages)
    """

    def __init__(
        self,
        repo_url: str,
        local_path: Path,
        branch: str = 'main',
        config: Optional[GitOperationConfig] = None
    ):
        """
        Initialize Git repository manager.

        Args:
            repo_url: Remote repository URL
            local_path: Local directory path
            branch: Branch to checkout (default: main)
            config: Operation configuration (uses defaults if None)
        """
        self.repo_url = repo_url
        self.local_path = local_path
        self.branch = branch
        self.config = config or GitOperationConfig()
        self.cache_file = local_path / '.multicord_cache.json'

    def ensure_repository(self, force_update: bool = False) -> None:
        """
        Ensure repository exists and is up-to-date.

        Implements smart caching:
        - If repository doesn't exist → clone it
        - If force_update or cache stale → update it
        - Otherwise → use cached version

        Args:
            force_update: Force update even if cache is fresh

        Raises:
            GitOperationError: If operation fails and no cache available
        """
        if not self.local_path.exists():
            self._clone_repository()
        elif force_update or self._should_update():
            self._update_repository()
        else:
            if self.config.show_progress:
                cache_age = self._cache_age_human()
                print(f"Using cached repository (updated {cache_age})", file=sys.stderr)

    def _clone_repository(self) -> None:
        """Clone repository with progress and retry logic."""
        if self.config.show_progress:
            print(f"Cloning template repository...", file=sys.stderr)

        def operation():
            args = ['git', 'clone']

            if self.config.shallow_clone:
                args.extend(['--depth', '1', '--single-branch'])

            args.extend(['-b', self.branch, self.repo_url, str(self.local_path)])

            self._run_git_command(
                args,
                timeout=self.config.clone_timeout,
                cwd=self.local_path.parent
            )

        self._retry_operation(operation, "clone")
        self._update_cache()

    def _update_repository(self) -> None:
        """Update repository with progress and retry logic."""
        if self.config.offline_mode:
            if self.config.show_progress:
                print("Offline mode enabled, using cached repository", file=sys.stderr)
            return

        if self.config.show_progress:
            print(f"Updating template repository...", file=sys.stderr)

        def operation():
            # Fetch latest changes
            self._run_git_command(
                ['git', 'fetch', 'origin', self.branch],
                timeout=self.config.fetch_timeout
            )

            # Reset to latest (safer than pull, avoids merge conflicts)
            self._run_git_command(
                ['git', 'reset', '--hard', f'origin/{self.branch}'],
                timeout=self.config.checkout_timeout
            )

        try:
            self._retry_operation(operation, "update")
            self._update_cache()
        except GitOperationError as e:
            if e.error_type == GitErrorType.TRANSIENT:
                # For transient errors, continue with cached version
                if self.config.show_progress:
                    print(f"Update failed, using cached repository", file=sys.stderr)
            else:
                # Permanent errors should be raised
                raise

    def _run_git_command(
        self,
        args: List[str],
        timeout: int,
        cwd: Optional[Path] = None
    ) -> str:
        """
        Execute Git command with real-time output streaming.

        Args:
            args: Command arguments (e.g., ['git', 'clone', ...])
            timeout: Maximum execution time in seconds
            cwd: Working directory (uses local_path if None)

        Returns:
            Combined stdout/stderr output

        Raises:
            GitOperationError: If command fails or times out
        """
        if cwd is None:
            cwd = self.local_path

        # Prepare environment to prevent interactive prompts
        env = os.environ.copy()
        env.update({
            'GIT_TERMINAL_PROMPT': '0',        # No interactive prompts
            'GIT_ASKPASS': '/bin/echo',        # Disable credential prompts
        })
        # Let Git handle its own connection timeouts - they work better!

        # Start process with output streaming
        process = subprocess.Popen(
            args,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1,  # Line-buffered
            universal_newlines=True
        )

        # Stream output in real-time
        output_lines = []
        try:
            if process.stdout:
                for line in process.stdout:
                    output_lines.append(line)
                    if self.config.show_progress:
                        # Print to stderr so it doesn't interfere with CLI output
                        print(line, end='', file=sys.stderr)

            # Wait for completion with timeout
            process.wait(timeout=timeout)

        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise GitOperationError(
                f"Git operation timed out after {timeout}s",
                error_type=GitErrorType.TIMEOUT,
                output=''.join(output_lines),
                suggestions=[
                    "Check your internet connection",
                    f"Try increasing timeout (current: {timeout}s)",
                    "Use --offline to work with cached templates"
                ]
            )

        output = ''.join(output_lines)

        # Check return code
        if process.returncode != 0:
            error_type = self._classify_error(output, process.returncode)

            raise GitOperationError(
                f"Git command failed with code {process.returncode}",
                error_type=error_type,
                output=output,
                suggestions=self._get_error_suggestions(error_type, output)
            )

        return output

    def _classify_error(self, output: str, returncode: int) -> GitErrorType:
        """
        Classify Git error for retry logic.

        Args:
            output: Command output
            returncode: Process exit code

        Returns:
            Error type (transient, permanent, or timeout)
        """
        output_lower = output.lower()

        # Transient errors that should be retried
        transient_indicators = [
            'timeout',
            'timed out',
            'connection refused',
            'connection reset',
            'temporary failure',
            '502',  # Bad Gateway
            '503',  # Service Unavailable
            '504',  # Gateway Timeout
            'could not resolve host',
            'failed to connect',
            'network is unreachable',
        ]

        for indicator in transient_indicators:
            if indicator in output_lower:
                return GitErrorType.TRANSIENT

        # Permanent errors that should not be retried
        permanent_indicators = [
            'authentication failed',
            '401',  # Unauthorized
            '403',  # Forbidden
            '404',  # Not Found
            'repository not found',
            'permission denied',
            'fatal: not a git repository',
        ]

        for indicator in permanent_indicators:
            if indicator in output_lower:
                return GitErrorType.PERMANENT

        # Default to transient for unknown errors (safer to retry)
        return GitErrorType.TRANSIENT

    def _get_error_suggestions(
        self,
        error_type: GitErrorType,
        output: str
    ) -> List[str]:
        """
        Generate actionable error suggestions.

        Args:
            error_type: Type of error that occurred
            output: Command output

        Returns:
            List of suggestions for user
        """
        suggestions = []
        output_lower = output.lower()

        if error_type == GitErrorType.TRANSIENT:
            suggestions.extend([
                "Check your internet connection",
                "Try again in a few minutes",
                "Check GitHub status: https://www.githubstatus.com",
                "Use --offline to work with cached templates"
            ])

        elif error_type == GitErrorType.PERMANENT:
            if '404' in output or 'not found' in output_lower:
                suggestions.extend([
                    "Verify the repository URL is correct",
                    "Check if the repository still exists",
                    "Contact repository owner for access"
                ])
            elif 'auth' in output_lower or '401' in output or '403' in output:
                suggestions.extend([
                    "Check your Git credentials",
                    "Use personal access token for private repos",
                    "Verify repository permissions"
                ])

        return suggestions

    def _retry_operation(
        self,
        operation: Callable[[], None],
        operation_name: str
    ) -> None:
        """
        Retry operation with exponential backoff.

        Args:
            operation: Function to retry
            operation_name: Human-readable operation name (for messages)

        Raises:
            GitOperationError: If all retries exhausted or permanent error
        """
        last_error = None

        for attempt in range(self.config.max_retries + 1):
            try:
                operation()
                return  # Success!

            except GitOperationError as e:
                last_error = e

                # Don't retry permanent errors
                if e.error_type == GitErrorType.PERMANENT:
                    raise

                # If this was the last attempt, raise with context
                if attempt == self.config.max_retries:
                    msg = f"Failed to {operation_name} template repository after {attempt} retries.\n\n"
                    msg += str(e)

                    raise GitOperationError(
                        msg,
                        e.error_type,
                        e.output,
                        e.suggestions
                    )

                # Calculate backoff delay: base * (2 ^ attempt) with jitter
                delay = min(
                    self.config.base_retry_delay * (2 ** attempt),
                    self.config.max_retry_delay
                )
                # Add jitter (±25%) to prevent thundering herd
                delay = delay * (0.75 + random.random() * 0.5)

                if self.config.show_progress:
                    print(
                        f"Retry {attempt + 1}/{self.config.max_retries} after {delay:.1f}s...",
                        file=sys.stderr
                    )

                time.sleep(delay)

    def _should_update(self) -> bool:
        """
        Determine if repository needs updating based on cache age.

        Returns:
            True if update is needed, False if cache is fresh
        """
        if not self.cache_file.exists():
            return True  # Never cached

        try:
            cache = json.loads(self.cache_file.read_text(encoding='utf-8'))
            last_update = datetime.fromisoformat(cache['last_update'])
            age_seconds = (datetime.now(timezone.utc) - last_update).total_seconds()

            return age_seconds > self.config.cache_ttl

        except (json.JSONDecodeError, KeyError, ValueError):
            return True  # Invalid cache, update needed

    def _update_cache(self) -> None:
        """Update cache metadata after successful operation."""
        # Get current commit SHA for tracking
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.local_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            commit_sha = result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            commit_sha = "unknown"

        cache = {
            'repository_url': self.repo_url,
            'last_update': datetime.now(timezone.utc).isoformat(),
            'last_commit_sha': commit_sha,
            'cache_ttl': self.config.cache_ttl,
            'status': 'healthy'
        }

        self.cache_file.write_text(json.dumps(cache, indent=2), encoding='utf-8')

    def _cache_age_human(self) -> str:
        """
        Get human-readable cache age.

        Returns:
            String like "2 hours ago" or "just now"
        """
        if not self.cache_file.exists():
            return "never"

        try:
            cache = json.loads(self.cache_file.read_text(encoding='utf-8'))
            last_update = datetime.fromisoformat(cache['last_update'])
            age = datetime.now(timezone.utc) - last_update

            if age < timedelta(minutes=1):
                return "just now"
            elif age < timedelta(hours=1):
                minutes = int(age.total_seconds() / 60)
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            elif age < timedelta(days=1):
                hours = int(age.total_seconds() / 3600)
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            else:
                days = age.days
                return f"{days} day{'s' if days != 1 else ''} ago"

        except:
            return "unknown"

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get cache information for debugging/monitoring.

        Returns:
            Dictionary with cache status and metadata
        """
        if not self.cache_file.exists():
            return {
                'exists': False,
                'last_update': None,
                'age_seconds': None,
                'age_human': 'never',
                'status': 'no_cache'
            }

        try:
            cache = json.loads(self.cache_file.read_text(encoding='utf-8'))
            last_update = datetime.fromisoformat(cache['last_update'])
            age_seconds = (datetime.now(timezone.utc) - last_update).total_seconds()

            return {
                'exists': True,
                'last_update': last_update.isoformat(),
                'age_seconds': age_seconds,
                'age_human': self._cache_age_human(),
                'commit_sha': cache.get('last_commit_sha'),
                'status': cache.get('status'),
                'is_stale': age_seconds > self.config.cache_ttl
            }

        except:
            return {
                'exists': True,
                'last_update': None,
                'age_seconds': None,
                'age_human': 'unknown',
                'status': 'corrupted'
            }
