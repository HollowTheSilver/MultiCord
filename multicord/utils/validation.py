"""
Input validation utilities for MultiCord CLI.

Provides validation functions for user inputs to prevent
path traversal, command injection, and other security issues.
"""

import re
from pathlib import Path
from typing import Optional

import click


def validate_bot_name_callback(ctx, param, value):
    """Click callback to validate bot name."""
    if value:
        is_valid, error_msg = validate_bot_name(value)
        if not is_valid:
            raise click.BadParameter(error_msg)
    return value


def validate_cog_name_callback(ctx, param, value):
    """Click callback to validate cog name."""
    if value:
        is_valid, error_msg = validate_cog_name(value)
        if not is_valid:
            raise click.BadParameter(error_msg)
    return value
from urllib.parse import urlparse


def validate_bot_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Validate bot name for safety and compatibility.

    Bot names must:
    - Start with alphanumeric character
    - Contain only alphanumeric, hyphens, underscores
    - Be 1-64 characters long
    - Not contain path separators or parent directory references

    Args:
        name: Bot name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Bot name cannot be empty"

    if len(name) > 64:
        return False, "Bot name must be 64 characters or fewer"

    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$', name):
        return False, "Bot name must start with alphanumeric and contain only letters, numbers, hyphens, and underscores"

    # Explicitly check for dangerous patterns
    dangerous = ['..', '/', '\\', '\0', ':']
    if any(char in name for char in dangerous):
        return False, "Bot name contains invalid characters"

    return True, None


def validate_cog_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Validate cog name (same rules as bot name).

    Args:
        name: Cog name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    return validate_bot_name(name)


def validate_path_containment(path: Path, parent: Path) -> tuple[bool, Optional[str]]:
    """
    Validate that a resolved path is contained within a parent directory.

    Prevents path traversal attacks by ensuring the resolved path
    doesn't escape the parent directory.

    Args:
        path: Path to validate (will be resolved)
        parent: Parent directory that should contain the path

    Returns:
        Tuple of (is_contained, error_message)
    """
    try:
        resolved_path = path.resolve()
        resolved_parent = parent.resolve()

        # Check if path starts with parent
        if not str(resolved_path).startswith(str(resolved_parent)):
            return False, f"Path escapes parent directory: {path}"

        return True, None

    except (OSError, RuntimeError) as e:
        return False, f"Path resolution failed: {e}"


def validate_git_url(url: str) -> tuple[bool, Optional[str]]:
    """
    Validate Git repository URL for safety.

    Only allows HTTPS and Git protocols to prevent:
    - file:// local file access
    - ssh:// unexpected credential prompts
    - other exotic protocols

    Args:
        url: Git URL to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "Git URL cannot be empty"

    try:
        parsed = urlparse(url)

        # Allow https:// and git://
        if parsed.scheme not in ('https', 'git'):
            return False, f"Git URL must use https:// or git:// protocol, got {parsed.scheme}://"

        # Require hostname
        if not parsed.netloc:
            return False, "Git URL must include a hostname"

        # Basic format check
        if parsed.scheme == 'https' and not url.startswith('https://'):
            return False, "Malformed HTTPS URL"

        if parsed.scheme == 'git' and not url.startswith('git://'):
            return False, "Malformed Git URL"

        return True, None

    except Exception as e:
        return False, f"Invalid URL format: {e}"


def validate_api_url_https(url: str) -> tuple[bool, Optional[str]]:
    """
    Validate that API URL uses HTTPS for non-localhost hosts.

    Localhost and Docker internal hosts are exempt from HTTPS requirement.

    Args:
        url: API URL to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "API URL cannot be empty"

    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or '').lower()

        # Localhost exemptions
        localhost_hosts = {'localhost', '127.0.0.1', '::1'}
        docker_internal_suffixes = ('.docker.internal', 'host.docker.internal')

        is_localhost = (
            hostname in localhost_hosts or
            any(hostname.endswith(suffix) for suffix in docker_internal_suffixes)
        )

        # Require HTTPS for non-localhost
        if not is_localhost and parsed.scheme != 'https':
            return False, f"Remote API URL must use HTTPS (got {parsed.scheme}://). Only localhost may use HTTP."

        return True, None

    except Exception as e:
        return False, f"Invalid URL format: {e}"
