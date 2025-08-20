"""
Embeds with Client Branding
====================================

Embed system that supports client-specific branding and customization.
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
    """Embed builder with client-specific branding support."""

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


# Creation functions with client branding
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
    bot_name = bot.get_branded_bot_name() if hasattr(bot, 'get_branded_bot_name') else str(bot.user)

    builder = ClientEmbedBuilder(
        bot,
        EmbedType.INFO,
        f"About {bot_name}",
        f"Multi-client Discord bot platform"
    )

    # Bot stats
    stats = bot.get_stats() if hasattr(bot, 'get_stats') else {}

    builder.add_field(
        "📊 Statistics",
        f"Servers: {stats.get('guilds', 0)}\n"
        f"Users: {stats.get('users', 0):,}\n"
        f"Commands: {stats.get('commands', 0)}",
        inline=True
    )

    builder.add_field(
        "⚡ Performance",
        f"Latency: {stats.get('latency', 0)}ms\n"
        f"Uptime: {'Unknown' if not hasattr(bot, '_start_time') else 'Online'}",
        inline=True
    )

    # Client-specific features
    if hasattr(bot, 'client_features'):
        enabled_features = [k for k, v in bot.client_features.items() if v]
        if enabled_features:
            features_text = ", ".join(enabled_features[:5])
            if len(enabled_features) > 5:
                features_text += f" +{len(enabled_features) - 5} more"

            builder.add_field(
                "🛠️ Features",
                features_text,
                inline=False
            )

    # Client branding info
    if hasattr(bot, 'client_id'):
        builder.add_field(
            "🏷️ Client Info",
            f"Client ID: {bot.client_id}\n"
            f"Platform: Multi-Client Bot",
            inline=True
        )

    if user:
        builder.set_footer_with_branding(
            f"Requested by {user.display_name}",
            icon_url=user.display_avatar.url
        )

    return builder.build()
