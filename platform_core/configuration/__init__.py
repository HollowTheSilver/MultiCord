"""
Configuration Management Package
===============================

Configuration loading, validation, and persistence for MultiCord platform.
Provides template configuration management with PostgreSQL integration.
"""

from .template_config_loader import (
    TemplateConfiguration,
    TemplateConfigurationLoader
)

__all__ = [
    "TemplateConfiguration",
    "TemplateConfigurationLoader"
]