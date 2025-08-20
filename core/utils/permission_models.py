"""
Permission Models
================

Shared data models for the permission system to avoid circular imports.
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Union, Any
from enum import Enum, IntEnum
from dataclasses import dataclass, field

import discord


# // ========================================( Permission Models )======================================== // #


class PermissionLevel(IntEnum):
    """
    Universal permission levels with proper hierarchy.
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


class RoleType(Enum):
    """Real-world role type classification for intelligent auto-configuration."""
    AUTHORITY = "authority"      # Human hierarchy roles (what we focus on for permissions)
    BOT = "bot"                  # Bot-managed roles
    INTEGRATION = "integration"  # Discord integrations (Nitro, Twitch, etc.)
    COSMETIC = "cosmetic"        # Color/display only, no meaningful permissions
    FUNCTIONAL = "functional"    # Channel-specific permissions only
    TEMPORARY = "temporary"      # Event/temporary roles
    UNKNOWN = "unknown"          # Couldn't classify confidently


class RoleCategory(Enum):
    """Categories for grouping authority roles by function."""
    ADMINISTRATIVE = "administrative"
    MODERATION = "moderation"
    TRUSTED_MEMBER = "trusted_member"
    SPECIAL = "special"
    UNKNOWN = "unknown"


class ChannelType(Enum):
    """Channel types for intelligent analysis."""
    CORE = "core"                # Important server channels
    TICKET = "ticket"            # Ticket system channels
    ARCHIVE = "archive"          # Archived/inactive channels
    BOT = "bot"                  # Bot-only channels
    TEMPORARY = "temporary"      # Temporary/event channels
    UNKNOWN = "unknown"          # Couldn't classify


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
    role_classifications: Dict[int, RoleType] = field(default_factory=dict)  # role_id -> type
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


@dataclass
class RoleAnalysis:
    """Analysis result for a single role."""
    def __init__(self, role: discord.Role):
        self.role = role
        self.role_type = RoleType.UNKNOWN
        self.category = RoleCategory.UNKNOWN
        self.permission_score = 0
        self.name_indicators: List[str] = []
        self.suggested_level: Optional[PermissionLevel] = None
        self.confidence = 0.0  # 0.0 to 1.0
        self.member_count = len(role.members)
        self.is_managed = role.is_bot_managed()
        self.has_channel_overrides = False
        self.is_owner_role = False
