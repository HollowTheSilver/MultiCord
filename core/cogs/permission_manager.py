"""
Permission Manager Cog
========================================================

Permission management commands with manual classification override,
improved validation, and better user experience.
"""

import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Union, List

from utils.loguruConfig import configure_logger
from utils.permission_models import PermissionLevel, RoleType
from utils.permissions import (
    require_permission,
    require_level,
    EnhancedPermissionManager,
    normalize_discord_text
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


class PermissionManager(commands.Cog):
    """
    Comprehensive permission management interface for server administrators.
    Enhanced with intelligent role classification, manual overrides, and Unicode text support.
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

    @property
    def permission_manager(self) -> EnhancedPermissionManager:
        """Get the permission manager instance."""
        if not hasattr(self.bot, 'permission_manager'):
            raise RuntimeError("Permission system not initialized")
        return self.bot.permission_manager

    # // ========================================( Cog Events )======================================== // #

    async def cog_load(self) -> None:
        """Called when the cog is loaded."""
        self.logger.info("Successfully loaded cog")

    async def cog_unload(self) -> None:
        """Called when the cog is unloaded."""
        self.logger.info("Successfully unloaded cog")

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle errors that occur in this cog's commands."""
        self.logger.error(f"Command error in Permissions Manager cog: {error}", extra={
            "command": ctx.command.qualified_name if ctx.command else "unknown",
            "user": str(ctx.author),
            "guild": ctx.guild.name if ctx.guild else "DM"
        })

    # // ========================================( Setup Commands )======================================== // #

    @commands.hybrid_command(
        name="permissions-setup",
        description="Auto-configure role permissions using intelligent classification and hierarchy analysis"
    )
    @commands.guild_only()
    @require_level(PermissionLevel.ADMIN)
    async def setup_permissions(self, ctx: commands.Context) -> None:
        """Auto-configure role permissions using intelligent classification and hierarchy analysis."""
        # Show loading message
        loading_embed = EmbedBuilder(
            EmbedType.LOADING,
            "🔍 Analyzing Server Roles",
            "Performing intelligent role classification and hierarchy analysis..."
        ).build()

        message = await ctx.send(embed=loading_embed)

        try:
            # Run auto-configuration
            confident_mappings, uncertain_roles = await self.permission_manager.auto_configure_guild(
                ctx.guild, ctx.author.id
            )

            # Get role classifications for display
            config = self.permission_manager.get_guild_config(ctx.guild.id)
            role_classifications = config.role_classifications

            # Count classifications
            classification_counts = {}
            for role_type in RoleType:
                count = sum(1 for rt in role_classifications.values() if rt == role_type)
                if count > 0:
                    classification_counts[role_type] = count

            # Create results embed
            embed = EmbedBuilder(
                EmbedType.SUCCESS,
                "🧠 Intelligent Setup Complete",
                f"Analyzed {len(ctx.guild.roles)} roles using intelligent classification. "
                f"Configured {len(confident_mappings)} authority roles for hierarchy."
            )

            # Show classification summary
            if classification_counts:
                classification_text = []
                for role_type, count in classification_counts.items():
                    icon = self._get_role_type_icon(role_type)
                    classification_text.append(f"{icon} **{role_type.value.title()}:** {count}")

                embed.add_field(
                    name="🔍 Role Classification Results",
                    value="\n".join(classification_text),
                    inline=False
                )

            # Show confident authority mappings
            if confident_mappings:
                confident_text = []
                for role_id, level in list(confident_mappings.items())[:8]:  # Limit display
                    role = ctx.guild.get_role(role_id)
                    if role:
                        confident_text.append(f"• {role.mention} → **{level.name.title()}**")

                if len(confident_mappings) > 8:
                    confident_text.append(f"... and {len(confident_mappings) - 8} more")

                embed.add_field(
                    name="✅ Authority Role Hierarchy",
                    value="\n".join(confident_text),
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

            # Key improvements
            embed.add_field(
                name="🚀 Intelligence Features",
                value="• **Bot roles filtered out** (no longer interfere with hierarchy)\n"
                      "• **Cosmetic roles identified** (colors, teams, etc.)\n"
                      "• **Position-based hierarchy** within authority roles\n"
                      "• **Unicode text normalization** for fancy role names",
                inline=False
            )

            # Next steps
            embed.add_field(
                name="📋 What's Next?",
                value="• Review with `/permissions-list`\n"
                      "• Check classifications with `/permissions-classify`\n"
                      "• Adjust roles with `/permissions-set-role`\n"
                      "• Override classifications with `/permissions-set-role-type`\n"
                      "• Debug with `/permissions-analyze`",
                inline=False
            )

            embed.set_footer(
                f"Configured by {ctx.author.display_name} • Intelligent classification system",
                icon_url=ctx.author.display_avatar.url
            )

            await message.edit(embed=embed.build())

        except Exception as e:
            error_embed = create_error_embed(
                title="Setup Failed",
                description=f"An error occurred during intelligent setup: {str(e)}",
                user=ctx.author
            )
            await message.edit(embed=error_embed)

    @commands.hybrid_command(
        name="permissions-classify",
        description="View intelligent role classifications for this server"
    )
    @commands.guild_only()
    @require_level(PermissionLevel.ADMIN)
    async def view_classifications(self, ctx: commands.Context) -> None:
        """View intelligent role classifications for this server."""
        config = self.permission_manager.get_guild_config(ctx.guild.id)

        if not config.role_classifications:
            embed = create_warning_embed(
                title="No Classifications",
                description="No role classifications found. Run `/permissions-setup` first to classify roles.",
                user=ctx.author
            )
            await ctx.send(embed=embed)
            return

        embed = EmbedBuilder(
            EmbedType.INFO,
            f"🔍 Role Classifications - {ctx.guild.name}",
            "Intelligent classification results for all server roles"
        )

        # Group roles by type
        role_groups = {}
        for role_id, role_type in config.role_classifications.items():
            if role_type not in role_groups:
                role_groups[role_type] = []

            role = ctx.guild.get_role(role_id)
            if role:
                role_groups[role_type].append(role)

        # Display each role type
        for role_type in RoleType:
            if role_type in role_groups:
                roles = role_groups[role_type]
                icon = self._get_role_type_icon(role_type)

                role_list = []
                for role in roles[:8]:  # Limit display
                    # Show if role is in authority hierarchy
                    if role.id in config.role_mappings:
                        level = config.role_mappings[role.id]
                        role_list.append(f"• {role.mention} → {level.name.title()}")
                    else:
                        role_list.append(f"• {role.mention}")

                if len(roles) > 8:
                    role_list.append(f"... and {len(roles) - 8} more")

                embed.add_field(
                    name=f"{icon} {role_type.value.title()} ({len(roles)})",
                    value="\n".join(role_list) if role_list else "None",
                    inline=False
                )

        # Add explanation
        embed.add_field(
            name="💡 Classification Types",
            value="**Authority:** Human hierarchy roles (used for permissions)\n"
                  "**Bot:** Bot-managed roles (filtered out)\n"  
                  "**Cosmetic:** Display-only roles (colors, teams)\n"
                  "**Integration:** Discord integrations (Nitro, etc.)\n"
                  "**Functional:** Channel-specific permissions\n"
                  "**Temporary:** Event/temporary roles\n"
                  "**Unknown:** Couldn't classify confidently",
            inline=False
        )

        embed.add_field(
            name="🔧 Manual Override",
            value="Use `/permissions-set-role-type` to manually override any classification.",
            inline=False
        )

        embed.set_footer(
            f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed.build())

    @commands.hybrid_command(
        name="permissions-analyze",
        description="Show detailed analysis of role hierarchy and classification (debug command)"
    )
    @commands.guild_only()
    @require_level(PermissionLevel.ADMIN)
    async def analyze_hierarchy(self, ctx: commands.Context) -> None:
        """Show detailed analysis of role hierarchy and classification for debugging."""
        # Show loading message
        loading_embed = EmbedBuilder(
            EmbedType.LOADING,
            "🔍 Performing Deep Analysis",
            "Analyzing role hierarchy, classifications, and Unicode normalization..."
        ).build()

        message = await ctx.send(embed=loading_embed)

        try:
            # Count roles by type and category
            config = self.permission_manager.get_guild_config(ctx.guild.id)

            type_counts = {}
            authority_categories = {}

            for role in ctx.guild.roles:
                if role.name == "@everyone":
                    continue

                # Get classification
                role_type = config.role_classifications.get(role.id, RoleType.UNKNOWN)
                type_counts[role_type] = type_counts.get(role_type, 0) + 1

                # If authority role, analyze category
                if role_type == RoleType.AUTHORITY:
                    analysis = self.permission_manager.role_classifier._analyze_single_role(role, ctx.guild)
                    category = analysis.category
                    authority_categories[category] = authority_categories.get(category, [])
                    authority_categories[category].append((role, analysis.confidence))

            # Summary statistics
            total_roles = len(ctx.guild.roles) - 1  # Exclude @everyone
            authority_count = type_counts.get(RoleType.AUTHORITY, 0)

            embed = EmbedBuilder(
                EmbedType.INFO,
                f"🧠 Deep Analysis - {ctx.guild.name}",
                "Detailed classification and hierarchy analysis for debugging"
            )

            embed.add_field(
                name="📊 Classification Summary",
                value=f"**Total Roles:** {total_roles}\n"
                      f"**Authority Roles:** {authority_count}\n"
                      f"**Bot Roles:** {type_counts.get(RoleType.BOT, 0)}\n"
                      f"**Cosmetic Roles:** {type_counts.get(RoleType.COSMETIC, 0)}\n"
                      f"**Other Types:** {total_roles - authority_count - type_counts.get(RoleType.BOT, 0) - type_counts.get(RoleType.COSMETIC, 0)}",
                inline=True
            )

            # Authority role breakdown
            if authority_categories:
                auth_text = []
                for category, roles_with_confidence in authority_categories.items():
                    # Sort by confidence (highest first)
                    roles_with_confidence.sort(key=lambda x: x[1], reverse=True)

                    auth_text.append(f"**{category.value.title()}:** {len(roles_with_confidence)}")
                    for role, confidence in roles_with_confidence[:3]:  # Top 3
                        auth_text.append(f"  • {role.name} ({confidence:.2f})")

                    if len(roles_with_confidence) > 3:
                        auth_text.append(f"  ... +{len(roles_with_confidence) - 3} more")

                embed.add_field(
                    name="🎭 Authority Categories",
                    value="\n".join(auth_text),
                    inline=True
                )

            # Unicode normalization examples
            unicode_examples = []
            for role in ctx.guild.roles[:5]:  # Check first 5 roles
                if role.name == "@everyone":
                    continue

                original = role.name
                normalized = normalize_discord_text(original)

                if original.lower() != normalized:
                    unicode_examples.append(f"• `{original}` → `{normalized}`")

            if unicode_examples:
                embed.add_field(
                    name="🔤 Unicode Normalization",
                    value="\n".join(unicode_examples[:3]) + (
                        f"\n... +{len(unicode_examples) - 3} more" if len(unicode_examples) > 3 else ""
                    ),
                    inline=False
                )

            # Key features explanation
            embed.add_field(
                name="🚀 Advanced Features",
                value="• **Intelligent Classification:** Separates bots, cosmetics, authority\n"
                      "• **Hierarchy Preservation:** Uses Discord position within categories\n"
                      "• **Unicode Support:** Handles fancy characters in role names\n"
                      "• **Performance Optimized:** Limits analysis scope intelligently\n"
                      "• **Manual Override:** Admins can correct classifications",
                inline=False
            )

            embed.add_field(
                name="💡 How This Works",
                value="1. **Classify** all roles by type (bot, cosmetic, authority, etc.)\n"
                      "2. **Filter** to only authority roles for hierarchy analysis\n"
                      "3. **Group** authority roles by function (admin, mod, member)\n"
                      "4. **Apply hierarchy** using Discord position within each group\n"
                      "5. **Normalize text** to handle Unicode characters",
                inline=False
            )

            embed.set_footer(
                f"Analysis by {ctx.author.display_name} • Deep analysis complete",
                icon_url=ctx.author.display_avatar.url
            )

            await message.edit(embed=embed.build())

            # Log the analysis
            self.logger.info("Deep analysis command executed", extra={
                "guild": ctx.guild.name,
                "guild_id": ctx.guild.id,
                "total_roles": total_roles,
                "authority_roles": authority_count,
                "bot_roles": type_counts.get(RoleType.BOT, 0),
                "cosmetic_roles": type_counts.get(RoleType.COSMETIC, 0),
                "user": str(ctx.author)
            })

        except Exception as e:
            error_embed = create_error_embed(
                title="Analysis Failed",
                description=f"An error occurred during deep analysis: {str(e)}",
                user=ctx.author
            )
            await message.edit(embed=error_embed)

            self.logger.error(f"Deep analysis failed: {e}", extra={
                "guild": ctx.guild.name,
                "user": str(ctx.author)
            })

    @commands.hybrid_command(
        name="permissions-list",
        description="Display the current permission configuration for this server"
    )
    @commands.guild_only()
    @require_level(PermissionLevel.ADMIN)
    async def list_permissions(self, ctx: commands.Context) -> None:
        """Display the current permission configuration for this server."""
        config = self.permission_manager.get_guild_config(ctx.guild.id)

        embed = EmbedBuilder(
            EmbedType.INFO,
            f"🎭 {ctx.guild.name} - Permission Configuration"
        )

        # Role mappings (only authority roles should be mapped)
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
                name="🎭 Authority Role Mappings",
                value="\n".join(role_text) if role_text else "No roles configured",
                inline=False
            )
        else:
            embed.add_field(
                name="🎭 Authority Role Mappings",
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

        # Classification summary
        if config.role_classifications:
            classification_counts = {}
            for role_type in RoleType:
                count = sum(1 for rt in config.role_classifications.values() if rt == role_type)
                if count > 0:
                    classification_counts[role_type] = count

            if classification_counts:
                class_text = []
                for role_type, count in classification_counts.items():
                    icon = self._get_role_type_icon(role_type)
                    class_text.append(f"{icon} {role_type.value.title()}: {count}")

                embed.add_field(
                    name="🔍 Role Classifications",
                    value="\n".join(class_text),
                    inline=True
                )

        # Configuration info
        status_text = []
        if config.auto_configured:
            status_text.append("✅ Auto-configured with intelligent classification")
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
        level="Permission level: EVERYONE, MEMBER, MODERATOR, LEAD_MOD, ADMIN, LEAD_ADMIN, OWNER, BOT_ADMIN, BOT_OWNER"
    )
    @commands.guild_only()
    @require_level(PermissionLevel.ADMIN)
    async def set_role_permission(
        self,
        ctx: commands.Context,
        role: discord.Role,
        level: str
    ) -> None:
        """Set the permission level for a specific role."""
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

        # Prevent setting BOT_ADMIN/BOT_OWNER unless user is bot owner
        if permission_level in [PermissionLevel.BOT_ADMIN, PermissionLevel.BOT_OWNER]:
            user_level = self.permission_manager.get_user_permission_level(ctx.author, ctx.guild)
            if user_level < PermissionLevel.BOT_OWNER:
                embed = create_error_embed(
                    title="Insufficient Permissions",
                    description=f"Only bot owners can assign {permission_level.name.title()} level.",
                    user=ctx.author
                )
                await ctx.send(embed=embed)
                return

        # Get current classification
        config = self.permission_manager.get_guild_config(ctx.guild.id)
        role_type = config.role_classifications.get(role.id, RoleType.UNKNOWN)

        # Set the role permission
        await self.permission_manager.set_role_permission_level(
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

        # Show role classification info
        icon = self._get_role_type_icon(role_type)
        embed.add_field(
            name="📊 Role Information",
            value=f"**Permission Level:** {permission_level.name.title()}\n"
                  f"**Role Type:** {icon} {role_type.value.title()}\n"
                  f"**Members:** {len(role.members)}",
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

        # Warning for non-authority roles
        if role_type != RoleType.AUTHORITY:
            embed.add_field(
                name="💡 Classification Note",
                value=f"This role is classified as **{role_type.value.title()}**. "
                      f"Consider if it should really have authority permissions.",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="permissions-set-role-type",
        description="Manually override the classification type for a specific role"
    )
    @app_commands.describe(
        role="The role to reclassify",
        role_type="Classification type: AUTHORITY, BOT, COSMETIC, FUNCTIONAL, INTEGRATION, TEMPORARY, UNKNOWN"
    )
    @commands.guild_only()
    @require_level(PermissionLevel.ADMIN)
    async def set_role_classification(
        self,
        ctx: commands.Context,
        role: discord.Role,
        role_type: str
    ) -> None:
        """Manually override the classification type for a specific role."""
        # Validate role type
        try:
            new_role_type = RoleType[role_type.upper()]
        except KeyError:
            valid_types = [rt.value.upper() for rt in RoleType]
            raise ValidationError(
                field_name="role_type",
                value=role_type,
                expected_format=f"one of: {', '.join(valid_types)}"
            )

        # Get current configuration
        config = self.permission_manager.get_guild_config(ctx.guild.id)
        old_role_type = config.role_classifications.get(role.id, RoleType.UNKNOWN)

        # Set the new classification (we need to add this method to the permission manager)
        if hasattr(self.permission_manager, 'set_role_classification'):
            self.permission_manager.set_role_classification(
                guild_id=ctx.guild.id,
                role_id=role.id,
                role_type=new_role_type,
                actor_id=ctx.author.id
            )
        else:
            # Temporary direct assignment until we add the method
            config.role_classifications[role.id] = new_role_type
            self.permission_manager.clear_cache()

        # Create success message
        embed = create_success_embed(
            title="✅ Role Classification Updated",
            description=f"{role.mention} classification changed from **{old_role_type.value.title()}** to **{new_role_type.value.title()}**",
            user=ctx.author
        )

        # Show before/after
        old_icon = self._get_role_type_icon(old_role_type)
        new_icon = self._get_role_type_icon(new_role_type)

        embed.add_field(
            name="📊 Classification Change",
            value=f"**Before:** {old_icon} {old_role_type.value.title()}\n"
                  f"**After:** {new_icon} {new_role_type.value.title()}",
            inline=True
        )

        # Show current permission mapping if any
        if role.id in config.role_mappings:
            level = config.role_mappings[role.id]
            embed.add_field(
                name="🎭 Permission Level",
                value=f"**Current:** {level.name.title()}\n"
                      f"*Permission level unchanged*",
                inline=True
            )

        # Warning about classification impact
        embed.add_field(
            name="💡 Impact of This Change",
            value=f"• **Hierarchy Analysis:** {'Included' if new_role_type == RoleType.AUTHORITY else 'Excluded'}\n"
                  f"• **Auto-Setup:** {'Will be mapped' if new_role_type == RoleType.AUTHORITY else 'Will be skipped'}\n"
                  f"• **Display Category:** Shows in {new_role_type.value.title()} section",
            inline=False
        )

        await ctx.send(embed=embed)

        self.logger.info(f"Role classification changed: {role.name} from {old_role_type.value} to {new_role_type.value}", extra={
            "guild": ctx.guild.name,
            "role_id": role.id,
            "user": str(ctx.author)
        })

    @commands.hybrid_command(
        name="permissions-set-command",
        description="Set the required permission level for a specific command"
    )
    @app_commands.describe(
        command="Command name (e.g., 'warn', 'kick', 'ban')",
        level="Required permission level: EVERYONE, MEMBER, MODERATOR, LEAD_MOD, ADMIN, LEAD_ADMIN, OWNER"
    )
    @commands.guild_only()
    @require_level(PermissionLevel.ADMIN)
    async def set_command_requirement(
        self,
        ctx: commands.Context,
        command: str,
        level: str
    ) -> None:
        """Set the required permission level for a specific command."""
        # Validate permission level
        try:
            permission_level = PermissionLevel[level.upper()]
        except KeyError:
            valid_levels = [level.name for level in PermissionLevel if level.value >= 0 and level.value <= 100]
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
        await self.permission_manager.set_command_requirement(
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

        # Check if any roles can use this command (only authority roles)
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
                value="No authority roles are currently mapped to this permission level or higher!\n"
                      "Consider using `/permissions-set-role` to grant access.",
                inline=False
            )

        await ctx.send(embed=embed)

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
        """Analyze and display permission information for a specific user."""
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

        # Role analysis with classifications
        config = self.permission_manager.get_guild_config(ctx.guild.id)
        role_analysis = []

        authority_roles = []
        other_roles = []

        for role in target_user.roles:
            if role.name == "@everyone":
                continue

            role_type = config.role_classifications.get(role.id, RoleType.UNKNOWN)
            icon = self._get_role_type_icon(role_type)

            if role.id in config.role_mappings:
                role_level = config.role_mappings[role.id]
                authority_roles.append(f"• {role.mention} → {role_level.name.title()}")
            else:
                other_roles.append(f"• {icon} {role.mention} ({role_type.value})")

        if authority_roles:
            embed.add_field(
                name="🎭 Authority Roles",
                value="\n".join(authority_roles[:8]),  # Limit display
                inline=False
            )

        if other_roles:
            embed.add_field(
                name="🏷️ Other Roles",
                value="\n".join(other_roles[:6]),  # Limit display
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
        """Reset the permission configuration to defaults."""
        # Confirmation message
        embed = create_warning_embed(
            title="⚠️ Reset Permission Configuration",
            description="This will reset ALL permission settings to defaults!",
            user=ctx.author
        )

        embed.add_field(
            name="What will be reset:",
            value="• All authority role permission mappings\n"
                  "• All role classifications\n"
                  "• All command requirement overrides\n"
                  "• Auto-configuration status",
            inline=False
        )

        embed.add_field(
            name="💡 What to do after reset:",
            value="Run `/permissions-setup` to reconfigure automatically with intelligent classification",
            inline=False
        )

        embed.add_field(
            name="Confirmation",
            value="React with ✅ to confirm reset, or ignore this message to cancel.",
            inline=False
        )

        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")

        # Wait for confirmation
        def check(reaction, user):
            return (user == ctx.author and
                    str(reaction.emoji) == "✅" and
                    reaction.message.id == message.id)

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)

            # Perform reset
            await self.permission_manager.reset_guild_config(ctx.guild.id, ctx.author.id)

            success_embed = create_success_embed(
                title="✅ Configuration Reset",
                description="Permission configuration has been reset to defaults.",
                user=ctx.author
            )

            success_embed.add_field(
                name="Next Steps",
                value="Run `/permissions-setup` to reconfigure your server permissions with intelligent classification.",
                inline=False
            )

            await message.edit(embed=success_embed)
            await message.clear_reactions()

        except asyncio.TimeoutError:
            timeout_embed = create_info_embed(
                title="Reset Cancelled",
                description="Permission reset was cancelled (no confirmation received).",
                user=ctx.author
            )
            await message.edit(embed=timeout_embed)
            await message.clear_reactions()

    # // ========================================( Bulk Operations )======================================== // #

    @commands.hybrid_command(
        name="permissions-bulk-set",
        description="Set permission levels for multiple roles at once (advanced)"
    )
    @commands.guild_only()
    @require_level(PermissionLevel.LEAD_ADMIN)
    async def bulk_set_permissions(self, ctx: commands.Context) -> None:
        """Interactive bulk permission setting for multiple roles."""
        config = self.permission_manager.get_guild_config(ctx.guild.id)

        # Get all authority roles
        authority_roles = []
        for role_id, role_type in config.role_classifications.items():
            if role_type == RoleType.AUTHORITY:
                role = ctx.guild.get_role(role_id)
                if role:
                    authority_roles.append(role)

        if not authority_roles:
            embed = create_warning_embed(
                title="No Authority Roles Found",
                description="No authority roles found to configure. Run `/permissions-setup` first.",
                user=ctx.author
            )
            await ctx.send(embed=embed)
            return

        embed = EmbedBuilder(
            EmbedType.INFO,
            "🔧 Bulk Permission Setup",
            f"Found {len(authority_roles)} authority roles to configure"
        )

        # Show current mappings
        role_list = []
        for role in authority_roles[:10]:  # Limit display
            current_level = config.role_mappings.get(role.id, "Not Set")
            level_str = current_level.name.title() if hasattr(current_level, 'name') else str(current_level)
            role_list.append(f"• {role.mention} → {level_str}")

        if len(authority_roles) > 10:
            role_list.append(f"... and {len(authority_roles) - 10} more")

        embed.add_field(
            name="🎭 Authority Roles",
            value="\n".join(role_list),
            inline=False
        )

        embed.add_field(
            name="💡 How to Use",
            value="This is a placeholder for bulk operations. For now, use:\n"
                  "• `/permissions-set-role` for individual roles\n"
                  "• `/permissions-setup` for automatic configuration",
            inline=False
        )

        await ctx.send(embed=embed.build())

    # // ========================================( Utility Methods )======================================== // #

    def _get_role_type_icon(self, role_type: RoleType) -> str:
        """Get an icon for a role type."""
        icons = {
            RoleType.AUTHORITY: "🎭",
            RoleType.BOT: "🤖",
            RoleType.INTEGRATION: "🔗",
            RoleType.COSMETIC: "🎨",
            RoleType.FUNCTIONAL: "⚙️",
            RoleType.TEMPORARY: "⏰",
            RoleType.UNKNOWN: "❓"
        }
        return icons.get(role_type, "❓")

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
    """Setup function to add the permission manager commands cog to the bot."""
    await bot.add_cog(PermissionManager(bot))
