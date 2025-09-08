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
from multicord.utils.config import ConfigManager
from multicord.utils.display import Display

console = Console()
display = Display()


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


@cli.group()
def auth():
    """Authentication commands for cloud features."""
    pass


@auth.command()
@click.option('--api-url', default=None, help='Custom API URL')
def login(api_url):
    """
    Login to MultiCord cloud services.
    
    Uses OAuth2 device flow for secure authentication.
    """
    display.info("Starting authentication flow...")
    
    client = APIClient(api_url=api_url)
    
    try:
        # Start device flow
        device_auth = client.start_device_flow()
        
        # Display user code
        console.print(f"\n[bold yellow]Please visit:[/] {device_auth['verification_uri']}")
        console.print(f"[bold yellow]Enter code:[/] [bold cyan]{device_auth['user_code']}[/]\n")
        
        # Poll for completion
        display.info("Waiting for authorization...")
        tokens = client.poll_for_token(device_auth['device_code'], device_auth['interval'])
        
        if tokens:
            display.success("Successfully authenticated!")
            console.print(f"Access token expires in {tokens['expires_in']} seconds")
        else:
            display.error("Authentication failed or timed out")
            
    except Exception as e:
        display.error(f"Authentication error: {e}")
        sys.exit(1)


@auth.command()
def logout():
    """Logout from MultiCord cloud services."""
    client = APIClient()
    
    if client.logout():
        display.success("Successfully logged out")
    else:
        display.warning("No active session found")


@auth.command()
def status():
    """Check authentication status."""
    client = APIClient()
    
    if client.is_authenticated():
        display.success("Authenticated with MultiCord cloud")
        # Show user info if available
    else:
        display.info("Not authenticated - local mode only")


@cli.group()
def bot():
    """Bot management commands."""
    pass


@bot.command()
@click.option('--local', is_flag=True, help='Show only local bots')
@click.option('--cloud', is_flag=True, help='Show only cloud bots')
@click.option('--status', type=click.Choice(['all', 'running', 'stopped', 'error']), default='all')
def list(local, cloud, status):
    """List all bots (local and cloud)."""
    manager = BotManager()
    client = APIClient()
    
    table = Table(title="Discord Bots")
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Template")
    table.add_column("PID/ID")
    
    # Get local bots
    if not cloud:
        local_bots = manager.list_bots(status=status)
        for bot in local_bots:
            status_color = "green" if bot['status'] == "running" else "red"
            table.add_row(
                bot['name'],
                f"[{status_color}]{bot['status']}[/]",
                "Local",
                bot.get('template', '-'),
                str(bot.get('pid', '-'))
            )
    
    # Get cloud bots if authenticated
    if not local and client.is_authenticated():
        try:
            cloud_bots = client.list_bots(status=status)
            for bot in cloud_bots:
                status_color = "green" if bot['status'] == "running" else "red"
                table.add_row(
                    bot['name'],
                    f"[{status_color}]{bot['status']}[/]",
                    "Cloud",
                    bot.get('template', '-'),
                    bot['id'][:8]
                )
        except Exception as e:
            display.warning(f"Could not fetch cloud bots: {e}")
    
    console.print(table)


@bot.command()
@click.argument('name')
@click.option('--template', default='basic', help='Bot template to use')
@click.option('--cloud', is_flag=True, help='Create in cloud instead of locally')
def create(name, template, cloud):
    """Create a new bot from template."""
    
    if cloud:
        client = APIClient()
        if not client.is_authenticated():
            display.error("Please login first: multicord auth login")
            sys.exit(1)
        
        display.info(f"Creating cloud bot '{name}' from template '{template}'...")
        try:
            bot = client.create_bot(name, template)
            display.success(f"Cloud bot created: {bot['id']}")
        except Exception as e:
            display.error(f"Failed to create cloud bot: {e}")
            sys.exit(1)
    else:
        manager = BotManager()
        display.info(f"Creating local bot '{name}' from template '{template}'...")
        
        try:
            bot_path = manager.create_bot(name, template)
            display.success(f"Bot created at: {bot_path}")
            console.print(f"\nEdit config at: {bot_path}/config.toml")
            console.print(f"Then start with: [yellow]multicord bot start {name}[/]")
        except Exception as e:
            display.error(f"Failed to create bot: {e}")
            sys.exit(1)


@bot.command()
@click.argument('names', nargs=-1, required=True)
@click.option('--cloud', is_flag=True, help='Start cloud bot')
def start(names, cloud):
    """Start one or more bots."""
    
    if cloud:
        client = APIClient()
        if not client.is_authenticated():
            display.error("Please login first: multicord auth login")
            sys.exit(1)
        
        for name in names:
            try:
                display.info(f"Starting cloud bot '{name}'...")
                result = client.start_bot(name)
                display.success(f"Cloud bot '{name}' starting on node {result['node']['name']}")
            except Exception as e:
                display.error(f"Failed to start cloud bot '{name}': {e}")
    else:
        manager = BotManager()
        
        for name in names:
            try:
                display.info(f"Starting local bot '{name}'...")
                pid = manager.start_bot(name)
                display.success(f"Bot '{name}' started with PID {pid}")
            except Exception as e:
                display.error(f"Failed to start bot '{name}': {e}")


@bot.command()
@click.argument('names', nargs=-1, required=True)
@click.option('--cloud', is_flag=True, help='Stop cloud bot')
def stop(names, cloud):
    """Stop one or more bots."""
    
    if cloud:
        client = APIClient()
        if not client.is_authenticated():
            display.error("Please login first: multicord auth login")
            sys.exit(1)
        
        for name in names:
            try:
                display.info(f"Stopping cloud bot '{name}'...")
                client.stop_bot(name)
                display.success(f"Cloud bot '{name}' stopped")
            except Exception as e:
                display.error(f"Failed to stop cloud bot '{name}': {e}")
    else:
        manager = BotManager()
        
        for name in names:
            try:
                display.info(f"Stopping local bot '{name}'...")
                manager.stop_bot(name)
                display.success(f"Bot '{name}' stopped")
            except Exception as e:
                display.error(f"Failed to stop bot '{name}': {e}")


@bot.command()
@click.argument('name')
def status(name):
    """Get detailed status of a bot."""
    manager = BotManager()
    client = APIClient()
    
    # Try local first
    local_status = manager.get_bot_status(name)
    if local_status:
        console.print(f"\n[bold cyan]Local Bot: {name}[/]")
        for key, value in local_status.items():
            console.print(f"  {key}: {value}")
    
    # Try cloud if authenticated
    if client.is_authenticated():
        try:
            cloud_status = client.get_bot(name)
            if cloud_status:
                console.print(f"\n[bold cyan]Cloud Bot: {name}[/]")
                for key, value in cloud_status.items():
                    if key != 'config':  # Don't show sensitive config
                        console.print(f"  {key}: {value}")
        except:
            pass  # Bot might not exist in cloud
    
    if not local_status and not cloud_status:
        display.error(f"Bot '{name}' not found")


@bot.command()
@click.argument('name')
@click.option('--lines', default=50, help='Number of log lines to show')
@click.option('--follow', is_flag=True, help='Follow log output')
def logs(name, lines, follow):
    """View bot logs."""
    manager = BotManager()
    
    try:
        if follow:
            display.info(f"Following logs for '{name}' (Ctrl+C to stop)...")
            manager.follow_logs(name)
        else:
            logs = manager.get_logs(name, lines)
            for line in logs:
                console.print(line)
    except Exception as e:
        display.error(f"Failed to get logs: {e}")


@cli.group()
def template():
    """Template management commands."""
    pass


@template.command(name='list')
def template_list():
    """List available bot templates."""
    manager = BotManager()
    templates = manager.list_templates()
    
    table = Table(title="Available Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Type", style="yellow")
    
    for tmpl in templates:
        table.add_row(
            tmpl['name'],
            tmpl['description'],
            tmpl['type']
        )
    
    console.print(table)


@template.command()
@click.argument('url')
@click.option('--name', help='Template name')
def install(url, name):
    """Install a bot template from URL."""
    manager = BotManager()
    
    try:
        display.info(f"Installing template from {url}...")
        template_name = manager.install_template(url, name)
        display.success(f"Template '{template_name}' installed successfully")
    except Exception as e:
        display.error(f"Failed to install template: {e}")


@cli.group()
def config():
    """Configuration commands."""
    pass


@config.command()
def show():
    """Show current configuration."""
    config = ConfigManager()
    
    console.print("[bold cyan]MultiCord Configuration[/]\n")
    
    # Local config
    console.print("[yellow]Local Settings:[/]")
    for key, value in config.get_local_config().items():
        console.print(f"  {key}: {value}")
    
    # API config
    console.print("\n[yellow]API Settings:[/]")
    console.print(f"  API URL: {config.get_api_url()}")
    console.print(f"  Authenticated: {APIClient().is_authenticated()}")


@config.command()
@click.argument('key')
@click.argument('value')
def set(key, value):
    """Set a configuration value."""
    config = ConfigManager()
    
    try:
        config.set(key, value)
        display.success(f"Set {key} = {value}")
    except Exception as e:
        display.error(f"Failed to set config: {e}")


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
        icon = "✅" if passed else "❌"
        console.print(f"{icon} {check}: {status}")
    
    # Overall status
    all_passed = all(p for _, _, p in checks if _ != "Authentication")
    if all_passed:
        display.success("\nAll checks passed! MultiCord is ready to use.")
    else:
        display.warning("\nSome checks failed. Please install missing dependencies.")


if __name__ == "__main__":
    cli()