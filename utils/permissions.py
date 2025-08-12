"""
Permission System
===========================

Comprehensive permission management system for Discord bots with role hierarchy,
channel restrictions, guild overrides, caching, and audit logging.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import (
    Dict, List, Optional, Set, Union, Callable, Any, Tuple
)
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from functools import wraps

import discord
from discord.ext import commands

from utils.exceptions import PermissionError, ValidationError
from utils.embeds import create_error_embed, create_warning_embed


# // ========================================( Permission Models )======================================== // #


class PermissionLevel(IntEnum):
    """
    Permission levels with hierarchy support (higher number = more permissions).
    """
    BANNED = -1  # Explicitly banned from using commands
    EVERYONE = 0  # Default permission level
    TRUSTED = 10  # Trusted users (verified members, etc.)
    VIP = 20  # VIP/Premium users
    HELPER = 30  # Community helpers
    MODERATOR = 50  # Server moderators
    ADMIN = 80  # Server administrators
    OWNER = 100  # Server owner
    BOT_ADMIN = 150  # Bot administrators (cross-server)
    BOT_OWNER = 200  # Bot owner (highest level)


class PermissionScope(Enum):
    """Scope of permission restrictions."""
    GLOBAL = "global"  # Applies everywhere
    GUILD = "guild"  # Applies to specific guild
    CATEGORY = "category"  # Applies to specific category
    CHANNEL = "channel"  # Applies to specific channel
    ROLE = "role"  # Applies to users with specific role


@dataclass
class PermissionNode:
    """A permission node defining access to a command or feature."""
    name: str  # Permission node name (e.g., "moderation.kick")
    level: PermissionLevel  # Required permission level
    description: str  # Human-readable description
    scope_restrictions: Set[int] = field(default_factory=set)  # Channel/category IDs where allowed
    role_restrictions: Set[int] = field(default_factory=set)  # Role IDs that can use this
    guild_specific: bool = False  # Whether this is guild-specific
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PermissionOverride:
    """A permission override for specific users/roles in specific contexts."""
    target_type: str  # "user" or "role"
    target_id: int  # User or role ID
    permission_node: str  # Permission node name
    granted: bool  # True = grant, False = deny
    scope_type: PermissionScope  # Where this override applies
    scope_id: Optional[int] = None  # Guild/channel/category ID if applicable
    reason: Optional[str] = None  # Reason for the override
    granted_by: Optional[int] = None  # User ID who granted this
    expires_at: Optional[datetime] = None  # When this override expires
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PermissionAuditEntry:
    """Audit log entry for permission changes."""
    action: str  # "grant", "deny", "remove"
    target_type: str  # "user" or "role"
    target_id: int  # User or role ID
    permission_node: str  # Permission node affected
    actor_id: int  # Who made the change
    reason: Optional[str] = None  # Reason for the change
    guild_id: Optional[int] = None  # Guild where change occurred
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# // ========================================( Permission Manager )======================================== // #


class PermissionManager:
    """
    Core permission management system with caching and audit logging.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        Initialize the permission manager.

        Args:
            bot: The bot instance
        """
        self.bot = bot
        self.logger = bot.logger if hasattr(bot, 'logger') else None

        # Permission nodes registry
        self.nodes: Dict[str, PermissionNode] = {}

        # Caching for performance
        self.user_permission_cache: Dict[Tuple[int, int], Tuple[PermissionLevel, float]] = {}
        self.permission_check_cache: Dict[str, Tuple[bool, float]] = {}
        self.cache_ttl: float = 300.0  # 5 minutes

        # Overrides storage (will be database-backed later)
        self.overrides: List[PermissionOverride] = []
        self.audit_log: List[PermissionAuditEntry] = []

        # Built-in permission levels by role
        self.role_permission_map: Dict[int, PermissionLevel] = {}

        # Performance tracking
        self.check_count = 0
        self.cache_hits = 0

        self._register_default_nodes()

    def _register_default_nodes(self) -> None:
        """Register default permission nodes."""
        default_nodes = [
            # Basic commands
            PermissionNode("basic.ping", PermissionLevel.EVERYONE, "Use ping command"),
            PermissionNode("basic.info", PermissionLevel.EVERYONE, "View bot information"),
            PermissionNode("basic.help", PermissionLevel.EVERYONE, "View help system"),
            PermissionNode("basic.avatar", PermissionLevel.EVERYONE, "View user avatars"),

            # Utility commands
            PermissionNode("utility.serverinfo", PermissionLevel.TRUSTED, "View server information"),
            PermissionNode("utility.userinfo", PermissionLevel.TRUSTED, "View user information"),

            # Moderation commands
            PermissionNode("moderation.kick", PermissionLevel.MODERATOR, "Kick members"),
            PermissionNode("moderation.ban", PermissionLevel.MODERATOR, "Ban members"),
            PermissionNode("moderation.mute", PermissionLevel.MODERATOR, "Mute members"),
            PermissionNode("moderation.warn", PermissionLevel.HELPER, "Warn members"),

            # Administration
            PermissionNode("admin.settings", PermissionLevel.ADMIN, "Modify bot settings"),
            PermissionNode("admin.permissions", PermissionLevel.ADMIN, "Manage permissions"),
            PermissionNode("admin.reload", PermissionLevel.BOT_ADMIN, "Reload bot components"),

            # Bot management
            PermissionNode("bot.shutdown", PermissionLevel.BOT_OWNER, "Shutdown the bot"),
            PermissionNode("bot.eval", PermissionLevel.BOT_OWNER, "Execute code"),
        ]

        for node in default_nodes:
            self.register_node(node)

    def register_node(self, node: PermissionNode) -> None:
        """
        Register a permission node.

        Args:
            node: The permission node to register
        """
        self.nodes[node.name] = node
        if self.logger:
            self.logger.debug(f"Registered permission node: {node.name}")

    def get_user_permission_level(
            self,
            user: Union[discord.Member, discord.User],
            guild: Optional[discord.Guild] = None
    ) -> PermissionLevel:
        """
        Get the permission level for a user in a specific context.

        Args:
            user: The user to check
            guild: The guild context (if applicable)

        Returns:
            The user's permission level
        """
        # Check cache first
        cache_key = (user.id, guild.id if guild else 0)
        if cache_key in self.user_permission_cache:
            level, timestamp = self.user_permission_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                self.cache_hits += 1
                return level

        # Calculate permission level
        level = self._calculate_user_permission_level(user, guild)

        # Cache the result
        self.user_permission_cache[cache_key] = (level, time.time())

        return level

    def _calculate_user_permission_level(
            self,
            user: Union[discord.Member, discord.User],
            guild: Optional[discord.Guild]
    ) -> PermissionLevel:
        """Calculate the actual permission level for a user."""
        # Bot owner always has the highest permissions
        if user.id in self.bot.config.OWNER_IDS:
            return PermissionLevel.BOT_OWNER

        # Check if user is banned from bot
        if self._is_user_banned(user.id, guild):
            return PermissionLevel.BANNED

        # If not in a guild, default to EVERYONE
        if not guild or not isinstance(user, discord.Member):
            return PermissionLevel.EVERYONE

        # Server owner gets OWNER level
        if guild.owner_id == user.id:
            return PermissionLevel.OWNER

        # Check Discord permissions for admin
        if user.guild_permissions.administrator:
            return PermissionLevel.ADMIN

        # Check specific role mappings
        user_level = PermissionLevel.EVERYONE
        for role in user.roles:
            if role.id in self.role_permission_map:
                role_level = self.role_permission_map[role.id]
                if role_level > user_level:
                    user_level = role_level

        # Check Discord permissions for moderator
        if user_level < PermissionLevel.MODERATOR:
            mod_perms = [
                user.guild_permissions.kick_members,
                user.guild_permissions.ban_members,
                user.guild_permissions.manage_messages,
                user.guild_permissions.manage_roles
            ]
            if any(mod_perms):
                user_level = PermissionLevel.MODERATOR

        return user_level

    def _is_user_banned(self, user_id: int, guild: Optional[discord.Guild]) -> bool:
        """Check if a user is banned from using the bot."""
        # Check for global bans
        for override in self.overrides:
            if (override.target_type == "user" and
                    override.target_id == user_id and
                    override.scope_type == PermissionScope.GLOBAL and
                    not override.granted):
                return True

        # Check for guild-specific bans
        if guild:
            for override in self.overrides:
                if (override.target_type == "user" and
                        override.target_id == user_id and
                        override.scope_type == PermissionScope.GUILD and
                        override.scope_id == guild.id and
                        not override.granted):
                    return True

        return False

    async def check_permission(
            self,
            user: Union[discord.Member, discord.User],
            permission_node: str,
            channel: Optional[Union[discord.TextChannel, discord.VoiceChannel]] = None,
            guild: Optional[discord.Guild] = None
    ) -> bool:
        """
        Check if a user has permission for a specific action.

        Args:
            user: The user to check
            permission_node: The permission node to check
            channel: The channel context (if applicable)
            guild: The guild context (if applicable)

        Returns:
            True if the user has permission, False otherwise
        """
        self.check_count += 1

        # Build cache key
        cache_key = f"{user.id}:{permission_node}:{channel.id if channel else 0}:{guild.id if guild else 0}"

        # Check cache
        if cache_key in self.permission_check_cache:
            result, timestamp = self.permission_check_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                self.cache_hits += 1
                return result

        # Perform actual permission check
        result = await self._check_permission_internal(user, permission_node, channel, guild)

        # Cache the result
        self.permission_check_cache[cache_key] = (result, time.time())

        return result

    async def _check_permission_internal(
            self,
            user: Union[discord.Member, discord.User],
            permission_node: str,
            channel: Optional[Union[discord.TextChannel, discord.VoiceChannel]],
            guild: Optional[discord.Guild]
    ) -> bool:
        """Internal permission checking logic."""
        # Check if permission node exists
        if permission_node not in self.nodes:
            if self.logger:
                self.logger.warning(f"Unknown permission node: {permission_node}")
            return False

        node = self.nodes[permission_node]

        # Get user's permission level
        user_level = self.get_user_permission_level(user, guild)

        # Banned users can't do anything
        if user_level == PermissionLevel.BANNED:
            return False

        # Check for explicit overrides first
        override_result = self._check_overrides(user, permission_node, channel, guild)
        if override_result is not None:
            return override_result

        # Check base permission level
        if user_level < node.level:
            return False

        # Check scope restrictions
        if not self._check_scope_restrictions(node, channel, guild):
            return False

        # Check role restrictions
        if not self._check_role_restrictions(node, user, guild):
            return False

        return True

    def _check_overrides(
            self,
            user: Union[discord.Member, discord.User],
            permission_node: str,
            channel: Optional[Union[discord.TextChannel, discord.VoiceChannel]],
            guild: Optional[discord.Guild]
    ) -> Optional[bool]:
        """Check for explicit permission overrides."""
        applicable_overrides = []

        for override in self.overrides:
            # Check if override applies to this permission
            if override.permission_node != permission_node:
                continue

            # Check if override has expired
            if override.expires_at and datetime.now(timezone.utc) > override.expires_at:
                continue

            # Check if override applies to this user
            if override.target_type == "user" and override.target_id == user.id:
                applicable_overrides.append(override)
            elif override.target_type == "role" and guild and isinstance(user, discord.Member):
                if any(role.id == override.target_id for role in user.roles):
                    applicable_overrides.append(override)

        if not applicable_overrides:
            return None

        # Process overrides by scope specificity (most specific first)
        scope_priority = {
            PermissionScope.CHANNEL: 4,
            PermissionScope.CATEGORY: 3,
            PermissionScope.GUILD: 2,
            PermissionScope.GLOBAL: 1
        }

        applicable_overrides.sort(
            key=lambda x: scope_priority.get(x.scope_type, 0),
            reverse=True
        )

        for override in applicable_overrides:
            if self._override_applies_to_context(override, channel, guild):
                return override.granted

        return None

    def _override_applies_to_context(
            self,
            override: PermissionOverride,
            channel: Optional[Union[discord.TextChannel, discord.VoiceChannel]],
            guild: Optional[discord.Guild]
    ) -> bool:
        """Check if an override applies to the current context."""
        if override.scope_type == PermissionScope.GLOBAL:
            return True
        elif override.scope_type == PermissionScope.GUILD:
            return guild is not None and guild.id == override.scope_id
        elif override.scope_type == PermissionScope.CHANNEL:
            return channel is not None and channel.id == override.scope_id
        elif override.scope_type == PermissionScope.CATEGORY:
            return (channel is not None and
                    hasattr(channel, 'category') and
                    channel.category is not None and
                    channel.category.id == override.scope_id)
        return False

    def _check_scope_restrictions(
            self,
            node: PermissionNode,
            channel: Optional[Union[discord.TextChannel, discord.VoiceChannel]],
            guild: Optional[discord.Guild]
    ) -> bool:
        """Check if the current context meets scope restrictions."""
        if not node.scope_restrictions:
            return True

        if channel and channel.id in node.scope_restrictions:
            return True

        if (channel and hasattr(channel, 'category') and
                channel.category and channel.category.id in node.scope_restrictions):
            return True

        return False

    def _check_role_restrictions(
            self,
            node: PermissionNode,
            user: Union[discord.Member, discord.User],
            guild: Optional[discord.Guild]
    ) -> bool:
        """Check if the user meets role restrictions."""
        if not node.role_restrictions:
            return True

        if not guild or not isinstance(user, discord.Member):
            return False

        user_role_ids = {role.id for role in user.roles}
        return bool(node.role_restrictions.intersection(user_role_ids))

    def set_role_permission_level(self, role_id: int, level: PermissionLevel) -> None:
        """
        Set a permission level for a specific role.

        Args:
            role_id: The role ID
            level: The permission level to assign
        """
        self.role_permission_map[role_id] = level
        self.clear_cache()

    def set_role_permission_by_name(
            self,
            guild: discord.Guild,
            role_name: str,
            level: PermissionLevel
    ) -> bool:
        """
        Set a permission level for a role by name.

        Args:
            guild: The guild to search for the role
            role_name: The role name (case-insensitive)
            level: The permission level to assign

        Returns:
            True if role was found and set, False otherwise
        """
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            self.set_role_permission_level(role.id, level)
            return True
        return False

    async def setup_guild_role_permissions(self, guild: discord.Guild) -> None:
        """
        Set up role permissions for a guild based on configuration.

        Args:
            guild: The guild to configure
        """
        if not hasattr(self.bot, 'config'):
            return

        # Parse default role permissions from config
        role_mappings = self.bot.config.parse_default_role_permissions()

        configured_count = 0
        for role_name, level_name in role_mappings.items():
            try:
                # Convert level name to enum
                level = PermissionLevel[level_name]

                # Find role by name (case-insensitive)
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    # Try case-insensitive search
                    role = discord.utils.find(
                        lambda r: r.name.lower() == role_name.lower(),
                        guild.roles
                    )

                if role:
                    self.set_role_permission_level(role.id, level)
                    configured_count += 1
                    if self.logger:
                        self.logger.info(f"Configured role permission: {role.name} -> {level.name}")
                else:
                    if self.logger:
                        self.logger.warning(f"Role not found in guild {guild.name}: {role_name}")

            except (KeyError, ValueError) as e:
                if self.logger:
                    self.logger.warning(f"Invalid permission level '{level_name}' for role '{role_name}': {e}")

        if self.logger and configured_count > 0:
            self.logger.info(f"Configured {configured_count} role permissions for guild: {guild.name}")

    def get_role_permission_level(self, role_id: int) -> Optional[PermissionLevel]:
        """
        Get the permission level for a specific role.

        Args:
            role_id: The role ID

        Returns:
            The permission level if set, None otherwise
        """
        return self.role_permission_map.get(role_id)

    def list_role_permissions(self, guild: Optional[discord.Guild] = None) -> Dict[str, PermissionLevel]:
        """
        List all configured role permissions.

        Args:
            guild: Optional guild to resolve role names

        Returns:
            Dictionary mapping role info to permission levels
        """
        result = {}

        for role_id, level in self.role_permission_map.items():
            if guild:
                role = guild.get_role(role_id)
                role_key = f"{role.name} ({role_id})" if role else f"Unknown Role ({role_id})"
            else:
                role_key = str(role_id)

            result[role_key] = level

        return result

    def add_override(self, override: PermissionOverride) -> None:
        """
        Add a permission override.

        Args:
            override: The permission override to add
        """
        self.overrides.append(override)
        self.clear_cache()

        # Log the action
        audit_entry = PermissionAuditEntry(
            action="grant" if override.granted else "deny",
            target_type=override.target_type,
            target_id=override.target_id,
            permission_node=override.permission_node,
            actor_id=override.granted_by or 0,
            reason=override.reason,
            guild_id=override.scope_id if override.scope_type == PermissionScope.GUILD else None
        )
        self.audit_log.append(audit_entry)

    def remove_override(
            self,
            target_type: str,
            target_id: int,
            permission_node: str,
            scope_type: PermissionScope,
            scope_id: Optional[int] = None,
            actor_id: Optional[int] = None
    ) -> bool:
        """
        Remove a permission override.

        Returns:
            True if an override was removed, False otherwise
        """
        for i, override in enumerate(self.overrides):
            if (override.target_type == target_type and
                    override.target_id == target_id and
                    override.permission_node == permission_node and
                    override.scope_type == scope_type and
                    override.scope_id == scope_id):
                removed_override = self.overrides.pop(i)
                self.clear_cache()

                # Log the action
                audit_entry = PermissionAuditEntry(
                    action="remove",
                    target_type=target_type,
                    target_id=target_id,
                    permission_node=permission_node,
                    actor_id=actor_id or 0,
                    guild_id=scope_id if scope_type == PermissionScope.GUILD else None
                )
                self.audit_log.append(audit_entry)

                return True

        return False

    def clear_cache(self) -> None:
        """Clear all permission caches."""
        self.user_permission_cache.clear()
        self.permission_check_cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        hit_rate = (self.cache_hits / self.check_count) * 100 if self.check_count > 0 else 0
        return {
            "total_checks": self.check_count,
            "cache_hits": self.cache_hits,
            "hit_rate": round(hit_rate, 2),
            "cached_users": len(self.user_permission_cache),
            "cached_checks": len(self.permission_check_cache)
        }


# // ========================================( Permission Decorators )======================================== // #


def require_permission(
        permission_node: str,
        *,
        fallback_level: Optional[PermissionLevel] = None,
        error_message: Optional[str] = None
) -> Callable:
    """
    Decorator to require a specific permission for a command.

    Args:
        permission_node: The permission node required
        fallback_level: Fallback permission level if node doesn't exist
        error_message: Custom error message to display

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            # Get permission manager from bot
            if not hasattr(ctx.bot, 'permission_manager'):
                raise PermissionError("Permission system not initialized")

            permission_manager: PermissionManager = ctx.bot.permission_manager

            # Check permission
            has_permission = await permission_manager.check_permission(
                user=ctx.author,
                permission_node=permission_node,
                channel=ctx.channel,
                guild=ctx.guild
            )

            if not has_permission:
                # Create contextual error message
                if error_message:
                    description = error_message
                else:
                    node = permission_manager.nodes.get(permission_node)
                    if node:
                        description = f"You need **{node.level.name.title()}** level permissions to use this command."
                    else:
                        description = "You don't have permission to use this command."

                embed = create_error_embed(
                    title="Insufficient Permissions",
                    description=description,
                    user=ctx.author
                )

                # Add permission details
                user_level = permission_manager.get_user_permission_level(ctx.author, ctx.guild)
                embed.add_field(
                    name="Your Permission Level",
                    value=user_level.name.title(),
                    inline=True
                )

                if permission_node in permission_manager.nodes:
                    required_level = permission_manager.nodes[permission_node].level
                    embed.add_field(
                        name="Required Level",
                        value=required_level.name.title(),
                        inline=True
                    )

                embed.add_field(
                    name="💡 Need Help?",
                    value="Contact a server administrator if you believe this is an error.",
                    inline=False
                )

                await ctx.send(embed=embed)
                return

            # Permission granted, execute command
            return await func(self, ctx, *args, **kwargs)

        return wrapper

    return decorator


def require_level(level: PermissionLevel, *, error_message: Optional[str] = None) -> Callable:
    """
    Decorator to require a minimum permission level for a command.

    Args:
        level: The minimum permission level required
        error_message: Custom error message to display

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            # Get permission manager from bot
            if not hasattr(ctx.bot, 'permission_manager'):
                raise PermissionError("Permission system not initialized")

            permission_manager: PermissionManager = ctx.bot.permission_manager

            # Get user's permission level
            user_level = permission_manager.get_user_permission_level(ctx.author, ctx.guild)

            if user_level < level:
                # Create contextual error message
                description = error_message or f"You need **{level.name.title()}** level permissions to use this command."

                embed = create_error_embed(
                    title="Insufficient Permissions",
                    description=description,
                    user=ctx.author
                )

                embed.add_field(
                    name="Your Permission Level",
                    value=user_level.name.title(),
                    inline=True
                )

                embed.add_field(
                    name="Required Level",
                    value=level.name.title(),
                    inline=True
                )

                embed.add_field(
                    name="💡 Need Help?",
                    value="Contact a server administrator if you believe this is an error.",
                    inline=False
                )

                await ctx.send(embed=embed)
                return

            # Permission granted, execute command
            return await func(self, ctx, *args, **kwargs)

        return wrapper

    return decorator


def channel_only(*channel_ids: int) -> Callable:
    """
    Decorator to restrict a command to specific channels.

    Args:
        *channel_ids: Channel IDs where the command is allowed

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            if ctx.channel.id not in channel_ids:
                allowed_channels = []
                for channel_id in channel_ids:
                    channel = ctx.bot.get_channel(channel_id)
                    if channel:
                        allowed_channels.append(f"#{channel.name}")
                    else:
                        allowed_channels.append(f"<#{channel_id}>")

                embed = create_warning_embed(
                    title="Wrong Channel",
                    description="This command can only be used in specific channels.",
                    user=ctx.author
                )

                embed.add_field(
                    name="Allowed Channels",
                    value="\n".join(allowed_channels) if allowed_channels else "None available",
                    inline=False
                )

                await ctx.send(embed=embed, delete_after=15)
                return

            # Channel check passed, execute command
            return await func(self, ctx, *args, **kwargs)

        return wrapper

    return decorator


# // ========================================( Integration Function )======================================== // #


def setup_permission_system(bot: commands.Bot) -> PermissionManager:
    """
    Set up the permission system for the bot.

    Args:
        bot: The bot instance

    Returns:
        The permission manager instance
    """
    permission_manager = PermissionManager(bot)
    bot.permission_manager = permission_manager

    # Set up event handlers for automatic role configuration
    @bot.event
    async def on_guild_join(guild: discord.Guild):
        """Configure role permissions when joining a new guild."""
        await permission_manager.setup_guild_role_permissions(guild)

    @bot.event
    async def on_ready():
        """Configure role permissions for all guilds on startup."""
        if hasattr(bot, '_permission_setup_complete'):
            return  # Avoid duplicate setup on reconnect

        for guild in bot.guilds:
            await permission_manager.setup_guild_role_permissions(guild)

        bot._permission_setup_complete = True

    if hasattr(bot, 'logger'):
        bot.logger.info("Permission system initialized")

    return permission_manager
