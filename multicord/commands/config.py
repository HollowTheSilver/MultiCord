"""Configuration commands for MultiCord CLI."""

import click
from rich.console import Console

from multicord.api.client import APIClient
from multicord.utils.config import ConfigManager
from multicord.utils.display import Display

# Initialize display and console
display = Display()
console = Console()


@click.group()
def config():
    """Configuration commands."""
    pass


@config.command()
def show():
    """Show current configuration."""
    config_mgr = ConfigManager()

    console.print("[bold cyan]MultiCord Configuration[/]\n")

    # Local config
    console.print("[yellow]Local Settings:[/]")
    for key, value in config_mgr.get_local_config().items():
        console.print(f"  {key}: {value}")

    # API config
    console.print("\n[yellow]API Settings:[/]")
    console.print(f"  API URL: {config_mgr.get_api_url()}")
    console.print(f"  Authenticated: {APIClient().is_authenticated()}")


@config.command()
@click.argument('key')
@click.argument('value')
def set(key, value):
    """Set a configuration value."""
    config_mgr = ConfigManager()

    try:
        config_mgr.set(key, value)
        display.success(f"Set {key} = {value}")
    except Exception as e:
        display.error(f"Failed to set config: {e}")
