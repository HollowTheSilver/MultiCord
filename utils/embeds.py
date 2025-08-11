"""
Enhanced Embed Utilities
========================

Comprehensive embed system for consistent, beautiful Discord embeds with smart
defaults, contextual styling, and utility functions for common use cases.
"""

import time
from datetime import datetime, timezone
from typing import Optional, Union, List, Dict, Any
from enum import Enum

import discord
from discord.ext import commands


# // ========================================( Enums & Constants )======================================== // #


class EmbedType(Enum):
    """Predefined embed types with consistent styling."""
    SUCCESS = ("✅", discord.Color.green())
    ERROR = ("❌", discord.Color.red())
    WARNING = ("⚠️", discord.Color.yellow())
    INFO = ("ℹ️", discord.Color.blue())
    LOADING = ("⏳", discord.Color.purple())
    QUESTION = ("❓", discord.Color.orange())
    ANNOUNCEMENT = ("📢", discord.Color.gold())
    SECURITY = ("🔒", discord.Color.dark_red())
    DEBUG = ("🐛", discord.Color.light_grey())


# Standard embed limits
EMBED_TITLE_LIMIT = 256
EMBED_DESCRIPTION_LIMIT = 4096
EMBED_FIELD_NAME_LIMIT = 256
EMBED_FIELD_VALUE_LIMIT = 1024
EMBED_FOOTER_LIMIT = 2048
EMBED_AUTHOR_LIMIT = 256
EMBED_TOTAL_LIMIT = 6000


# // ========================================( Utility Functions )======================================== // #


def truncate_text(text: str, limit: int, suffix: str = "...") -> str:
    """
    Truncate text to fit within embed limits.

    Args:
        text: Text to truncate
        limit: Character limit
        suffix: Suffix to add when truncating

    Returns:
        Truncated text with suffix if needed
    """
    if not text:
        return ""

    if len(text) <= limit:
        return text

    return text[:limit - len(suffix)] + suffix


def format_user_mention(user: Union[discord.User, discord.Member, int]) -> str:
    """
    Format user mention consistently.

    Args:
        user: User object or ID

    Returns:
        Formatted user mention or display name
    """
    if isinstance(user, (discord.User, discord.Member)):
        return f"{user.mention} ({user.display_name})"
    elif isinstance(user, int):
        return f"<@{user}>"
    else:
        return str(user)


def format_timestamp(
        timestamp: Optional[datetime] = None,
        style: str = "F"
) -> str:
    """
    Format timestamp for Discord's timestamp formatting.

    Args:
        timestamp: Datetime object (defaults to now)
        style: Discord timestamp style (F=full, R=relative, etc.)

    Returns:
        Formatted Discord timestamp string
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    unix_timestamp = int(timestamp.timestamp())
    return f"<t:{unix_timestamp}:{style}>"


# // ========================================( Main Embed Builder )======================================== // #


class EmbedBuilder:
    """
    Professional embed builder with smart defaults and validation.
    """

    def __init__(
            self,
            embed_type: Optional[EmbedType] = None,
            title: Optional[str] = None,
            description: Optional[str] = None,
            color: Optional[discord.Color] = None
    ) -> None:
        """
        Initialize embed builder.

        Args:
            embed_type: Predefined embed type for consistent styling
            title: Embed title
            description: Embed description
            color: Custom color (overrides embed_type color)
        """
        self.embed = discord.Embed()

        # Apply embed type styling
        if embed_type:
            icon, default_color = embed_type.value
            self.embed.color = color or default_color

            # Add icon to title if provided
            if title:
                self.embed.title = f"{icon} {title}"

        else:
            if title:
                self.embed.title = title
            if color:
                self.embed.color = color

        if description:
            self.embed.description = truncate_text(description, EMBED_DESCRIPTION_LIMIT)

    def set_title(self, title: str, with_icon: bool = True) -> "EmbedBuilder":
        """Set embed title with optional icon preservation."""
        if with_icon and self.embed.title and self.embed.title.startswith(
                ("✅", "❌", "⚠️", "ℹ️", "⏳", "❓", "📢", "🔒", "🐛")):
            # Preserve existing icon
            icon = self.embed.title.split(" ", 1)[0]
            self.embed.title = f"{icon} {truncate_text(title, EMBED_TITLE_LIMIT - 2)}"
        else:
            self.embed.title = truncate_text(title, EMBED_TITLE_LIMIT)
        return self

    def set_description(self, description: str) -> "EmbedBuilder":
        """Set embed description with truncation."""
        self.embed.description = truncate_text(description, EMBED_DESCRIPTION_LIMIT)
        return self

    def add_field(
            self,
            name: str,
            value: str,
            inline: bool = False
    ) -> "EmbedBuilder":
        """Add field with truncation."""
        self.embed.add_field(
            name=truncate_text(name, EMBED_FIELD_NAME_LIMIT),
            value=truncate_text(value, EMBED_FIELD_VALUE_LIMIT),
            inline=inline
        )
        return self

    def add_fields(self, fields: List[Dict[str, Any]]) -> "EmbedBuilder":
        """Add multiple fields from list of dictionaries."""
        for field in fields:
            self.add_field(
                name=field.get("name", "Unknown"),
                value=field.get("value", "N/A"),
                inline=field.get("inline", False)
            )
        return self

    def set_footer(
            self,
            text: str,
            icon_url: Optional[str] = None,
            timestamp: bool = True
    ) -> "EmbedBuilder":
        """Set footer with optional timestamp."""
        self.embed.set_footer(
            text=truncate_text(text, EMBED_FOOTER_LIMIT),
            icon_url=icon_url
        )
        if timestamp:
            self.embed.timestamp = datetime.now(timezone.utc)
        return self

    def set_author(
            self,
            name: str,
            icon_url: Optional[str] = None,
            url: Optional[str] = None
    ) -> "EmbedBuilder":
        """Set author information."""
        self.embed.set_author(
            name=truncate_text(name, EMBED_AUTHOR_LIMIT),
            icon_url=icon_url,
            url=url
        )
        return self

    def set_thumbnail(self, url: str) -> "EmbedBuilder":
        """Set thumbnail image."""
        self.embed.set_thumbnail(url=url)
        return self

    def set_image(self, url: str) -> "EmbedBuilder":
        """Set main embed image."""
        self.embed.set_image(url=url)
        return self

    def build(self) -> discord.Embed:
        """Build and return the final embed."""
        return self.embed


# // ========================================( Quick Embed Functions )======================================== // #


def create_success_embed(
        title: str = "Success",
        description: Optional[str] = None,
        user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """Create a success embed with consistent styling."""
    builder = EmbedBuilder(EmbedType.SUCCESS, title, description)

    if user:
        builder.set_footer(
            f"Requested by {user.display_name}",
            icon_url=user.display_avatar.url
        )

    return builder.build()


def create_error_embed(
        title: str = "Error",
        description: Optional[str] = None,
        error_code: Optional[str] = None,
        user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """Create an error embed with optional error code."""
    builder = EmbedBuilder(EmbedType.ERROR, title, description)

    if error_code:
        builder.add_field("Error Code", f"`{error_code}`", inline=True)

    if user:
        builder.set_footer(
            f"Requested by {user.display_name}",
            icon_url=user.display_avatar.url
        )

    return builder.build()


def create_warning_embed(
        title: str = "Warning",
        description: Optional[str] = None,
        user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """Create a warning embed."""
    builder = EmbedBuilder(EmbedType.WARNING, title, description)

    if user:
        builder.set_footer(
            f"Requested by {user.display_name}",
            icon_url=user.display_avatar.url
        )

    return builder.build()


def create_info_embed(
        title: str = "Information",
        description: Optional[str] = None,
        user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """Create an info embed."""
    builder = EmbedBuilder(EmbedType.INFO, title, description)

    if user:
        builder.set_footer(
            f"Requested by {user.display_name}",
            icon_url=user.display_avatar.url
        )

    return builder.build()


def create_loading_embed(
        title: str = "Loading",
        description: str = "Please wait...",
        user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """Create a loading embed for long operations."""
    builder = EmbedBuilder(EmbedType.LOADING, title, description)

    if user:
        builder.set_footer(
            f"Requested by {user.display_name}",
            icon_url=user.display_avatar.url
        )

    return builder.build()


# // ========================================( Specialized Embeds )======================================== // #


def create_command_help_embed(
        command: Union[commands.Command, commands.Group],
        prefix: str = "!"
) -> discord.Embed:
    """Create a help embed for a specific command."""
    builder = EmbedBuilder(
        EmbedType.INFO,
        f"Command: {prefix}{command.qualified_name}",
        command.help or "No description available."
    )

    # Usage
    if hasattr(command, 'signature') and command.signature:
        usage = f"{prefix}{command.qualified_name} {command.signature}"
    else:
        usage = f"{prefix}{command.qualified_name}"
    builder.add_field("Usage", f"`{usage}`", inline=False)

    # Aliases
    if command.aliases:
        aliases = ", ".join([f"`{prefix}{alias}`" for alias in command.aliases])
        builder.add_field("Aliases", aliases, inline=True)

    # Cooldown
    if command.cooldown:
        cooldown_text = f"{command.cooldown.rate} uses per {command.cooldown.per}s"
        builder.add_field("Cooldown", cooldown_text, inline=True)

    return builder.build()


def create_latency_embed(
        api_latency: float,
        message_latency: Optional[float] = None,
        user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """Create a ping/latency embed with status indicators."""
    # Determine status based on API latency
    if api_latency < 100:
        embed_type = EmbedType.SUCCESS
        status = "🟢 Excellent"
    elif api_latency < 200:
        embed_type = EmbedType.WARNING
        status = "🟡 Good"
    else:
        embed_type = EmbedType.ERROR
        status = "🔴 Poor"

    builder = EmbedBuilder(embed_type, "🏓 Pong!")

    builder.add_field("🌐 API Latency", f"`{api_latency}ms`", inline=True)

    if message_latency:
        builder.add_field("💬 Message Latency", f"`{message_latency}ms`", inline=True)

    builder.add_field("📊 Status", status, inline=True)

    if user:
        builder.set_footer(
            f"Requested by {user.display_name}",
            icon_url=user.display_avatar.url
        )

    return builder.build()


def create_bot_info_embed(
        bot: commands.Bot,
        uptime_seconds: float,
        user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """Create a comprehensive bot info embed."""
    builder = EmbedBuilder(
        EmbedType.INFO,
        f"🤖 {bot.config.BOT_NAME}",
        bot.config.BOT_DESCRIPTION
    )

    # Bot statistics
    stats = bot.get_stats()
    builder.add_field(
        "📊 Statistics",
        f"**Guilds:** {stats['guilds']:,}\n"
        f"**Users:** {stats['users']:,}\n"
        f"**Commands:** {stats['commands']:,}\n"
        f"**Cogs:** {stats['cogs']:,}",
        inline=True
    )

    # Format uptime
    days, remainder = divmod(int(uptime_seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    uptime_parts = []
    if days: uptime_parts.append(f"{days}d")
    if hours: uptime_parts.append(f"{hours}h")
    if minutes: uptime_parts.append(f"{minutes}m")
    if seconds or not uptime_parts: uptime_parts.append(f"{seconds}s")
    uptime_str = " ".join(uptime_parts)

    # Technical information
    builder.add_field(
        "⚙️ Technical",
        f"**Version:** {bot.config.BOT_VERSION}\n"
        f"**Uptime:** {uptime_str}\n"
        f"**Latency:** {round(bot.latency * 1000, 2)}ms\n"
        f"**Python:** {bot.config.BOT_VERSION}",
        inline=True
    )

    # Add bot avatar
    if bot.user and bot.user.avatar:
        builder.set_thumbnail(bot.user.avatar.url)

    if user:
        builder.set_footer(
            f"Requested by {user.display_name}",
            icon_url=user.display_avatar.url
        )

    return builder.build()


def create_permission_error_embed(
        missing_permissions: List[str],
        user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """Create a permission error embed with helpful information."""
    permissions_text = ", ".join([f"`{perm}`" for perm in missing_permissions])

    builder = EmbedBuilder(
        EmbedType.ERROR,
        "Missing Permissions",
        f"I don't have the required permissions to execute this command."
    )

    builder.add_field(
        "Required Permissions",
        permissions_text,
        inline=False
    )

    builder.add_field(
        "💡 How to Fix",
        "Ask a server administrator to grant me the required permissions.",
        inline=False
    )

    if user:
        builder.set_footer(
            f"Requested by {user.display_name}",
            icon_url=user.display_avatar.url
        )

    return builder.build()


# // ========================================( Pagination Support )======================================== // #


class PaginatedEmbed:
    """
    Paginated embed system for handling large amounts of data.
    """

    def __init__(
            self,
            title: str,
            items: List[Any],
            items_per_page: int = 10,
            embed_type: EmbedType = EmbedType.INFO
    ) -> None:
        """
        Initialize paginated embed.

        Args:
            title: Base title for all pages
            items: List of items to paginate
            items_per_page: Number of items per page
            embed_type: Embed type for styling
        """
        self.title = title
        self.items = items
        self.items_per_page = items_per_page
        self.embed_type = embed_type
        self.current_page = 0

    @property
    def total_pages(self) -> int:
        """Get total number of pages."""
        return (len(self.items) + self.items_per_page - 1) // self.items_per_page

    def get_page(self, page: int = 0) -> discord.Embed:
        """
        Get a specific page embed.

        Args:
            page: Page number (0-indexed)

        Returns:
            Discord embed for the specified page
        """
        # Validate page number
        page = max(0, min(page, self.total_pages - 1))
        self.current_page = page

        # Calculate item range for this page
        start_idx = page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.items))
        page_items = self.items[start_idx:end_idx]

        # Create embed
        builder = EmbedBuilder(
            self.embed_type,
            f"{self.title} (Page {page + 1}/{self.total_pages})"
        )

        # Add items to embed
        for i, item in enumerate(page_items, start=start_idx + 1):
            if isinstance(item, dict):
                builder.add_field(
                    item.get("name", f"Item {i}"),
                    item.get("value", "N/A"),
                    item.get("inline", False)
                )
            else:
                builder.add_field(f"Item {i}", str(item), inline=False)

        # Add page info in footer
        builder.set_footer(f"Page {page + 1} of {self.total_pages} • {len(self.items)} total items")

        return builder.build()
