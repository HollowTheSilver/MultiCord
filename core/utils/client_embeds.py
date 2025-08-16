"""
Enhanced Embeds with Client Branding
====================================

Enhanced embed system that supports client-specific branding and customization.
"""

import discord
from typing import Optional, Union, Dict, Any
from datetime import datetime, timezone

# Import base embed utilities
from .embeds import (
    EmbedBuilder, EmbedType, truncate_text, format_timestamp,
    EMBED_TITLE_LIMIT, EMBED_DESCRIPTION_LIMIT
)


class ClientEmbedBuilder(EmbedBuilder):
    """
    Enhanced embed builder with client-specific branding support.
    """

    def __init__(
            self,
            bot,  # ClientApplication instance
            embed_type: Optional[EmbedType] = None,
            title: Optional[str] = None,
            description: Optional[str] = None,
            color: Optional[discord.Color] = None
    ):
        """Initialize client embed builder with branding."""
        self.bot = bot

        # Get client-specific color if not provided
        if not color and hasattr(bot, 'client_branding'):
            color_int = bot.get_branded_embed_color(embed_type.name.lower() if embed_type else "default")
            color = discord.Color(color_int)

        super().__init__(embed_type, title, description, color)

        # Apply client branding
        self._apply_client_branding()

    def _apply_client_branding(self) -> None:
        """Apply client-specific branding to the embed."""
        if not hasattr(self.bot, 'client_branding'):
            return

        branding = self.bot.client_branding
        style = branding.get('embed_style', {})

        # Apply footer branding if enabled
        if style.get('show_footer_branding', True):
            footer_text = branding.get('footer_text')
            footer_icon = branding.get('footer_icon')

            if footer_text:
                self.embed.set_footer(
                    text=footer_text,
                    icon_url=footer_icon
                )

    def set_footer_with_branding(
            self,
            text: str,
            icon_url: Optional[str] = None,
            timestamp: bool = True,
            include_branding: bool = True
    ) -> "ClientEmbedBuilder":
        """Set footer with optional client branding."""
        footer_text = text

        # Add branding if enabled
        if include_branding and hasattr(self.bot, 'client_branding'):
            branding = self.bot.client_branding
            brand_footer = branding.get('footer_text')

            if brand_footer and text.lower() not in brand_footer.lower():
                footer_text = f"{text} • {brand_footer}"

        self.embed.set_footer(
            text=truncate_text(footer_text, 2048),
            icon_url=icon_url
        )

        if timestamp:
            self.embed.timestamp = datetime.now(timezone.utc)

        return self

    def add_client_signature(self) -> "ClientEmbedBuilder":
        """Add client signature to embed."""
        if hasattr(self.bot, 'client_branding'):
            bot_name = self.bot.get_branded_bot_name()
            self.add_field(
                name="",
                value=f"*Powered by {bot_name}*",
                inline=False
            )
        return self


# Enhanced creation functions with client branding
def create_client_success_embed(
        bot,
        title: str = "Success",
        description: Optional[str] = None,
        user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """Create a success embed with client branding."""
    builder = ClientEmbedBuilder(bot, EmbedType.SUCCESS, title, description)

    if user and hasattr(bot, 'client_branding'):
        style = bot.client_branding.get('embed_style', {})
        if style.get('show_user_avatars', True):
            builder.set_footer_with_branding(
                f"Requested by {user.display_name}",
                icon_url=user.display_avatar.url
            )

    return builder.build()


def create_client_error_embed(
        bot,
        title: str = "Error",
        description: Optional[str] = None,
        error_code: Optional[str] = None,
        user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """Create an error embed with client branding."""
    builder = ClientEmbedBuilder(bot, EmbedType.ERROR, title, description)

    if error_code:
        builder.add_field("Error Code", f"`{error_code}`", inline=True)

    if user and hasattr(bot, 'client_branding'):
        style = bot.client_branding.get('embed_style', {})
        if style.get('show_user_avatars', True):
            builder.set_footer_with_branding(
                f"Requested by {user.display_name}",
                icon_url=user.display_avatar.url
            )

    return builder.build()


def create_client_info_embed(
        bot,
        title: str = "Information",
        description: Optional[str] = None,
        user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """Create an info embed with client branding."""
    builder = ClientEmbedBuilder(bot, EmbedType.INFO, title, description)

    if user and hasattr(bot, 'client_branding'):
        style = bot.client_branding.get('embed_style', {})
        if style.get('show_user_avatars', True):
            builder.set_footer_with_branding(
                f"Requested by {user.display_name}",
                icon_url=user.display_avatar.url
            )

    return builder.build()


def create_client_warning_embed(
        bot,
        title: str = "Warning",
        description: Optional[str] = None,
        user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """Create a warning embed with client branding."""
    builder = ClientEmbedBuilder(bot, EmbedType.WARNING, title, description)

    if user and hasattr(bot, 'client_branding'):
        style = bot.client_branding.get('embed_style', {})
        if style.get('show_user_avatars', True):
            builder.set_footer_with_branding(
                f"Requested by {user.display_name}",
                icon_url=user.display_avatar.url
            )

    return builder.build()


def create_client_bot_info_embed(
        bot,
        user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """Create a comprehensive bot info embed with client branding."""
    uptime_seconds = getattr(bot, 'uptime_seconds', 0)

    # Get branded bot name and description
    bot_name = bot.get_branded_bot_name() if hasattr(bot, 'get_branded_bot_name') else bot.config.BOT_NAME
    bot_description = bot.client_branding.get('bot_description', bot.config.BOT_DESCRIPTION) if hasattr(bot,
                                                                                                        'client_branding') else bot.config.BOT_DESCRIPTION

    builder = ClientEmbedBuilder(
        bot,
        EmbedType.INFO,
        f"🤖 {bot_name}",
        bot_description
    )

    # Get bot statistics
    stats = bot.get_stats() if hasattr(bot, 'get_stats') else {}

    # Basic stats
    builder.add_field(
        name="📊 Statistics",
        value=f"**Guilds:** {stats.get('guilds', 0):,}\n"
              f"**Users:** {stats.get('users', 0):,}\n"
              f"**Commands:** {stats.get('commands', 0):,}\n"
              f"**Cogs:** {stats.get('cogs', 0):,}",
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
        name="⚙️ Technical",
        value=f"**Version:** {bot.config.BOT_VERSION}\n"
              f"**Uptime:** {uptime_str}\n"
              f"**Latency:** {round(bot.latency * 1000, 2)}ms\n"
              f"**Client ID:** {getattr(bot, 'client_id', 'Unknown')}",
        inline=True
    )

    # Add client-specific features if available
    if hasattr(bot, 'client_features') and bot.client_features:
        enabled_features = [name for name, enabled in bot.client_features.items() if enabled]
        if enabled_features:
            builder.add_field(
                name="✨ Enabled Features",
                value="\n".join([f"• {feature.replace('_', ' ').title()}" for feature in enabled_features[:8]]),
                inline=False
            )

    # Add bot avatar
    if bot.user and bot.user.avatar:
        builder.set_thumbnail(bot.user.avatar.url)

    # Add user footer
    if user:
        builder.set_footer_with_branding(
            f"Requested by {user.display_name}",
            icon_url=user.display_avatar.url
        )

    return builder.build()
