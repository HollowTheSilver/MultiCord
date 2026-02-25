"""
MultiCord Manifest System.

This package provides the 3-layer hybrid manifest system:
- Layer 1: multicord.json (repository-level manifest)
- Layer 2: bot.json/cog.json (item-level manifests)
- Layer 3: config.toml/.env (user configuration)

Key components:
- parser: ManifestParser for reading and validating manifests
- generator: Auto-generation for Discord.py bots
- schemas: JSON schemas for validation
"""

from .parser import ManifestParser, ManifestType, ManifestValidationError
from .generator import ManifestGenerator, BotStructureAnalyzer

__all__ = [
    'ManifestParser',
    'ManifestType',
    'ManifestValidationError',
    'ManifestGenerator',
    'BotStructureAnalyzer',
]
