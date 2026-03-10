"""Bot management commands for MultiCord CLI."""

import sys
import getpass
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table

from multicord.api.client import APIClient
from multicord.local.bot_manager import BotManager
from multicord.docker import DockerManager
from multicord.utils.display import Display
from multicord.utils.source_resolver import SourceResolver, discover_cog_structure
from multicord.utils.errors import handle_error
from multicord.utils.validation import validate_bot_name_callback, validate_cog_name_callback

# Initialize display and console
display = Display()
console = Console()



@click.group()
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
    table.add_column("Port/Source")
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

        # Determine what to show in Port/Source column
        if bot.get('source') == 'local':
            port_or_source = str(bot.get('port', '-'))
        else:
            port_or_source = bot.get('template', '-')

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
            port_or_source,
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
@click.argument('name', callback=validate_bot_name_callback)
@click.option('--from', 'source', default='basic', help='Source: repo name, Git URL, or local path')
@click.option('--cloud', is_flag=True, help='Create in cloud instead of locally')
@click.option('--token', 'set_token_flag', is_flag=True, help='Prompt for Discord token after creation')
def create(name, source, cloud, set_token_flag):
    """Create a new bot from any source.

    Sources can be:
      - Built-in bots: basic, advanced
      - Imported repos: custom repo names
      - Git URLs: https://github.com/user/bot
      - Local paths: ./my-bot or /absolute/path

    Examples:
        multicord bot create my-bot                                    # From 'basic' (default)
        multicord bot create my-bot --from advanced                    # From built-in
        multicord bot create my-bot --from my-repo                     # From imported repo
        multicord bot create my-bot --from https://github.com/user/bot # From Git URL
        multicord bot create my-bot --from ./local-bot                 # From local path
    """
    import getpass
    import re
    from pathlib import Path
    from multicord.utils.source_resolver import SourceResolver

    if cloud:
        client = APIClient()
        if not client.is_authenticated():
            display.error("Please login first: multicord auth login")
            sys.exit(1)

        if set_token_flag:
            display.warning("--token flag is only supported for local bots")

        display.info(f"Creating cloud bot '{name}' from '{source}'...")
        try:
            bot = client.create_bot(name, source)
            display.success(f"Cloud bot created: {bot['id']}")
        except Exception as e:
            display.error(f"Failed to create cloud bot: {e}")
            sys.exit(1)
    else:
        manager = BotManager()
        resolver = SourceResolver()

        # Detect source type: Git URL, local path, or repo name
        is_git_url = source.startswith('https://') or source.startswith('git@')
        is_local_path = not is_git_url and Path(source).exists()

        if is_git_url:
            # Clone from Git URL directly
            display.info(f"Creating bot '{name}' from Git URL...")
            try:
                from multicord.utils.git_operations import GitRepository, GitOperationConfig

                bot_path = manager.bots_dir / name
                if bot_path.exists():
                    display.error(f"Bot '{name}' already exists")
                    sys.exit(1)

                config = GitOperationConfig.from_env()
                git_repo = GitRepository(source, bot_path, 'main', config)
                git_repo.ensure_repository(force_update=False)

                # Create metadata
                import json
                meta_file = bot_path / '.multicord_meta.json'
                meta_file.write_text(json.dumps({
                    'source': 'git',
                    'source_url': source,
                    'created_at': __import__('datetime').datetime.now().isoformat(),
                }, indent=2))

            except Exception as e:
                display.error(f"Failed to clone from Git: {e}")
                sys.exit(1)

        elif is_local_path:
            # Copy from local path directly
            source_path = Path(source).resolve()
            display.info(f"Creating bot '{name}' from local path...")

            if not source_path.is_dir():
                display.error(f"Not a directory: {source}")
                sys.exit(1)

            try:
                bot_path = manager.create_bot_from_path(name, source_path, source_name='local')
            except Exception as e:
                display.error(f"Failed to create from local path: {e}")
                sys.exit(1)

        else:
            # Use existing resolver flow for repo names (built-ins + imported repos)
            display.info(f"Creating local bot '{name}' from '{source}'...")

            try:
                # SourceResolver handles lazy-fetch for built-ins and imported repo lookup
                source_path = resolver.resolve_source(source)
                bot_path = manager.create_bot_from_path(name, source_path, source_name=source)

                # Show success with source info
                meta_file = bot_path / ".multicord_meta.json"
                if meta_file.exists():
                    import json
                    with open(meta_file) as f:
                        meta = json.load(f)
                        used_source = meta.get('source', 'unknown')
                        source_version = meta.get('source_version', 'unknown')
                        display.success(f"Bot created from '{used_source}' (v{source_version})")
                else:
                    display.success(f"Bot created at: {bot_path}")

                console.print(f"\n[dim]Location:[/] {bot_path}")
                console.print(f"[dim]Config:[/] {bot_path}/config.toml")
            except Exception as e:
                display.error(f"Failed to create bot: {e}")
                sys.exit(1)

            # Handle --token flag: prompt for and store Discord token
            token_stored = False
            if set_token_flag:
                console.print()
                try:
                    token_value = getpass.getpass('Discord bot token: ')
                    if token_value:
                        from multicord.utils.token_manager import TokenManager
                        token_mgr = TokenManager()
                        token_mgr.store_token(name, token_value)
                        storage_method = token_mgr.get_storage_method()
                        display.success(f"Token stored securely ({storage_method})")
                        token_stored = True
                    else:
                        display.warning("No token provided, skipping token storage")
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[yellow]Token input cancelled[/]")
                except Exception as e:
                    display.error(f"Failed to store token: {e}")

            # Show start command hint
            console.print(f"\n[yellow]Run with:[/] multicord bot run {name}")
            if token_stored:
                console.print(f"[dim]Tip: Use --follow to watch logs in real-time[/]")


@bot.command()
@click.argument('name', required=True)
@click.option('--docker', 'mode_docker', is_flag=True, help='Force Docker container mode')
@click.option('--local', 'mode_local', is_flag=True, help='Force local process mode')
@click.option('--shards', '-s', default=1, type=int, help='Number of shards (Docker mode, 2500+ guilds)')
@click.option('--rebuild', is_flag=True, help='Force rebuild Docker image (Docker mode)')
@click.option('--env', '-e', multiple=True, help='Environment variables (KEY=VALUE)')
@click.option('--follow', is_flag=True, help='Follow logs after starting')
def run(name, mode_docker, mode_local, shards, rebuild, env, follow):
    """
    Run a bot locally or in Docker.

    By default, auto-detects the best mode:
      - Docker mode if Dockerfile exists and Docker is available
      - Local process mode otherwise

    Use --docker or --local to force a specific mode.

    Examples:
        multicord bot run my-bot                # Auto-detect mode
        multicord bot run my-bot --local        # Force local process
        multicord bot run my-bot --docker       # Force Docker container
        multicord bot run my-bot --shards 4     # Docker with 4 shards
        multicord bot run my-bot --follow       # Follow logs after starting
        multicord bot run my-bot --env LOG_LEVEL=DEBUG
    """
    # Validate mutually exclusive flags
    if mode_docker and mode_local:
        display.error("Cannot use both --docker and --local")
        sys.exit(1)

    # Parse environment variables
    env_vars = {}
    if env:
        for env_arg in env:
            if '=' in env_arg:
                key, value = env_arg.split('=', 1)
                env_vars[key] = value
            else:
                display.warning(f"Ignoring invalid environment variable format: {env_arg}")

    manager = BotManager()

    # Validate bot exists
    bot_path = manager.bots_dir / name
    if not bot_path.exists():
        display.error(f"Bot '{name}' does not exist")
        display.info(f"Create it with: multicord bot create {name} --from <source>")
        sys.exit(1)

    # Determine mode: explicit flag, or auto-detect
    use_docker = False
    if mode_docker:
        use_docker = True
    elif mode_local:
        use_docker = False
    else:
        # Auto-detect: use Docker if Dockerfile exists and Docker is available
        dockerfile_exists = (bot_path / "Dockerfile").exists()
        docker_available = False
        if dockerfile_exists:
            try:
                docker_mgr = DockerManager()
                docker_available = True
            except Exception:
                pass
        use_docker = dockerfile_exists and docker_available

    if use_docker:
        # ═══════════════════════════════════════════════════════════════
        # DOCKER MODE
        # ═══════════════════════════════════════════════════════════════
        try:
            docker_mgr = DockerManager()
        except Exception as e:
            display.error(f"Docker not available: {e}")
            display.info("Use --local to run as a local process instead")
            sys.exit(1)

        # Validate shards
        if shards < 1:
            display.error("Shards must be at least 1")
            sys.exit(1)

        if shards > 16:
            display.error("Shards cannot exceed 16 (Discord limitation)")
            display.info("For larger deployments, contact Discord for increased shard limits")
            sys.exit(1)

        if shards > 1:
            display.info(f"Running bot '{name}' with {shards} shards in Docker...")
        else:
            display.info(f"Running bot '{name}' in Docker...")

        # Build or rebuild Docker image (tag must be lowercase)
        tag = f"multicord/{name.lower()}:latest"

        # Check if image exists
        try:
            existing_images = docker_mgr.docker_client.client.images.list(name=tag)
            image_exists = len(existing_images) > 0
        except Exception:
            image_exists = False

        if rebuild or not image_exists:
            action = "Rebuilding" if rebuild else "Building"
            display.info(f"{action} Docker image for '{name}'...")
            try:
                image_id = docker_mgr.build_image(bot_path, tag=tag, show_progress=True)
                console.print()  # Newline after progress
            except Exception as e:
                display.error(f"Failed to build Docker image: {e}")
                sys.exit(1)
        else:
            display.info(f"Using existing Docker image: {tag}")

        # Check for existing containers and clean them up
        existing_containers = docker_mgr.list_bot_containers(name)
        if existing_containers:
            display.info(f"Found {len(existing_containers)} existing container(s), removing them...")
            for container in existing_containers:
                try:
                    if container.status == "running":
                        docker_mgr.stop_container(container.id, timeout=10)
                    docker_mgr.remove_container(container.id, force=True)
                    display.success(f"✓ Removed container: {container.name}")
                except Exception as cleanup_error:
                    display.warning(f"Failed to remove container {container.name}: {cleanup_error}")

        # Create and start containers (sharded or single)
        if shards > 1:
            display.info(f"Creating {shards} shard containers...")
            try:
                container_ids = docker_mgr.create_sharded_containers(
                    bot_name=name,
                    image_id=tag,
                    shard_count=shards,
                    resource_limits=None
                )
                console.print()
                display.success(f"✓ Bot '{name}' is now running with {shards} shards")
                display.info(f"View status: multicord bot status {name}")
                display.info(f"View logs: multicord bot logs {name} --follow")
                display.info(f"Stop: multicord bot stop {name}")
            except Exception as e:
                display.error(f"Failed to create sharded containers: {e}")
                sys.exit(1)
        else:
            display.info("Creating container...")
            try:
                container_id = docker_mgr.create_container(
                    bot_name=name,
                    image_id=tag,
                    instance_id=1,
                    env_vars=env_vars if env_vars else None,
                    resource_limits=None
                )
                docker_mgr.start_container(container_id)
                console.print()
                display.success(f"✓ Bot '{name}' is now running in Docker")
                display.info(f"View logs: multicord bot logs {name} --follow")
                display.info(f"Stop: multicord bot stop {name}")
            except Exception as e:
                display.error(f"Failed to start container: {e}")
                sys.exit(1)

        if shards > 1:
            display.info("All containers share multicord-network for communication")

        # Follow logs if requested (Docker mode)
        if follow:
            import time
            time.sleep(1)  # Brief pause to let container initialize
            console.print()
            display.info(f"Following logs for '{name}' (Ctrl+C to stop)...")
            try:
                docker_mgr.follow_logs(name)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped following logs[/]")
            except Exception as e:
                display.warning(f"Could not follow logs: {e}")

    else:
        # ═══════════════════════════════════════════════════════════════
        # LOCAL PROCESS MODE
        # ═══════════════════════════════════════════════════════════════
        if shards > 1:
            display.warning("--shards is only supported in Docker mode, ignoring")

        if rebuild:
            display.warning("--rebuild is only supported in Docker mode, ignoring")

        display.info(f"Running bot '{name}' as local process...")
        if env_vars:
            display.info(f"  Injecting {len(env_vars)} environment variable(s)")

        try:
            pid = manager.start_bot(name, env_vars=env_vars)
            status = manager.get_bot_status(name)
            if status and status.get('port'):
                display.success(f"✓ Bot '{name}' started with PID {pid} on port {status['port']}")
            else:
                display.success(f"✓ Bot '{name}' started with PID {pid}")

            display.info(f"View logs: multicord bot logs {name} --follow")
            display.info(f"Stop: multicord bot stop {name}")

        except Exception as e:
            display.error(f"Failed to start bot: {e}")
            sys.exit(1)

        # Follow logs if requested (local mode)
        if follow:
            import time
            time.sleep(0.5)  # Brief pause to let bot initialize
            console.print()
            display.info(f"Following logs for '{name}' (Ctrl+C to stop)...")
            try:
                manager.follow_logs(name)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped following logs[/]")


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

        # Try to initialize Docker manager
        docker_mgr = None
        try:
            docker_mgr = DockerManager()
        except Exception as docker_init_error:
            # Docker not available, will use local process manager only
            pass

        for name in names:
            try:
                docker_containers = []

                # Check for Docker containers if Docker is available
                if docker_mgr:
                    try:
                        docker_containers = docker_mgr.list_bot_containers(name)
                    except Exception as docker_list_error:
                        # Docker listing failed, fall back to process manager
                        pass

                if docker_containers:
                    # Stop Docker containers
                    display.info(f"Stopping {len(docker_containers)} Docker container(s) for '{name}'...")

                    stopped_count = 0
                    for container in docker_containers:
                        try:
                            timeout = 10 if not force else 5
                            docker_mgr.stop_container(container.id, timeout=timeout)

                            # Remove container after stopping
                            docker_mgr.remove_container(container.id, force=force)

                            stopped_count += 1
                            display.success(f"✓ Stopped container: {container.name}")
                        except Exception as container_error:
                            display.warning(f"Failed to stop container {container.name}: {container_error}")

                    if stopped_count == len(docker_containers):
                        display.success(f"All {stopped_count} container(s) for '{name}' stopped")
                    elif stopped_count > 0:
                        display.warning(f"Stopped {stopped_count}/{len(docker_containers)} container(s)")
                    else:
                        display.error(f"Failed to stop any containers for '{name}'")

                else:
                    # No Docker containers, try local process
                    if force:
                        display.info(f"Force stopping local bot '{name}'...")
                    else:
                        display.info(f"Stopping local bot '{name}'...")

                    manager.stop_bot(name, force=force)
                    display.success(f"Bot '{name}' stopped")

            except Exception as e:
                display.error(f"Failed to stop bot '{name}': {e}")


@bot.command()
@click.argument('name', callback=validate_bot_name_callback)
def status(name):
    """Get detailed status of a bot."""
    from multicord.docker.docker_manager import DockerManager

    manager = BotManager()
    client = APIClient()

    # Check for Docker containers first
    try:
        docker_mgr = DockerManager()
        docker_containers = docker_mgr.list_bot_containers(name)

        if docker_containers:
            # Check if this is a sharded deployment
            is_sharded = any('shard-id' in c.labels for c in docker_containers)

            if is_sharded:
                # Sharded deployment - show shard table
                console.print(f"\n[bold cyan]Docker Bot (Sharded): {name}[/]")

                # Get shard count from first container
                shard_count = docker_containers[0].labels.get('shard-count', len(docker_containers))
                console.print(f"  Shards: {shard_count}")
                console.print()

                # Create Rich table for shards
                table = Table(title=f"{name} - Shard Status", show_header=True, header_style="bold cyan")
                table.add_column("Shard", style="cyan", width=8)
                table.add_column("Container", style="dim")
                table.add_column("Status", width=10)
                table.add_column("Memory", justify="right", width=12)
                table.add_column("CPU", justify="right", width=8)
                table.add_column("Network", justify="right", width=15)

                # Sort containers by shard ID
                sorted_containers = sorted(
                    docker_containers,
                    key=lambda c: int(c.labels.get('shard-id', 0))
                )

                for container in sorted_containers:
                    container.reload()  # Refresh state
                    shard_id = container.labels.get('shard-id', '?')
                    status = container.status
                    status_color = "green" if status == "running" else "red"

                    # Get stats if running
                    memory_str = "-"
                    cpu_str = "-"
                    network_str = "-"
                    if status == "running":
                        try:
                            stats = docker_mgr.get_container_stats(container.id)
                            if stats:
                                memory_str = f"{stats['memory_mb']:.1f} / {stats['memory_limit_mb']:.0f} MB"
                                cpu_str = f"{stats['cpu_percent']:.1f}%"
                                network_str = f"↓{stats['network_rx_mb']:.1f} ↑{stats['network_tx_mb']:.1f} MB"
                        except Exception:
                            pass  # Stats not available

                    table.add_row(
                        f"Shard {shard_id}",
                        container.name,
                        f"[{status_color}]{status}[/{status_color}]",
                        memory_str,
                        cpu_str,
                        network_str
                    )

                console.print(table)
                console.print()

            else:
                # Single container deployment - traditional display
                console.print(f"\n[bold cyan]Docker Bot: {name}[/]")
                console.print(f"  Containers: {len(docker_containers)}")

                for idx, container in enumerate(docker_containers, 1):
                    container.reload()  # Refresh container state
                    status = container.status
                    status_color = "green" if status == "running" else "red"

                    console.print(f"\n  [bold]Container {idx}:[/] {container.name}")
                    console.print(f"    Status: [{status_color}]{status}[/{status_color}]")
                    console.print(f"    ID: {container.short_id}")
                    console.print(f"    Image: {container.image.tags[0] if container.image.tags else 'none'}")

                    # Get stats if running
                    if status == "running":
                        try:
                            stats = docker_mgr.get_container_stats(container.id)
                            if stats:
                                console.print(f"\n    [yellow]Health Metrics:[/]")
                                console.print(f"      Memory: {stats['memory_mb']:.1f} MB / {stats['memory_limit_mb']:.1f} MB")
                                console.print(f"      CPU: {stats['cpu_percent']:.1f}%")
                                console.print(f"      Network RX: {stats['network_rx_mb']:.2f} MB")
                                console.print(f"      Network TX: {stats['network_tx_mb']:.2f} MB")
                        except Exception as e:
                            # Stats not available - don't show metrics section at all
                            pass

            return  # Docker containers found, skip process check
    except Exception:
        pass  # Docker not available or error, fall back to process check

    # Try local process
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
@click.argument('name', callback=validate_bot_name_callback)
@click.option('--lines', '--tail', default=50, help='Number of log lines to show')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
@click.option('--instance', '-i', default=None, type=int, help='Container instance number (for Docker bots)')
def logs(name, lines, follow, instance):
    """
    View bot logs (process or Docker container).

    Automatically detects if the bot is running in Docker containers
    or as a local process and displays the appropriate logs.

    Examples:
        multicord bot logs my-bot                      # Last 50 lines
        multicord bot logs my-bot --follow             # Stream logs live
        multicord bot logs my-bot --instance 2         # View container instance 2
        multicord bot logs my-bot -f -i 1              # Follow instance 1 logs
    """
    from multicord.docker.docker_client import DockerConnectionError

    manager = BotManager()

    # Try Docker first, but gracefully fall back if Docker unavailable
    docker_containers = []
    try:
        docker_mgr = DockerManager()
        docker_containers = docker_mgr.list_bot_containers(name)
    except DockerConnectionError:
        # Docker not available - will use process logs
        pass

    try:

        if docker_containers:
            # Docker mode
            if len(docker_containers) > 1 and instance is None:
                # Multiple containers, user needs to specify which one
                display.warning(f"Bot '{name}' has {len(docker_containers)} running containers")
                display.info("Please specify which instance to view with --instance:")
                for container in docker_containers:
                    # Extract instance ID from container name (multicord_name_N)
                    try:
                        inst_id = int(container.name.split('_')[-1])
                        status_icon = "🟢" if container.status == "running" else "🔴"
                        console.print(f"  {status_icon} Instance {inst_id}: {container.name} ({container.status})")
                    except (ValueError, IndexError):
                        console.print(f"  • {container.name} ({container.status})")
                console.print()
                display.info(f"Example: multicord bot logs {name} --instance 1 --follow")
                sys.exit(0)

            # Select container
            if instance is not None:
                # Find container with matching instance ID (normalize to lowercase)
                container_name = f"multicord_{name.lower()}_{instance}"
                selected_container = None
                for container in docker_containers:
                    if container.name == container_name:
                        selected_container = container
                        break

                if not selected_container:
                    display.error(f"Container instance {instance} not found for bot '{name}'")
                    display.info(f"Available instances: {', '.join([c.name.split('_')[-1] for c in docker_containers])}")
                    sys.exit(1)
            else:
                # Single container, use it
                selected_container = docker_containers[0]

            # Stream Docker logs
            display.info(f"Viewing logs for container: {selected_container.name}")
            if follow:
                display.info("Following logs (Ctrl+C to stop)...")
            console.print()

            try:
                for log_line in docker_mgr.get_container_logs(
                    selected_container.id,
                    follow=follow,
                    tail=lines
                ):
                    # Docker logs come with timestamps and stream prefixes, print as-is
                    console.print(log_line, end='')

            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped following logs[/]")

        else:
            # Local process mode (file-based logs)
            if instance is not None:
                display.warning("--instance flag is only for Docker containers, ignoring")

            if follow:
                display.info(f"Following logs for '{name}' (Ctrl+C to stop)...")
                manager.follow_logs(name)
            else:
                log_lines = manager.get_logs(name, lines)
                for line in log_lines:
                    console.print(line)

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped following logs[/]")
    except Exception as e:
        display.error(f"Failed to get logs: {e}")


@bot.command('set-token')
@click.argument('name', callback=validate_bot_name_callback)
@click.option('--token', default=None,
              help='Discord bot token to store securely')
def set_token(name, token):
    """Set Discord bot token securely.

    Stores the token using Windows Credential Manager (or encrypted file fallback).
    Your token will be encrypted and never stored in plain text.

    Examples:
        multicord bot set-token my-bot              # Interactive prompt (recommended)
        multicord bot set-token my-bot --token xxx  # Provide token directly
    """
    import getpass

    manager = BotManager()

    # If token not provided via flag, prompt interactively
    if not token:
        try:
            token = getpass.getpass('Discord bot token: ')
            if not token:
                display.error("Token cannot be empty")
                sys.exit(1)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled[/]")
            sys.exit(0)

    try:
        manager.set_bot_token(name, token)
        storage_method = manager.get_token_storage_method()
        display.success(f"Token stored securely using: {storage_method}")
        display.info("Old .env file can be safely deleted (token migrated)")
        display.info(f"Start bot with: multicord bot run {name}")
    except ValueError as e:
        display.error(str(e))
        sys.exit(1)
    except Exception as e:
        display.error(f"Failed to store token: {e}")
        sys.exit(1)


@bot.command('migrate-tokens')
@click.option('--all', 'migrate_all', is_flag=True, help='Migrate tokens for all bots')
@click.argument('names', nargs=-1)
def migrate_tokens(migrate_all, names):
    """Migrate Discord tokens from .env files to secure storage.

    Scans .env files for DISCORD_TOKEN and migrates them to encrypted storage.
    Original .env files are backed up as .env.backup.

    Examples:
        multicord bot migrate-tokens my-bot           # Migrate one bot
        multicord bot migrate-tokens bot1 bot2 bot3   # Migrate multiple bots
        multicord bot migrate-tokens --all            # Migrate all bots
    """
    manager = BotManager()

    # Determine which bots to migrate
    if migrate_all:
        # Get all bots
        all_bots = manager.list_bots()
        bot_names = [bot['name'] for bot in all_bots]
        if not bot_names:
            display.warning("No bots found to migrate")
            return
        display.info(f"Migrating tokens for {len(bot_names)} bots...")
    elif names:
        bot_names = names
    else:
        display.error("Please specify bot name(s) or use --all flag")
        display.info("Examples:")
        display.info("  multicord bot migrate-tokens my-bot")
        display.info("  multicord bot migrate-tokens --all")
        sys.exit(1)

    # Migrate each bot
    migrated = 0
    skipped = 0
    failed = 0

    for bot_name in bot_names:
        try:
            success, message = manager.migrate_bot_token(bot_name)
            if success:
                display.success(f"{bot_name}: {message}")
                migrated += 1
            else:
                display.warning(f"{bot_name}: {message}")
                skipped += 1
        except Exception as e:
            display.error(f"{bot_name}: Failed - {e}")
            failed += 1

    # Summary
    console.print()
    display.info(f"Migration complete:")
    display.info(f"  Migrated: {migrated}")
    if skipped:
        display.info(f"  Skipped: {skipped} (already migrated or no valid token)")
    if failed:
        display.error(f"  Failed: {failed}")

    if migrated > 0:
        storage_method = manager.get_token_storage_method()
        display.success(f"All tokens now stored securely using: {storage_method}")


@bot.command()
@click.argument('name', callback=validate_bot_name_callback)
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
@click.argument('name', callback=validate_bot_name_callback)
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
@click.argument('name', callback=validate_bot_name_callback)
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
    """Check if source updates are available for bot(s)."""
    from multicord.utils.update_detector import UpdateDetector

    detector = UpdateDetector()

    if check_all or not name:
        # Check all bots
        display.info("Checking all bots for updates...")

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
        table.add_column("Source", style="blue")

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
                update_info.source_name or "unknown"
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
        console.print(f"[bold]Source:[/] {update_info.source_name}")

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
@click.argument('name', callback=validate_bot_name_callback)
@click.option('--strategy', type=click.Choice(['core-only', 'safe-merge', 'full-replace']),
              default='safe-merge', help='Update strategy (default: safe-merge)')
@click.option('--dry-run', is_flag=True, help='Preview changes without applying')
@click.option('--version', 'target_version', help='Update to specific version (default: latest)')
@click.option('--no-backup', is_flag=True, help='Skip creating backup before update')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt')
def update_bot(name, strategy, dry_run, target_version, no_backup, yes):
    """Update a bot to the latest source version."""
    from multicord.utils.bot_updater import BotUpdater, UpdateStrategy
    from multicord.utils.update_detector import UpdateDetector

    # Map strategy string to enum
    strategy_map = {
        'core-only': UpdateStrategy.CORE_ONLY,
        'safe-merge': UpdateStrategy.SAFE_MERGE,
        'full-replace': UpdateStrategy.FULL_REPLACE
    }
    update_strategy = strategy_map[strategy]

    updater = BotUpdater()
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
@click.argument('name', callback=validate_bot_name_callback)
@click.option('--backup', help='Specific backup file to restore (default: latest)')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt')
def rollback_bot(name, backup, yes):
    """Rollback a bot to a previous backup."""
    from multicord.utils.bot_updater import BotUpdater
    from multicord.utils.backup_manager import BackupManager

    updater = BotUpdater()
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
    console.print(f"[bold]Source Version:[/] {target_backup.template_version}")
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
        console.print(f"[dim]Restored to source version {target_backup.template_version}[/]")
    else:
        display.error("Rollback failed")
        sys.exit(1)


# Register cog subgroup from dedicated module
from multicord.commands.cog import cog
bot.add_command(cog)

# =============================================================================
