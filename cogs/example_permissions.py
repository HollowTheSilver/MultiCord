"""
Example Commands with Permission System
======================================

Example cog demonstrating how to use the permission system in commands.
"""

import discord
from discord.ext import commands
from discord import app_commands

from utils.loguruConfig import configure_logger
from utils.permissions import (
    require_permission,
    require_level,
    channel_only,
    PermissionLevel
)
from utils.embeds import (
    create_success_embed,
    create_info_embed,
    create_warning_embed,
    EmbedBuilder,
    EmbedType
)


class ExamplePermissionCommands(commands.Cog):
    """
    Example commands demonstrating the permission system.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the example permission commands cog."""
        self.bot = bot
        self.logger = configure_logger(
            log_dir=bot.config.LOG_DIR,
            level=bot.config.LOG_LEVEL,
            format_extra=True,
            discord_compat=True
        )

    # // ======================================( Basic Permission Examples )====================================== // #

    @commands.hybrid_command(
        name="userinfo",
        description="Display detailed information about a user"
    )
    @require_permission("utility.userinfo")
    async def userinfo(
            self,
            ctx: commands.Context,
            user: discord.Member = None
    ) -> None:
        """
        Display user information - requires utility.userinfo permission.

        Args:
            ctx: Command context
            user: User to get info about (defaults to command author)
        """
        target = user or ctx.author

        # Get user's permission level
        user_level = self.bot.permission_manager.get_user_permission_level(target, ctx.guild)

        embed = EmbedBuilder(
            EmbedType.INFO,
            f"👤 User Information: {target.display_name}"
        )

        # Basic information
        embed.add_field(
            name="📝 Basic Info",
            value=f"**Username:** {target}\n"
                  f"**Display Name:** {target.display_name}\n"
                  f"**ID:** `{target.id}`\n"
                  f"**Bot:** {'Yes' if target.bot else 'No'}",
            inline=True
        )

        # Dates
        embed.add_field(
            name="📅 Dates",
            value=f"**Created:** <t:{int(target.created_at.timestamp())}:D>\n"
                  f"**Joined:** <t:{int(target.joined_at.timestamp())}:D>",
            inline=True
        )

        # Permission level
        embed.add_field(
            name="🔐 Permission Level",
            value=f"**Level:** {user_level.name.title()}\n"
                  f"**Value:** {user_level.value}",
            inline=True
        )

        # Roles (top 10)
        if target.roles[1:]:  # Exclude @everyone
            roles = [role.mention for role in target.roles[1:][:10]]
            role_text = ", ".join(roles)
            if len(target.roles) > 11:
                role_text += f" (+{len(target.roles) - 11} more)"
            embed.add_field(
                name=f"🎭 Roles ({len(target.roles) - 1})",
                value=role_text,
                inline=False
            )

        # Set avatar
        embed.set_thumbnail(target.display_avatar.url)
        embed.set_footer(
            f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed.build())

    @commands.hybrid_command(
        name="warn",
        description="Warn a user for breaking rules"
    )
    @require_permission("moderation.warn")
    async def warn(
            self,
            ctx: commands.Context,
            user: discord.Member,
            *,
            reason: str = "No reason provided"
    ) -> None:
        """
        Warn a user - requires moderation.warn permission.

        Args:
            ctx: Command context
            user: User to warn
            reason: Reason for the warning
        """
        # Check if target has higher permission level
        user_level = self.bot.permission_manager.get_user_permission_level(ctx.author, ctx.guild)
        target_level = self.bot.permission_manager.get_user_permission_level(user, ctx.guild)

        if target_level >= user_level:
            embed = create_warning_embed(
                title="Cannot Warn User",
                description="You cannot warn someone with equal or higher permissions.",
                user=ctx.author
            )
            await ctx.send(embed=embed)
            return

        # Issue the warning
        embed = create_success_embed(
            title="User Warned",
            description=f"{user.mention} has been warned.",
            user=ctx.author
        )

        embed.add_field(
            name="👤 Target",
            value=f"{user.mention}\n`{user.id}`",
            inline=True
        )

        embed.add_field(
            name="👮 Moderator",
            value=f"{ctx.author.mention}\n`{ctx.author.id}`",
            inline=True
        )

        embed.add_field(
            name="📝 Reason",
            value=reason[:1000],  # Limit reason length
            inline=False
        )

        await ctx.send(embed=embed)

        # Log the action
        self.logger.info("User warned", extra={
            "target": str(user),
            "target_id": user.id,
            "moderator": str(ctx.author),
            "moderator_id": ctx.author.id,
            "reason": reason,
            "guild": ctx.guild.name,
            "guild_id": ctx.guild.id
        })

    # // ========================================( Level-based Examples )======================================== // #

    @commands.hybrid_command(
        name="kick",
        description="Kick a member from the server"
    )
    @require_level(PermissionLevel.MODERATOR)
    async def kick(
            self,
            ctx: commands.Context,
            user: discord.Member,
            *,
            reason: str = "No reason provided"
    ) -> None:
        """
        Kick a user - requires MODERATOR level or higher.

        Args:
            ctx: Command context
            user: User to kick
            reason: Reason for the kick
        """
        # Check bot permissions
        if not ctx.guild.me.guild_permissions.kick_members:
            embed = create_warning_embed(
                title="Missing Bot Permissions",
                description="I don't have permission to kick members.",
                user=ctx.author
            )
            await ctx.send(embed=embed)
            return

        # Check if target has higher permission level
        user_level = self.bot.permission_manager.get_user_permission_level(ctx.author, ctx.guild)
        target_level = self.bot.permission_manager.get_user_permission_level(user, ctx.guild)

        if target_level >= user_level:
            embed = create_warning_embed(
                title="Cannot Kick User",
                description="You cannot kick someone with equal or higher permissions.",
                user=ctx.author
            )
            await ctx.send(embed=embed)
            return

        # Perform the kick
        try:
            await user.kick(reason=f"Kicked by {ctx.author}: {reason}")

            embed = create_success_embed(
                title="Member Kicked",
                description=f"{user.mention} has been kicked from the server.",
                user=ctx.author
            )

            embed.add_field(
                name="👤 Target",
                value=f"{user.mention}\n`{user.id}`",
                inline=True
            )

            embed.add_field(
                name="👮 Moderator",
                value=f"{ctx.author.mention}\n`{ctx.author.id}`",
                inline=True
            )

            embed.add_field(
                name="📝 Reason",
                value=reason[:1000],
                inline=False
            )

            await ctx.send(embed=embed)

            # Log the action
            self.logger.info("User kicked", extra={
                "target": str(user),
                "target_id": user.id,
                "moderator": str(ctx.author),
                "moderator_id": ctx.author.id,
                "reason": reason,
                "guild": ctx.guild.name,
                "guild_id": ctx.guild.id
            })

        except discord.Forbidden:
            embed = create_warning_embed(
                title="Kick Failed",
                description="I don't have permission to kick this user.",
                user=ctx.author
            )
            await ctx.send(embed=embed)

        except discord.HTTPException as e:
            embed = create_warning_embed(
                title="Kick Failed",
                description=f"An error occurred: {e}",
                user=ctx.author
            )
            await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="settings",
        description="View or modify bot settings"
    )
    @require_level(PermissionLevel.ADMIN)
    async def settings(self, ctx: commands.Context) -> None:
        """
        View bot settings - requires ADMIN level or higher.

        Args:
            ctx: Command context
        """
        embed = EmbedBuilder(
            EmbedType.INFO,
            "⚙️ Bot Settings",
            "Current bot configuration for this server"
        )

        # Permission system stats
        perm_stats = self.bot.permission_manager.get_cache_stats()
        embed.add_field(
            name="🔐 Permission System",
            value=f"**Cache Hit Rate:** {perm_stats['hit_rate']}%\n"
                  f"**Total Checks:** {perm_stats['total_checks']:,}\n"
                  f"**Cached Users:** {perm_stats['cached_users']:,}",
            inline=True
        )

        # Bot stats
        bot_stats = self.bot.get_stats()
        embed.add_field(
            name="📊 Bot Statistics",
            value=f"**Guilds:** {bot_stats['guilds']:,}\n"
                  f"**Users:** {bot_stats['users']:,}\n"
                  f"**Commands:** {bot_stats['commands']:,}",
            inline=True
        )

        # Configuration
        embed.add_field(
            name="🔧 Configuration",
            value=f"**Prefix:** `{self.bot.config.COMMAND_PREFIX}`\n"
                  f"**Log Level:** {self.bot.config.LOG_LEVEL}\n"
                  f"**Debug Mode:** {self.bot.config.DEBUG_MODE}",
            inline=True
        )

        embed.set_footer(
            f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed.build())

    # // =====================================( Channel Restriction Example )===================================== // #

    @commands.hybrid_command(
        name="announce",
        description="Make an announcement (channel restricted)"
    )
    @require_level(PermissionLevel.MODERATOR)
    @channel_only(123456789012345678)  # Replace with actual channel ID
    async def announce(
            self,
            ctx: commands.Context,
            *,
            message: str
    ) -> None:
        """
        Make an announcement - restricted to specific channels.

        Args:
            ctx: Command context
            message: Announcement message
        """
        embed = EmbedBuilder(
            EmbedType.ANNOUNCEMENT,
            "📢 Announcement",
            message
        )

        embed.set_footer(
            f"Announced by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed.build())

        # Try to delete the original command message
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    # // =======================================( Permission Info Commands )======================================= // #

    @commands.hybrid_command(
        name="permissions",
        description="View your permission level and available commands"
    )
    async def permissions(self, ctx: commands.Context) -> None:
        """
        View your permission level and available commands.

        Args:
            ctx: Command context
        """
        user_level = self.bot.permission_manager.get_user_permission_level(ctx.author, ctx.guild)

        embed = EmbedBuilder(
            EmbedType.INFO,
            f"🔐 Your Permissions",
            f"Your current permission level in this server"
        )

        embed.add_field(
            name="📊 Permission Level",
            value=f"**Level:** {user_level.name.title()}\n"
                  f"**Value:** {user_level.value}\n"
                  f"**Description:** {self._get_level_description(user_level)}",
            inline=False
        )

        # Show available permission nodes
        available_nodes = []
        for node_name, node in self.bot.permission_manager.nodes.items():
            if user_level >= node.level:
                available_nodes.append(f"• `{node_name}` - {node.description}")

        if available_nodes:
            # Limit to prevent embed overflow
            visible_nodes = available_nodes[:15]
            if len(available_nodes) > 15:
                visible_nodes.append(f"... and {len(available_nodes) - 15} more")

            embed.add_field(
                name="✅ Available Permissions",
                value="\n".join(visible_nodes),
                inline=False
            )

        embed.set_footer(
            f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed.build())

    @commands.hybrid_command(
        name="role-permissions",
        description="View or manage role permission levels"
    )
    @require_level(PermissionLevel.ADMIN)
    async def role_permissions(self, ctx: commands.Context, action: str = "list") -> None:
        """
        View or manage role permission levels.

        Args:
            ctx: Command context
            action: Action to perform (list, setup)
        """
        if action.lower() == "list":
            # List current role permissions
            role_perms = self.bot.permission_manager.list_role_permissions(ctx.guild)

            embed = EmbedBuilder(
                EmbedType.INFO,
                "🎭 Role Permissions",
                f"Configured role permissions for {ctx.guild.name}"
            )

            if role_perms:
                perm_text = []
                for role_info, level in role_perms.items():
                    perm_text.append(f"**{role_info}:** {level.name.title()}")

                embed.add_field(
                    name="📋 Current Mappings",
                    value="\n".join(perm_text[:10]),  # Limit for embed size
                    inline=False
                )

                if len(role_perms) > 10:
                    embed.add_field(
                        name="ℹ️ Additional Roles",
                        value=f"... and {len(role_perms) - 10} more roles configured",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="📋 Current Mappings",
                    value="No role permissions configured",
                    inline=False
                )

            embed.add_field(
                name="🔧 Management",
                value="Use `role-permissions setup` to auto-configure from environment",
                inline=False
            )

        elif action.lower() == "setup":
            # Reconfigure role permissions from environment
            await self.bot.permission_manager.setup_guild_role_permissions(ctx.guild)

            embed = create_success_embed(
                title="Role Permissions Configured",
                description="Role permissions have been reconfigured from environment settings.",
                user=ctx.author
            )

        else:
            embed = create_warning_embed(
                title="Invalid Action",
                description="Valid actions: `list`, `setup`",
                user=ctx.author
            )

        embed.set_footer(
            f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed.build())

    def _get_level_description(self, level: PermissionLevel) -> str:
        """Get a human-readable description of a permission level."""
        descriptions = {
            PermissionLevel.BANNED: "You are banned from using commands",
            PermissionLevel.EVERYONE: "Basic user with standard permissions",
            PermissionLevel.TRUSTED: "Trusted user with extended permissions",
            PermissionLevel.VIP: "VIP user with special privileges",
            PermissionLevel.HELPER: "Community helper with moderation tools",
            PermissionLevel.MODERATOR: "Server moderator with management powers",
            PermissionLevel.ADMIN: "Server administrator with advanced controls",
            PermissionLevel.OWNER: "Server owner with full permissions",
            PermissionLevel.BOT_ADMIN: "Bot administrator with cross-server access",
            PermissionLevel.BOT_OWNER: "Bot owner with complete control"
        }
        return descriptions.get(level, "Unknown permission level")


async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the example permission commands cog to the bot.

    Args:
        bot: The bot instance
    """
    await bot.add_cog(ExamplePermissionCommands(bot))
