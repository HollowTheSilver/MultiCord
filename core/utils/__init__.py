"""
Core Utilities Module
====================

Utility functions and helpers for the Discord bot.
"""

# Logging configuration
from .loguruConfig import configure_logger

# Error handling
from .error_handler import (
    EnhancedErrorHandler,
    ErrorContext,
    ErrorMessages,
    setup_enhanced_error_handling
)

# Embed utilities
from .embeds import (
    create_success_embed,
    create_error_embed,
    create_info_embed,
    create_warning_embed,
    create_latency_embed,
    create_bot_info_embed,
    create_permission_error_embed,
    EmbedBuilder,
    EmbedType
)

# Permission system
from .permission_models import (
    PermissionLevel,
    RoleType,
    PermissionScope,
    RoleCategory,
    ChannelType,
    GuildPermissionConfig,  # NOT GuildConfig
    PermissionNode,
    PermissionOverride,
    PermissionAuditEntry,
    RoleAnalysis
    # CommandPermission does NOT exist
)

from .permissions import (
    setup_enhanced_permission_system,
    require_permission,
    require_level,
    EnhancedPermissionManager,
    normalize_discord_text
)

# Exception classes
from .exceptions import (
    BotError,
    CommandError,
    ValidationError,
    PermissionError,
    ConfigurationError,
    DatabaseError,
    APIError,
    ShutdownError
)

# Database utilities
try:
    from .database import DatabaseManager
except ImportError:
    DatabaseManager = None

# Permission persistence
try:
    from .permission_persistence import PermissionPersistence
except ImportError:
    PermissionPersistence = None

__all__ = [
    # Logging
    "configure_logger",

    # Error handling
    "EnhancedErrorHandler",
    "ErrorContext",
    "ErrorMessages",
    "setup_enhanced_error_handling",

    # Embeds
    "create_success_embed",
    "create_error_embed",
    "create_info_embed",
    "create_warning_embed",
    "create_latency_embed",
    "create_bot_info_embed",
    "create_permission_error_embed",
    "EmbedBuilder",
    "EmbedType",

    # Permissions
    "PermissionLevel",
    "RoleType",
    "PermissionScope",
    "RoleCategory",
    "ChannelType",
    "GuildPermissionConfig",  # Corrected name
    "PermissionNode",
    "PermissionOverride",
    "PermissionAuditEntry",
    "RoleAnalysis",
    "setup_enhanced_permission_system",
    "require_permission",
    "require_level",
    "EnhancedPermissionManager",
    "normalize_discord_text",

    # Exceptions
    "BotError",
    "CommandError",
    "ValidationError",
    "PermissionError",
    "ConfigurationError",
    "DatabaseError",
    "APIError",
    "ShutdownError",

    # Database (if available)
    "DatabaseManager",
    "PermissionPersistence"
]
