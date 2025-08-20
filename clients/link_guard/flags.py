"""Client FLAGS Configuration for Link Guard"""

# FLAGS system - General-purpose feature configuration
# Template: Custom Template | Plan: enterprise
FLAGS = {
    # ================== Core Platform FLAGS ================== #
    # Basic functionality available to all clients
    "base_commands": True,
    "permission_system": True,
    "error_handling": True,
    "logging_enabled": True,

    # ================== Template-Populated FLAGS ================== #
    # These are populated based on the selected template
    "moderation_enabled": True,
    "custom_commands_enabled": True,
    "analytics_enabled": True,
    "automod_enabled": True,
    "tickets_enabled": True,
    "forms_enabled": True,
    "polls_enabled": True,
    "advanced_logging_enabled": True,
    "integrations_enabled": True,
    "api_access_enabled": True,
    "priority_support_enabled": True,

    # ================== Database Configuration ================== #
    "database": {
        "backend": "sqlite",  # sqlite, firestore, postgresql
        "config": {
            # Database-specific configuration will be populated here
            # SQLite: {"file_name": "bot.db"}
            # Firestore: {"project_id": "...", "collection_prefix": "..."}
            # PostgreSQL: {"host": "...", "database": "...", "user": "..."}
        }
    },

    # ================== Limits and Quotas ================== #
    "limits": {
        "max_custom_commands": 200,
        "max_automod_rules": 50,
        "max_ticket_categories": 20,
        "analytics_retention_days": 365,

        # Performance limits
        "max_concurrent_operations": 50,
        "rate_limit_per_user": 30,  # commands per minute
        "max_embed_fields": 25,

        # Storage limits
        "max_log_size_mb": 100,
        "max_cache_entries": 1000,
    },

    # ================== User-Customizable FLAGS ================== #
    # These can be modified by users through the FLAGS editor
    "custom_embeds": True,
    "webhook_notifications": False,
    "debug_mode": False,
    "maintenance_mode": False,

    # Performance settings
    "cache_enabled": True,
    "auto_cleanup": True,
    "compress_logs": True,

    # Security settings
    "require_permissions": True,
    "audit_logging": True,
    "rate_limiting": True,

    # ================== Plan-Based Features (Optional) ================== #
    # Business model features - only populated when plan is selected
    "plan_features": {
        "plan_name": "enterprise",
        "monthly_fee": "$500",
        "support_level": "community",  # community, basic, premium, enterprise
        "priority_support": True,
        "custom_branding": True,
        "api_access": True,
    },

    # ================== Template Metadata ================== #
    "template_info": {
        "name": "Custom Template",
        "version": "1.0.0",
        "category": "custom",
        "author": "User",
        "description": "Custom client",
        "last_updated": "2025-08-20T14:41:30.513927+00:00",
        "database_recommended": "sqlite",
    },

    # ================== Custom User FLAGS ================== #
    # User-defined flags for specific use cases
    "custom": {
        # Examples:
        # "special_role_id": "123456789",
        # "welcome_channel": "general",
        # "prefix_override": "!custom",
        # "timezone": "America/New_York",
        # "language": "en-US",

        # Template-specific custom flags will be added here
        # based on template requirements and user input
    }
}

# ================== Template Processing Metadata ================== #
# This section is used by the platform for template processing
_TEMPLATE_META = {
    "flags_version": "1.0.0",
    "supports_database_backends": ["sqlite"],
    "supports_templates": ["Custom Template"],
    "plan_based": True,
    "customizable_flags": [
        "custom_embeds",
        "webhook_notifications",
        "debug_mode",
        "limits.max_custom_commands",
        "limits.rate_limit_per_user",
        "custom.*"  # All custom flags are editable
    ],
    "template_flags": [
        "moderation_enabled",
        "automod_enabled",
        "tickets_enabled",
        "analytics_enabled"
    ],
    "created_at": "2025-08-20T14:41:30.513927+00:00",
    "platform_version": "2.0.1"
}
