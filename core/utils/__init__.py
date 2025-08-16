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

# Client-specific embed utilities
from .client_embeds import (
    create_client_success_embed,
    create_client_error_embed,
    create_client_info_embed,
    create_client_warning_embed,
    create_client_bot_info_embed,
    ClientEmbedBuilder
)

# Permission system
from .permission_models import (
    PermissionLevel,
    RoleType,
    PermissionScope,
    RoleCategory,
    ChannelType,
    GuildPermissionConfig,
    PermissionNode,
    PermissionOverride,
    PermissionAuditEntry,
    RoleAnalysis
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

    # Client embeds
    "create_client_success_embed",
    "create_client_error_embed",
    "create_client_info_embed",
    "create_client_warning_embed",
    "create_client_bot_info_embed",
    "ClientEmbedBuilder",

    # Permissions
    "PermissionLevel",
    "RoleType",
    "PermissionScope",
    "RoleCategory",
    "ChannelType",
    "GuildPermissionConfig",
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
