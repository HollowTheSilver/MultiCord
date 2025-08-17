"""
Permission System
===========================

Permission management system with:
- HIERARCHY-AWARE auto-detection of Discord roles
- ROLE CLASSIFICATION system (Bot, Cosmetic, Authority, etc.)
- UNICODE NORMALIZATION for fancy Discord text
- INTELLIGENT CHANNEL ANALYSIS with performance optimization
- SMART OWNER DETECTION using multi-factor analysis
- CHANNEL PERMISSION OVERRIDE detection for functional roles
- Guild-specific permission node overrides
- Management commands for configuration
- Two-layer architecture (Universal levels + Guild customization)
"""

import asyncio
import time
import re
import unicodedata
from datetime import datetime, timezone
from typing import (
    Dict, List, Optional, Set, Union, Callable, Any, Tuple
)
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from functools import wraps

import discord
from discord.ext import commands

# Unicode normalization library
try:
    from unidecode import unidecode
except ImportError:
    # Fallback if unidecode is not installed
    def unidecode(text: str) -> str:
        return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')

from .exceptions import PermissionError, ValidationError
from .database import DatabaseManager
from .embeds import create_error_embed, create_warning_embed, create_success_embed, create_info_embed

# Import shared models
from .permission_models import (
    PermissionLevel, PermissionScope, RoleType, RoleCategory, ChannelType,
    PermissionNode, PermissionOverride, GuildPermissionConfig,
    PermissionAuditEntry, RoleAnalysis
)


# // ========================================( Delayed Import )======================================== // #

# Import PermissionPersistence after models are available
def _get_permission_persistence():
    """Lazy import to avoid circular dependencies."""
    from .permission_persistence import PermissionPersistence
    return PermissionPersistence


# // ========================================( Unicode Text Normalization )======================================== // #


class UnicodeTextNormalizer:
    """Normalize Discord's fancy Unicode text to searchable ASCII."""

    def __init__(self):
        self.logger = None

        # Common decorative Unicode patterns used in Discord
        self.decorative_patterns = [
            # Box drawing characters (like your ━━━━━━━━━)
            r'[─━│┃┄┅┆┇┈┉┊┋┌┍┎┏┐┑┒┓└┕┖┗┘┙┚┛├┝┞┟┠┡┢┣┤┥┦┧┨┩┪┫┬┭┮┯┰┱┲┳┴┵┶┷┸┹┺┻┼┽┾┿╀╁╂╃╄╅╆╇╈╉╊╋╌╍╎╏═║╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬╭╮╯╰╱╲╳╴╵╶╷╸╹╺╻╼╽╾╿]',
            # Block elements
            r'[▀▁▂▃▄▅▆▇█▉▊▋▌▍▎▏▐░▒▓▔▕▖▗▘▙▚▛▜▝▞▟]',
            # Geometric shapes
            r'[◀◁◂◃◄◅◆◇◈◉◊○◌◍◎●◐◑◒◓◔◕◖◗◘◙◚◛◜◝◞◟◠◡◢◣◤◥◦◧◨◩◪◫◬◭◮◯]',
            # Various symbols
            r'[♀♁♂♃♄♅♆♇♈♉♊♋♌♍♎♏♐♑♒♓♔♕♖♗♘♙♚♛♜♝♞♟♠♡♢♣♤♥♦♧♨♩♪♫♬♭♮♯]',
            # Arrows
            r'[←↑→↓↔↕↖↗↘↙↚↛↜↝↞↟↠↡↢↣↤↥↦↧↨↩↪↫↬↭↮↯↰↱↲↳↴↵↶↷↸↹↺↻↼↽↾↿⇀⇁⇂⇃⇄⇅⇆⇇⇈⇉⇊⇋⇌⇍⇎⇏]',
        ]

    def normalize_text(self, text: str) -> str:
        """Convert fancy Discord text to searchable ASCII."""
        if not text:
            return ""

        try:
            # Step 1: Unicode normalization (handles accents, composites)
            normalized = unicodedata.normalize('NFKD', text)

            # Step 2: Remove decorative elements (language-agnostic)
            for pattern in self.decorative_patterns:
                normalized = re.sub(pattern, '', normalized)

            # Step 3: Clean brackets and extra whitespace
            normalized = re.sub(r'[\[\](){}〈〉《》「」『』〈〉【】]', ' ', normalized)
            normalized = re.sub(r'\s+', ' ', normalized).strip()

            # Step 4: Convert to ASCII using unidecode (handles Mathematical Bold Unicode)
            ascii_version = unidecode(normalized)

            # Step 5: Final cleanup BUT PRESERVE important punctuation for age ranges
            # Keep +, -, numbers, letters, spaces, and some punctuation
            ascii_version = re.sub(r'[^\w\s+\-]', '', ascii_version)  # Keep + and -
            ascii_version = re.sub(r'\s+', ' ', ascii_version).strip().lower()

            return ascii_version

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Text normalization failed for '{text}': {e}")
            # Fallback: basic cleanup but preserve + and -
            return re.sub(r'[^\w\s+\-]', '', text).lower().strip()


# Global normalizer instance
_text_normalizer = UnicodeTextNormalizer()


def normalize_discord_text(text: str) -> str:
    """Convenience function to normalize Discord text."""
    return _text_normalizer.normalize_text(text)


# // =======================================( Intelligent Channel Analysis )======================================= // #


class ChannelAnalysisStrategy:
    """Intelligent channel permission analysis that avoids performance traps."""

    def __init__(self, guild: discord.Guild, logger=None):
        self.guild = guild
        self.logger = logger
        self.analyzed_channels = 0
        self.max_channels = 50  # Performance limit

    def get_channels_to_analyze(self) -> List[Union[discord.TextChannel, discord.VoiceChannel, discord.ForumChannel, discord.StageChannel]]:
        """Get channels worth analyzing for permissions."""
        channels = []

        # 1. PRIORITIZE core server channels
        priority_channels = self._get_priority_channels()
        channels.extend(priority_channels)

        # 2. ADD other channels but filter problematic ones
        other_channels = self._get_filtered_channels()
        channels.extend(other_channels)

        # 3. LIMIT total analysis for performance
        limited_channels = channels[:self.max_channels]

        if self.logger and len(channels) > self.max_channels:
            self.logger.debug(f"Limited channel analysis to {self.max_channels} channels (from {len(channels)})")

        return limited_channels

    def _get_priority_channels(self) -> List[Union[discord.TextChannel, discord.VoiceChannel]]:
        """Get high-priority channels that represent real permissions."""
        priority = []

        # Main server channels (likely in top categories)
        for category in self.guild.categories[:3]:  # Top 3 categories
            for channel in category.channels[:5]:  # Max 5 per category
                if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel, discord.StageChannel)):
                    if self._is_core_channel(channel):
                        priority.append(channel)

        # Uncategorized channels (often important)
        uncategorized = [ch for ch in self.guild.channels if not ch.category and isinstance(ch, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel, discord.StageChannel))]
        for channel in uncategorized[:5]:
            if self._is_core_channel(channel):
                priority.append(channel)

        return priority

    def _get_filtered_channels(self) -> List[Union[discord.TextChannel, discord.VoiceChannel]]:
        """Get other channels, filtering out problematic ones."""
        filtered = []

        for channel in self.guild.channels:
            if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel, discord.StageChannel)):
                continue

            # Skip if already in priority
            if channel in filtered:
                continue

            # SKIP: Ticket system channels
            if self._is_ticket_channel(channel):
                continue

            # SKIP: Archived channels
            if self._is_archived_channel(channel):
                continue

            # SKIP: Bot-only channels
            if self._is_bot_channel(channel):
                continue

            # SKIP: Temporary channels
            if self._is_temporary_channel(channel):
                continue

            filtered.append(channel)

            # Performance limit
            if len(filtered) >= self.max_channels:
                break

        return filtered

    def _is_core_channel(self, channel) -> bool:
        """Identify core server channels that represent real permissions."""
        normalized_name = normalize_discord_text(channel.name)

        core_indicators = [
            'general', 'main', 'chat', 'discussion', 'announcements',
            'staff', 'admin', 'mod', 'member', 'welcome'
        ]
        return any(indicator in normalized_name for indicator in core_indicators)

    def _is_ticket_channel(self, channel) -> bool:
        """Detect ticket system channels."""
        normalized_name = normalize_discord_text(channel.name)

        ticket_patterns = [
            'ticket', 'support', 'help', 'claim', 'report'
        ]

        # Check for ticket patterns
        if any(pattern in normalized_name for pattern in ticket_patterns):
            return True

        # Check for number patterns (ticket-12345)
        if re.search(r'\b\d{3,}\b', normalized_name):  # 3+ digits often indicate tickets
            return True

        return False

    def _is_archived_channel(self, channel) -> bool:
        """Detect archived/inactive channels based on server management patterns."""

        # Check if in an "archive" category
        if channel.category:
            normalized_category = normalize_discord_text(channel.category.name)
            archive_patterns = ['archive', 'expired', 'old', 'inactive', 'closed']
            if any(pattern in normalized_category for pattern in archive_patterns):
                return True

        # Check channel name
        normalized_name = normalize_discord_text(channel.name)
        archive_patterns = ['archive', 'old-', 'closed-', 'expired', 'inactive']
        if any(pattern in normalized_name for pattern in archive_patterns):
            return True

        # Check if channel is read-only (common archive pattern)
        try:
            if hasattr(channel, 'permissions_for') and not channel.permissions_for(channel.guild.default_role).send_messages:
                # Additional checks to confirm it's archived vs restricted
                if any(archive_word in normalized_name for archive_word in ['old', 'archive', 'closed']):
                    return True
        except:
            pass  # Ignore permission check errors

        return False

    def _is_bot_channel(self, channel) -> bool:
        """Detect bot-only channels."""
        normalized_name = normalize_discord_text(channel.name)

        bot_indicators = ['bot-', 'logs', 'audit', 'commands', 'spam', 'automod']
        return any(indicator in normalized_name for indicator in bot_indicators)

    def _is_temporary_channel(self, channel) -> bool:
        """Detect temporary/event channels."""
        normalized_name = normalize_discord_text(channel.name)

        temp_indicators = ['temp-', 'event-', 'contest-', 'giveaway']
        return any(indicator in normalized_name for indicator in temp_indicators)


# // ========================================( Role Classification System )======================================== // #


class EnhancedRoleClassifier:
    """
    Intelligent role classification system that identifies role types and applies
    hierarchy-aware analysis only to authority roles.
    """

    def __init__(self, logger=None):
        self.logger = logger

        # Permission scoring weights for intelligent analysis
        self.permission_weights = {
            # Administrative permissions (highest weight)
            'administrator': 100,
            'manage_guild': 80,
            'manage_roles': 70,
            'manage_channels': 60,

            # Advanced moderation permissions
            'ban_members': 50,
            'kick_members': 45,
            'moderate_members': 40,  # Timeout permission
            'manage_messages': 35,
            'manage_nicknames': 30,
            'mute_members': 25,
            'deafen_members': 25,
            'move_members': 20,

            # Trusted member permissions
            'create_private_threads': 15,
            'create_public_threads': 10,
            'external_emojis': 8,
            'external_stickers': 8,
            'attach_files': 5,
            'embed_links': 5,
            'use_external_emojis': 5,
        }

        # Enhanced role name patterns with confidence scores
        self.authority_patterns = {
            PermissionLevel.OWNER: [
                (r'\bowner\b', 0.95),
                (r'\bfounder\b', 0.90),
                (r'\bcreator\b', 0.85),
            ],
            PermissionLevel.LEAD_ADMIN: [
                (r'\bhead.*admin\b', 0.95),
                (r'\bsenior.*admin\b', 0.95),
                (r'\blead.*admin\b', 0.95),
                (r'\bchief.*admin\b', 0.90),
                (r'\bsuper.*admin\b', 0.90),
                (r'\bco.*owner\b', 0.85),
            ],
            PermissionLevel.ADMIN: [
                (r'\badmin\b(?!.*mod)', 0.90),  # Admin but not containing mod
                (r'\badministrator\b', 0.95),
                (r'\bmanager\b', 0.75),
                (r'\bexecutive\b', 0.70),
                (r'\bdirector\b', 0.70),
                (r'\bleader\b', 0.65),
            ],
            PermissionLevel.LEAD_MOD: [
                (r'\bhead.*mod\b', 0.95),
                (r'\bsenior.*mod\b', 0.95),
                (r'\blead.*mod\b', 0.95),
                (r'\bchief.*mod\b', 0.90),
                (r'\bsuper.*mod\b', 0.90),
                (r'\bmaster.*mod\b', 0.85),
            ],
            PermissionLevel.MODERATOR: [
                (r'\bmoderator\b', 0.90),
                (r'\bmod\b(?!.*admin)', 0.85),  # Mod but not containing admin
                (r'\bhelper\b', 0.70),
                (r'\bassistant\b', 0.65),
                (r'\btrainee.*mod\b', 0.60),
                (r'\bjunior.*mod\b', 0.60),
                (r'\btrial.*mod\b', 0.55),
            ],
            PermissionLevel.MEMBER: [
                (r'\bmember\b', 0.85),
                (r'\bvip\b', 0.80),
                (r'\bverified\b', 0.75),
                (r'\btrusted\b', 0.75),
                (r'\bsupporter\b', 0.70),
                (r'\bdonator\b', 0.70),
                (r'\bregular\b', 0.65),
                (r'\bactive\b', 0.60),
            ],
        }

    def analyze_guild_roles(self, guild: discord.Guild) -> Tuple[Dict[int, PermissionLevel], List[discord.Role], Dict[int, RoleType]]:
        """
        Analyze guild roles with intelligent classification and hierarchy awareness.

        Returns:
            Tuple of (confident_mappings, uncertain_roles, role_classifications)
        """
        if self.logger:
            self.logger.info(f"Analyzing {len(guild.roles)} roles for {guild.name} with intelligent classification")

        # Step 1: Classify ALL roles by type
        role_classifications = {}
        role_analyses = []

        for role in guild.roles:
            if role.name == "@everyone":
                continue

            analysis = self._analyze_single_role(role, guild)
            role_analyses.append(analysis)
            role_classifications[role.id] = analysis.role_type

        # Step 2: ONLY process AUTHORITY roles for hierarchy
        authority_analyses = [a for a in role_analyses if a.role_type == RoleType.AUTHORITY]

        # Step 3: Apply hierarchy logic to authority roles only
        confident_mappings, uncertain_roles = self._apply_hierarchy_logic(authority_analyses, guild)

        if self.logger:
            self.logger.info(f"Role classification complete: {len(confident_mappings)} authority mappings, "
                           f"{len(uncertain_roles)} uncertain, {len(role_classifications)} total classified")

        return confident_mappings, uncertain_roles, role_classifications

    def _analyze_single_role(self, role: discord.Role, guild: discord.Guild) -> RoleAnalysis:
        """Analyze a single role for type and authority level."""
        analysis = RoleAnalysis(role)

        # Step 1: Classify role type first
        analysis.role_type = self._classify_role_type(role, guild)

        # Step 2: Check for channel overrides
        analysis.has_channel_overrides = self._has_any_channel_overrides(role, guild)

        # Step 3: Check if this is an owner role
        analysis.is_owner_role = self._is_owner_role(role, guild)

        # Step 4: If it's an authority role, analyze hierarchy details
        if analysis.role_type == RoleType.AUTHORITY:
            analysis.permission_score = self._calculate_permission_score(role.permissions)

            # Analyze name patterns
            name_level, confidence = self._analyze_authority_name(role.name)
            if name_level:
                analysis.name_indicators.append(f"{name_level.name}({confidence:.2f})")

            # Categorize the authority role
            analysis.category = self._categorize_authority_role(role, analysis.permission_score, name_level)

            # Calculate overall confidence
            analysis.confidence = self._calculate_confidence(analysis, role)

        return analysis

    def _classify_role_type(self, role: discord.Role, guild: discord.Guild) -> RoleType:
        """Intelligently classify role type using contextual patterns with permissions-first logic."""

        # PRIORITY 1: Bot roles (highest priority)
        if role.is_bot_managed():
            return RoleType.BOT

        # Check role tags for bots
        if hasattr(role, 'tags') and role.tags:
            if getattr(role.tags, 'bot_id', None):
                return RoleType.BOT

        # PRIORITY 2: Discord integrations (before other checks)
        if hasattr(role, 'tags') and role.tags:
            # Only classify as integration if there's a specific integration ID or it's premium subscriber
            if (getattr(role.tags, 'integration_id', None) or
                    getattr(role.tags, 'premium_subscriber', None) == True):
                if self.logger:
                    self.logger.info(f"Role '{role.name}' classified as INTEGRATION due to tags")
                return RoleType.INTEGRATION

        # Normalize name for pattern matching
        normalized_name = normalize_discord_text(role.name)

        # Check for Discord-specific integration patterns
        integration_patterns = ['booster', 'boost', 'nitro', 'premium']
        if any(pattern in normalized_name for pattern in integration_patterns):
            if self.logger:
                self.logger.info(f"Role '{role.name}' classified as INTEGRATION due to pattern")
            return RoleType.INTEGRATION

        # PRIORITY 3: Channel permission overrides = FUNCTIONAL (before name checks)
        if self._has_any_channel_overrides(role, guild):
            # SPECIAL CASE: Check if this is still an authority role despite channel overrides
            authority_name_patterns = [
                'admin', 'administrator', 'mod', 'moderator', 'owner', 'founder',
                'staff', 'leader', 'manager', 'executive', 'director', 'member'  # Added 'member'
            ]

            # If it matches authority patterns OR has authority permissions, treat as authority
            if (any(pattern in normalized_name for pattern in authority_name_patterns) or
                    self._has_authority_permissions(role) or
                    self._is_verification_role(role, guild)):
                # This is an authority role that happens to have channel overrides
                # Continue to authority classification below
                pass
            else:
                # No authority indicators but has channel overrides = functional
                return RoleType.FUNCTIONAL

        # PRIORITY 4: Authority permissions and patterns
        if self._has_authority_permissions(role):
            if self.logger:
                self.logger.info(f"Role '{role.name}' classified as AUTHORITY due to permissions")
            return RoleType.AUTHORITY

        # Check for staff/hierarchy authority patterns
        authority_name_patterns = [
            'admin', 'administrator', 'mod', 'moderator', 'owner', 'founder',
            'staff', 'leader', 'manager', 'executive', 'director'
        ]
        if any(pattern in normalized_name for pattern in authority_name_patterns):
            if self.logger:
                self.logger.info(f"Role '{role.name}' classified as AUTHORITY due to staff pattern")
            return RoleType.AUTHORITY

        # Check for verification/base authority roles
        if self._is_verification_role(role, guild):
            if self.logger:
                self.logger.info(f"Role '{role.name}' classified as AUTHORITY due to verification pattern")
            return RoleType.AUTHORITY

        # PRIORITY 5: Single-member analysis (for bots or special cases)
        if len(role.members) == 1:
            member = role.members[0]
            if member.bot:
                return RoleType.BOT
            # Single human member with no authority permissions might be functional
            if not self._has_authority_permissions(role) and not self._has_any_channel_overrides(role, guild):
                # Single member, no special permissions = probably cosmetic/personal
                return RoleType.COSMETIC

        # PRIORITY 6: No permissions + demographic patterns = COSMETIC
        if role.permissions.value == 0 or self._has_only_cosmetic_permissions(role):
            # Enhanced demographic/cosmetic patterns
            demographic_patterns = [
                # Age groups (common reaction role pattern)
                r'\d{2}[+-]', r'\d{2}-\d{2}', r'\d{2}\+',
                r'\bteen\b', r'\badult\b', r'\bsenior\b',

                # Employment/life status (classic reaction roles)
                r'\bemployed\b', r'\bunemployed\b', r'\bstudent\b', r'\bretired\b',
                r'\bworking\b', r'\buniversity\b', r'\bcollege\b', r'\bhigh.*school\b',

                # Demographics/identity (popular reaction categories)
                r'\bmale\b', r'\bfemale\b', r'\bsingle\b', r'\bmarried\b', r'\btaken\b',

                # Geographic/timezone (common server reaction roles)
                r'\best\b', r'\bpst\b', r'\bcst\b', r'\bmst\b', r'\butc\b', r'\bgmt\b',
                r'\busa\b', r'\bcanada\b', r'\beurope\b', r'\basia\b', r'\baest\b', r'\bjst\b',
                r'\beet\b', r'\bcet\b', r'\bbrt\b',

                # Personality/community types (trendy reaction roles)
                r'\bedger\b', r'\bgooner\b', r'\bnormie\b', r'\bweeb\b', r'\bgamer\b',

                # Community-specific identity
                r'\basylee\b', r'\brefugee\b', r'\bimmigrant\b', r'\bnewbie\b', r'\bseeker\b',
                r'\bdetainee\b', r'\bresident\b', r'\bnational\b',

                # LGBTQ+ and identity terms
                r'\btrans\b', r'\bgay\b', r'\blesbian\b', r'\bbi\b', r'\bqueer\b',

                # Racial/ethnic descriptors (sometimes used in communities)
                r'\bblack\b', r'\bwhite\b', r'\basian\b', r'\blatino\b', r'\bharkie\b', r'\bdarkie\b'
            ]

            if any(re.search(pattern, normalized_name, re.IGNORECASE) for pattern in demographic_patterns):
                return RoleType.COSMETIC

            # High member count with no/minimal permissions = cosmetic
            if len(role.members) > 5:
                return RoleType.COSMETIC

        # PRIORITY 7: Team/color roles (classic cosmetic pattern)
        team_patterns = ['team', 'red', 'blue', 'green', 'yellow', 'purple', 'orange', 'squad']
        if any(pattern in normalized_name for pattern in team_patterns):
            return RoleType.COSMETIC

        # PRIORITY 8: Event/temporary roles
        temp_patterns = ['event', 'contest', 'giveaway', 'temp', 'trial', 'beta', 'test']
        if any(pattern in normalized_name for pattern in temp_patterns):
            return RoleType.TEMPORARY

        # PRIORITY 9: Emoji-only or decorative names (like @🎀🌸🎀)
        # If role name is mostly/only emojis and symbols, it's likely cosmetic
        emoji_and_symbol_count = sum(1 for char in role.name if not char.isalnum() and not char.isspace())
        if emoji_and_symbol_count >= len(role.name) * 0.7:  # 70% or more non-alphanumeric
            return RoleType.COSMETIC

        # DEFAULT: If we get here, log why it's unknown
        if self.logger:
            self.logger.info(f"Role '{role.name}' classified as UNKNOWN - no clear pattern matched", extra={
                "permissions_value": role.permissions.value,
                "member_count": len(role.members),
                "normalized_name": normalized_name,
                "has_channel_overrides": self._has_any_channel_overrides(role, guild),
                "has_authority_perms": self._has_authority_permissions(role)
            })

        return RoleType.UNKNOWN

    def _is_verification_role(self, role: discord.Role, guild: discord.Guild) -> bool:
        """Detect main server verification/access role using multi-factor analysis."""
        member_count = guild.member_count or 1  # Avoid division by zero
        adoption_rate = len(role.members) / member_count

        # High adoption (40%+) + channel config + name pattern
        has_channel_config = self._has_any_channel_overrides(role, guild)

        verification_patterns = ['member', 'verified', 'citizen', 'user']
        name_match = any(pattern in normalize_discord_text(role.name)
                        for pattern in verification_patterns)

        return (adoption_rate >= 0.4 and has_channel_config and name_match)

    def _is_owner_role(self, role: discord.Role, guild: discord.Guild) -> bool:
        """Detect owner role using multi-factor analysis."""
        confidence = 0.0

        # Server owner has this role
        if guild.owner and guild.owner in role.members:
            confidence += 0.4

        # High position (top 10%)
        total_roles = len(guild.roles)
        if total_roles > 1:
            relative_position = role.position / total_roles
            if relative_position > 0.9:
                confidence += 0.3

        # Has admin permissions
        if role.permissions.administrator:
            confidence += 0.2

        # Small exclusive membership (1-3 people)
        if 1 <= len(role.members) <= 3:
            confidence += 0.1

        return confidence > 0.6  # Require multiple factors

    def _has_any_channel_overrides(self, role: discord.Role, guild: discord.Guild) -> bool:
        """Check if role has ANY channel permission configuration using smart analysis."""
        # Use our existing performance-optimized channel analysis
        channel_analyzer = ChannelAnalysisStrategy(guild, self.logger)
        channels_to_check = channel_analyzer.get_channels_to_analyze()

        # Check the filtered set (max 50 channels, skips tickets/archives)
        for channel in channels_to_check:
            if role in channel.overwrites:
                return True

        # Also check categories (fewer to analyze)
        for category in guild.categories[:10]:  # Limit categories too
            if role in category.overwrites:
                return True

        return False

    def _has_authority_permissions(self, role: discord.Role) -> bool:
        """Check if role has permissions that indicate hierarchical authority."""
        authority_perms = [
            'administrator', 'manage_guild', 'manage_roles', 'manage_channels',
            'kick_members', 'ban_members', 'moderate_members', 'manage_messages',
            'mute_members', 'deafen_members', 'move_members'  # Added more mod permissions
        ]

        # Check for any authority permissions
        has_authority = any(getattr(role.permissions, perm, False) for perm in authority_perms)

        # Also check if role is high in hierarchy (top 30% of roles)
        if not has_authority and role.guild:
            total_roles = len(role.guild.roles)
            if total_roles > 1:
                relative_position = role.position / total_roles
                # If role is in top 30% and has some permissions, might be authority
                if relative_position > 0.7 and role.permissions.value > 0:
                    has_authority = True

        return has_authority

    def _has_only_cosmetic_permissions(self, role: discord.Role) -> bool:
        """Check if role only has cosmetic/display permissions."""
        cosmetic_perms = [
            'external_emojis', 'external_stickers', 'attach_files',
            'embed_links', 'use_external_emojis', 'change_nickname'
        ]
        # Has some cosmetic perms but no authority perms
        return (any(getattr(role.permissions, perm, False) for perm in cosmetic_perms) and
                not self._has_authority_permissions(role))

    def _calculate_permission_score(self, permissions: discord.Permissions) -> int:
        """Calculate a numeric score based on Discord permissions."""
        score = 0

        for perm_name, weight in self.permission_weights.items():
            if hasattr(permissions, perm_name) and getattr(permissions, perm_name):
                score += weight

        return score

    def _analyze_authority_name(self, role_name: str) -> Tuple[Optional[PermissionLevel], float]:
        """Analyze role name for authority level indicators."""
        normalized_name = normalize_discord_text(role_name)
        best_match = None
        best_confidence = 0.0

        for level, patterns in self.authority_patterns.items():
            for pattern, confidence in patterns:
                if re.search(pattern, normalized_name, re.IGNORECASE):
                    if confidence > best_confidence:
                        best_match = level
                        best_confidence = confidence

        return best_match, best_confidence

    def _categorize_authority_role(self, role: discord.Role, permission_score: int, name_level: Optional[PermissionLevel]) -> RoleCategory:
        """Categorize an authority role based on permissions and name."""
        # Administrator permission = administrative
        if role.permissions.administrator:
            return RoleCategory.ADMINISTRATIVE

        # High permission score = likely moderation
        if permission_score >= 40:  # Has ban/kick or multiple mod permissions
            return RoleCategory.MODERATION

        # Some mod permissions but not high score
        if permission_score >= 15:  # Has some moderation capabilities
            return RoleCategory.MODERATION

        # Trusted permissions but not moderation
        if permission_score >= 5:  # Has trusted member permissions
            return RoleCategory.TRUSTED_MEMBER

        # Name indicates special role
        if name_level and name_level >= PermissionLevel.MEMBER:
            return RoleCategory.SPECIAL

        return RoleCategory.UNKNOWN

    def _calculate_confidence(self, analysis: RoleAnalysis, role: discord.Role) -> float:
        """Calculate overall confidence in the authority role analysis."""
        confidence = 0.0

        # Permission-based confidence
        if role.permissions.administrator:
            confidence += 0.8  # Very confident about admin roles
        elif analysis.permission_score >= 40:
            confidence += 0.7  # Confident about clear moderation roles
        elif analysis.permission_score >= 15:
            confidence += 0.5  # Moderately confident
        elif analysis.permission_score >= 5:
            confidence += 0.3  # Some confidence for trusted roles

        # Name-based confidence
        name_level, name_confidence = self._analyze_authority_name(role.name)
        if name_level:
            confidence += name_confidence * 0.4  # Name contributes up to 40%

        # Role characteristics
        if not role.is_bot_managed() and not role.is_integration():
            confidence += 0.1  # More confident in manually created roles

        # Position indicators (very high or very low positions are clearer)
        total_roles = len(role.guild.roles)
        if total_roles > 1:  # Avoid division by zero
            relative_position = role.position / total_roles
            if relative_position > 0.8:  # Top 20% of roles
                confidence += 0.1
            elif relative_position < 0.2:  # Bottom 20% of roles
                confidence += 0.05

        return min(confidence, 1.0)

    def _apply_hierarchy_logic(self, authority_analyses: List[RoleAnalysis], guild: discord.Guild) -> Tuple[Dict[int, PermissionLevel], List[discord.Role]]:
        """Apply hierarchy-aware logic to authority roles with name-first, position-fallback approach."""
        confident_mappings = {}
        uncertain_roles = []

        for analysis in authority_analyses:
            role = analysis.role

            # Special case: Owner role detection
            if analysis.is_owner_role:
                confident_mappings[role.id] = PermissionLevel.OWNER
                continue

            # Try name-based detection first
            name_level, confidence = self._analyze_authority_name(role.name)

            if name_level and confidence > 0.7:
                # High confidence in name - use it
                confident_mappings[role.id] = name_level
            else:
                # Name unclear - use position-based assignment
                position_level = self._position_based_level(role, authority_analyses)
                if position_level:
                    confident_mappings[role.id] = position_level
                else:
                    uncertain_roles.append(role)

        return confident_mappings, uncertain_roles

    def _position_based_level(self, role: discord.Role, authority_analyses: List[RoleAnalysis]) -> Optional[PermissionLevel]:
        """Assign authority level based on Discord position hierarchy."""
        # Sort all authority roles by position (highest first)
        sorted_roles = sorted([a.role for a in authority_analyses], key=lambda r: r.position, reverse=True)

        try:
            role_index = sorted_roles.index(role)
            total_authority_roles = len(sorted_roles)

            if total_authority_roles == 1:
                return PermissionLevel.ADMIN  # Single authority role

            # Position-based percentile assignment
            percentile = role_index / total_authority_roles

            if percentile <= 0.1:  # Top 10%
                return PermissionLevel.LEAD_ADMIN
            elif percentile <= 0.3:  # Next 20%
                return PermissionLevel.ADMIN
            elif percentile <= 0.5:  # Next 20%
                return PermissionLevel.LEAD_MOD
            elif percentile <= 0.7:  # Next 20%
                return PermissionLevel.MODERATOR
            else:  # Bottom 30%
                return PermissionLevel.MEMBER

        except ValueError:
            return None

    def get_analysis_report(self, guild: discord.Guild) -> str:
        """Generate a detailed analysis report for debugging."""
        lines = [f"Enhanced Role Analysis Report for {guild.name}"]
        lines.append("=" * 60)

        role_analyses = []
        for role in guild.roles:
            if role.name == "@everyone":
                continue
            role_analyses.append(self._analyze_single_role(role, guild))

        # Sort by position (highest first)
        role_analyses.sort(key=lambda a: a.role.position, reverse=True)

        # Group by role type for better organization
        role_types = {}
        for analysis in role_analyses:
            if analysis.role_type not in role_types:
                role_types[analysis.role_type] = []
            role_types[analysis.role_type].append(analysis)

        for role_type, analyses in role_types.items():
            lines.append(f"\n{role_type.value.upper()} ROLES ({len(analyses)}):")
            lines.append("-" * 40)

            for analysis in analyses[:10]:  # Limit per type
                role = analysis.role
                lines.append(f"\n{role.name} (Position: {role.position})")
                lines.append(f"  Members: {analysis.member_count}")
                lines.append(f"  Managed: {analysis.is_managed}")
                lines.append(f"  Channel Overrides: {analysis.has_channel_overrides}")
                lines.append(f"  Owner Role: {analysis.is_owner_role}")

                if analysis.role_type == RoleType.AUTHORITY:
                    lines.append(f"  Category: {analysis.category.value}")
                    lines.append(f"  Permission Score: {analysis.permission_score}")
                    lines.append(f"  Confidence: {analysis.confidence:.2f}")

                    name_level, name_confidence = self._analyze_authority_name(role.name)
                    lines.append(f"  Name Level: {name_level.name if name_level else 'None'} ({name_confidence:.2f})")

                lines.append(f"  Discord Perms: admin={role.permissions.administrator}, "
                            f"ban={role.permissions.ban_members}, kick={role.permissions.kick_members}")

            if len(analyses) > 10:
                lines.append(f"  ... and {len(analyses) - 10} more {role_type.value} roles")

        return "\n".join(lines)


# // =======================================( Enhanced Permission Manager )======================================= // #


class EnhancedPermissionManager:
    """
    Permission management system with intelligent role classification,
    hierarchy-aware auto-detection, and performance optimization.
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

        # Guild configurations
        self.guild_configs: Dict[int, GuildPermissionConfig] = {}

        # Caching for performance
        self.user_permission_cache: Dict[Tuple[int, int], Tuple[PermissionLevel, float]] = {}
        self.permission_check_cache: Dict[str, Tuple[bool, float]] = {}
        self.cache_ttl: float = 300.0  # 5 minutes

        # Overrides storage (database-backed)
        self.overrides: List[PermissionOverride] = []
        self.audit_log: List[PermissionAuditEntry] = []

        # Database persistence (initialized later)
        self.db_manager: Optional[DatabaseManager] = None
        self.persistence: Optional[Any] = None  # PermissionPersistence (delayed import)

        # Enhanced role classification system
        self.role_classifier = EnhancedRoleClassifier(self.logger)

        # Performance tracking
        self.check_count = 0
        self.cache_hits = 0

        # Set up text normalizer logging
        if self.logger:
            _text_normalizer.logger = self.logger

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
        Auto-configure permission mappings for a guild using intelligent role classification.

        Args:
            guild: The guild to configure
            actor_id: User ID who initiated the configuration

        Returns:
            Tuple of (confident_mappings, uncertain_roles)
        """
        if self.logger:
            self.logger.info(f"Auto-configuring permissions for guild: {guild.name} with intelligent role classification")

        # Use enhanced role classification system
        confident_mappings, uncertain_roles, role_classifications = self.role_classifier.analyze_guild_roles(guild)

        # Get guild config
        config = self.get_guild_config(guild.id)

        # Store role classifications and mappings
        config.role_classifications.update(role_classifications)
        config.role_mappings.update(confident_mappings)
        config.auto_configured = True
        config.configured_by = actor_id
        config.configured_at = datetime.now(timezone.utc)

        # Log the action with classification summary
        classification_summary = {}
        for role_type in RoleType:
            count = sum(1 for rt in role_classifications.values() if rt == role_type)
            if count > 0:
                classification_summary[role_type.value] = count

        audit_entry = PermissionAuditEntry(
            action="auto_configure",
            target_type="guild",
            target_id=guild.id,
            permission_data=f"Intelligent classification: {classification_summary}, {len(confident_mappings)} authority mappings",
            actor_id=actor_id or 0,
            guild_id=guild.id
        )
        self.audit_log.append(audit_entry)
        await self._save_audit_entry(audit_entry)

        # Clear cache
        self.clear_cache()
        await self._save_to_database(guild.id)

        if self.logger:
            self.logger.info(f"Intelligent auto-configuration complete for {guild.name}: "
                           f"{len(confident_mappings)} authority roles mapped, "
                           f"{len(uncertain_roles)} need review, "
                           f"{len(role_classifications)} total classified")

        return confident_mappings, uncertain_roles

    async def set_role_permission_level(self, guild_id: int, role_id: int, level: PermissionLevel, actor_id: Optional[int] = None) -> None:
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
        await self._save_to_database(guild_id)

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
        await self._save_audit_entry(audit_entry)

        if self.logger:
            self.logger.info(f"Set role {role_id} to {level.name} in guild {guild_id}")

    async def set_role_classification(self, guild_id: int, role_id: int, role_type: RoleType,
                                      actor_id: Optional[int] = None) -> None:
        """
        Manually override the classification for a specific role.

        Args:
            guild_id: The guild ID
            role_id: The role ID
            role_type: The role type to assign
            actor_id: User ID who made the change
        """
        config = self.get_guild_config(guild_id)
        old_type = config.role_classifications.get(role_id)

        config.role_classifications[role_id] = role_type
        self.clear_cache()
        await self._save_to_database(guild_id)

        # Log the action
        audit_entry = PermissionAuditEntry(
            action="set_role_type",
            target_type="role",
            target_id=role_id,
            permission_data=f"Changed from {old_type.value if old_type else 'None'} to {role_type.value}",
            actor_id=actor_id or 0,
            guild_id=guild_id
        )
        self.audit_log.append(audit_entry)
        await self._save_audit_entry(audit_entry)

        if self.logger:
            self.logger.info(f"Set role {role_id} classification to {role_type.value} in guild {guild_id}")

    async def set_command_requirement(self, guild_id: int, command_node: str, level: PermissionLevel, actor_id: Optional[int] = None) -> None:
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
        await self._save_to_database(guild_id)

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
        await self._save_audit_entry(audit_entry)

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

        # Check specific role mappings (only AUTHORITY roles should be mapped)
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

        # Check scope and role restrictions
        node = self.nodes[permission_node]
        if not self._check_scope_restrictions(node, channel, guild):
            return False

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

    def get_guild_role_classifications(self, guild: discord.Guild) -> Dict[str, RoleType]:
        """
        Get role classifications for a guild with role names.

        Args:
            guild: The guild to get classifications for

        Returns:
            Dictionary mapping role info to role types
        """
        config = self.get_guild_config(guild.id)
        result = {}

        for role_id, role_type in config.role_classifications.items():
            role = guild.get_role(role_id)
            if role:
                result[f"{role.name} ({role_id})"] = role_type
            else:
                result[f"Unknown Role ({role_id})"] = role_type

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

    async def reset_guild_config(self, guild_id: int, actor_id: Optional[int] = None) -> None:
        """
        Reset guild configuration to defaults.

        Args:
            guild_id: The guild ID
            actor_id: User ID who initiated the reset
        """
        if guild_id in self.guild_configs:
            del self.guild_configs[guild_id]

        if self.persistence:
            await self.persistence.delete_guild_config(guild_id)

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
        await self._save_audit_entry(audit_entry)

        if self.logger:
            self.logger.info(f"Reset permission configuration for guild {guild_id}")

    # // ========================================( Database Methods )======================================== // #

    async def initialize_database(self, db_path: str = "data/permissions.db") -> None:
        """Initialize database persistence layer."""
        try:
            self.db_manager = DatabaseManager(db_path, self.logger)
            await self.db_manager.initialize()

            # Use delayed import to avoid circular dependency
            PermissionPersistence = _get_permission_persistence()
            self.persistence = PermissionPersistence(self.db_manager, self.logger)

            # Load existing configurations from database
            await self._load_from_database()

            if self.logger:
                self.logger.info("Database persistence initialized")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Database initialization failed: {e}")
            # Continue without database persistence
            self.db_manager = None
            self.persistence = None

    async def _load_from_database(self) -> None:
        """Load existing configurations from database."""
        if not self.persistence:
            return

        try:
            # Load all guild configurations
            stored_configs = await self.persistence.load_all_guild_configs()
            self.guild_configs.update(stored_configs)

            # Load permission overrides
            self.overrides = await self.persistence.load_permission_overrides()

            # Load recent audit entries (last 1000)
            recent_entries = await self.persistence.load_audit_entries(limit=1000)
            self.audit_log.extend(recent_entries)

            if self.logger:
                self.logger.info(f"Loaded {len(stored_configs)} guild configs from database")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load from database: {e}")

    async def _save_to_database(self, guild_id: int) -> None:
        """Save guild configuration to database."""
        if not self.persistence:
            return

        try:
            config = self.guild_configs.get(guild_id)
            if config:
                await self.persistence.save_guild_config(guild_id, config)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save guild {guild_id} to database: {e}")

    async def _save_audit_entry(self, entry: PermissionAuditEntry) -> None:
        """Save audit entry to database."""
        if self.persistence:
            await self.persistence.save_audit_entry(entry)

    async def cleanup_database(self) -> None:
        """Cleanup old database entries."""
        if self.persistence:
            # Cleanup old audit entries (older than 30 days)
            await self.db_manager.cleanup_old_data(30)

            # Cleanup expired overrides
            await self.persistence.cleanup_expired_overrides()

    # Add shutdown method:
    async def shutdown(self) -> None:
        """Shutdown database connections."""
        if self.db_manager:
            await self.db_manager.close()


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

    if hasattr(bot, 'logger'):
        bot.logger.info("Successfully initialized module")

    return permission_manager
