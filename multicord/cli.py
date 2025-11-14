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
from multicord.utils.errors import handle_error, FriendlyError, NetworkError, AuthenticationError

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
@handle_error
def login(api_url, no_browser):
    """
    Login to MultiCord cloud services.

    Uses Discord OAuth2 with smart authentication:
    - Browser flow when available (default)
    - Device flow for SSH/Docker/EC2 (auto-detected or --no-browser)
    """
    from multicord.auth import authenticate

    # Use default API URL if not provided
    api_url = api_url or "http://localhost:8000"

    # Check if API is reachable
    client = APIClient(api_url=api_url)
    if not client.is_online():
        raise NetworkError("Cannot connect to MultiCord API. Please check your internet connection.")

    # Use hybrid authentication
    success = authenticate(no_browser=no_browser, api_url=api_url)

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

    api_url = api_url or "http://localhost:8000"
    auth_logout(api_url)
    display.success("Successfully logged out")


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
@click.option('--sync', is_flag=True, help='Sync and show both local and cloud bots')
@click.option('--status', type=click.Choice(['all', 'running', 'stopped', 'error']), default='all')
def list(local, cloud, sync, status):
    """List all bots (local and cloud)."""
    manager = BotManager()
    client = APIClient()

    # If sync flag is set, show both local and cloud
    if sync:
        local = False
        cloud = False

    table = Table(title="Discord Bots")
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Location", style="yellow")
    table.add_column("Port/Template")
    table.add_column("CPU %", justify="right")
    table.add_column("Memory MB", justify="right")
    table.add_column("PID/ID")

    all_bots = {}

    # Get local bots
    if not cloud or sync:
        local_bots = manager.list_bots(status=status)
        for bot in local_bots:
            all_bots[bot['name']] = {
                **bot,
                'location': 'Local',
                'source': 'local'
            }

    # Get cloud bots if authenticated or sync requested
    if (not local or sync) and client.is_authenticated():
        try:
            # Use cache for sync to improve performance
            cloud_bots = client.list_bots(status=status, use_cache=True)
            for bot in cloud_bots:
                bot_name = bot['name']
                if bot_name in all_bots:
                    # Bot exists both locally and in cloud
                    all_bots[bot_name]['location'] = 'Both'
                    all_bots[bot_name]['cloud_id'] = bot.get('id', '')[:8]
                    all_bots[bot_name]['cloud_status'] = bot.get('status', 'unknown')
                else:
                    # Cloud-only bot
                    all_bots[bot_name] = {
                        'name': bot_name,
                        'status': bot.get('status', 'unknown'),
                        'location': 'Cloud',
                        'template': bot.get('template', '-'),
                        'cloud_id': bot.get('id', '')[:8],
                        'source': 'cloud'
                    }
        except Exception as e:
            if sync:
                display.warning(f"Could not fetch cloud bots: {e}")
                display.info("Showing cached cloud data if available...")
                # Try to use cached data
                cached_bots = client.cache.get_bots()
                if cached_bots:
                    for bot in cached_bots:
                        bot_name = bot['name']
                        if bot_name not in all_bots:
                            all_bots[bot_name] = {
                                'name': bot_name,
                                'status': bot.get('status', 'unknown'),
                                'location': 'Cloud (cached)',
                                'template': bot.get('template', '-'),
                                'cloud_id': bot.get('id', '')[:8],
                                'source': 'cloud_cached'
                            }

    # Display all bots
    for bot_name, bot in sorted(all_bots.items()):
        status_color = "green" if bot.get('status') == "running" else "red"
        location = bot.get('location', 'Unknown')

        # Determine what to show in Port/Template column
        if bot.get('source') == 'local':
            port_template = str(bot.get('port', '-'))
        else:
            port_template = bot.get('template', '-')

        # Determine PID/ID
        if bot.get('source') == 'local':
            pid_id = str(bot.get('pid', '-'))
        elif bot.get('cloud_id'):
            pid_id = bot.get('cloud_id')
        else:
            pid_id = '-'

        table.add_row(
            bot_name,
            f"[{status_color}]{bot.get('status', 'unknown')}[/]",
            location,
            port_template,
            f"{bot.get('cpu_percent', 0):.1f}" if bot.get('status') == "running" and bot.get('source') == 'local' else "-",
            f"{bot.get('memory_mb', 0):.1f}" if bot.get('status') == "running" and bot.get('source') == 'local' else "-",
            pid_id
        )

    console.print(table)

    # Show cache status if using sync
    if sync:
        cache_status = client.cache.get_cache_status()
        if cache_status.get('caches', {}).get('bots'):
            bot_cache = cache_status['caches']['bots']
            if bot_cache['is_valid']:
                console.print(f"\n[dim]Cloud data cached {bot_cache['age_seconds']}s ago, expires in {bot_cache['expires_in_seconds']}s[/]")


@bot.command()
@click.argument('name')
@click.option('--template', default='basic', help='Bot template to use')
@click.option('--cloud', is_flag=True, help='Create in cloud instead of locally')
@click.option('--repo', help='Specific repository to use (default: auto-detect by priority)')
def create(name, template, cloud, repo):
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

        # Show which repository will be used
        if repo:
            display.info(f"Creating local bot '{name}' from template '{template}' (repository: {repo})...")
        else:
            display.info(f"Creating local bot '{name}' from template '{template}' (auto-detecting repository)...")

        try:
            bot_path = manager.create_bot(name, template, repo=repo)

            # Show success with repository info
            meta_file = bot_path / ".multicord_meta.json"
            if meta_file.exists():
                import json
                with open(meta_file) as f:
                    meta = json.load(f)
                    used_repo = meta.get('repository', 'unknown')
                    template_version = meta.get('template_version', 'unknown')
                    display.success(f"Bot created from '{used_repo}' repository (v{template_version})")
            else:
                display.success(f"Bot created at: {bot_path}")

            console.print(f"\n[dim]Location:[/] {bot_path}")
            console.print(f"[dim]Config:[/] {bot_path}/config.toml")
            console.print(f"\n[yellow]Start with:[/] multicord bot start {name}")
        except Exception as e:
            display.error(f"Failed to create bot: {e}")
            sys.exit(1)


@bot.command()
@click.argument('names', nargs=-1, required=True)
@click.option('--cloud', is_flag=True, help='Start cloud bot')
@click.option('--env', '-e', multiple=True, help='Environment variables (KEY=VALUE format, can be used multiple times)')
def start(names, cloud, env):
    """
    Start one or more bots.

    You can inject environment variables using --env:
        multicord bot start my-bot --env DISCORD_TOKEN=xxx --env LOG_LEVEL=DEBUG
    """
    # Parse environment variables
    env_vars = {}
    if env:
        for env_arg in env:
            if '=' in env_arg:
                key, value = env_arg.split('=', 1)
                env_vars[key] = value
            else:
                display.warning(f"Ignoring invalid environment variable format: {env_arg}")

    if cloud:
        client = APIClient()
        if not client.is_authenticated():
            display.error("Please login first: multicord auth login")
            sys.exit(1)

        if env_vars:
            display.warning("Environment variables are ignored for cloud bots")

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
                if env_vars:
                    display.info(f"  Injecting {len(env_vars)} environment variable(s)")
                pid = manager.start_bot(name, env_vars=env_vars)
                # Get status to show port
                status = manager.get_bot_status(name)
                if status and status.get('port'):
                    display.success(f"Bot '{name}' started with PID {pid} on port {status['port']}")
                else:
                    display.success(f"Bot '{name}' started with PID {pid}")
            except Exception as e:
                display.error(f"Failed to start bot '{name}': {e}")


@bot.command()
@click.argument('names', nargs=-1, required=True)
@click.option('--cloud', is_flag=True, help='Stop cloud bot')
@click.option('--force', is_flag=True, help='Force stop if graceful shutdown fails')
def stop(names, cloud, force):
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
                if force:
                    display.info(f"Force stopping local bot '{name}'...")
                else:
                    display.info(f"Stopping local bot '{name}'...")
                manager.stop_bot(name, force=force)
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
        
        # Status with color
        status = local_status.get('status', 'unknown')
        status_color = "green" if status == "running" else "red"
        console.print(f"  Status: [{status_color}]{status}[/{status_color}]")
        
        # Basic info
        console.print(f"  Path: {local_status.get('path', '-')}")
        console.print(f"  PID: {local_status.get('pid', '-')}")
        console.print(f"  Port: {local_status.get('port', '-')}")
        
        # Health metrics if running
        if status == "running":
            console.print(f"\n  [yellow]Health Metrics:[/]")
            console.print(f"    Memory: {local_status.get('memory_mb', 0):.1f} MB")
            console.print(f"    CPU: {local_status.get('cpu_percent', 0):.1f}%")
            
            # Uptime formatting
            uptime = local_status.get('uptime_seconds', 0)
            if uptime > 3600:
                uptime_str = f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m"
            elif uptime > 60:
                uptime_str = f"{int(uptime // 60)}m {int(uptime % 60)}s"
            else:
                uptime_str = f"{int(uptime)}s"
            console.print(f"    Uptime: {uptime_str}")
            
            # Health status
            is_healthy = local_status.get('is_healthy', False)
            health_color = "green" if is_healthy else "yellow"
            console.print(f"    Healthy: [{health_color}]{is_healthy}[/{health_color}]")
            
            # Additional info
            if local_status.get('restart_count', 0) > 0:
                console.print(f"    Restarts: {local_status['restart_count']}")
            if local_status.get('started_at'):
                console.print(f"    Started: {local_status['started_at']}")
    
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
@click.argument('names', nargs=-1, required=True)
@click.option('--cloud', is_flag=True, help='Restart cloud bot')
def restart(names, cloud):
    """Restart one or more bots."""
    
    if cloud:
        client = APIClient()
        if not client.is_authenticated():
            display.error("Please login first: multicord auth login")
            sys.exit(1)
        
        for name in names:
            try:
                display.info(f"Restarting cloud bot '{name}'...")
                client.restart_bot(name)
                display.success(f"Cloud bot '{name}' restarted")
            except Exception as e:
                display.error(f"Failed to restart cloud bot '{name}': {e}")
    else:
        manager = BotManager()
        
        for name in names:
            try:
                display.info(f"Restarting local bot '{name}'...")
                pid = manager.restart_bot(name)
                # Get status to show port
                status = manager.get_bot_status(name)
                if status and status.get('port'):
                    display.success(f"Bot '{name}' restarted with PID {pid} on port {status['port']}")
                else:
                    display.success(f"Bot '{name}' restarted with PID {pid}")
            except Exception as e:
                display.error(f"Failed to restart bot '{name}': {e}")


@bot.command()
@click.option('--watch', is_flag=True, help='Watch health in real-time')
def health(watch):
    """Display health dashboard for all running bots."""
    manager = BotManager()
    
    try:
        if watch:
            display.info("Starting health monitoring (Ctrl+C to stop)...")
            manager.display_health_dashboard()
            # TODO: Implement live updating with rich.Live
        else:
            # Get health summary
            summary = manager.get_health_dashboard()
            
            # Display summary stats
            console.print("\n[bold cyan]System Health Summary[/]\n")
            console.print(f"Total Bots: {summary['total_bots']}")
            console.print(f"[green]Healthy: {summary['healthy']}[/green]")
            console.print(f"[yellow]Warning: {summary['warning']}[/yellow]")
            console.print(f"[red]Critical: {summary['critical']}[/red]")
            console.print(f"[red]Dead: {summary['dead']}[/red]")
            console.print(f"\nTotal Memory: {summary['total_memory_mb']:.1f} MB")
            console.print(f"Average CPU: {summary['average_cpu_percent']:.1f}%")
            
            # Display bot details
            if summary['bots']:
                console.print("\n[bold]Bot Details:[/]")
                table = Table()
                table.add_column("Bot", style="cyan")
                table.add_column("Health", style="bold")
                table.add_column("Memory MB", justify="right")
                table.add_column("CPU %", justify="right")
                table.add_column("Uptime", justify="right")
                
                for bot in summary['bots']:
                    # Health color
                    level_colors = {
                        'healthy': 'green',
                        'warning': 'yellow', 
                        'critical': 'red',
                        'dead': 'red bold'
                    }
                    health_color = level_colors.get(bot['level'], 'white')
                    
                    # Format uptime
                    uptime = bot.get('uptime_seconds', 0)
                    if uptime > 3600:
                        uptime_str = f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m"
                    elif uptime > 60:
                        uptime_str = f"{int(uptime // 60)}m {int(uptime % 60)}s"
                    else:
                        uptime_str = f"{int(uptime)}s"
                    
                    table.add_row(
                        bot['name'],
                        f"[{health_color}]{bot['level'].upper()}[/{health_color}]",
                        f"{bot['memory_mb']:.1f}",
                        f"{bot['cpu_percent']:.1f}",
                        uptime_str
                    )
                
                console.print(table)
            else:
                console.print("\n[yellow]No bots currently running[/]")
                
    except Exception as e:
        display.error(f"Failed to get health dashboard: {e}")


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


@bot.command()
@click.argument('name')
@click.option('--token', help='Bot token (will prompt if not provided)')
@click.option('--force', is_flag=True, help='Force deployment even if bot exists in cloud')
def deploy(name, token, force):
    """Deploy a local bot to the cloud."""
    manager = BotManager()
    client = APIClient()

    # Check authentication
    if not client.is_authenticated():
        display.error("Please login first: multicord auth login")
        sys.exit(1)

    # Check if bot exists locally
    bot_package = manager.export_bot_for_deploy(name)
    if not bot_package:
        display.error(f"Bot '{name}' not found locally")
        sys.exit(1)

    # Handle token
    if not token and not bot_package['config'].get('token'):
        # Prompt for token if not provided
        import getpass
        token = getpass.getpass(f"Enter Discord bot token for '{name}': ")

    if token:
        bot_package['config']['token'] = token

    # Check if bot exists in cloud
    if not force:
        try:
            existing_bot = client.get_bot(name)
            if existing_bot:
                if not click.confirm(f"Bot '{name}' already exists in cloud. Update it?"):
                    display.info("Deployment cancelled")
                    return
        except:
            pass  # Bot doesn't exist, proceed with deployment

    # Deploy to cloud
    try:
        display.info(f"Deploying bot '{name}' to cloud...")
        result = client.deploy_bot(name, bot_package)
        display.success(f"Bot '{name}' successfully deployed!")

        if 'id' in result:
            console.print(f"Cloud Bot ID: {result['id']}")
        if 'status' in result:
            console.print(f"Status: {result['status']}")

        # Offer to start the bot
        if click.confirm("Start the bot in cloud now?"):
            try:
                client.start_bot(result.get('id', name))
                display.success(f"Bot '{name}' started in cloud")
            except Exception as e:
                display.warning(f"Could not start bot: {e}")

    except Exception as e:
        display.error(f"Failed to deploy bot: {e}")
        sys.exit(1)


@bot.command()
@click.argument('name')
@click.option('--strategy', type=click.Choice(['local_first', 'cloud_first', 'newest', 'manual']),
              default='newest', help='Merge strategy for conflicts')
def pull(name, strategy):
    """Pull bot configuration from cloud to local."""
    manager = BotManager()
    client = APIClient()

    # Check authentication
    if not client.is_authenticated():
        display.error("Please login first: multicord auth login")
        sys.exit(1)

    try:
        display.info(f"Pulling configuration for '{name}' from cloud...")

        # Get cloud configuration
        cloud_config = client.pull_bot_config(name)
        if not cloud_config:
            display.error(f"Bot '{name}' not found in cloud")
            sys.exit(1)

        # Import or sync with local
        if not (manager.bots_dir / name).exists():
            # Bot doesn't exist locally, import it
            if manager.import_bot_from_cloud(name, cloud_config):
                display.success(f"Bot '{name}' imported from cloud")
            else:
                display.error(f"Failed to import bot '{name}'")
        else:
            # Bot exists locally, sync configurations
            result = manager.sync_bot_with_cloud(name, cloud_config, strategy)

            if result.get('success'):
                display.success(f"Bot '{name}' configuration synced")
                if result.get('changes'):
                    console.print("\n[yellow]Changes made:[/]")
                    for change in result['changes']:
                        console.print(f"  • {change}")
            elif result.get('requires_manual'):
                display.warning("Manual conflict resolution required")
                console.print("\n[yellow]Conflicts found:[/]")
                for conflict in result.get('conflicts', []):
                    console.print(f"  • {conflict['key']}:")
                    console.print(f"    Local: {conflict['local_value']}")
                    console.print(f"    Cloud: {conflict['cloud_value']}")
            else:
                display.error(f"Failed to sync: {result.get('error', 'Unknown error')}")

    except Exception as e:
        display.error(f"Failed to pull bot configuration: {e}")
        sys.exit(1)


@bot.command()
@click.argument('name')
@click.option('--strategy', type=click.Choice(['local_first', 'cloud_first', 'newest']),
              default='newest', help='Merge strategy for conflicts')
@click.option('--bidirectional', is_flag=True, help='Sync in both directions')
def sync(name, strategy, bidirectional):
    """Synchronize bot configuration between local and cloud."""
    manager = BotManager()
    client = APIClient()

    # Check authentication
    if not client.is_authenticated():
        display.error("Please login first: multicord auth login")
        sys.exit(1)

    try:
        display.info(f"Synchronizing bot '{name}'...")

        # Get local configuration
        from multicord.utils.sync import ConfigSync
        sync_manager = ConfigSync(manager.bots_dir)
        local_config = sync_manager.get_local_config(name)

        if not local_config:
            # No local bot, try to pull from cloud
            display.info(f"Bot '{name}' not found locally, attempting to pull from cloud...")
            cloud_config = client.pull_bot_config(name)
            if cloud_config:
                if manager.import_bot_from_cloud(name, cloud_config):
                    display.success(f"Bot '{name}' imported from cloud")
                else:
                    display.error(f"Failed to import bot")
            else:
                display.error(f"Bot '{name}' not found locally or in cloud")
            return

        # Sync with cloud
        result = client.sync_bot_config(name, local_config)
        display.success(f"Configuration synced to cloud")

        if bidirectional:
            # Also pull cloud changes
            cloud_config = client.pull_bot_config(name)
            if cloud_config:
                sync_result = manager.sync_bot_with_cloud(name, cloud_config, strategy)
                if sync_result.get('changes'):
                    console.print("\n[yellow]Local changes:[/]")
                    for change in sync_result['changes']:
                        console.print(f"  • {change}")

        # Invalidate cache after sync
        client.cache.invalidate(f"bot_{name}_config")
        client.cache.invalidate("bots")

    except Exception as e:
        display.error(f"Failed to sync bot: {e}")
        sys.exit(1)


@bot.command(name='check-updates')
@click.argument('name', required=False)
@click.option('--all', 'check_all', is_flag=True, help='Check all bots for updates')
def check_updates(name, check_all):
    """Check if template updates are available for bot(s)."""
    from multicord.utils.update_detector import UpdateDetector

    detector = UpdateDetector()

    if check_all or not name:
        # Check all bots
        display.info("Checking all bots for template updates...")

        all_updates = detector.check_all_bots_updates()

        if not all_updates:
            display.info("No bots found")
            return

        # Filter to only bots with updates
        bots_with_updates = {
            bot_name: info
            for bot_name, info in all_updates.items()
            if info.available
        }

        if not bots_with_updates:
            display.success("All bots are up to date!")
            return

        # Show table of available updates
        table = Table(title=f"Available Updates ({len(bots_with_updates)} bot(s))")
        table.add_column("Bot", style="cyan")
        table.add_column("Current", style="yellow")
        table.add_column("Latest", style="green")
        table.add_column("Type", style="magenta")
        table.add_column("Repository", style="blue")

        for bot_name, update_info in sorted(bots_with_updates.items()):
            # Color code update type
            update_type = update_info.update_type or "unknown"
            if update_info.breaking_changes:
                type_display = f"[red]⚠️ {update_type}[/]"
            elif update_type == "feature":
                type_display = f"[yellow]✨ {update_type}[/]"
            else:
                type_display = f"[green]🔧 {update_type}[/]"

            table.add_row(
                bot_name,
                update_info.current_version,
                update_info.latest_version,
                type_display,
                update_info.repository or "unknown"
            )

        console.print(table)

        # Show summary
        summary = detector.get_update_summary()
        console.print(f"\n[bold]Summary:[/]")
        console.print(f"  Updates available: {summary['total']}")
        if summary['breaking'] > 0:
            console.print(f"  ⚠️  Breaking changes: {summary['breaking']}")
        if summary['feature'] > 0:
            console.print(f"  ✨ Feature updates: {summary['feature']}")
        if summary['patch'] > 0:
            console.print(f"  🔧 Patch updates: {summary['patch']}")

        console.print(f"\n[yellow]Run:[/] multicord bot update <name> to update")

    else:
        # Check specific bot
        update_info = detector.check_bot_updates(name)

        if not update_info:
            display.error(f"Bot '{name}' not found")
            sys.exit(1)

        if not update_info.available:
            display.success(f"Bot '{name}' is up to date (v{update_info.current_version or 'unknown'})")
            return

        # Show update details
        console.print(f"\n[bold cyan]Update Available for '{name}'[/]\n")
        console.print(f"[bold]Current Version:[/] {update_info.current_version}")
        console.print(f"[bold]Latest Version:[/] {update_info.latest_version}")
        console.print(f"[bold]Update Type:[/] {update_info.update_type}")
        console.print(f"[bold]Repository:[/] {update_info.repository}")

        if update_info.breaking_changes:
            console.print(f"\n[red]⚠️  WARNING: This update includes BREAKING CHANGES[/]")

        # Show changelog if available
        changes = detector.get_changes_between_versions(name)
        if changes:
            console.print(f"\n[bold]Changelog:[/]")
            for change in changes:
                console.print(f"  • {change}")

        console.print(f"\n[yellow]Run:[/] multicord bot update {name} to apply update")


@bot.command(name='update')
@click.argument('name')
@click.option('--strategy', type=click.Choice(['core-only', 'safe-merge', 'full-replace']),
              default='safe-merge', help='Update strategy (default: safe-merge)')
@click.option('--dry-run', is_flag=True, help='Preview changes without applying')
@click.option('--version', 'target_version', help='Update to specific version (default: latest)')
@click.option('--no-backup', is_flag=True, help='Skip creating backup before update')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt')
def update_bot(name, strategy, dry_run, target_version, no_backup, yes):
    """Update a bot to the latest template version."""
    from multicord.utils.template_updater import TemplateUpdater, UpdateStrategy
    from multicord.utils.update_detector import UpdateDetector

    # Map strategy string to enum
    strategy_map = {
        'core-only': UpdateStrategy.CORE_ONLY,
        'safe-merge': UpdateStrategy.SAFE_MERGE,
        'full-replace': UpdateStrategy.FULL_REPLACE
    }
    update_strategy = strategy_map[strategy]

    updater = TemplateUpdater()
    detector = UpdateDetector()

    # Check if update is available
    update_info = detector.check_bot_updates(name)
    if not update_info:
        display.error(f"Bot '{name}' not found")
        sys.exit(1)

    if not update_info.available:
        display.success(f"Bot '{name}' is already up to date (v{update_info.current_version})")
        return

    # Show update information
    console.print(f"\n[bold cyan]Update Plan for '{name}'[/]\n")
    console.print(f"[bold]Strategy:[/] {strategy}")
    console.print(f"[bold]Current Version:[/] {update_info.current_version}")
    console.print(f"[bold]Target Version:[/] {target_version or update_info.latest_version}")

    if update_info.breaking_changes:
        console.print(f"\n[red]⚠️  WARNING: This update includes BREAKING CHANGES[/]")

    # Get update plan
    plan = updater.get_update_plan(name, update_strategy, target_version)

    # Show what will change
    if plan['will_update']:
        console.print(f"\n[bold]Files to Update:[/]")
        for file in plan['will_update']:
            console.print(f"  [green]✓[/] {file}")

    if plan['will_merge']:
        console.print(f"\n[bold]Files to Merge:[/]")
        for file in plan['will_merge']:
            console.print(f"  [yellow]⚡[/] {file}")

    if plan['will_skip']:
        console.print(f"\n[bold]Files to Skip:[/]")
        for file in plan['will_skip']:
            console.print(f"  [dim]○[/] {file}")

    if plan['conflicts']:
        console.print(f"\n[bold red]Conflicts Detected:[/]")
        for conflict in plan['conflicts']:
            console.print(f"  [red]✗[/] {conflict}")

    # Show backup status
    if not no_backup:
        console.print(f"\n[bold]Backup:[/] Will create backup before update")
        if plan['can_rollback']:
            console.print(f"[dim]Previous backups available for rollback[/]")

    # Dry run mode
    if dry_run:
        console.print(f"\n[yellow]DRY RUN MODE:[/] No changes will be applied")
        console.print(f"[dim]Remove --dry-run flag to apply update[/]")
        return

    # Confirm before applying
    if not yes and plan['conflicts']:
        console.print(f"\n[yellow]⚠️  Conflicts detected - manual intervention may be needed[/]")
        if not click.confirm("Continue with update?"):
            console.print("[dim]Update cancelled[/]")
            return
    elif not yes:
        if not click.confirm("\nProceed with update?"):
            console.print("[dim]Update cancelled[/]")
            return

    # Apply update
    console.print(f"\n[bold]Applying update...[/]")

    result = updater.update_bot(
        bot_name=name,
        strategy=update_strategy,
        target_version=target_version,
        create_backup=not no_backup,
        dry_run=False
    )

    if result.success:
        display.success(f"Successfully updated '{name}' from v{result.old_version} to v{result.new_version}")

        if result.backup_created:
            console.print(f"[dim]Backup saved: {result.backup_created}[/]")

        if result.files_updated:
            console.print(f"\n[green]Updated {len(result.files_updated)} file(s)[/]")

        if result.files_merged:
            console.print(f"[yellow]Merged {len(result.files_merged)} file(s)[/]")

        if result.conflicts:
            console.print(f"\n[yellow]⚠️  {len(result.conflicts)} conflict(s) require manual review[/]")

        console.print(f"\n[dim]To rollback: multicord bot rollback {name}[/]")
    else:
        display.error(f"Update failed: {result.error_message}")
        if result.backup_created:
            console.print(f"\n[yellow]Backup available: {result.backup_created}[/]")
            console.print(f"[dim]Rollback with: multicord bot rollback {name}[/]")
        sys.exit(1)


@bot.command(name='rollback')
@click.argument('name')
@click.option('--backup', help='Specific backup file to restore (default: latest)')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt')
def rollback_bot(name, backup, yes):
    """Rollback a bot to a previous backup."""
    from multicord.utils.template_updater import TemplateUpdater
    from multicord.utils.backup_manager import BackupManager

    updater = TemplateUpdater()
    backup_manager = BackupManager()

    # Get available backups
    backups = backup_manager.list_backups(name)

    if not backups:
        display.error(f"No backups found for bot '{name}'")
        sys.exit(1)

    # Determine which backup to restore
    if backup:
        target_backup = next((b for b in backups if b.backup_file == backup), None)
        if not target_backup:
            display.error(f"Backup '{backup}' not found")
            sys.exit(1)
    else:
        target_backup = backups[0]  # Latest

    # Show backup information
    console.print(f"\n[bold cyan]Rollback '{name}'[/]\n")
    console.print(f"[bold]Backup:[/] {target_backup.backup_file}")
    console.print(f"[bold]Created:[/] {target_backup.timestamp}")
    console.print(f"[bold]Template Version:[/] {target_backup.template_version}")
    console.print(f"[bold]Reason:[/] {target_backup.reason}")

    # Confirm
    if not yes:
        console.print(f"\n[yellow]⚠️  This will replace current bot files[/]")
        console.print(f"[dim]A safety backup will be created before rollback[/]")
        if not click.confirm("\nProceed with rollback?"):
            console.print("[dim]Rollback cancelled[/]")
            return

    # Perform rollback
    console.print(f"\n[bold]Rolling back...[/]")

    success = updater.rollback_update(name, target_backup.backup_file)

    if success:
        display.success(f"Successfully rolled back '{name}' to {target_backup.backup_file}")
        console.print(f"[dim]Restored to template version {target_backup.template_version}[/]")
    else:
        display.error("Rollback failed")
        sys.exit(1)


@cli.group()
def template():
    """Template management commands."""
    pass


@template.command(name='list')
@click.option('--repo', help='List templates from specific repository only')
def template_list(repo):
    """List available bot templates from all repositories."""
    from multicord.utils.template_repository import TemplateRepository

    template_repo = TemplateRepository()

    if repo:
        # List from specific repository
        try:
            templates = template_repo.list_templates(repo)
            repo_config = template_repo.get_repository_config(repo)

            table = Table(title=f"Templates from '{repo}' Repository")
            table.add_column("Name", style="cyan")
            table.add_column("Description")
            table.add_column("Version", style="yellow")
            table.add_column("Category", style="magenta")

            for name, info in templates.items():
                table.add_row(
                    name,
                    info.get('description', 'No description'),
                    info.get('version', 'unknown'),
                    info.get('category', 'general')
                )

            console.print(table)

            # Show repository info
            if repo_config:
                console.print(f"\n[dim]Repository Priority: {repo_config.get('priority', 0)} | "
                             f"URL: {repo_config.get('url', 'unknown')}[/]")

        except Exception as e:
            display.error(f"Failed to list templates from '{repo}': {e}")
            sys.exit(1)
    else:
        # List from all enabled repositories with priority indication
        all_templates = template_repo.list_all_templates(enabled_only=True)

        if not all_templates:
            display.info("No templates found. Run 'multicord repo update --all' to fetch templates.")
            return

        table = Table(title="Available Templates (All Repositories)")
        table.add_column("Name", style="cyan")
        table.add_column("Repository", style="blue")
        table.add_column("Description")
        table.add_column("Version", style="yellow")
        table.add_column("Priority", justify="right", style="magenta")

        # Flatten and sort by priority
        template_rows = []
        for template_name, repo_list in all_templates.items():
            for repo_name, template_info in repo_list:
                repo_config = template_repo.get_repository_config(repo_name)
                priority = repo_config.get('priority', 0) if repo_config else 0
                template_rows.append((
                    template_name,
                    repo_name,
                    template_info.get('description', 'No description'),
                    template_info.get('version', 'unknown'),
                    priority
                ))

        # Sort by priority (highest first)
        template_rows.sort(key=lambda x: x[4], reverse=True)

        # Add rows to table
        for name, repo_name, desc, version, priority in template_rows:
            # Truncate description if too long
            if len(desc) > 60:
                desc = desc[:57] + "..."

            # Indicate highest priority with a star
            if priority > 0:
                repo_display = f"{repo_name} ⭐"
            else:
                repo_display = repo_name

            table.add_row(name, repo_display, desc, version, str(priority))

        console.print(table)
        console.print(f"\n[dim]Templates with ⭐ will be used by default for their name.[/]")
        console.print(f"[dim]Use --repo to specify a different source.[/]")


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
def repo():
    """Repository management commands."""
    pass


@repo.command(name='list')
@click.option('--all', 'show_all', is_flag=True, help='Show disabled repositories')
def repo_list(show_all):
    """List all configured template repositories."""
    from multicord.utils.template_repository import TemplateRepository
    from datetime import datetime

    template_repo = TemplateRepository()
    repos = template_repo.list_repositories(enabled_only=not show_all)

    if not repos:
        display.info("No repositories configured")
        return

    table = Table(title="Template Repositories")
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="blue")
    table.add_column("Priority", justify="right", style="yellow")
    table.add_column("Status", style="green")
    table.add_column("Last Synced", style="magenta")

    # Sort by priority (descending)
    sorted_repos = sorted(repos.items(), key=lambda x: x[1].get('priority', 0), reverse=True)

    for name, config in sorted_repos:
        # Format status
        if config.get('enabled', True):
            status = "[green]✓ Enabled[/]"
        else:
            status = "[red]✗ Disabled[/]"

        # Format last synced
        last_synced = config.get('last_synced')
        if last_synced:
            try:
                synced_dt = datetime.fromisoformat(last_synced)
                time_ago = datetime.now() - synced_dt
                if time_ago.days > 0:
                    synced_str = f"{time_ago.days}d ago"
                elif time_ago.seconds > 3600:
                    synced_str = f"{time_ago.seconds // 3600}h ago"
                else:
                    synced_str = f"{time_ago.seconds // 60}m ago"
            except:
                synced_str = "Unknown"
        else:
            synced_str = "Never"

        # Truncate URL if too long
        url = config.get('url', '')
        if len(url) > 50:
            url = url[:47] + "..."

        table.add_row(
            name,
            url,
            str(config.get('priority', 0)),
            status,
            synced_str
        )

    console.print(table)


@repo.command(name='add')
@click.argument('name')
@click.argument('url')
@click.option('--priority', type=int, default=10, help='Repository priority (higher = checked first)')
@click.option('--branch', default='main', help='Git branch to use')
@click.option('--description', help='Repository description')
def repo_add(name, url, priority, branch, description):
    """Add a new template repository."""
    from multicord.utils.template_repository import TemplateRepository

    template_repo = TemplateRepository()

    try:
        template_repo.add_repository(
            name=name,
            url=url,
            priority=priority,
            branch=branch,
            description=description or f"Custom repository: {name}"
        )
        display.success(f"Repository '{name}' added successfully")
        display.info(f"Run 'multicord repo update {name}' to fetch templates")
    except ValueError as e:
        display.error(str(e))
        sys.exit(1)
    except Exception as e:
        display.error(f"Failed to add repository: {e}")
        sys.exit(1)


@repo.command(name='remove')
@click.argument('name')
@click.confirmation_option(prompt='Are you sure you want to remove this repository?')
def repo_remove(name):
    """Remove a template repository."""
    from multicord.utils.template_repository import TemplateRepository

    template_repo = TemplateRepository()

    try:
        if template_repo.remove_repository(name):
            display.success(f"Repository '{name}' removed successfully")
        else:
            display.error(f"Repository '{name}' not found")
            sys.exit(1)
    except ValueError as e:
        display.error(str(e))
        sys.exit(1)
    except Exception as e:
        display.error(f"Failed to remove repository: {e}")
        sys.exit(1)


@repo.command(name='update')
@click.argument('name', required=False)
@click.option('--all', 'update_all', is_flag=True, help='Update all repositories')
def repo_update(name, update_all):
    """Update repository (git pull)."""
    from multicord.utils.template_repository import TemplateRepository

    template_repo = TemplateRepository()

    if update_all:
        # Update all enabled repositories
        repos = template_repo.list_repositories(enabled_only=True)
        if not repos:
            display.info("No enabled repositories to update")
            return

        display.info(f"Updating {len(repos)} repositories...")

        success_count = 0
        for repo_name in repos.keys():
            try:
                console.print(f"  [cyan]→[/] {repo_name}...", end=" ")
                template_repo.clone_repository(repo_name, force_update=True)
                console.print("[green]✓[/]")
                success_count += 1
            except Exception as e:
                console.print(f"[red]✗ {e}[/]")

        display.success(f"Updated {success_count}/{len(repos)} repositories")

    elif name:
        # Update specific repository
        try:
            display.info(f"Updating repository '{name}'...")
            template_repo.clone_repository(name, force_update=True)
            display.success(f"Repository '{name}' updated successfully")
        except ValueError as e:
            display.error(str(e))
            sys.exit(1)
        except Exception as e:
            display.error(f"Failed to update repository: {e}")
            sys.exit(1)
    else:
        display.error("Specify a repository name or use --all")
        sys.exit(1)


@repo.command(name='info')
@click.argument('name')
def repo_info(name):
    """Show detailed repository information."""
    from multicord.utils.template_repository import TemplateRepository

    template_repo = TemplateRepository()
    config = template_repo.get_repository_config(name)

    if not config:
        display.error(f"Repository '{name}' not found")
        sys.exit(1)

    console.print(f"\n[bold cyan]Repository: {name}[/]\n")
    console.print(f"[bold]Name:[/] {config.get('name', name)}")
    console.print(f"[bold]URL:[/] {config.get('url', 'Unknown')}")
    console.print(f"[bold]Type:[/] {config.get('type', 'custom')}")
    console.print(f"[bold]Branch:[/] {config.get('branch', 'main')}")
    console.print(f"[bold]Priority:[/] {config.get('priority', 0)}")
    console.print(f"[bold]Status:[/] {'Enabled' if config.get('enabled', True) else 'Disabled'}")
    console.print(f"[bold]Auto-update:[/] {'Yes' if config.get('auto_update', False) else 'No'}")

    last_synced = config.get('last_synced')
    if last_synced:
        console.print(f"[bold]Last Synced:[/] {last_synced}")
    else:
        console.print(f"[bold]Last Synced:[/] Never")

    description = config.get('description', '')
    if description:
        console.print(f"[bold]Description:[/] {description}")

    # Try to get template count
    try:
        templates = template_repo.list_templates(name)
        console.print(f"[bold]Templates:[/] {len(templates)}")
    except:
        pass

    console.print()


@repo.command(name='priority')
@click.argument('name')
@click.argument('priority', type=int)
def repo_priority(name, priority):
    """Set repository priority (higher = checked first)."""
    from multicord.utils.template_repository import TemplateRepository

    template_repo = TemplateRepository()

    try:
        template_repo.set_repository_priority(name, priority)
        display.success(f"Repository '{name}' priority set to {priority}")
    except ValueError as e:
        display.error(str(e))
        sys.exit(1)
    except Exception as e:
        display.error(f"Failed to set priority: {e}")
        sys.exit(1)


@repo.command(name='enable')
@click.argument('name')
def repo_enable(name):
    """Enable a repository."""
    from multicord.utils.template_repository import TemplateRepository

    template_repo = TemplateRepository()

    try:
        template_repo.enable_repository(name)
        display.success(f"Repository '{name}' enabled")
    except ValueError as e:
        display.error(str(e))
        sys.exit(1)
    except Exception as e:
        display.error(f"Failed to enable repository: {e}")
        sys.exit(1)


@repo.command(name='disable')
@click.argument('name')
def repo_disable(name):
    """Disable a repository."""
    from multicord.utils.template_repository import TemplateRepository

    template_repo = TemplateRepository()

    try:
        template_repo.disable_repository(name)
        display.success(f"Repository '{name}' disabled")
    except ValueError as e:
        display.error(str(e))
        sys.exit(1)
    except Exception as e:
        display.error(f"Failed to disable repository: {e}")
        sys.exit(1)


@cli.group()
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
        icon = "[OK]" if passed else "[FAIL]"
        color = "green" if passed else "red"
        console.print(f"[{color}]{icon}[/{color}] {check}: {status}")
    
    # Overall status
    all_passed = all(p for _, _, p in checks if _ != "Authentication")
    if all_passed:
        display.success("\nAll checks passed! MultiCord is ready to use.")
    else:
        display.warning("\nSome checks failed. Please install missing dependencies.")


@cli.group()
def cog():
    """Manage bot cogs and extensions."""
    pass


@cog.command()
def available():
    """List all available cogs from repository."""
    from multicord.utils.template_repository import TemplateRepository
    from multicord.utils.cog_repository import CogRepository

    # Get template repository
    template_repo = TemplateRepository()

    try:
        # Clone/update repository
        repo_path = template_repo.clone_repository('official')

        # Get cog repository
        cog_repo = CogRepository(repo_path)
        available_cogs = cog_repo.list_available_cogs()

        if not available_cogs:
            display.warning("No cogs available in repository")
            return

        console.print("\n[bold cyan]Available Cogs[/]\n")

        # Group cogs by category
        from collections import defaultdict
        by_category = defaultdict(list)

        for cog_id, cog_info in available_cogs.items():
            category = cog_info.get('category', 'other')
            by_category[category].append((cog_id, cog_info))

        # Display by category
        for category, cogs in sorted(by_category.items()):
            # Get category display name
            category_name = category.replace('_', ' ').title()
            console.print(f"\n[yellow]{category_name}[/]")

            for cog_id, cog_info in sorted(cogs, key=lambda x: x[1].get('name', '')):
                name = cog_info.get('name', cog_id)
                desc = cog_info.get('description', 'No description')
                version = cog_info.get('version', '?.?.?')
                author = cog_info.get('author', 'Unknown')
                featured = ' ⭐' if cog_info.get('featured') else ''

                console.print(f"  [cyan]{cog_id}[/] ({version}){featured}")
                console.print(f"    {desc}")
                console.print(f"    [dim]by {author}[/]\n")

        display.success(f"Total: {len(available_cogs)} cogs available")

    except Exception as e:
        display.error(f"Failed to list cogs: {e}")


@cog.command()
@click.argument('bot_name')
def list(bot_name):
    """List installed cogs for a bot."""
    from multicord.local.bot_manager import BotManager
    from multicord.utils.template_repository import TemplateRepository
    from multicord.utils.cog_repository import CogRepository

    manager = BotManager()
    bot_path = manager.bots_dir / bot_name

    if not bot_path.exists():
        display.error(f"Bot '{bot_name}' not found")
        return

    # Get cog repository for metadata
    template_repo = TemplateRepository()
    try:
        repo_path = template_repo.clone_repository('official')
        cog_repo = CogRepository(repo_path)
    except:
        cog_repo = None

    # Get installed cogs
    installed = cog_repo.list_installed_cogs(bot_path) if cog_repo else []

    if not installed:
        display.warning(f"No cogs installed in '{bot_name}'")
        return

    console.print(f"\n[bold cyan]Installed Cogs for '{bot_name}'[/]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Cog", style="cyan")
    table.add_column("Version")
    table.add_column("Description")

    for cog_name in sorted(installed):
        # Try to get cog info
        cog_info = cog_repo.get_installed_cog_info(bot_path, cog_name) if cog_repo else {}

        version = cog_info.get('version', '?.?.?')
        description = cog_info.get('description', 'No description')

        table.add_row(cog_name, version, description)

    console.print(table)
    display.success(f"Total: {len(installed)} cogs installed")


@cog.command()
@click.argument('bot_name')
@click.argument('cog_name')
def add(bot_name, cog_name):
    """Add a cog to an existing bot."""
    from multicord.local.bot_manager import BotManager
    from multicord.utils.template_repository import TemplateRepository
    from multicord.utils.cog_repository import CogRepository

    manager = BotManager()
    bot_path = manager.bots_dir / bot_name

    if not bot_path.exists():
        display.error(f"Bot '{bot_name}' not found")
        return

    display.info(f"Installing cog '{cog_name}' into '{bot_name}'...")

    try:
        # Get template repository
        template_repo = TemplateRepository()
        repo_path = template_repo.clone_repository('official')

        # Get cog repository
        cog_repo = CogRepository(repo_path)

        # Check if cog exists
        cog_metadata = cog_repo.get_cog_metadata(cog_name)
        if not cog_metadata:
            display.error(f"Cog '{cog_name}' not found in repository")
            return

        # Install the cog
        cog_repo.install_cog(bot_path, cog_name)

        display.success(f"✓ Cog '{cog_name}' installed successfully")

        # Show next steps
        console.print("\n[yellow]Next steps:[/]")
        console.print(f"  1. The cog has been copied to {bot_path / 'cogs' / cog_name}")
        console.print(f"  2. Dependencies have been installed automatically")
        console.print(f"  3. Restart your bot to load the cog")
        console.print(f"  4. Use the cog's commands (see README in cog directory)")

    except ValueError as e:
        display.error(str(e))
    except Exception as e:
        display.error(f"Failed to install cog: {e}")


@cog.command()
@click.argument('bot_name')
@click.argument('cog_name')
def remove(bot_name, cog_name):
    """Remove a cog from a bot."""
    from multicord.local.bot_manager import BotManager
    from multicord.utils.template_repository import TemplateRepository
    from multicord.utils.cog_repository import CogRepository

    manager = BotManager()
    bot_path = manager.bots_dir / bot_name

    if not bot_path.exists():
        display.error(f"Bot '{bot_name}' not found")
        return

    if not click.confirm(f"Remove cog '{cog_name}' from '{bot_name}'?"):
        display.info("Removal cancelled")
        return

    try:
        # Get template repository
        template_repo = TemplateRepository()
        repo_path = template_repo.clone_repository('official')

        # Get cog repository
        cog_repo = CogRepository(repo_path)

        # Remove the cog
        cog_repo.remove_cog(bot_path, cog_name)

        display.success(f"✓ Cog '{cog_name}' removed successfully")
        display.warning("Note: Dependencies were not uninstalled automatically")

    except ValueError as e:
        display.error(str(e))
    except Exception as e:
        display.error(f"Failed to remove cog: {e}")


@cog.command()
@click.argument('bot_name')
@click.option('--all', 'update_all', is_flag=True, help='Update all installed cogs')
@click.argument('cog_name', required=False)
def update(bot_name, update_all, cog_name):
    """Update cogs in a bot to latest version."""
    from multicord.local.bot_manager import BotManager
    from multicord.utils.template_repository import TemplateRepository
    from multicord.utils.cog_repository import CogRepository

    manager = BotManager()
    bot_path = manager.bots_dir / bot_name

    if not bot_path.exists():
        display.error(f"Bot '{bot_name}' not found")
        return

    try:
        # Get repositories
        template_repo = TemplateRepository()
        repo_path = template_repo.clone_repository('official')
        cog_repo = CogRepository(repo_path)

        if update_all:
            # Update all installed cogs
            installed = cog_repo.list_installed_cogs(bot_path)

            if not installed:
                display.warning("No cogs installed")
                return

            display.info(f"Updating {len(installed)} cogs...")

            for cog in installed:
                try:
                    cog_repo.update_cog(bot_path, cog)
                    display.success(f"✓ Updated {cog}")
                except Exception as e:
                    display.error(f"✗ Failed to update {cog}: {e}")

            display.success("Update complete")

        elif cog_name:
            # Update specific cog
            display.info(f"Updating cog '{cog_name}'...")
            cog_repo.update_cog(bot_path, cog_name)
            display.success(f"✓ Cog '{cog_name}' updated successfully")

        else:
            display.error("Specify a cog name or use --all to update all cogs")

    except ValueError as e:
        display.error(str(e))
    except Exception as e:
        display.error(f"Failed to update cog: {e}")


if __name__ == "__main__":
    cli()