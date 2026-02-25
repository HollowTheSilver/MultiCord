"""Cache management commands for MultiCord CLI."""

import click
from rich.console import Console
from rich.table import Table

from multicord.api.client import APIClient
from multicord.utils.display import Display

# Initialize display and console
display = Display()
console = Console()


@click.group()
def cache():
    """Cache management commands."""
    pass


@cache.command()
def status():
    """Show cache status and statistics."""
    client = APIClient()
    cache_status = client.cache.get_cache_status()

    console.print("[bold cyan]Cache Status[/]\n")
    console.print(f"Cache Directory: {cache_status['cache_dir']}")

    if not cache_status['caches']:
        console.print("\n[yellow]No cached data found[/]")
        return

    table = Table(title="Cached Data")
    table.add_column("Type", style="cyan")
    table.add_column("Age", justify="right")
    table.add_column("Expires In", justify="right")
    table.add_column("Status", style="bold")

    for cache_type, info in cache_status['caches'].items():
        age = info['age_seconds']
        expires = info['expires_in_seconds']

        # Format age
        if age > 3600:
            age_str = f"{age // 3600}h {(age % 3600) // 60}m"
        elif age > 60:
            age_str = f"{age // 60}m {age % 60}s"
        else:
            age_str = f"{age}s"

        # Format expiry
        if expires > 3600:
            expires_str = f"{expires // 3600}h {(expires % 3600) // 60}m"
        elif expires > 60:
            expires_str = f"{expires // 60}m {expires % 60}s"
        elif expires > 0:
            expires_str = f"{expires}s"
        else:
            expires_str = "Expired"

        status = "[green]Valid[/]" if info['is_valid'] else "[red]Expired[/]"

        table.add_row(cache_type, age_str, expires_str, status)

    console.print(table)


@cache.command()
def clear():
    """Clear all cached data."""
    client = APIClient()

    if click.confirm("Clear all cached data?"):
        client.cache.invalidate()
        display.success("Cache cleared")
    else:
        display.info("Cache clear cancelled")


@cache.command()
def refresh():
    """Refresh cached data from API."""
    client = APIClient()

    if not client.is_authenticated():
        display.error("Please login first: multicord auth login")
        return

    display.info("Refreshing cache from API...")

    try:
        # Refresh bots
        bots = client.list_bots(use_cache=False)
        display.success(f"Cached {len(bots)} bots")

        # Refresh templates
        templates = client.get_templates(use_cache=False)
        display.success(f"Cached {len(templates)} templates")

        display.success("Cache refreshed successfully")
    except Exception as e:
        display.error(f"Failed to refresh cache: {e}")
