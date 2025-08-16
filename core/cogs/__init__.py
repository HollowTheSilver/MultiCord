"""
Core Cogs Module
===============

Discord bot command modules and event handlers.
"""

# Import main cogs
from .base_commands import BaseCommands
from .permission_manager import PermissionManager

__all__ = [
    "BaseCommands",
    "PermissionManager"
]
