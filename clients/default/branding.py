"""Client Branding Configuration"""
BRANDING = {
    # Bot Identity
    "bot_name": "Link Guard",
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

    # These will cycle automatically based on STATUS_CYCLE_INTERVAL in .env
    # Types: playing, watching, listening, streaming, competing, custom
    # Format: [("Message text", "type"), ("Another message", "type")]
    "status_messages": [
        ("💻 Developed by Hollow", "custom"),
    ],

    # Footer branding for embeds
    "footer_text": "Powered by Link Guard",

    # Optional: Custom emoji or additional branding
    "custom_emoji": {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
        "shield": "🛡️"
    }
}
