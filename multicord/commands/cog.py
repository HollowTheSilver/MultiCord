"""Cog management commands for MultiCord CLI."""

import shutil
import click
from rich.console import Console
from rich.table import Table
from collections import defaultdict

from multicord.local.bot_manager import BotManager
from multicord.utils.display import Display
from multicord.utils.source_resolver import SourceResolver, discover_cog_structure

display = Display()
console = Console()


@click.group()
def cog():
    """Manage bot cogs and extensions."""
    pass


@cog.command(name='available')
def bot_cog_available():
    """List all available cogs from official sources and imported repos."""
    resolver = SourceResolver()
    sources = resolver.list_sources()

    # Filter to cogs only
    cogs = {name: info for name, info in sources.items() if info.get('type') == 'cog'}

    if not cogs:
        display.warning("No cogs available")
        return

    console.print("\n[bold cyan]Available Cogs[/]\n")

    # Group by source type
    by_source = defaultdict(list)
    for cog_name, cog_info in cogs.items():
        source_type = cog_info.get('source', 'unknown')
        by_source[source_type].append((cog_name, cog_info))

    # Display built-ins first
    if 'built-in' in by_source:
        console.print("[yellow]BUILT-IN (always available)[/]")
        for cog_name, cog_info in sorted(by_source['built-in'], key=lambda x: x[0]):
            cached = " (cached)" if cog_info.get('cached') else ""
            console.print(f"  [cyan]{cog_name}[/]{cached}")
            console.print(f"    {cog_info.get('description', 'No description')}")
        console.print()

    # Display imported repos
    if 'imported' in by_source:
        console.print("[yellow]IMPORTED (Git repos)[/]")
        for cog_name, cog_info in sorted(by_source['imported'], key=lambda x: x[0]):
            console.print(f"  [cyan]{cog_name}[/]")
            console.print(f"    {cog_info.get('description', 'No description')}")
            console.print(f"    [dim]{cog_info.get('url', '')}[/]")
        console.print()

    display.success(f"Total: {len(cogs)} cogs available")
    display.info("Install with: multicord bot cog add <cog-name> <bot-name>")


@cog.command(name='list')
@click.argument('bot_name')
def bot_cog_list(bot_name):
    """List installed cogs for a bot."""
    from multicord.utils.cog_manager import CogManager

    manager = BotManager()
    bot_path = manager.bots_dir / bot_name

    if not bot_path.exists():
        display.error(f"Bot '{bot_name}' not found")
        return

    # Get cog repository for metadata
    resolver = SourceResolver()
    try:
        # Any official cog to get repo path
        official_path = resolver.resolve_source('permissions')
        cog_manager = CogManager(official_path.parent)
    except:
        cog_manager = None

    # Get installed cogs
    installed = cog_manager.list_installed_cogs(bot_path) if cog_manager else []

    if not installed:
        display.warning(f"No cogs installed in '{bot_name}'")
        display.info(f"Install with: multicord bot cog add <cog-name> {bot_name}")
        return

    console.print(f"\n[bold cyan]Installed Cogs for '{bot_name}'[/]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Cog", style="cyan")
    table.add_column("Version")
    table.add_column("Description")

    for cog_name in sorted(installed):
        cog_info = cog_manager.get_installed_cog_info(bot_path, cog_name) if cog_manager else {}

        version = cog_info.get('version', '?.?.?')
        description = cog_info.get('description', 'No description')

        table.add_row(cog_name, version, description)

    console.print(table)
    display.success(f"Total: {len(installed)} cogs installed")


@cog.command(name='add')
@click.argument('cog_name')
@click.argument('bot_name')
@click.option('--offline', is_flag=True, help='Use cached sources without network updates')
@click.option('--force-update', is_flag=True, help='Force update source before installing')
@click.option('--no-deps', is_flag=True, help='Skip automatic dependency installation')
def bot_cog_add(cog_name, bot_name, offline, force_update, no_deps):
    """Add a cog to an existing bot.

    Cogs are automatically resolved from:
    1. Official built-ins (permissions, moderation, music)
    2. Your imported repos (from 'multicord repo import')

    Examples:
        multicord bot cog add permissions my-bot     # Official cog
        multicord bot cog add my-custom-cog my-bot   # From imported repo
    """
    import os
    from multicord.utils.cog_manager import CogManager, CircularDependencyError

    # Set environment variables for Git operations
    if offline:
        os.environ['MULTICORD_OFFLINE'] = '1'

    manager = BotManager()
    bot_path = manager.bots_dir / bot_name

    if not bot_path.exists():
        display.error(f"Bot '{bot_name}' not found")
        return

    display.info(f"Installing cog '{cog_name}' into '{bot_name}'...")

    try:
        # Resolve cog source (auto-fetches if official and not cached)
        resolver = SourceResolver()
        cog_source_path = resolver.resolve_source(cog_name, force_update=force_update)

        # Get cog repository for installation
        cog_manager = CogManager(cog_source_path.parent)

        # Check if cog exists in resolved path
        cog_metadata = cog_manager.get_cog_metadata(cog_name)
        if not cog_metadata:
            # The source might be the cog itself (not a collection)
            # Use intelligent discovery to find package and metadata
            try:
                package_path, metadata_path = discover_cog_structure(cog_source_path, cog_name)
            except ValueError as e:
                display.error(str(e))
                return

            # It's a standalone cog - install directly
            cogs_dir = bot_path / 'cogs'
            cogs_dir.mkdir(exist_ok=True)
            dest_path = cogs_dir / cog_name

            if dest_path.exists():
                display.warning(f"Cog '{cog_name}' already installed, updating...")
                shutil.rmtree(dest_path)

            # Copy the Python package
            SourceResolver.copy_source_files(package_path, dest_path)

            # Copy metadata file if found
            if metadata_path:
                metadata_dest = dest_path / metadata_path.name
                shutil.copy2(metadata_path, metadata_dest)
                display.info(f"Copied metadata: {metadata_path.name}")

            display.success(f"Cog '{cog_name}' installed successfully")
            console.print("\n[yellow]Next steps:[/]")
            console.print(f"  1. Restart your bot to load the cog")
            console.print(f"  2. Use the cog's commands (see README in cog directory)")
            return

        # Check for dependencies
        missing_deps = cog_manager.check_missing_dependencies(bot_path, cog_name)
        if missing_deps and not no_deps:
            console.print(f"\n[cyan]Checking dependencies for '{cog_name}'...[/]")
            for dep_name, version_req in missing_deps:
                console.print(f"  [yellow]![/] Missing: {dep_name} ({version_req})")

            if not click.confirm("\nInstall dependencies automatically?", default=True):
                display.warning("Installation cancelled (dependencies required)")
                return

            # Show dependency installation progress
            console.print()
            deps_to_install = cog_manager.resolve_dependencies(cog_name, bot_path)
            for dep_name in deps_to_install:
                console.print(f"  Installing {dep_name}...", end=" ")
                cog_manager.install_cog(bot_path, dep_name, auto_install_deps=False)
                console.print("[green]done[/]")

        # Install the cog
        console.print(f"  Installing {cog_name}...", end=" ")
        cog_manager.install_cog(bot_path, cog_name, auto_install_deps=not no_deps)
        console.print("[green]done[/]")

        display.success(f"\nCog '{cog_name}' installed successfully")

        # Show next steps
        console.print("\n[yellow]Next steps:[/]")
        console.print(f"  1. Restart your bot to load the cog")
        console.print(f"  2. Use the cog's commands (see README in cog directory)")

    except CircularDependencyError as e:
        display.error(f"Circular dependency detected: {e}")
    except ValueError as e:
        display.error(str(e))
    except Exception as e:
        display.error(f"Failed to install cog: {e}")


@cog.command(name='remove')
@click.argument('cog_name')
@click.argument('bot_name')
def bot_cog_remove(cog_name, bot_name):
    """Remove a cog from a bot."""
    manager = BotManager()
    bot_path = manager.bots_dir / bot_name

    if not bot_path.exists():
        display.error(f"Bot '{bot_name}' not found")
        return

    cog_path = bot_path / 'cogs' / cog_name

    if not cog_path.exists():
        display.error(f"Cog '{cog_name}' not installed in '{bot_name}'")
        return

    if not click.confirm(f"Remove cog '{cog_name}' from '{bot_name}'?"):
        display.info("Removal cancelled")
        return

    try:
        shutil.rmtree(cog_path)
        display.success(f"Cog '{cog_name}' removed successfully")
        display.warning("Note: Dependencies were not uninstalled automatically")
        console.print(f"[dim]  To clean up unused packages: multicord venv clean {bot_name}[/]")
        console.print(f"\n[dim]Restart your bot to apply changes[/]")

    except Exception as e:
        display.error(f"Failed to remove cog: {e}")


@cog.command(name='update')
@click.argument('cog_name', required=False)
@click.argument('bot_name')
@click.option('--all', 'update_all', is_flag=True, help='Update all installed cogs')
def bot_cog_update(cog_name, bot_name, update_all):
    """Update cogs in a bot to latest version."""
    manager = BotManager()
    bot_path = manager.bots_dir / bot_name

    if not bot_path.exists():
        display.error(f"Bot '{bot_name}' not found")
        return

    resolver = SourceResolver()

    try:
        if update_all:
            # Update all installed cogs
            cogs_dir = bot_path / 'cogs'
            if not cogs_dir.exists():
                display.warning("No cogs installed")
                return

            installed = [d.name for d in cogs_dir.iterdir() if d.is_dir() and (d / '__init__.py').exists()]

            if not installed:
                display.warning("No cogs installed")
                return

            display.info(f"Updating {len(installed)} cogs...")

            for cog_item in installed:
                try:
                    cog_source = resolver.resolve_source(cog_item, force_update=True)

                    cog_dest = cogs_dir / cog_item
                    if cog_dest.exists():
                        shutil.rmtree(cog_dest)
                    SourceResolver.copy_source_files(cog_source, cog_dest)

                    display.success(f"Updated {cog_item}")
                except Exception as e:
                    display.warning(f"Failed to update {cog_item}: {e}")

            display.success("Update complete")

        elif cog_name:
            # Update specific cog
            display.info(f"Updating cog '{cog_name}'...")

            cog_source = resolver.resolve_source(cog_name, force_update=True)
            cog_dest = bot_path / 'cogs' / cog_name

            if cog_dest.exists():
                shutil.rmtree(cog_dest)
            SourceResolver.copy_source_files(cog_source, cog_dest)

            display.success(f"Cog '{cog_name}' updated successfully")
            console.print(f"\n[dim]Restart your bot to apply changes[/]")

        else:
            display.error("Specify a cog name or use --all to update all cogs")

    except Exception as e:
        display.error(f"Failed to update cog: {e}")
