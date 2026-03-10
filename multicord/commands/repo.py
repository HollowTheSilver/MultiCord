"""Source repository management commands for MultiCord CLI."""

import sys
import click
from rich.console import Console
from rich.table import Table

from multicord.utils.display import Display

# Initialize display and console
display = Display()
console = Console()


@click.group()
def repo():
    """
    Source repository management.

    Sources include bots and cogs. Built-in sources (basic, advanced,
    permissions, moderation, music) are always available without import.

    Use 'repo import' to add third-party Git repositories.
    """
    pass


@repo.command(name='list')
def repo_list():
    """
    List all available sources (built-ins + imported).

    Shows official built-in bots and cogs, plus any
    Git repositories you've imported.
    """
    from multicord.utils.source_resolver import SourceResolver

    resolver = SourceResolver()
    sources = resolver.list_sources()

    if not sources:
        display.info("No sources available")
        return

    # Separate into built-in and imported
    builtins = {k: v for k, v in sources.items() if v.get('source') == 'built-in'}
    imported = {k: v for k, v in sources.items() if v.get('source') == 'imported'}

    # Display built-ins
    console.print("\n[bold yellow]BUILT-IN (always available)[/]")
    console.print("─" * 60)

    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Name", style="cyan", width=15)
    table.add_column("Type", width=10)
    table.add_column("Description")
    table.add_column("Cached", width=8)

    for name in sorted(builtins.keys()):
        info = builtins[name]
        cached = "[green]✓[/]" if info.get('cached') else "[dim]–[/]"
        table.add_row(
            name,
            info.get('type', 'unknown'),
            info.get('description', 'No description'),
            cached
        )

    console.print(table)

    # Display imported
    if imported:
        console.print("\n[bold yellow]IMPORTED (Git repos)[/]")
        console.print("─" * 60)

        table2 = Table(show_header=True, header_style="bold magenta", box=None)
        table2.add_column("Name", style="cyan", width=15)
        table2.add_column("Type", width=10)
        table2.add_column("URL")

        for name in sorted(imported.keys()):
            info = imported[name]
            url = info.get('url', '')
            if len(url) > 40:
                url = url[:37] + "..."
            table2.add_row(
                name,
                info.get('type', 'unknown'),
                url
            )

        console.print(table2)

    console.print()
    display.info("Use built-ins with: multicord bot create my-bot --from basic")
    display.info("Import Git repos with: multicord repo import <git-url> --as <name>")


@repo.command(name='import')
@click.argument('git_url')
@click.option('--as', 'name', required=True, help='Local name for this repository')
@click.option('--description', help='Description of this repository')
def repo_import(git_url, name, description):
    """
    Import a Git repository as a reusable source.

    The repository must be a Git URL (https:// or git@).
    For local directories, use 'multicord bot create --from <local-path>' instead.

    Examples:
        multicord repo import https://github.com/user/cool-template --as cool
        multicord repo import https://github.com/org/utility-cog --as utils
    """
    from multicord.utils.source_resolver import SourceResolver

    # Validate it's a Git URL
    if not (git_url.startswith('https://') or git_url.startswith('git@')):
        display.error("repo import only accepts Git URLs")
        display.info("For local directories, use: multicord bot create --from <local-path>")
        sys.exit(1)

    resolver = SourceResolver()

    try:
        repo_path = resolver.import_repo(git_url, name, description or "")
        console.print(f"\n[dim]Location: {repo_path}[/]")
        display.info(f"Use with: multicord bot create my-bot --from {name}")
    except ValueError as e:
        display.error(str(e))
        sys.exit(1)
    except Exception as e:
        display.error(f"Failed to import repository: {e}")
        sys.exit(1)


@repo.command(name='remove')
@click.argument('name')
def repo_remove(name):
    """
    Remove an imported repository.

    Built-in sources cannot be removed.

    Example:
        multicord repo remove my-custom-template
    """
    from multicord.utils.source_resolver import SourceResolver

    resolver = SourceResolver()

    if not click.confirm(f"Remove repository '{name}'?"):
        display.info("Removal cancelled")
        return

    try:
        resolver.remove_repo(name)
    except ValueError as e:
        display.error(str(e))
        sys.exit(1)
    except Exception as e:
        display.error(f"Failed to remove repository: {e}")
        sys.exit(1)


@repo.command(name='update')
@click.argument('name')
def repo_update(name):
    """
    Update a repository (git pull).

    Works for both built-in sources and imported repositories.

    Examples:
        multicord repo update basic           # Update built-in
        multicord repo update my-custom       # Update imported
    """
    from multicord.utils.source_resolver import SourceResolver

    resolver = SourceResolver()

    try:
        resolver.update_repo(name)
    except ValueError as e:
        display.error(str(e))
        sys.exit(1)
    except Exception as e:
        display.error(f"Failed to update repository: {e}")
        sys.exit(1)


@repo.command(name='info')
@click.argument('name')
def repo_info(name):
    """
    Show detailed information about a source.

    Example:
        multicord repo info permissions
    """
    from multicord.utils.source_resolver import SourceResolver

    resolver = SourceResolver()
    info = resolver.get_source_info(name)

    if not info:
        display.error(f"Source '{name}' not found")
        display.info("Use 'multicord repo list' to see available sources")
        sys.exit(1)

    console.print(f"\n[bold cyan]Source: {name}[/]\n")
    console.print(f"[bold]Type:[/] {info.get('type', 'unknown')}")
    console.print(f"[bold]Source:[/] {info.get('source', 'unknown')}")
    console.print(f"[bold]URL:[/] {info.get('url', 'N/A')}")
    console.print(f"[bold]Description:[/] {info.get('description', 'No description')}")

    if info.get('source') == 'built-in':
        cached = "Yes" if info.get('cached') else "No (will be fetched on first use)"
        console.print(f"[bold]Cached:[/] {cached}")
    else:
        console.print(f"[bold]Last Updated:[/] {info.get('last_updated', 'Unknown')}")

    console.print()
