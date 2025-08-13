"""
Permission Management Commands
===============================================

Updated to use hybrid commands for both slash and text command support.
"""

import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Union, List

from utils.loguruConfig import configure_logger
from utils.permissions import (
    require_permission,
    require_level,
    PermissionLevel,
    EnhancedPermissionManager
)
from utils.embeds import (
    create_success_embed,
    create_info_embed,
    create_warning_embed,
    create_error_embed,
    EmbedBuilder,
    EmbedType
)
from utils.exceptions import ValidationError


class PermissionManagementCommands(commands.Cog):
    """
    Comprehensive permission management interface for server administrators.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the permission management commands cog."""
        self.bot = bot
        self.logger = configure_logger(
            log_dir=bot.config.LOG_DIR,
            level=bot.config.LOG_LEVEL,
            format_extra=True,
            discord_compat=True
        )
        self.logger.info("Permission Manager cog initialized")

    @property
    def permission_manager(self) -> EnhancedPermissionManager:
        """Get the permission manager instance."""
        if not hasattr(self.bot, 'permission_manager'):
            raise RuntimeError("Permission system not initialized")
        return self.bot.permission_manager

    # // ========================================( Setup Commands )======================================== // #

    @commands.hybrid_command(
        name="permissions-setup",
        description="Auto-configure role permissions based on Discord permissions and role names"
    )
    @commands.guild_only()
    @require_level(PermissionLevel.ADMIN)
    async def setup_permissions(self, ctx: commands.Context) -> None:
        """
        Auto-configure role permissions based on Discord permissions and role names.
        """
        # Show loading message
        loading_embed = EmbedBuilder(
            EmbedType.LOADING,
            "🔍 Analyzing Server Roles",
            "Detecting role permissions and suggesting mappings..."
        ).build()

        message = await ctx.send(embed=loading_embed)

        try:
            # Run auto-configuration
            confident_mappings, uncertain_roles = await self.permission_manager.auto_configure_guild(
                ctx.guild, ctx.author.id
            )

            # Create results embed
            embed = EmbedBuilder(
                EmbedType.SUCCESS,
                "🔧 Permission Setup Complete",
                f"Analyzed {len(ctx.guild.roles)} roles and configured {len(confident_mappings)} automatically."
            )

            # Show confident mappings
            if confident_mappings:
                confident_text = []
                for role_id, level in confident_mappings.items():
                    role = ctx.guild.get_role(role_id)
                    if role:
                        confident_text.append(f"• {role.mention} → **{level.name.title()}**")

                # Limit display to prevent embed overflow
                display_mappings = confident_text[:10]
                if len(confident_text) > 10:
                    display_mappings.append(f"... and {len(confident_text) - 10} more")

                embed.add_field(
                    name="✅ Auto-Configured Roles",
                    value="\n".join(display_mappings),
                    inline=False
                )

            # Show uncertain roles
            if uncertain_roles:
                uncertain_text = []
                for role in uncertain_roles[:5]:  # Limit to 5
                    uncertain_text.append(f"• {role.mention}")

                if len(uncertain_roles) > 5:
                    uncertain_text.append(f"... and {len(uncertain_roles) - 5} more")

                embed.add_field(
                    name="❓ Needs Manual Review",
                    value="\n".join(uncertain_text),
                    inline=False
                )

                embed.add_field(
                    name="🔧 Manual Configuration",
                    value="Use `/permissions-set-role` to configure these roles.\n"
                          "Use `/permissions-help` to check specific user permissions.",
                    inline=False
                )

            # Next steps
            embed.add_field(
                name="📋 What's Next?",
                value="• Review with `/permissions-list`\n"
                      "• Adjust roles with `/permissions-set-role`\n"
                      "• Customize commands with `/permissions-set-command`",
                inline=False
            )

            embed.set_footer(
                f"Configured by {ctx.author.display_name}",
                icon_url=ctx.author.display_avatar.url
            )

            await message.edit(embed=embed.build())

        except Exception as e:
            error_embed = create_error_embed(
                title="Setup Failed",
                description=f"An error occurred during setup: {str(e)}",
                user=ctx.author
            )
            await message.edit(embed=error_embed)

    @commands.hybrid_command(
        name="permissions-list",
        description="Display the current permission configuration for this server"
    )
    @commands.guild_only()
    @require_level(PermissionLevel.ADMIN)
    async def list_permissions(self, ctx: commands.Context) -> None:
        """
        Display the current permission configuration for this server.
        """
        config = self.permission_manager.get_guild_config(ctx.guild.id)

        embed = EmbedBuilder(
            EmbedType.INFO,
            f"🎭 {ctx.guild.name} - Permission Configuration"
        )

        # Role mappings
        if config.role_mappings:
            role_mappings = self.permission_manager.get_guild_role_mappings(ctx.guild)
            role_text = []

            # Sort by permission level (highest first)
            sorted_mappings = sorted(role_mappings.items(), key=lambda x: x[1].value, reverse=True)

            for role_info, level in sorted_mappings[:15]:  # Limit display
                role_name = role_info.split(' (')[0]  # Remove ID from display
                role_text.append(f"• **{role_name}** → {level.name.title()} ({level.value})")

            if len(role_mappings) > 15:
                role_text.append(f"... and {len(role_mappings) - 15} more roles")

            embed.add_field(
                name="🎭 Role Mappings",
                value="\n".join(role_text) if role_text else "No roles configured",
                inline=False
            )
        else:
            embed.add_field(
                name="🎭 Role Mappings",
                value="❌ No roles configured\nRun `/permissions-setup` to auto-configure roles.",
                inline=False
            )

        # Command overrides
        if config.node_overrides:
            override_text = []
            for node, level in list(config.node_overrides.items())[:10]:  # Limit display
                command_name = node.split('.')[-1]  # Get just the command name
                default_level = self.permission_manager.nodes.get(node)
                if default_level:
                    override_text.append(
                        f"• **{command_name}** → {level.name.title()} "
                        f"(was {default_level.default_level.name.title()})"
                    )

            if len(config.node_overrides) > 10:
                override_text.append(f"... and {len(config.node_overrides) - 10} more")

            embed.add_field(
                name="⚙️ Command Overrides",
                value="\n".join(override_text),
                inline=False
            )

        # Configuration info
        status_text = []
        if config.auto_configured:
            status_text.append("✅ Auto-configured")
        else:
            status_text.append("❌ Not auto-configured")

        if config.configured_by:
            user = self.bot.get_user(config.configured_by)
            if user:
                status_text.append(f"👤 Configured by {user.display_name}")

        if config.configured_at:
            status_text.append(f"📅 <t:{int(config.configured_at.timestamp())}:R>")

        embed.add_field(
            name="📊 Configuration Status",
            value="\n".join(status_text) if status_text else "No configuration info",
            inline=True
        )

        # Cache stats
        cache_stats = self.permission_manager.get_cache_stats()
        embed.add_field(
            name="⚡ Performance",
            value=f"Cache hit rate: {cache_stats['hit_rate']}%\n"
                  f"Total checks: {cache_stats['total_checks']:,}",
            inline=True
        )

        embed.set_footer(
            f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed.build())

    # // ========================================( Role Management )======================================== // #

    @commands.hybrid_command(
        name="permissions-set-role",
        description="Set the permission level for a specific role"
    )
    @app_commands.describe(
        role="The role to configure",
        level="Permission level (EVERYONE, MEMBER, MODERATOR, LEAD_MOD, ADMIN, LEAD_ADMIN, OWNER)"
    )
    @commands.guild_only()
    @require_level(PermissionLevel.ADMIN)
    async def set_role_permission(
        self,
        ctx: commands.Context,
        role: discord.Role,
        level: str
    ) -> None:
        """
        Set the permission level for a specific role.
        """
        # Validate permission level
        try:
            permission_level = PermissionLevel[level.upper()]
        except KeyError:
            valid_levels = [level.name for level in PermissionLevel if level.value >= 0]
            raise ValidationError(
                field_name="level",
                value=level,
                expected_format=f"one of: {', '.join(valid_levels)}"
            )

        # Set the role permission
        self.permission_manager.set_role_permission_level(
            guild_id=ctx.guild.id,
            role_id=role.id,
            level=permission_level,
            actor_id=ctx.author.id
        )

        # Create success message
        embed = create_success_embed(
            title="✅ Role Permission Updated",
            description=f"{role.mention} is now mapped to **{permission_level.name.title()}** level",
            user=ctx.author
        )

        # Show what this role can now do
        embed.add_field(
            name="📊 Permission Level",
            value=f"**Level:** {permission_level.name.title()}\n"
                  f"**Value:** {permission_level.value}",
            inline=True
        )

        # List available commands at this level
        available_commands = []
        for node_name, node in self.permission_manager.nodes.items():
            config = self.permission_manager.get_guild_config(ctx.guild.id)
            required_level = config.get_required_level(node_name, self.permission_manager.nodes)

            if permission_level >= required_level:
                command_name = node_name.split('.')[-1]  # Get just the command name
                available_commands.append(command_name)

        if available_commands:
            # Limit display to prevent overflow
            display_commands = available_commands[:8]
            if len(available_commands) > 8:
                display_commands.append(f"... +{len(available_commands) - 8} more")

            embed.add_field(
                name="✅ Can Use Commands",
                value=", ".join([f"`{cmd}`" for cmd in display_commands]),
                inline=False
            )

        await ctx.send(embed=embed.build())

    @commands.hybrid_command(
        name="permissions-set-command",
        description="Set the required permission level for a specific command"
    )
    @app_commands.describe(
        command="Command name (e.g., 'warn', 'kick', 'ban')",
        level="Required permission level"
    )
    @commands.guild_only()
    @require_level(PermissionLevel.ADMIN)
    async def set_command_requirement(
        self,
        ctx: commands.Context,
        command: str,
        level: str
    ) -> None:
        """
        Set the required permission level for a specific command.
        """
        # Validate permission level
        try:
            permission_level = PermissionLevel[level.upper()]
        except KeyError:
            valid_levels = [level.name for level in PermissionLevel if level.value >= 0]
            raise ValidationError(
                field_name="level",
                value=level,
                expected_format=f"one of: {', '.join(valid_levels)}"
            )

        # Find matching permission node
        matching_nodes = []
        for node_name in self.permission_manager.nodes.keys():
            if command.lower() in node_name.lower():
                matching_nodes.append(node_name)

        if not matching_nodes:
            # Show available commands
            available_commands = []
            for node_name in self.permission_manager.nodes.keys():
                command_name = node_name.split('.')[-1]
                available_commands.append(command_name)

            embed = create_error_embed(
                title="Command Not Found",
                description=f"No command found matching '{command}'",
                user=ctx.author
            )

            embed.add_field(
                name="💡 Available Commands",
                value=", ".join([f"`{cmd}`" for cmd in sorted(available_commands)[:20]]),
                inline=False
            )

            await ctx.send(embed=embed)
            return

        if len(matching_nodes) > 1:
            # Multiple matches - let user choose
            embed = create_warning_embed(
                title="Multiple Matches Found",
                description=f"Multiple commands match '{command}'. Please be more specific:",
                user=ctx.author
            )

            match_list = []
            for node in matching_nodes[:10]:  # Limit display
                command_name = node.split('.')[-1]
                match_list.append(f"`{command_name}` ({node})")

            embed.add_field(
                name="Matching Commands",
                value="\n".join(match_list),
                inline=False
            )

            await ctx.send(embed=embed)
            return

        # Single match found
        node_name = matching_nodes[0]
        command_name = node_name.split('.')[-1]

        # Get current requirement
        config = self.permission_manager.get_guild_config(ctx.guild.id)
        old_level = config.get_required_level(node_name, self.permission_manager.nodes)

        # Set new requirement
        self.permission_manager.set_command_requirement(
            guild_id=ctx.guild.id,
            command_node=node_name,
            level=permission_level,
            actor_id=ctx.author.id
        )

        # Create success message
        embed = create_success_embed(
            title="✅ Command Requirement Updated",
            description=f"The `{command_name}` command now requires **{permission_level.name.title()}** level",
            user=ctx.author
        )

        embed.add_field(
            name="📊 Change Summary",
            value=f"**Command:** {command_name}\n"
                  f"**Was:** {old_level.name.title()}\n"
                  f"**Now:** {permission_level.name.title()}",
            inline=True
        )

        # Check if any roles can use this command
        config = self.permission_manager.get_guild_config(ctx.guild.id)
        eligible_roles = []
        for role_id, role_level in config.role_mappings.items():
            if role_level >= permission_level:
                role = ctx.guild.get_role(role_id)
                if role:
                    eligible_roles.append(role.mention)

        if eligible_roles:
            embed.add_field(
                name="✅ Who Can Use This Command",
                value=", ".join(eligible_roles[:5]) + (f" (+{len(eligible_roles)-5} more)" if len(eligible_roles) > 5 else ""),
                inline=False
            )
        else:
            embed.add_field(
                name="⚠️ Warning",
                value="No roles are currently mapped to this permission level or higher!\n"
                      "Consider using `/permissions-set-role` to grant access.",
                inline=False
            )

        await ctx.send(embed=embed.build())

    # // ========================================( Help & Analysis )======================================== // #

    @commands.hybrid_command(
        name="permissions-help",
        description="Analyze and display permission information for a specific user"
    )
    @app_commands.describe(user="User to analyze (defaults to yourself)")
    @commands.guild_only()
    @require_level(PermissionLevel.ADMIN)
    async def help_user(
        self,
        ctx: commands.Context,
        user: Optional[discord.Member] = None
    ) -> None:
        """
        Analyze and display permission information for a specific user.
        """
        target_user = user or ctx.author

        # Get user's permission level
        user_level = self.permission_manager.get_user_permission_level(target_user, ctx.guild)

        embed = EmbedBuilder(
            EmbedType.INFO,
            f"🔍 Permission Analysis: {target_user.display_name}"
        )

        # Basic permission info
        embed.add_field(
            name="📊 Permission Level",
            value=f"**Level:** {user_level.name.title()}\n"
                  f"**Value:** {user_level.value}\n"
                  f"**Status:** {self._get_level_description(user_level)}",
            inline=False
        )

        # Role analysis
        config = self.permission_manager.get_guild_config(ctx.guild.id)
        role_analysis = []

        for role in target_user.roles:
            if role.name == "@everyone":
                continue

            if role.id in config.role_mappings:
                role_level = config.role_mappings[role.id]
                role_analysis.append(f"• {role.mention} → {role_level.name.title()}")
            else:
                role_analysis.append(f"• {role.mention} → Not configured")

        if role_analysis:
            embed.add_field(
                name="🎭 Role Analysis",
                value="\n".join(role_analysis[:8]),  # Limit display
                inline=False
            )

        # Available commands
        available_commands = []
        for node_name, node in self.permission_manager.nodes.items():
            config = self.permission_manager.get_guild_config(ctx.guild.id)
            required_level = config.get_required_level(node_name, self.permission_manager.nodes)

            if user_level >= required_level:
                command_name = node_name.split('.')[-1]
                available_commands.append(command_name)

        if available_commands:
            embed.add_field(
                name="✅ Available Commands",
                value=", ".join([f"`{cmd}`" for cmd in available_commands[:10]]) +
                      (f" (+{len(available_commands)-10} more)" if len(available_commands) > 10 else ""),
                inline=False
            )

        embed.set_thumbnail(target_user.display_avatar.url)
        embed.set_footer(
            f"Analysis by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed.build())

    @commands.hybrid_command(
        name="permissions-reset",
        description="Reset the permission configuration to defaults"
    )
    @commands.guild_only()
    @require_level(PermissionLevel.ADMIN)
    async def reset_config(self, ctx: commands.Context) -> None:
        """
        Reset the permission configuration to defaults.
        ⚠️ This will remove all custom role mappings and command overrides!
        """
        # Confirmation message
        embed = create_warning_embed(
            title="⚠️ Reset Permission Configuration",
            description="This will reset ALL permission settings to defaults!",
            user=ctx.author
        )

        embed.add_field(
            name="What will be reset:",
            value="• All role permission mappings\n"
                  "• All command requirement overrides\n"
                  "• Auto-configuration status",
            inline=False
        )

        embed.add_field(
            name="💡 What to do after reset:",
            value="Run `/permissions-setup` to reconfigure automatically",
            inline=False
        )

        embed.add_field(
            name="Confirmation",
            value="React with ✅ to confirm reset, or ignore this message to cancel.",
            inline=False
        )

        message = await ctx.send(embed=embed.build())
        await message.add_reaction("✅")

        # Wait for confirmation
        def check(reaction, user):
            return (user == ctx.author and
                    str(reaction.emoji) == "✅" and
                    reaction.message.id == message.id)

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)

            # Perform reset
            self.permission_manager.reset_guild_config(ctx.guild.id, ctx.author.id)

            success_embed = create_success_embed(
                title="✅ Configuration Reset",
                description="Permission configuration has been reset to defaults.",
                user=ctx.author
            )

            success_embed.add_field(
                name="Next Steps",
                value="Run `/permissions-setup` to reconfigure your server permissions.",
                inline=False
            )

            await message.edit(embed=success_embed.build())
            await message.clear_reactions()

        except asyncio.TimeoutError:
            timeout_embed = create_info_embed(
                title="Reset Cancelled",
                description="Permission reset was cancelled (no confirmation received).",
                user=ctx.author
            )
            await message.edit(embed=timeout_embed.build())
            await message.clear_reactions()

    def _get_level_description(self, level: PermissionLevel) -> str:
        """Get a human-readable description of a permission level."""
        descriptions = {
            PermissionLevel.BANNED: "🚫 Banned from using commands",
            PermissionLevel.EVERYONE: "👤 Basic user with standard permissions",
            PermissionLevel.MEMBER: "⭐ Trusted user with extended permissions",
            PermissionLevel.MODERATOR: "🛡️ Moderator with basic moderation tools",
            PermissionLevel.LEAD_MOD: "🛡️⭐ Senior moderator with advanced tools",
            PermissionLevel.ADMIN: "🔧 Administrator with management powers",
            PermissionLevel.LEAD_ADMIN: "🔧⭐ Senior administrator with full control",
            PermissionLevel.OWNER: "👑 Server owner with complete permissions",
            PermissionLevel.BOT_ADMIN: "🤖 Bot administrator (cross-server)",
            PermissionLevel.BOT_OWNER: "🤖👑 Bot owner (highest level)"
        }
        return descriptions.get(level, "❓ Unknown permission level")


async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the permission management commands cog to the bot.
    """
    await bot.add_cog(PermissionManagementCommands(bot))
