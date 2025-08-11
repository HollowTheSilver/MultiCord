"""
Sample Cog - Basic Commands
===========================

A sample cog demonstrating best practices for command structure, error handling,
and logging integration with the professional bot template.
"""

import asyncio
import platform
import time
from typing import Optional, Union

import discord
from discord.ext import commands
from discord import app_commands

from utils.loguruConfig import configure_logger
from utils.exceptions import ValidationError, CommandError


class BasicCommands(commands.Cog):
    """
    Basic commands cog with essential bot functionality.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        Initialize the BasicCommands cog.

        Args:
            bot: The bot instance
        """
        self.bot = bot
        self.logger = configure_logger(
            log_dir=bot.config.LOG_DIR,
            level=bot.config.LOG_LEVEL,
            format_extra=True,
            discord_compat=True  # Use Discord-compatible formatting
        )
        self._start_time = time.time()

        self.logger.info("BasicCommands cog initialized")

    # // ========================================( Cog Events )======================================== // #

    async def cog_load(self) -> None:
        """Called when the cog is loaded."""
        self.logger.info("BasicCommands cog loaded successfully")

    async def cog_unload(self) -> None:
        """Called when the cog is unloaded."""
        self.logger.info("BasicCommands cog unloaded")

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle errors that occur in this cog's commands."""
        self.logger.error(f"Command error in BasicCommands: {error}", extra={
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

    # // ========================================( Basic Commands )======================================== // #

    @commands.hybrid_command(
        name="ping",
        description="Check the bot's latency and responsiveness"
    )
    async def ping(self, ctx: commands.Context) -> None:
        """
        Display bot latency information.

        Args:
            ctx: The command context
        """
        start_time = time.perf_counter()

        # Create initial embed
        embed = discord.Embed(
            title="🏓 Pong!",
            description="Measuring latency...",
            color=discord.Color.blue()
        )

        message = await ctx.send(embed=embed)
        end_time = time.perf_counter()

        # Calculate latencies
        api_latency = round(self.bot.latency * 1000, 2)
        message_latency = round((end_time - start_time) * 1000, 2)

        # Update embed with results
        embed.description = None
        embed.add_field(
            name="🌐 API Latency",
            value=f"`{api_latency}ms`",
            inline=True
        )
        embed.add_field(
            name="💬 Message Latency",
            value=f"`{message_latency}ms`",
            inline=True
        )

        # Add status indicator
        if api_latency < 100:
            embed.color = discord.Color.green()
            status = "🟢 Excellent"
        elif api_latency < 200:
            embed.color = discord.Color.yellow()
            status = "🟡 Good"
        else:
            embed.color = discord.Color.red()
            status = "🔴 Poor"

        embed.add_field(
            name="📊 Status",
            value=status,
            inline=True
        )

        await message.edit(embed=embed)

        self.logger.info("Ping command executed", extra={
            "api_latency": f"{api_latency}ms",
            "message_latency": f"{message_latency}ms",
            "user": str(ctx.author)
        })

    @commands.hybrid_command(
        name="info",
        description="Display bot information and statistics"
    )
    async def info(self, ctx: commands.Context) -> None:
        """
        Display comprehensive bot information.

        Args:
            ctx: The command context
        """
        # Calculate uptime
        uptime_seconds = time.time() - self._start_time
        uptime_str = self._format_uptime(uptime_seconds)

        # Get bot statistics
        stats = self.bot.get_stats()
        system_info = self._get_system_info()

        # Create embed
        embed = discord.Embed(
            title=f"🤖 {self.bot.config.BOT_NAME}",
            description=self.bot.config.BOT_DESCRIPTION,
            color=discord.Color.blue()
        )

        # Bot information
        embed.add_field(
            name="📊 Statistics",
            value=(
                f"**Guilds:** {stats['guilds']:,}\n"
                f"**Users:** {stats['users']:,}\n"
                f"**Commands:** {stats['commands']:,}\n"
                f"**Cogs:** {stats['cogs']:,}"
            ),
            inline=True
        )

        # Technical information
        embed.add_field(
            name="⚙️ Technical",
            value=(
                f"**Version:** {self.bot.config.BOT_VERSION}\n"
                f"**Uptime:** {uptime_str}\n"
                f"**Latency:** {round(self.bot.latency * 1000, 2)}ms\n"
                f"**Python:** {system_info['python_version']}"
            ),
            inline=True
        )

        # System information
        embed.add_field(
            name="🖥️ System",
            value=(
                f"**Platform:** {system_info['platform']}\n"
                f"**Architecture:** {system_info['architecture']}\n"
                f"**Discord.py:** {system_info['discord_py_version']}"
            ),
            inline=True
        )

        # Add bot avatar if available
        if self.bot.user and self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        # Add footer with additional info
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed)

        self.logger.info("Info command executed", extra={
            "uptime": uptime_str,
            "guilds": stats['guilds'],
            "users": stats['users'],
            "user": str(ctx.author)
        })

    @commands.hybrid_command(
        name="uptime",
        description="Display how long the bot has been running"
    )
    async def uptime(self, ctx: commands.Context) -> None:
        """
        Display bot uptime information.

        Args:
            ctx: The command context
        """
        uptime_seconds = time.time() - self._start_time
        uptime_str = self._format_uptime(uptime_seconds)

        embed = discord.Embed(
            title="⏰ Bot Uptime",
            description=f"I've been online for **{uptime_str}**",
            color=discord.Color.green()
        )

        embed.add_field(
            name="📅 Started",
            value=f"<t:{int(self._start_time)}:F>",
            inline=False
        )

        await ctx.send(embed=embed)

    # // ========================================( Utility Commands )======================================== // #

    @commands.hybrid_command(
        name="avatar",
        description="Display a user's avatar"
    )
    @app_commands.describe(user="The user whose avatar to display")
    async def avatar(
        self,
        ctx: commands.Context,
        user: Optional[Union[discord.Member, discord.User]] = None
    ) -> None:
        """
        Display a user's avatar.

        Args:
            ctx: The command context
            user: The user whose avatar to display (defaults to command author)
        """
        target_user = user or ctx.author

        embed = discord.Embed(
            title=f"🖼️ {target_user.display_name}'s Avatar",
            color=discord.Color.blue()
        )

        # Set the avatar image
        avatar_url = target_user.display_avatar.url
        embed.set_image(url=avatar_url)

        # Add download link
        embed.add_field(
            name="🔗 Links",
            value=f"[Download]({avatar_url})",
            inline=False
        )

        await ctx.send(embed=embed)

        self.logger.info("Avatar command executed", extra={
            "target_user": str(target_user),
            "requested_by": str(ctx.author)
        })

    @commands.hybrid_command(
        name="serverinfo",
        description="Display information about the current server"
    )
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context) -> None:
        """
        Display server information.

        Args:
            ctx: The command context
        """
        if not ctx.guild:
            raise CommandError("This command can only be used in a server")

        guild = ctx.guild

        # Create embed
        embed = discord.Embed(
            title=f"📋 {guild.name}",
            color=discord.Color.blue()
        )

        # Basic information
        embed.add_field(
            name="👥 Members",
            value=f"**Total:** {guild.member_count:,}\n**Online:** {sum(1 for m in guild.members if m.status != discord.Status.offline):,}",
            inline=True
        )

        # Channel information
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)

        embed.add_field(
            name="📺 Channels",
            value=f"**Text:** {text_channels}\n**Voice:** {voice_channels}\n**Categories:** {categories}",
            inline=True
        )

        # Server details
        embed.add_field(
            name="🔧 Details",
            value=(
                f"**Owner:** {guild.owner.mention if guild.owner else 'Unknown'}\n"
                f"**Created:** <t:{int(guild.created_at.timestamp())}:D>\n"
                f"**Verification:** {guild.verification_level.name.title()}"
            ),
            inline=True
        )

        # Add server icon if available
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        # Add footer
        embed.set_footer(text=f"Server ID: {guild.id}")

        await ctx.send(embed=embed)

        self.logger.info("Serverinfo command executed", extra={
            "guild": guild.name,
            "guild_id": guild.id,
            "member_count": guild.member_count,
            "user": str(ctx.author)
        })

    # // ========================================( Admin Commands )======================================== // #

    @commands.command(name="shutdown")
    @commands.is_owner()
    async def shutdown(self, ctx: commands.Context) -> None:
        """
        Gracefully shutdown the bot (owner only).

        Args:
            ctx: The command context
        """
        embed = discord.Embed(
            title="🔄 Shutting Down",
            description="Shutting down bot...",
            color=discord.Color.red()
        )

        await ctx.send(embed=embed)

        self.logger.warning("Shutdown command executed", extra={
            "user": str(ctx.author),
            "guild": ctx.guild.name if ctx.guild else "DM"
        })

        # Request shutdown using simple flag approach
        self.bot.request_shutdown()

    @commands.hybrid_command(
        name="reload",
        description="Reload a specific cog (owner only)"
    )
    @commands.is_owner()
    @app_commands.describe(cog="The name of the cog to reload")
    async def reload_cog(self, ctx: commands.Context, cog: str) -> None:
        """
        Reload a specific cog.

        Args:
            ctx: The command context
            cog: The name of the cog to reload
        """
        try:
            # Unload and reload the cog
            await self.bot.unload_extension(f"cogs.{cog}")
            await self.bot.load_extension(f"cogs.{cog}")

            embed = discord.Embed(
                title="✅ Cog Reloaded",
                description=f"Successfully reloaded `{cog}`",
                color=discord.Color.green()
            )

            self.logger.info(f"Cog reloaded: {cog}", extra={
                "user": str(ctx.author),
                "cog": cog
            })

        except Exception as e:
            embed = discord.Embed(
                title="❌ Reload Failed",
                description=f"Failed to reload `{cog}`: {str(e)}",
                color=discord.Color.red()
            )

            self.logger.error(f"Failed to reload cog: {cog}", extra={
                "error": str(e),
                "user": str(ctx.author)
            })

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the cog to the bot.

    Args:
        bot: The bot instance
    """
    await bot.add_cog(BasicCommands(bot))
