"""
MultiCord Platform CLI Package
=============================

Command-line interface for MultiCord Platform bot management.
Provides professional bot orchestration with zero learning curve.
"""

from .controllers.platform_controller import PlatformController, PlatformConfig

__version__ = "2.0.0-alpha"
__author__ = "MultiCord Platform"
__description__ = "Professional Discord Bot Infrastructure CLI"

__all__ = [
    "PlatformController",
    "PlatformConfig"
]