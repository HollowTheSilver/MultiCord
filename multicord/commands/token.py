"""Token management commands for MultiCord CLI."""

import sys
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table

from multicord.utils.display import Display

# Initialize display and console
display = Display()
console = Console()


@click.group()
def token():
    """Manage Discord bot tokens and API credentials."""
    pass


@token.command(name='list')
@click.argument('bot_name', required=False)
@click.option('--all', 'show_all', is_flag=True, help='Show all bots including those without tokens')
def token_list(bot_name, show_all):
    """
    List stored bot tokens.

    Shows which bots have tokens stored and their storage method.
    If BOT_NAME provided, shows details for that specific bot.
    If no BOT_NAME, shows summary for all bots.

    Examples:
        multicord token list                # All bots with tokens
        multicord token list --all          # All bots (including without tokens)
        multicord token list my-bot         # Specific bot details
    """
    from multicord.utils.token_manager import TokenManager
    from multicord.local.bot_manager import BotManager

    token_mgr = TokenManager()
    bot_mgr = BotManager()

    if bot_name:
        # Show details for specific bot
        bot_path = bot_mgr.bots_dir / bot_name
        if not bot_path.exists():
            display.error(f"Bot '{bot_name}' does not exist")
            sys.exit(1)

        has_token = token_mgr.has_token(bot_name)
        if has_token:
            storage_method = token_mgr.get_storage_method()
            token_value = token_mgr.get_token(bot_name)

            console.print(f"\n[bold]Token for '{bot_name}'[/bold]")
            console.print("─" * 60)
            console.print(f"Storage:  {storage_method}")
            console.print(f"Status:   [green]✓ Stored securely[/green]")
            console.print(f"Token:    {_mask_token(token_value)} (masked)")

            # Show when token was set (if available)
            from multicord.utils.token_manager import Path as TokenPath
            token_file = TokenPath.home() / '.multicord' / 'config' / 'tokens.json'
            if token_file.exists():
                import json
                tokens_data = json.loads(token_file.read_text())
                if bot_name in tokens_data and 'set_on' in tokens_data[bot_name]:
                    console.print(f"Set on:   {tokens_data[bot_name]['set_on']}")

            console.print("─" * 60)
        else:
            console.print(f"\n[yellow]No token stored for '{bot_name}'[/yellow]")
            console.print(f"Set with: multicord token set {bot_name}")

    else:
        # Show summary for all bots
        all_bots = sorted([d.name for d in bot_mgr.bots_dir.iterdir() if d.is_dir()])
        if not all_bots:
            display.info("No bots found. Create one with: multicord bot create <name> --from <source>")
            return

        # Filter bots based on --all flag
        if show_all:
            bots_to_show = all_bots
        else:
            bots_to_show = [b for b in all_bots if token_mgr.has_token(b)]

        if not bots_to_show:
            if show_all:
                display.info("No bots found")
            else:
                display.info("No bots with stored tokens. Use --all to show all bots")
            return

        # Build summary table
        console.print("\n[bold]MultiCord Credentials[/bold]")
        console.print("═" * 60)
        console.print()

        # Show API authentication status
        console.print("[bold]API Authentication[/bold]")
        console.print("─" * 60)

        # Check if user is authenticated
        try:
            from multicord.api.auth import TokenManager as APITokenManager
            api_token_mgr = APITokenManager()
            if api_token_mgr.has_valid_tokens():
                tokens = api_token_mgr.get_tokens()
                user_info = tokens.get('user_info', {})
                console.print(f"Status:        [green]✓ Authenticated[/green]")
                console.print(f"User:          {user_info.get('username', 'Unknown')}")
                console.print(f"Method:        Discord OAuth2")
                # TODO: Show token expiry
            else:
                console.print(f"Status:        [yellow]✗ Not authenticated[/yellow]")
                console.print(f"Login with:    multicord auth login")
        except Exception:
            console.print(f"Status:        [dim]Not available[/dim]")

        console.print("─" * 60)
        console.print()

        # Show bot tokens
        console.print("[bold]Bot Tokens[/bold]")
        console.print("─" * 60)

        storage_method = token_mgr.get_storage_method()

        table = Table(show_header=True, header_style="bold")
        table.add_column("Bot Name", style="cyan")
        table.add_column("Storage Method")
        table.add_column("Status")

        for bot in bots_to_show:
            has_token = token_mgr.has_token(bot)
            if has_token:
                status = "[green]✓ Stored[/green]"
            else:
                status = "[yellow]✗ Missing[/yellow]"

            table.add_row(bot, storage_method if has_token else "Not Set", status)

        console.print(table)
        console.print("─" * 60)

        # Summary
        with_tokens = sum(1 for b in bots_to_show if token_mgr.has_token(b))
        console.print(f"{len(bots_to_show)} bots, {with_tokens} with tokens stored")
        console.print()
        console.print("[dim]Tip: Use 'multicord token set <bot>' to add missing tokens[/dim]")


@token.command(name='set')
@click.argument('bot_name')
@click.option('--token', 'token_value', prompt=True, hide_input=True,
              help='Discord bot token (will prompt if not provided)')
def token_set(bot_name, token_value):
    """
    Store a Discord bot token securely.

    Tokens are stored using the most secure method available:
      - Windows: Windows Credential Manager
      - macOS: Keychain
      - Linux: Secret Service (libsecret)

    Fallback: AES-encrypted file if system keyring unavailable.

    Examples:
        multicord token set my-bot                    # Prompt for token
        multicord token set my-bot --token TOKEN      # Provide inline
    """
    from multicord.utils.token_manager import TokenManager
    from multicord.local.bot_manager import BotManager

    bot_mgr = BotManager()

    # Validate bot exists
    bot_path = bot_mgr.bots_dir / bot_name
    if not bot_path.exists():
        display.error(f"Bot '{bot_name}' does not exist")
        display.info(f"Create it with: multicord bot create {bot_name} --from <source>")
        sys.exit(1)

    # Validate token format (basic check)
    if not token_value or len(token_value) < 20:
        display.error("Invalid token: Token too short")
        display.info("Discord bot tokens are at least 59 characters long")
        sys.exit(1)

    # Store token
    token_mgr = TokenManager()
    try:
        token_mgr.store_token(bot_name, token_value)
        storage_method = token_mgr.get_storage_method()

        display.success(f"Token stored securely for '{bot_name}'")
        console.print(f"[dim]Storage method: {storage_method}[/dim]")
        console.print(f"[dim]View with: multicord token show {bot_name}[/dim]")

    except Exception as e:
        display.error(f"Failed to store token: {e}")
        sys.exit(1)


@token.command(name='delete')
@click.argument('bot_name')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt')
def token_delete(bot_name, yes):
    """
    Delete a stored bot token.

    This removes the token from secure storage but does NOT delete the bot itself.

    Examples:
        multicord token delete my-bot          # With confirmation
        multicord token delete my-bot -y       # Skip confirmation
    """
    from multicord.utils.token_manager import TokenManager

    token_mgr = TokenManager()

    # Check if token exists
    if not token_mgr.has_token(bot_name):
        display.warning(f"No token stored for '{bot_name}'")
        return

    # Confirm deletion
    if not yes:
        console.print(f"\n[yellow]Delete token for '{bot_name}'?[/yellow]")
        console.print("This will remove the token from secure storage.")
        console.print("The bot itself will NOT be deleted.")

        confirm = click.confirm("\nContinue?", default=False)
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            return

    # Delete token
    try:
        token_mgr.delete_token(bot_name)
        display.success(f"Token deleted for '{bot_name}'")
        console.print(f"[dim]Set a new token with: multicord token set {bot_name}[/dim]")

    except Exception as e:
        display.error(f"Failed to delete token: {e}")
        sys.exit(1)


@token.command(name='show')
@click.argument('bot_name')
@click.option('--unmask', is_flag=True, help='Show full unmasked token (dangerous!)')
def token_show(bot_name, unmask):
    """
    Display token details for a bot.

    By default, shows masked token. Use --unmask to reveal full token.
    WARNING: --unmask will display your token in plain text!

    Examples:
        multicord token show my-bot            # Masked
        multicord token show my-bot --unmask   # Full token (dangerous!)
    """
    from multicord.utils.token_manager import TokenManager
    from multicord.local.bot_manager import BotManager

    bot_mgr = BotManager()

    # Validate bot exists
    bot_path = bot_mgr.bots_dir / bot_name
    if not bot_path.exists():
        display.error(f"Bot '{bot_name}' does not exist")
        sys.exit(1)

    token_mgr = TokenManager()

    # Check if token exists
    if not token_mgr.has_token(bot_name):
        display.warning(f"No token stored for '{bot_name}'")
        console.print(f"Set with: multicord token set {bot_name}")
        return

    # Get token
    try:
        token_value = token_mgr.get_token(bot_name)
        storage_method = token_mgr.get_storage_method()

        console.print(f"\n[bold]Token for '{bot_name}'[/bold]")
        console.print("─" * 60)
        console.print(f"Storage:  {storage_method}")
        console.print(f"Status:   [green]✓ Stored securely[/green]")

        if unmask:
            console.print("[yellow]⚠ WARNING: Full token displayed below[/yellow]")
            console.print(f"Token:    {token_value}")
        else:
            console.print(f"Token:    {_mask_token(token_value)} (masked)")
            console.print("[dim]Use --unmask to reveal full token[/dim]")

        # Show when token was set (if available)
        from multicord.utils.token_manager import Path as TokenPath
        token_file = TokenPath.home() / '.multicord' / 'config' / 'tokens.json'
        if token_file.exists():
            import json
            tokens_data = json.loads(token_file.read_text())
            if bot_name in tokens_data and 'set_on' in tokens_data[bot_name]:
                console.print(f"Set on:   {tokens_data[bot_name]['set_on']}")

        console.print("─" * 60)

    except Exception as e:
        display.error(f"Failed to retrieve token: {e}")
        sys.exit(1)


def _mask_token(token: str) -> str:
    """
    Mask a Discord bot token for display.

    Discord tokens have format: user_id.timestamp.hmac
    Shows first 5 chars of user_id, masks timestamp completely, shows last 4 of hmac.

    Args:
        token: Full Discord token

    Returns:
        Masked token string (e.g., "OTc2N...****...XXXX")
    """
    if not token or len(token) < 20:
        return "****"

    # Discord tokens have format: user_id.timestamp.hmac
    parts = token.split('.')

    if len(parts) >= 3:
        # Show first 5 chars of first segment, mask rest
        first = parts[0][:5] + "..." if len(parts[0]) > 5 else parts[0]
        # Mask middle segment completely
        middle = "****"
        # Show last 4 chars of last segment
        last = "..." + parts[-1][-4:] if len(parts[-1]) > 4 else parts[-1]
        return f"{first}.{middle}.{last}"
    else:
        # Fallback: show first 8 and last 4 chars
        return f"{token[:8]}...****...{token[-4:]}"
