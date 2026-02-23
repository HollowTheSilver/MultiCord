"""
MultiCord authentication module - Hybrid authentication strategy.

Provides both browser-based Discord OAuth2 and device flow for browserless environments.
Automatically detects the best method based on the environment.
"""

import os
import sys
from typing import Optional
from urllib.parse import urlparse
from .discord import DiscordAuth
from .device import DeviceFlowClient


def is_browser_available() -> bool:
    """Check if a browser is likely available in the current environment.

    Returns:
        True if browser is likely available, False otherwise
    """
    # Windows and macOS typically have browsers available
    if sys.platform in ['win32', 'darwin']:
        return True

    # Linux - check for display environment variable
    if sys.platform.startswith('linux'):
        # Check for X11 or Wayland display
        return (
            os.environ.get('DISPLAY') is not None or
            os.environ.get('WAYLAND_DISPLAY') is not None
        )

    # Default to assuming no browser
    return False


def is_localhost_api(api_url: str) -> bool:
    """Check if API URL is localhost/local development.

    Args:
        api_url: Base URL for MultiCord API

    Returns:
        True if API is localhost, False if remote
    """
    parsed = urlparse(api_url)
    hostname = parsed.hostname or ''

    # Check for localhost indicators
    localhost_names = {'localhost', '127.0.0.1', '::1'}
    if hostname.lower() in localhost_names:
        return True

    # Check for Docker internal networks
    if '.docker.internal' in hostname:
        return True

    # Remote API
    return False


def authenticate(no_browser: bool = False, api_url: Optional[str] = None, method: Optional[str] = None) -> bool:
    """
    Authenticate with MultiCord API using environment-aware method selection.

    Automatically selects the optimal authentication method based on environment:
    - Localhost API: Device flow
    - Remote API with browser: Browser callback flow
    - Remote API without browser: Device flow
    - Manual override available via method parameter

    Args:
        no_browser: Force device flow even if browser is available
        api_url: Base URL for MultiCord API
        method: Manual auth method override ('auto', 'device', 'browser')

    Returns:
        True if authentication successful
    """
    from multicord.constants import DEFAULT_API_URL
    if api_url is None:
        api_url = DEFAULT_API_URL

    auth_client = DiscordAuth(api_url)
    if auth_client.is_authenticated():
        user_info = auth_client.get_user_info()
        if user_info:
            print(f"[OK] Already authenticated as: {user_info.get('discord_username', 'Unknown')}")
            return True

    localhost = is_localhost_api(api_url)
    browser_available = is_browser_available()

    if method == 'device' or no_browser:
        print("[AUTH] Using device flow authentication (manual override)")
        device_client = DeviceFlowClient(api_url)
        return device_client.authenticate()

    elif method == 'browser':
        print("[AUTH] Using browser callback authentication (manual override)")
        try:
            return auth_client.authenticate()
        except Exception as e:
            print(f"\n[ERROR] Browser authentication failed: {e}")
            return False

    elif localhost:
        print("[AUTH] Detected localhost API - using device flow authentication")
        device_client = DeviceFlowClient(api_url)
        return device_client.authenticate()

    elif not browser_available:
        print("[AUTH] No browser detected - using device flow authentication")
        device_client = DeviceFlowClient(api_url)
        return device_client.authenticate()

    else:
        print("[AUTH] Detected remote API with browser - using browser callback")
        try:
            success = auth_client.authenticate()
            if success:
                return True

            print("\n[WARNING] Browser authentication failed or was cancelled")
            print("Would you like to try device flow authentication instead? (y/n): ", end="")
            response = input().strip().lower()

            if response == 'y':
                device_client = DeviceFlowClient(api_url)
                return device_client.authenticate()
            else:
                return False

        except Exception as e:
            print(f"\n[WARNING] Browser authentication error: {e}")
            print("Falling back to device flow authentication...")
            device_client = DeviceFlowClient(api_url)
            return device_client.authenticate()


def get_tokens() -> Optional[dict]:
    """Get stored authentication tokens.

    Returns:
        Dictionary with tokens or None
    """
    # Try Discord auth first (same keyring storage)
    auth_client = DiscordAuth()
    return auth_client.get_tokens()


def logout(api_url: Optional[str] = None) -> None:
    """Clear all stored authentication data."""
    from multicord.constants import DEFAULT_API_URL
    if api_url is None:
        api_url = DEFAULT_API_URL

    # Clear from both auth methods (they use same keyring)
    auth_client = DiscordAuth(api_url)
    auth_client.logout()


__all__ = ['authenticate', 'get_tokens', 'logout', 'DiscordAuth', 'DeviceFlowClient']