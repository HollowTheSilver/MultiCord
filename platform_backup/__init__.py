"""
Platform Management Module
==========================

Multi-client platform management and deployment tools.
"""

__version__ = "1.0.0"

# Import platform classes when they're implemented
try:
    from .launcher import PlatformLauncher
    from .client_manager import ClientManager
    from .client_runner import ClientRunner

    __all__ = [
        "PlatformLauncher",
        "ClientManager",
        "ClientRunner",
        "__version__"
    ]
except ImportError:
    # During initial setup, these might not be fully implemented yet
    __all__ = ["__version__"]
