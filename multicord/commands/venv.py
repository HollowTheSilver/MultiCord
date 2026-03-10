"""Virtual environment management commands for MultiCord CLI."""

import click
from rich.console import Console
from rich.table import Table

from multicord.utils.display import Display

# Initialize display and console
display = Display()
console = Console()


@click.group()
def venv():
    """Manage bot virtual environments."""
    pass


@venv.command()
@click.argument('bot_name')
@click.option('--upgrade', is_flag=True, help='Upgrade existing packages')
def install(bot_name, upgrade):
    """Install/reinstall bot dependencies from requirements.txt"""
    from multicord.local.bot_manager import BotManager

    manager = BotManager()
    bot_path = manager.bots_dir / bot_name

    if not bot_path.exists():
        display.error(f"Bot '{bot_name}' not found")
        return

    requirements_file = bot_path / "requirements.txt"
    if not requirements_file.exists():
        display.warning(f"No requirements.txt found for '{bot_name}'")
        return

    display.info(f"Installing dependencies for '{bot_name}'...")

    try:
        success, msg = manager.venv_manager.install_requirements(bot_path, upgrade=upgrade)
        if success:
            display.success(f"✓ {msg}")
        else:
            display.error(f"✗ {msg}")
    except Exception as e:
        display.error(f"Failed to install dependencies: {e}")


@venv.command()
@click.argument('bot_name')
def clean(bot_name):
    """Remove and recreate bot's venv from scratch"""
    from multicord.local.bot_manager import BotManager

    manager = BotManager()
    bot_path = manager.bots_dir / bot_name

    if not bot_path.exists():
        display.error(f"Bot '{bot_name}' not found")
        return

    if not click.confirm(f"Recreate virtual environment for '{bot_name}'?"):
        display.info("Clean cancelled")
        return

    display.info(f"Cleaning virtual environment for '{bot_name}'...")

    try:
        success, msg = manager.venv_manager.clean_venv(bot_path)
        if success:
            display.success(f"✓ {msg}")
        else:
            display.error(f"✗ {msg}")
    except Exception as e:
        display.error(f"Failed to clean venv: {e}")


@venv.command()
@click.argument('bot_name')
def update(bot_name):
    """Upgrade all packages in bot's venv to latest versions"""
    from multicord.local.bot_manager import BotManager

    manager = BotManager()
    bot_path = manager.bots_dir / bot_name

    if not bot_path.exists():
        display.error(f"Bot '{bot_name}' not found")
        return

    display.info(f"Updating packages for '{bot_name}'...")

    try:
        success, msg = manager.venv_manager.update_venv(bot_path)
        if success:
            display.success(f"✓ {msg}")
        else:
            display.error(f"✗ {msg}")
    except Exception as e:
        display.error(f"Failed to update packages: {e}")


@venv.command()
@click.argument('bot_name', required=False)
@click.option('--all', 'show_all', is_flag=True, help='Show info for all bots')
def info(bot_name, show_all):
    """Show venv information (Python version, packages, disk usage)"""
    from multicord.local.bot_manager import BotManager

    manager = BotManager()

    if show_all:
        # Show info for all bots
        venvs = manager.venv_manager.list_all_venvs()

        if not venvs:
            display.warning("No bots found")
            return

        console.print("\n[bold cyan]Virtual Environments[/]\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Bot", style="cyan")
        table.add_column("Status")
        table.add_column("Python")
        table.add_column("Packages")
        table.add_column("Disk Usage")

        for venv_info in venvs:
            bot = venv_info['bot_name']
            exists = venv_info['exists']
            valid = venv_info['valid']

            if not exists:
                table.add_row(bot, "[red]Missing[/]", "-", "-", "-")
            elif not valid:
                table.add_row(bot, "[yellow]Invalid[/]", "-", "-", "-")
            else:
                py_version = venv_info.get('python_version', '?').replace('Python ', '')
                pkg_count = venv_info.get('package_count', 0)
                disk_mb = venv_info.get('disk_usage_mb', 0)
                table.add_row(
                    bot,
                    "[green]Valid[/]",
                    py_version,
                    str(pkg_count),
                    f"{disk_mb} MB"
                )

        console.print(table)

        # Show pip cache info
        cache_info = manager.venv_manager.get_cache_info()
        if cache_info.get('exists'):
            console.print(f"\n[dim]Shared pip cache: {cache_info.get('size_mb', 0)} MB "
                        f"({cache_info.get('file_count', 0)} files)[/]")

    elif bot_name:
        # Show info for specific bot
        bot_path = manager.bots_dir / bot_name

        if not bot_path.exists():
            display.error(f"Bot '{bot_name}' not found")
            return

        venv_info = manager.venv_manager.get_venv_info(bot_path)

        if not venv_info:
            display.error(f"Virtual environment for '{bot_name}' is invalid or missing")
            return

        console.print(f"\n[bold cyan]Virtual Environment: {bot_name}[/]\n")

        # Basic info
        console.print(f"[yellow]Location:[/] {venv_info['venv_path']}")
        console.print(f"[yellow]Python:[/] {venv_info.get('python_version', '?')}")
        console.print(f"[yellow]Packages:[/] {venv_info.get('package_count', 0)}")
        console.print(f"[yellow]Disk Usage:[/] {venv_info.get('disk_usage_mb', 0)} MB")

        # Package list
        packages = venv_info.get('packages', [])
        if packages:
            console.print(f"\n[bold]Installed Packages:[/]\n")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Package", style="cyan")
            table.add_column("Version")

            for pkg in sorted(packages, key=lambda x: x['name'].lower()):
                table.add_row(pkg['name'], pkg['version'])

            console.print(table)

    else:
        display.error("Specify a bot name or use --all to show all bots")
