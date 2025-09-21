"""
MultiCord authentication module - Hybrid authentication strategy.

Provides both browser-based Discord OAuth2 and device flow for browserless environments.
Automatically detects the best method based on the environment.
"""

import os
import sys
from typing import Optional
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


def authenticate(no_browser: bool = False, api_url: str = "http://localhost:8000") -> bool:
    """
    Smart authentication with automatic detection and fallback.

    Args:
        no_browser: Force device flow even if browser is available
        api_url: Base URL for MultiCord API

    Returns:
        True if authentication successful
    """
    # Check if already authenticated
    auth_client = DiscordAuth(api_url)
    if auth_client.is_authenticated():
        user_info = auth_client.get_user_info()
        if user_info:
            print(f"[OK] Already authenticated as: {user_info.get('discord_username', 'Unknown')}")
            return True

    # Determine authentication method
    browser_available = is_browser_available()

    if no_browser:
        print("[AUTH] Using device flow authentication (--no-browser flag set)")
        device_client = DeviceFlowClient(api_url)
        return device_client.authenticate()

    elif not browser_available:
        print("[AUTH] No browser detected - using device flow authentication")
        print("   (You're likely in an SSH session or container)")
        device_client = DeviceFlowClient(api_url)
        return device_client.authenticate()

    else:
        # Try browser flow first
        print("[AUTH] Opening browser for Discord authentication...")
        try:
            success = auth_client.authenticate()
            if success:
                return True

            # Browser flow failed, offer device flow
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


def logout(api_url: str = "http://localhost:8000") -> None:
    """Clear all stored authentication data."""
    # Clear from both auth methods (they use same keyring)
    auth_client = DiscordAuth(api_url)
    auth_client.logout()


__all__ = ['authenticate', 'get_tokens', 'logout', 'DiscordAuth', 'DeviceFlowClient']