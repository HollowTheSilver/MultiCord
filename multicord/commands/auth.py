"""Authentication commands for MultiCord CLI."""

import click
from rich.console import Console

from multicord.api.client import APIClient
from multicord.utils.display import Display
from multicord.utils.errors import handle_error, NetworkError, AuthenticationError

# Initialize display and console
display = Display()
console = Console()


@click.group()
def auth():
    """Authentication commands for cloud features."""
    pass


@auth.command()
def status():
    """Check authentication status."""
    from multicord.auth import get_tokens
    from multicord.auth.discord import DiscordAuth

    tokens = get_tokens()
    if tokens:
        # Get user info
        auth_client = DiscordAuth()
        user_info = auth_client.get_user_info()

        if user_info:
            console.print("[green][OK][/] Authenticated as:", style="bold")
            console.print(f"  Discord User: {user_info.get('discord_username', 'Unknown')}")
            console.print(f"  Discord ID: {user_info.get('discord_id', 'Unknown')}")
            console.print(f"  Email: {user_info.get('discord_email', 'Not available')}")
        else:
            console.print("[green][OK][/] Authenticated (user info not available)")
    else:
        console.print("[red]✗[/] Not authenticated")
        console.print("Use [yellow]multicord auth login[/] to authenticate")


@auth.command()
@click.option('--api-url', default=None, help='Custom API URL')
@click.option('--no-browser', is_flag=True, help='Use device flow for browserless environments')
@click.option('--method', type=click.Choice(['auto', 'device', 'browser']), default='auto',
              help='Authentication method: auto (smart detection), device (code flow), browser (callback flow)')
@handle_error
def login(api_url, no_browser, method):
    """
    Login to MultiCord cloud services.

    Uses Discord OAuth2 with environment-aware authentication:
    - Localhost API: Device flow
    - Remote API with browser: Browser callback flow
    - Remote API without browser: Device flow
    - Manual override available with --method flag

    Examples:
        multicord auth login                    # Auto-detect (recommended)
        multicord auth login --method device    # Force device flow
        multicord auth login --method browser   # Force browser callback
    """
    from multicord.auth import authenticate
    from multicord.constants import DEFAULT_API_URL

    api_url = api_url or DEFAULT_API_URL

    client = APIClient(api_url=api_url)
    if not client.is_online():
        raise NetworkError("Cannot connect to MultiCord API. Please check your internet connection.")

    success = authenticate(no_browser=no_browser, api_url=api_url, method=method if method != 'auto' else None)

    if success:
        display.success("Successfully authenticated!")
    else:
        raise AuthenticationError(
            "Authentication failed",
            "The authentication process was cancelled or failed."
        )


@auth.command()
@click.option('--api-url', default=None, help='Custom API URL')
def logout(api_url):
    """Logout from MultiCord cloud services."""
    from multicord.auth import logout as auth_logout
    from multicord.constants import DEFAULT_API_URL

    api_url = api_url or DEFAULT_API_URL
    auth_logout(api_url)
    display.success("Successfully logged out")
