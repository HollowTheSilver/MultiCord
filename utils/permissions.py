"""
Enhanced Permission System
===========================

Upgraded permission management system with:
- Enhanced permission levels (LEAD_MOD, LEAD_ADMIN)
- Auto-detection of Discord roles
- Guild-specific permission node overrides
- Management commands for configuration
- Two-layer architecture (Universal levels + Guild customization)
"""

import asyncio
import time
import re
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
from utils.embeds import create_error_embed, create_warning_embed, create_success_embed, create_info_embed


# // ========================================( Enhanced Permission Models )======================================== // #


class PermissionLevel(IntEnum):
    """
    Enhanced universal permission levels with proper hierarchy.
    These levels work across all Discord servers regardless of role names.
    """
    BANNED = -1        # Explicitly banned from using commands
    EVERYONE = 0       # Default permission level (no special roles needed)
    MEMBER = 10        # Verified/trusted members, VIPs, supporters, etc.
    MODERATOR = 50     # Basic moderation permissions (warn, mute, kick)
    LEAD_MOD = 65      # Senior/Lead moderators (advanced moderation)
    ADMIN = 80         # Basic administration permissions
    LEAD_ADMIN = 90    # Senior/Lead administrators (advanced admin)
    OWNER = 100        # Full server permissions
    BOT_ADMIN = 150    # Bot administrators (cross-server)
    BOT_OWNER = 200    # Bot owner (highest level)


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
    default_level: PermissionLevel  # Default required permission level
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
class GuildPermissionConfig:
    """Per-guild permission configuration."""
    guild_id: int
    role_mappings: Dict[int, PermissionLevel] = field(default_factory=dict)  # role_id -> level
    node_overrides: Dict[str, PermissionLevel] = field(default_factory=dict)  # node -> required_level
    auto_configured: bool = False  # Whether auto-detection has been run
    configured_by: Optional[int] = None  # User who configured this
    configured_at: Optional[datetime] = None  # When it was configured

    def get_required_level(self, node: str, default_nodes: Dict[str, PermissionNode]) -> PermissionLevel:
        """Get required level for a node, checking guild override first."""
        if node in self.node_overrides:
            return self.node_overrides[node]

        if node in default_nodes:
            return default_nodes[node].default_level

        return PermissionLevel.OWNER  # Safe default for unknown nodes


@dataclass
class PermissionAuditEntry:
    """Audit log entry for permission changes."""
    action: str  # "grant", "deny", "remove", "set_role", "set_command", "auto_configure"
    target_type: str  # "user", "role", "command", "guild"
    target_id: Union[int, str]  # User/role ID or command name
    permission_data: str  # What changed
    actor_id: int  # Who made the change
    reason: Optional[str] = None  # Reason for the change
    guild_id: Optional[int] = None  # Guild where change occurred
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# // ========================================( Role Detection System )======================================== // #


class RoleDetectionSystem:
    """Automatically detects and suggests role mappings based on Discord permissions and names."""

    def __init__(self, logger=None):
        self.logger = logger

        # Common role name patterns for different permission levels
        self.role_patterns = {
            PermissionLevel.MEMBER: [
                r'\bvip\b', r'\bmember\b', r'\bverified\b', r'\btrusted\b',
                r'\bsupporter\b', r'\bregular\b', r'\bactive\b', r'\bdonator\b'
            ],
            PermissionLevel.MODERATOR: [
                r'\bmod\b', r'\bmoderator\b', r'\bhelper\b', r'\btrial.*mod\b',
                r'\bjunior.*mod\b', r'\btemp.*mod\b', r'\btrainee\b'
            ],
            PermissionLevel.LEAD_MOD: [
                r'\bsenior.*mod\b', r'\blead.*mod\b', r'\bhead.*mod\b',
                r'\bsuper.*mod\b', r'\bchief.*mod\b', r'\bmaster.*mod\b'
            ],
            PermissionLevel.ADMIN: [
                r'\badmin\b', r'\badministrator\b', r'\bmanager\b', r'\bstaff\b',
                r'\bleader\b', r'\bexecutive\b', r'\bdirector\b'
            ],
            PermissionLevel.LEAD_ADMIN: [
                r'\bsenior.*admin\b', r'\blead.*admin\b', r'\bhead.*admin\b',
                r'\bchief.*admin\b', r'\bsuper.*admin\b', r'\bco.*owner\b'
            ]
        }

    def analyze_guild_roles(self, guild: discord.Guild) -> Tuple[Dict[int, PermissionLevel], List[discord.Role]]:
        """
        Analyze guild roles and suggest permission mappings.

        Returns:
            Tuple of (confident_mappings, uncertain_roles)
        """
        confident_mappings = {}
        uncertain_roles = []

        for role in guild.roles:
            if role.name == "@everyone":
                continue

            # Check for administrator permission (always ADMIN level)
            if role.permissions.administrator:
                # But check if it should be LEAD_ADMIN based on name
                if self._matches_pattern(role.name, PermissionLevel.LEAD_ADMIN):
                    confident_mappings[role.id] = PermissionLevel.LEAD_ADMIN
                else:
                    confident_mappings[role.id] = PermissionLevel.ADMIN
                continue

            # Check for ownership (guild owner gets special treatment elsewhere)
            if role.position == len(guild.roles) - 1:  # Highest role
                if self._matches_pattern(role.name, PermissionLevel.OWNER, ['owner', 'founder', 'creator']):
                    confident_mappings[role.id] = PermissionLevel.OWNER
                    continue

            # Analyze by Discord permissions
            detected_level = self._analyze_role_permissions(role)

            if detected_level:
                # Double-check with name patterns
                name_level = self._analyze_role_name(role.name)

                if name_level and name_level != detected_level:
                    # Conflict between permissions and name - mark as uncertain
                    uncertain_roles.append(role)
                    if self.logger:
                        self.logger.debug(f"Role permission/name conflict: {role.name} - "
                                        f"permissions suggest {detected_level.name}, "
                                        f"name suggests {name_level.name}")
                else:
                    confident_mappings[role.id] = detected_level
            else:
                # No clear permissions detected, try name-based detection
                name_level = self._analyze_role_name(role.name)
                if name_level:
                    # Less confident about name-only detection
                    if name_level in [PermissionLevel.MODERATOR, PermissionLevel.LEAD_MOD]:
                        uncertain_roles.append(role)
                    else:
                        confident_mappings[role.id] = name_level
                else:
                    # No clear indication - add to uncertain if it might be important
                    if not role.is_bot_managed() and not role.is_integration():
                        uncertain_roles.append(role)

        return confident_mappings, uncertain_roles

    def _analyze_role_permissions(self, role: discord.Role) -> Optional[PermissionLevel]:
        """Analyze Discord permissions to determine appropriate bot permission level."""
        perms = role.permissions

        # Check for moderation permissions
        basic_mod_perms = [
            perms.kick_members,
            perms.ban_members,
            perms.moderate_members,  # Timeout permission
            perms.manage_messages
        ]

        advanced_mod_perms = [
            perms.manage_channels,
            perms.manage_roles,
            perms.manage_guild
        ]

        # Count how many permissions they have
        basic_mod_count = sum(basic_mod_perms)
        advanced_mod_count = sum(advanced_mod_perms)

        if advanced_mod_count >= 2:
            return PermissionLevel.ADMIN  # Can manage server structure
        elif basic_mod_count >= 2:
            return PermissionLevel.MODERATOR  # Can moderate users
        elif any(basic_mod_perms):
            return PermissionLevel.MODERATOR  # Any moderation ability
        elif self._has_trusted_permissions(perms):
            return PermissionLevel.MEMBER  # Trusted permissions

        return None  # No clear permission level

    def _has_trusted_permissions(self, perms: discord.Permissions) -> bool:
        """Check if role has permissions that indicate trusted status."""
        trusted_indicators = [
            perms.send_messages_in_threads,
            perms.create_public_threads,
            perms.create_private_threads,
            perms.external_emojis,
            perms.external_stickers,
            perms.attach_files,
            perms.embed_links
        ]
        # If they have most trusted permissions, probably a trusted member role
        return sum(trusted_indicators) >= 4

    def _analyze_role_name(self, role_name: str) -> Optional[PermissionLevel]:
        """Analyze role name to suggest permission level."""
        name_lower = role_name.lower()

        # Check each level's patterns
        for level, patterns in self.role_patterns.items():
            if self._matches_pattern(name_lower, level, patterns):
                return level

        return None

    def _matches_pattern(self, name: str, level: PermissionLevel, custom_patterns: List[str] = None) -> bool:
        """Check if role name matches patterns for a permission level."""
        patterns = custom_patterns or self.role_patterns.get(level, [])

        for pattern in patterns:
            if re.search(pattern, name, re.IGNORECASE):
                return True

        return False


# // =======================================( Enhanced Permission Manager )======================================= // #


class EnhancedPermissionManager:
    """
    Enhanced permission management system with auto-detection and guild customization.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        Initialize the enhanced permission manager.

        Args:
            bot: The bot instance
        """
        self.bot = bot
        self.logger = bot.logger if hasattr(bot, 'logger') else None

        # Permission nodes registry
        self.nodes: Dict[str, PermissionNode] = {}

        # Guild configurations
        self.guild_configs: Dict[int, GuildPermissionConfig] = {}

        # Caching for performance
        self.user_permission_cache: Dict[Tuple[int, int], Tuple[PermissionLevel, float]] = {}
        self.permission_check_cache: Dict[str, Tuple[bool, float]] = {}
        self.cache_ttl: float = 300.0  # 5 minutes

        # Overrides storage (will be database-backed later)
        self.overrides: List[PermissionOverride] = []
        self.audit_log: List[PermissionAuditEntry] = []

        # Role detection system
        self.role_detector = RoleDetectionSystem(self.logger)

        # Performance tracking
        self.check_count = 0
        self.cache_hits = 0

        self._register_default_nodes()

    def _register_default_nodes(self) -> None:
        """Register default permission nodes with enhanced hierarchy."""
        default_nodes = [
            # Basic commands - anyone can use
            PermissionNode("basic.ping", PermissionLevel.EVERYONE, "Use ping command"),
            PermissionNode("basic.info", PermissionLevel.EVERYONE, "View bot information"),
            PermissionNode("basic.help", PermissionLevel.EVERYONE, "View help system"),
            PermissionNode("basic.avatar", PermissionLevel.EVERYONE, "View user avatars"),
            PermissionNode("basic.uptime", PermissionLevel.EVERYONE, "View bot uptime"),

            # Utility commands - trusted members
            PermissionNode("utility.userinfo", PermissionLevel.MEMBER, "View user information"),
            PermissionNode("utility.serverinfo", PermissionLevel.MEMBER, "View server information"),
            PermissionNode("utility.roleinfo", PermissionLevel.MEMBER, "View role information"),

            # Basic moderation commands
            PermissionNode("moderation.warn", PermissionLevel.MODERATOR, "Warn members"),
            PermissionNode("moderation.mute", PermissionLevel.MODERATOR, "Mute members"),
            PermissionNode("moderation.kick", PermissionLevel.MODERATOR, "Kick members"),
            PermissionNode("moderation.ban", PermissionLevel.MODERATOR, "Ban members"),

            # Advanced moderation commands
            PermissionNode("moderation.mass_ban", PermissionLevel.LEAD_MOD, "Mass ban members"),
            PermissionNode("moderation.lockdown", PermissionLevel.LEAD_MOD, "Lock down channels"),
            PermissionNode("moderation.purge", PermissionLevel.LEAD_MOD, "Purge messages"),

            # Basic administration
            PermissionNode("admin.settings", PermissionLevel.ADMIN, "Modify bot settings"),
            PermissionNode("admin.permissions", PermissionLevel.ADMIN, "View permissions"),
            PermissionNode("admin.reload", PermissionLevel.ADMIN, "Reload bot components"),

            # Advanced administration
            PermissionNode("admin.server_config", PermissionLevel.LEAD_ADMIN, "Configure server settings"),
            PermissionNode("admin.audit_logs", PermissionLevel.LEAD_ADMIN, "View audit logs"),
            PermissionNode("admin.permission_management", PermissionLevel.LEAD_ADMIN, "Manage permission system"),

            # Owner commands
            PermissionNode("owner.shutdown", PermissionLevel.OWNER, "Shutdown the bot"),
            PermissionNode("owner.eval", PermissionLevel.BOT_OWNER, "Execute code"),
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

    def get_guild_config(self, guild_id: int) -> GuildPermissionConfig:
        """
        Get or create guild permission configuration.

        Args:
            guild_id: The guild ID

        Returns:
            Guild permission configuration
        """
        if guild_id not in self.guild_configs:
            self.guild_configs[guild_id] = GuildPermissionConfig(guild_id=guild_id)

        return self.guild_configs[guild_id]

    async def auto_configure_guild(self, guild: discord.Guild, actor_id: Optional[int] = None) -> Tuple[Dict[int, PermissionLevel], List[discord.Role]]:
        """
        Auto-configure permission mappings for a guild.

        Args:
            guild: The guild to configure
            actor_id: User ID who initiated the configuration

        Returns:
            Tuple of (confident_mappings, uncertain_roles)
        """
        if self.logger:
            self.logger.info(f"Auto-configuring permissions for guild: {guild.name}")

        # Analyze roles
        confident_mappings, uncertain_roles = self.role_detector.analyze_guild_roles(guild)

        # Get guild config
        config = self.get_guild_config(guild.id)

        # Apply confident mappings
        config.role_mappings.update(confident_mappings)
        config.auto_configured = True
        config.configured_by = actor_id
        config.configured_at = datetime.now(timezone.utc)

        # Log the action
        audit_entry = PermissionAuditEntry(
            action="auto_configure",
            target_type="guild",
            target_id=guild.id,
            permission_data=f"Configured {len(confident_mappings)} roles",
            actor_id=actor_id or 0,
            guild_id=guild.id
        )
        self.audit_log.append(audit_entry)

        # Clear cache
        self.clear_cache()

        if self.logger:
            self.logger.info(f"Auto-configured {len(confident_mappings)} roles for {guild.name}, "
                           f"{len(uncertain_roles)} roles need manual review")

        return confident_mappings, uncertain_roles

    def set_role_permission_level(self, guild_id: int, role_id: int, level: PermissionLevel, actor_id: Optional[int] = None) -> None:
        """
        Set a permission level for a specific role.

        Args:
            guild_id: The guild ID
            role_id: The role ID
            level: The permission level to assign
            actor_id: User ID who made the change
        """
        config = self.get_guild_config(guild_id)
        old_level = config.role_mappings.get(role_id)

        config.role_mappings[role_id] = level
        self.clear_cache()

        # Log the action
        audit_entry = PermissionAuditEntry(
            action="set_role",
            target_type="role",
            target_id=role_id,
            permission_data=f"Changed from {old_level.name if old_level else 'None'} to {level.name}",
            actor_id=actor_id or 0,
            guild_id=guild_id
        )
        self.audit_log.append(audit_entry)

        if self.logger:
            self.logger.info(f"Set role {role_id} to {level.name} in guild {guild_id}")

    def set_command_requirement(self, guild_id: int, command_node: str, level: PermissionLevel, actor_id: Optional[int] = None) -> None:
        """
        Set the required permission level for a command in a specific guild.

        Args:
            guild_id: The guild ID
            command_node: The permission node name
            level: The required permission level
            actor_id: User ID who made the change
        """
        config = self.get_guild_config(guild_id)
        old_level = config.node_overrides.get(command_node)

        config.node_overrides[command_node] = level
        self.clear_cache()

        # Log the action
        audit_entry = PermissionAuditEntry(
            action="set_command",
            target_type="command",
            target_id=command_node,
            permission_data=f"Changed from {old_level.name if old_level else 'default'} to {level.name}",
            actor_id=actor_id or 0,
            guild_id=guild_id
        )
        self.audit_log.append(audit_entry)

        if self.logger:
            self.logger.info(f"Set command {command_node} to require {level.name} in guild {guild_id}")

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
        if hasattr(self.bot, 'config') and hasattr(self.bot.config, 'OWNER_IDS'):
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
            # Check if they should be LEAD_ADMIN based on role mappings
            config = self.get_guild_config(guild.id)
            for role in user.roles:
                if role.id in config.role_mappings:
                    role_level = config.role_mappings[role.id]
                    if role_level == PermissionLevel.LEAD_ADMIN:
                        return PermissionLevel.LEAD_ADMIN
            return PermissionLevel.ADMIN

        # Check specific role mappings
        config = self.get_guild_config(guild.id)
        user_level = PermissionLevel.EVERYONE

        for role in user.roles:
            if role.id in config.role_mappings:
                role_level = config.role_mappings[role.id]
                if role_level > user_level:
                    user_level = role_level

        # If no role mappings found, fall back to Discord permission analysis
        if user_level == PermissionLevel.EVERYONE:
            user_level = self._analyze_user_discord_permissions(user)

        return user_level

    def _analyze_user_discord_permissions(self, user: discord.Member) -> PermissionLevel:
        """Analyze user's Discord permissions to determine bot permission level."""
        perms = user.guild_permissions

        # Check for moderation permissions
        mod_perms = [
            perms.kick_members,
            perms.ban_members,
            perms.manage_messages,
            perms.moderate_members
        ]

        if any(mod_perms):
            return PermissionLevel.MODERATOR

        # Check for trusted permissions
        trusted_perms = [
            perms.external_emojis,
            perms.attach_files,
            perms.embed_links,
            perms.create_public_threads
        ]

        if sum(trusted_perms) >= 2:
            return PermissionLevel.MEMBER

        return PermissionLevel.EVERYONE

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

        # Get user's permission level
        user_level = self.get_user_permission_level(user, guild)

        # Banned users can't do anything
        if user_level == PermissionLevel.BANNED:
            return False

        # Check for explicit overrides first
        override_result = self._check_overrides(user, permission_node, channel, guild)
        if override_result is not None:
            return override_result

        # Get required level (with guild overrides)
        if guild:
            config = self.get_guild_config(guild.id)
            required_level = config.get_required_level(permission_node, self.nodes)
        else:
            required_level = self.nodes[permission_node].default_level

        # Check base permission level
        if user_level < required_level:
            return False

        # Check scope and role restrictions (existing logic)
        node = self.nodes[permission_node]
        if not self._check_scope_restrictions(node, channel, guild):
            return False

        if not self._check_role_restrictions(node, user, guild):
            return False

        return True

    # ... (keeping existing methods for overrides, scope restrictions, etc.)

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
            "cached_checks": len(self.permission_check_cache),
            "guild_configs": len(self.guild_configs)
        }

    def get_guild_role_mappings(self, guild: discord.Guild) -> Dict[str, PermissionLevel]:
        """
        Get role permission mappings for a guild with role names.

        Args:
            guild: The guild to get mappings for

        Returns:
            Dictionary mapping role info to permission levels
        """
        config = self.get_guild_config(guild.id)
        result = {}

        for role_id, level in config.role_mappings.items():
            role = guild.get_role(role_id)
            if role:
                result[f"{role.name} ({role_id})"] = level
            else:
                result[f"Unknown Role ({role_id})"] = level

        return result

    def get_guild_command_overrides(self, guild_id: int) -> Dict[str, PermissionLevel]:
        """
        Get command permission overrides for a guild.

        Args:
            guild_id: The guild ID

        Returns:
            Dictionary mapping command nodes to required levels
        """
        config = self.get_guild_config(guild_id)
        return config.node_overrides.copy()

    def reset_guild_config(self, guild_id: int, actor_id: Optional[int] = None) -> None:
        """
        Reset guild configuration to defaults.

        Args:
            guild_id: The guild ID
            actor_id: User ID who initiated the reset
        """
        if guild_id in self.guild_configs:
            del self.guild_configs[guild_id]

        self.clear_cache()

        # Log the action
        audit_entry = PermissionAuditEntry(
            action="reset_config",
            target_type="guild",
            target_id=guild_id,
            permission_data="Reset to defaults",
            actor_id=actor_id or 0,
            guild_id=guild_id
        )
        self.audit_log.append(audit_entry)

        if self.logger:
            self.logger.info(f"Reset permission configuration for guild {guild_id}")


# // ========================================( Updated Decorators )======================================== // #


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

            permission_manager: EnhancedPermissionManager = ctx.bot.permission_manager

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
                        # Check for guild override
                        if ctx.guild:
                            config = permission_manager.get_guild_config(ctx.guild.id)
                            required_level = config.get_required_level(permission_node, permission_manager.nodes)
                        else:
                            required_level = node.default_level
                        description = f"You need **{required_level.name.title()}** level permissions to use this command."
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
                    if ctx.guild:
                        config = permission_manager.get_guild_config(ctx.guild.id)
                        required_level = config.get_required_level(permission_node, permission_manager.nodes)
                    else:
                        required_level = permission_manager.nodes[permission_node].default_level
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

            permission_manager: EnhancedPermissionManager = ctx.bot.permission_manager

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


# Keep existing channel_only decorator unchanged
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


def setup_enhanced_permission_system(bot: commands.Bot) -> EnhancedPermissionManager:
    """
    Set up the enhanced permission system for the bot.

    Args:
        bot: The bot instance

    Returns:
        The enhanced permission manager instance
    """
    permission_manager = EnhancedPermissionManager(bot)
    bot.permission_manager = permission_manager

    # NOTE: Event handlers (on_ready, on_guild_join) moved to Application class
    # to avoid event override conflicts with @bot.event decorators

    if hasattr(bot, 'logger'):
        bot.logger.info("Successfully initialized module")

    return permission_manager
