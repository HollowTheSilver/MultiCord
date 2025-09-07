"""
Core domain entities for MultiCord platform.

Contains the fundamental business objects and value objects that represent
the core concepts of the Discord bot infrastructure platform.
"""

from .process_info import ProcessInfo, ProcessSource, HealthStatus
from .bot_instance import BotInstance, BotStatus

__all__ = [
    "ProcessInfo",
    "ProcessSource", 
    "HealthStatus",
    "BotInstance",
    "BotStatus"
]