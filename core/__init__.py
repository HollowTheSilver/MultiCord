"""
Discord Bot Core Module
======================

Shared functionality for the multi-client platform.
"""

__version__ = "2.0.1"

# Import main classes for easier access
from .application import Application

__all__ = [
    "Application",
    "__version__"
]
