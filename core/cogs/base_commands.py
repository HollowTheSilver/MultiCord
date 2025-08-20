"""
Base Commands Cog
================================

Base commands cog featuring:
- Beautiful, consistent embeds
- Command cooldowns
- Input validation
- Error handling
- Better user experience
"""

import asyncio
import platform
import time
from typing import Optional, Union, List

import discord
from discord.ext import commands
from discord import app_commands

from core.utils.loguruConfig import configure_logger
from core.utils.exceptions import ValidationError, CommandError
from core.utils.embeds import (
    create_success_embed,
    create_info_embed,
    create_warning_embed,
    create_latency_embed,
    create_bot_info_embed,
    EmbedBuilder,
    EmbedType
)


class BaseCommands(commands.Cog):
    """
    Basic commands cog with beautiful embeds and improved UX.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        Initialize the Basic Commands cog.

        Args:
            bot: The bot instance
        """
        self.bot = bot
        self.logger = configure_logger(
            log_dir=bot.config.LOG_DIR,
            level=bot.config.LOG_LEVEL,
            format_extra=True,
            discord_compat=True
        )
        self._start_time = time.time()

        # Auto-register event listeners
        _listeners: List[callable] = list()
        for attr in dir(self):
            if awaitable := getattr(self, attr, None):
                if callable(awaitable) and attr.startswith("on_"):
                    _listeners.append(awaitable)
        _failed: List[Optional[callable]] = list()
        for _listener in _listeners:
            try:
                self.bot.add_listener(_listener, _listener.__name__)
            except (TypeError, AttributeError, Exception):
                _failed.append(str(_listener) if not callable(_listener) else _listener.__name__)
        if _listeners:
            self.logger.info(f"Registered <{len(_listeners)}> event listeners")
        for _listener in _failed:
            self.logger.error(f"Failed to register listener '{_listener}'")

    # // ========================================( Cog Events )======================================== // #

    async def cog_load(self) -> None:
        """Called when the cog is loaded."""
        self.logger.info("Successfully loaded cog")

    async def cog_unload(self) -> None:
        """Called when the cog is unloaded."""
        self.logger.info("Successfully unloaded cog")

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle errors that occur in this cog's commands."""
        self.logger.error(f"Command error in Base Commands cog: {error}", extra={
            "command": ctx.command.qualified_name if ctx.command else "unknown",
            "user": str(ctx.author),
            "guild": ctx.guild.name if ctx.guild else "DM"
        })

    # // ========================================( Utility Functions )======================================== // #

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime seconds into a human-readable string."""
        days, remainder = divmod(int(seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds or not parts:
            parts.append(f"{seconds}s")

        return " ".join(parts)

    def _get_system_info(self) -> dict:
        """Get system information for the info command."""
        return {
            "python_version": platform.python_version(),
            "discord_py_version": discord.__version__,
            "platform": f"{platform.system()} {platform.release()}",
            "architecture": platform.machine()
        }

    def _validate_user_input(self, value: str, max_length: int = 100) -> str:
        """
        Validate user input to prevent abuse.

        Args:
            value: Input value to validate
            max_length: Maximum allowed length

        Returns:
            Validated input

        Raises:
            ValidationError: If input is invalid
        """
        if not value or not value.strip():
            raise ValidationError(
                field_name="input",
                value=value,
                expected_format="non-empty string"
            )

        if len(value) > max_length:
            raise ValidationError(
                field_name="input",
                value=f"{len(value)} characters",
                expected_format=f"maximum {max_length} characters"
            )

        return value.strip()

    # // ========================================( Base Commands )======================================== // #

    @commands.hybrid_command(
        name="ping",
        description="Check the bot's latency and responsiveness"
    )
    @commands.cooldown(1, 5, commands.BucketType.user)  # 1 use per 5 seconds per user
    async def ping(self, ctx: commands.Context) -> None:
        """
        Display bot latency information with beautiful embed.

        Args:
            ctx: The command context
        """
        start_time = time.perf_counter()

        # Create initial loading embed
        loading_embed = EmbedBuilder(
            EmbedType.LOADING,
            "Measuring Latency",
            "Calculating response times..."
        ).build()

        message = await ctx.send(embed=loading_embed)
        end_time = time.perf_counter()

        # Calculate latencies
        api_latency = round(self.bot.latency * 1000, 2)
        message_latency = round((end_time - start_time) * 1000, 2)

        # Create final latency embed
        latency_embed = create_latency_embed(
            api_latency=api_latency,
            message_latency=message_latency,
            user=ctx.author
        )

        await message.edit(embed=latency_embed)

        self.logger.info("Ping command executed", extra={
            "api_latency": f"{api_latency}ms",
            "message_latency": f"{message_latency}ms",
            "user": str(ctx.author)
        })

    @commands.hybrid_command(
        name="info",
        description="Display comprehensive bot information and statistics"
    )
    @commands.cooldown(2, 30, commands.BucketType.guild)  # 2 uses per 30 seconds per guild
    async def info(self, ctx: commands.Context) -> None:
        """
        Display comprehensive bot information with styling.

        Args:
            ctx: The command context
        """
        # Calculate uptime
        uptime_seconds = time.time() - self._start_time

        # Create comprehensive bot info embed
        info_embed = create_bot_info_embed(
            bot=self.bot,
            uptime_seconds=uptime_seconds,
            user=ctx.author
        )

        # Add additional technical details
        system_info = self._get_system_info()
        info_embed.add_field(
            name="🖥️ System Details",
            value=f"**Platform:** {system_info['platform']}\n"
            f"**Architecture:** {system_info['architecture']}\n"
            f"**Discord.py:** {system_info['discord_py_version']}",
            inline=True
        )

        await ctx.send(embed=info_embed)

        self.logger.info("Info command executed", extra={
            "uptime": self._format_uptime(uptime_seconds),
            "guilds": len(self.bot.guilds),
            "users": sum(guild.member_count or 0 for guild in self.bot.guilds),
            "user": str(ctx.author)
        })

    @commands.hybrid_command(
        name="uptime",
        description="Display how long the bot has been running"
    )
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def uptime(self, ctx: commands.Context) -> None:
        """
        Display bot uptime information with formatting.

        Args:
            ctx: The command context
        """
        uptime_seconds = time.time() - self._start_time
        uptime_str = self._format_uptime(uptime_seconds)

        embed = EmbedBuilder(
            EmbedType.SUCCESS,
            "⏰ Bot Uptime",
            f"I've been online for **{uptime_str}**"
        )

        embed.add_field(
            name="📅 Started",
            value=f"<t:{int(self._start_time)}:F>",
            inline=False
        )

        embed.add_field(
            name="📊 Status",
            value="🟢 Online and Operational",
            inline=True
        )

        embed.set_footer(
            f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed.build())

    # // ========================================( Utility Commands )======================================== // #

    @commands.hybrid_command(
        name="avatar",
        description="Display a user's avatar in high quality"
    )
    @app_commands.describe(
        user="The user whose avatar to display",
        size="Avatar size (64, 128, 256, 512, 1024, 2048, 4096)"
    )
    @commands.cooldown(3, 15, commands.BucketType.user)
    async def avatar(
        self,
        ctx: commands.Context,
        user: Optional[Union[discord.Member, discord.User]] = None,
        size: Optional[int] = None
    ) -> None:
        """
        Display a user's avatar with download options.

        Args:
            ctx: The command context
            user: The user whose avatar to display
            size: Requested avatar size
        """
        target_user = user or ctx.author

        # Validate size parameter
        valid_sizes = [64, 128, 256, 512, 1024, 2048, 4096]
        if size and size not in valid_sizes:
            raise ValidationError(
                field_name="size",
                value=size,
                expected_format=f"one of: {', '.join(map(str, valid_sizes))}"
            )

        # Get avatar URL with requested size
        avatar_url = target_user.display_avatar.url
        if size:
            avatar_url = target_user.display_avatar.with_size(size).url

        embed = EmbedBuilder(
            EmbedType.INFO,
            f"🖼️ {target_user.display_name}'s Avatar"
        )

        # Set the avatar image
        embed.set_image(avatar_url)

        # Add user information
        embed.add_field(
            name="👤 User",
            value=f"{target_user.mention}\n`{target_user.id}`",
            inline=True
        )

        if size:
            embed.add_field(
                name="📐 Size",
                value=f"{size}x{size} pixels",
                inline=True
            )

        # Add download links for different sizes
        download_links = []
        for link_size in [256, 512, 1024]:
            size_url = target_user.display_avatar.with_size(link_size).url
            download_links.append(f"[{link_size}px]({size_url})")

        embed.add_field(
            name="🔗 Download Links",
            value=" • ".join(download_links),
            inline=False
        )

        embed.set_footer(
            f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed.build())

        self.logger.info("Avatar command executed", extra={
            "target_user": str(target_user),
            "requested_size": size,
            "requested_by": str(ctx.author)
        })

    @commands.hybrid_command(
        name="serverinfo",
        description="Display comprehensive information about the current server"
    )
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def serverinfo(self, ctx: commands.Context) -> None:
        """
        Display comprehensive server information.

        Args:
            ctx: The command context
        """
        if not ctx.guild:
            raise CommandError("This command can only be used in a server")

        guild = ctx.guild

        # Create comprehensive server info embed
        embed = EmbedBuilder(
            EmbedType.INFO,
            f"📋 {guild.name}",
            f"Server information and statistics"
        )

        # Basic server information
        embed.add_field(
            name="👥 Members",
            value=f"**Total:** {guild.member_count:,}\n"
            f"**Online:** {sum(1 for m in guild.members if m.status != discord.Status.offline):,}\n"
            f"**Bots:** {sum(1 for m in guild.members if m.bot):,}",
            inline=True
        )

        # Channel information
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        stage_channels = len(guild.stage_channels)

        embed.add_field(
            name="📺 Channels",
            value=f"**Text:** {text_channels}\n"
            f"**Voice:** {voice_channels}\n"
            f"**Stage:** {stage_channels}\n"
            f"**Categories:** {categories}",
            inline=True
        )

        # Server features and details
        embed.add_field(
            name="🔧 Server Details",
            value=f"**Owner:** {guild.owner.mention if guild.owner else 'Unknown'}\n"
            f"**Created:** <t:{int(guild.created_at.timestamp())}:D>\n"
            f"**Verification:** {guild.verification_level.name.title()}\n"
            f"**Boost Level:** {guild.premium_tier}",
            inline=True
        )

        # Emoji and sticker information
        emoji_count = len(guild.emojis)
        sticker_count = len(guild.stickers)

        embed.add_field(
            name="😄 Emojis & Stickers",
            value=f"**Emojis:** {emoji_count}/{guild.emoji_limit}\n"
            f"**Stickers:** {sticker_count}/{guild.sticker_limit}",
            inline=True
        )

        # Role information
        role_count = len(guild.roles) - 1  # Exclude @everyone
        embed.add_field(
            name="🎭 Roles",
            value=f"**Total:** {role_count}\n"
            f"**Highest:** {guild.roles[-1].mention if len(guild.roles) > 1 else 'None'}",
            inline=True
        )

        # Boost information
        if guild.premium_subscription_count:
            embed.add_field(
                name="💎 Nitro Boosts",
                value=f"**Boosts:** {guild.premium_subscription_count}\n"
                f"**Boosters:** {len(guild.premium_subscribers)}",
                inline=True
            )

        # Add server icon if available
        if guild.icon:
            embed.set_thumbnail(guild.icon.url)

        # Add banner if available
        if guild.banner:
            embed.set_image(guild.banner.url)

        # Server features
        if guild.features:
            feature_list = []
            feature_names = {
                'ANIMATED_ICON': 'Animated Icon',
                'BANNER': 'Server Banner',
                'COMMERCE': 'Commerce',
                'COMMUNITY': 'Community Server',
                'DISCOVERABLE': 'Server Discovery',
                'FEATURABLE': 'Featurable',
                'INVITE_SPLASH': 'Invite Splash',
                'MEMBER_VERIFICATION_GATE_ENABLED': 'Membership Screening',
                'NEWS': 'News Channels',
                'PARTNERED': 'Partnered',
                'PREVIEW_ENABLED': 'Preview Enabled',
                'VANITY_URL': 'Custom Invite Link',
                'VERIFIED': 'Verified',
                'VIP_REGIONS': 'VIP Voice Regions',
                'WELCOME_SCREEN_ENABLED': 'Welcome Screen'
            }

            for feature in guild.features:
                feature_name = feature_names.get(feature, feature.replace('_', ' ').title())
                feature_list.append(feature_name)

            if feature_list:
                embed.add_field(
                    name="✨ Special Features",
                    value="\n".join([f"• {feature}" for feature in feature_list[:10]]),  # Limit to prevent overflow
                    inline=False
                )

        embed.set_footer(
            f"Server ID: {guild.id} • Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed.build())

        self.logger.info("Server info command executed", extra={
            "guild": guild.name,
            "guild_id": guild.id,
            "member_count": guild.member_count,
            "user": str(ctx.author)
        })

    # // ========================================( Fun Commands )======================================== // #

    @commands.hybrid_command(
        name="echo",
        description="Repeat a message with style"
    )
    @app_commands.describe(message="The message to echo")
    @commands.cooldown(2, 10, commands.BucketType.user)
    async def echo(self, ctx: commands.Context, *, message: str) -> None:
        """
        Echo a message with validation and beautiful formatting.

        Args:
            ctx: The command context
            message: The message to echo
        """
        # Validate input
        validated_message = self._validate_user_input(message, max_length=500)

        embed = EmbedBuilder(
            EmbedType.INFO,
            "📢 Echo",
            validated_message
        )

        embed.set_footer(
            f"Echoed for {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        # Try to delete the original message if possible
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass  # Bot doesn't have permission to delete messages

        await ctx.send(embed=embed.build())

        self.logger.info("Echo command executed", extra={
            "message_length": len(validated_message),
            "user": str(ctx.author)
        })

    # // ========================================( Admin Commands )======================================== // #

    @commands.hybrid_command(
        name="get-role-ids",
        description="Get role IDs and names for this server (owner only)"
    )
    @commands.is_owner()
    @commands.guild_only()
    async def get_role_ids(self, ctx: commands.Context) -> None:
        """Get role IDs and names for server configuration."""
        roles_info = []
        for role in ctx.guild.roles:
            if role.name != "@everyone":
                roles_info.append(f"`{role.id}` - {role.name}")

        # Create embed for better formatting
        embed = EmbedBuilder(
            EmbedType.INFO,
            f"🎭 Role IDs - {ctx.guild.name}",
            "Role IDs and names for configuration"
        )

        # Split into chunks if too many roles
        role_chunks = [roles_info[i:i + 20] for i in range(0, len(roles_info), 20)]

        for i, chunk in enumerate(role_chunks[:3]):  # Limit to 3 chunks to prevent embed overflow
            embed.add_field(
                name=f"Roles {i * 20 + 1}-{i * 20 + len(chunk)}" if len(role_chunks) > 1 else "Roles",
                value="\n".join(chunk),
                inline=False
            )

        if len(role_chunks) > 3:
            embed.add_field(
                name="Note",
                value=f"Showing first 60 roles. Total roles: {len(roles_info)}",
                inline=False
            )

        embed.set_footer(
            f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed.build())

    @commands.hybrid_command(
        name="shutdown",
        description="Gracefully shutdown the bot (owner only)"
    )
    @commands.is_owner()
    @commands.cooldown(1, 60, commands.BucketType.default)
    async def shutdown(self, ctx: commands.Context) -> None:
        """
        Gracefully shutdown the bot (owner only).

        Args:
            ctx: The command context
        """
        embed = EmbedBuilder(
            EmbedType.WARNING,
            "🔄 Shutting Down",
            "Initiating graceful shutdown sequence..."
        )

        embed.add_field(
            "⚠️ Warning",
            "The bot will be offline until manually restarted.",
            inline=False
        )

        embed.set_footer(
            f"Initiated by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed.build())

        self.logger.warning("Shutdown command executed", extra={
            "user": str(ctx.author),
            "guild": ctx.guild.name if ctx.guild else "DM"
        })

        # Wait a moment for the message to send
        await asyncio.sleep(2)

        # Request shutdown using the bot's shutdown system
        self.bot.request_shutdown()

    @commands.hybrid_command(
        name="reload",
        description="Reload a specific cog (owner only)"
    )
    @commands.is_owner()
    @app_commands.describe(cog="The name of the cog to reload")
    @commands.cooldown(3, 30, commands.BucketType.default)
    async def reload_cog(self, ctx: commands.Context, cog: str) -> None:
        """
        Reload a specific cog with feedback.

        Args:
            ctx: The command context
            cog: The name of the cog to reload
        """
        # Validate cog name
        validated_cog = self._validate_user_input(cog, max_length=50)

        try:
            # Show loading message
            loading_embed = EmbedBuilder(
                EmbedType.LOADING,
                "🔄 Reloading Cog",
                f"Reloading `{validated_cog}`..."
            ).build()

            message = await ctx.send(embed=loading_embed)

            # Unload and reload the cog
            await self.bot.unload_extension(f"cogs.{validated_cog}")
            await self.bot.reload_extension(f"cogs.{validated_cog}")

            # Success message
            success_embed = create_success_embed(
                title="✅ Cog Reloaded",
                description=f"Successfully reloaded `{validated_cog}`",
                user=ctx.author
            )

            await message.edit(embed=success_embed)

            self.logger.info(f"Cog reloaded: {validated_cog}", extra={
                "user": str(ctx.author),
                "cog": validated_cog
            })

        except Exception as e:
            # Error message with details
            error_embed = EmbedBuilder(
                EmbedType.ERROR,
                "❌ Reload Failed",
                f"Failed to reload `{validated_cog}`"
            )

            error_embed.add_field(
                name="Error Details",
                value=f"```\n{str(e)[:500]}...\n```" if len(str(e)) > 500 else f"```\n{str(e)}\n```",
                inline=False
            )

            error_embed.add_field(
                name="💡 Suggestion",
                value="Check the bot logs for more detailed error information.",
                inline=False
            )

            error_embed.set_footer(
                f"Requested by {ctx.author.display_name}",
                icon_url=ctx.author.display_avatar.url
            )

            try:
                await message.edit(embed=error_embed.build())
            except:
                await ctx.send(embed=error_embed.build())

            self.logger.error(f"Failed to reload cog: {validated_cog}", extra={
                "error": str(e),
                "user": str(ctx.author)
            })


async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the cog to the bot.

    Args:
        bot: The bot instance
    """
    await bot.add_cog(BaseCommands(bot))
