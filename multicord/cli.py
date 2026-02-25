"""
Main CLI interface for MultiCord.
Provides commands for local bot management and cloud integration.
"""

import click
from rich.console import Console
from rich.table import Table
from pathlib import Path
import sys

from multicord.api.client import APIClient
from multicord.local.bot_manager import BotManager
from multicord.docker import DockerManager
from multicord.utils.config import ConfigManager
from multicord.utils.display import Display
from multicord.utils.errors import handle_error, FriendlyError, NetworkError, AuthenticationError
from multicord.utils.validation import validate_bot_name, validate_cog_name
from multicord.commands import auth, bot, cache, config, repo, token, venv

console = Console()
display = Display()


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


@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help='Show version')
@click.pass_context
def cli(ctx, version):
    """
    MultiCord - Run multiple Discord bots with ease.
    
    Local bot management and cloud orchestration platform.
    """
    if version:
        from multicord import __version__
        console.print(f"[bold cyan]MultiCord CLI[/] version {__version__}")
        sys.exit(0)
    
    if ctx.invoked_subcommand is None:
        console.print("[bold cyan]MultiCord CLI[/] - Run multiple Discord bots with ease")
        console.print("\nUse [yellow]multicord --help[/] to see available commands")



@cli.command()
def doctor():
    """Check system health and dependencies."""
    console.print("[bold cyan]MultiCord System Check[/]\n")
    
    checks = []
    
    # Check Python version
    import sys
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks.append(("Python Version", py_version, sys.version_info >= (3, 9)))
    
    # Check for discord.py
    try:
        import discord
        checks.append(("discord.py", discord.__version__, True))
    except ImportError:
        checks.append(("discord.py", "Not installed", False))
    
    # Check API connectivity
    client = APIClient()
    api_status = client.check_health()
    checks.append(("API Connection", "Online" if api_status else "Offline", api_status))
    
    # Check authentication
    auth_status = client.is_authenticated()
    checks.append(("Authentication", "Valid" if auth_status else "Not authenticated", True))
    
    # Display results
    for check, status, passed in checks:
        icon = "[OK]" if passed else "[FAIL]"
        color = "green" if passed else "red"
        console.print(f"[{color}]{icon}[/{color}] {check}: {status}")
    
    # Overall status
    all_passed = all(p for _, _, p in checks if _ != "Authentication")
    if all_passed:
        display.success("\nAll checks passed! MultiCord is ready to use.")
    else:
        display.warning("\nSome checks failed. Please install missing dependencies.")



# Register command modules
cli.add_command(auth)
cli.add_command(bot)
cli.add_command(cache)
cli.add_command(config)
cli.add_command(repo)
cli.add_command(token)
cli.add_command(venv)


if __name__ == "__main__":
    cli()