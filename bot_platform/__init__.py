"""
Platform Management Module
=====================================================

Multi-client platform management and deployment tools.
Uses clean architecture with dependency injection.
"""

__version__ = "2.0.0"

try:
    from .service_manager import PlatformOrchestrator, ServiceManager
    from .process_manager import ProcessManager
    from .config_manager import ConfigManager
    from .client_manager import ClientManager
    from .client_runner import ClientRunner

    __all__ = [
        "PlatformOrchestrator",  # Main orchestrator
        "ServiceManager",
        "ProcessManager",
        "ConfigManager",
        # Active components
        "ClientManager",
        "ClientRunner",
        "__version__"
    ]

except ImportError:
    # During initial setup, these might not be fully implemented yet
    __all__ = ["__version__"]
