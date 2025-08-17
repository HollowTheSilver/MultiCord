"""Client Feature Configuration"""
FEATURES = {
    "base_commands": True,
    "permission_system": True,
    "moderation": {MODERATION_ENABLED},
    "custom_commands": True,
    "limits": {
        "max_custom_commands": 200,
    }
}
