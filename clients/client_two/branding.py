"""Client Branding Configuration for Link Guard 2

This file is the SINGLE SOURCE OF TRUTH for all bot branding and status messages.
Do NOT use STATUS_MESSAGES in .env files - configure everything here.

Status Message Configuration:
- Multiple messages will cycle automatically
- Available types: playing, watching, listening, streaming, competing, custom
- Format: [("Message text", "type"), ("Another message", "type")]
"""

BRANDING = {
    # Bot Identity
    "bot_name": "Link Guard 2",
    "bot_description": "Link Guard Dev-Build-v2",

    # Embed Color Scheme
    "embed_colors": {
        "default": 0x3498db,    # Blue
        "success": 0x2ecc71,    # Green
        "error": 0xe74c3c,      # Red
        "warning": 0xf39c12,    # Orange
        "info": 0x17a2b8,       # Cyan
        "primary": 0x007bff,    # Primary blue
    },

    # ✅ STATUS MESSAGES - Primary Configuration Location
    # These will cycle automatically based on STATUS_CYCLE_INTERVAL in .env
    "status_messages": [
        ("💻 Developed by Hollow", "custom"),
    ],

    # Footer branding for embeds
    "footer_text": "Powered by Link Guard 2",

    # Optional: Custom emoji or additional branding
    "custom_emoji": {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️"
    }
}

# ============================
# IMPORTANT NOTES:
# ============================
#
# ✅ DO: Configure status messages here in branding.py
# ❌ DON'T: Use STATUS_MESSAGES in .env files (conflicts resolved)
#
# The platform will:
# 1. Load status messages from this file
# 2. Cycle through them automatically
# 3. Use ENABLE_STATUS_CYCLING and STATUS_CYCLE_INTERVAL from .env
#
# For multiple status messages, add more tuples to the list:
# "status_messages": [
#     ("First message", "custom"),
#     ("Second message", "watching"),
#     ("Third message", "listening")
# ]
