"""
Bot execution strategies for MultiCord platform.

Contains strategy pattern implementations for different bot execution approaches.
"""

from .bot_execution_strategy import (
    BotExecutionStrategy,
    BotConfiguration,
    ProcessHandle,
    ExecutionStrategyFactory,
    ExecutionError
)
from .standard_discordpy_strategy import StandardDiscordPyStrategy
from .template_based_strategy import TemplateBasedStrategy

__all__ = [
    "BotExecutionStrategy",
    "BotConfiguration", 
    "ProcessHandle",
    "ExecutionStrategyFactory",
    "ExecutionError",
    "StandardDiscordPyStrategy",
    "TemplateBasedStrategy"
]