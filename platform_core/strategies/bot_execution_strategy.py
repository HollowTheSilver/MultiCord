"""
Bot Execution Strategy Interface
===============================

Core strategy pattern interface for multi-path bot execution.
Enables standard Discord.py, template-based, and enhanced bots as equal first-class citizens.
"""

import asyncio
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from uuid import UUID
from pathlib import Path

from ..entities.process_info import ProcessInfo, HealthStatus


@dataclass
class BotConfiguration:
    """Configuration for bot execution."""
    client_id: str
    instance_id: UUID
    execution_strategy: str
    environment_config: Dict[str, Any]
    technical_features: List[str]
    log_directory: Path
    
    # Strategy-specific configuration
    discord_token: Optional[str] = None
    template_path: Optional[Path] = None
    custom_flags: Optional[Dict[str, Any]] = None
    

@dataclass
class ProcessHandle:
    """Handle for managing a running bot process."""
    process_info: ProcessInfo
    subprocess_handle: Optional[subprocess.Popen] = None
    
    @property
    def is_running(self) -> bool:
        """Check if the process is currently running."""
        return self.process_info.is_running
    
    def get_health_status(self) -> HealthStatus:
        """Get current health status."""
        return self.process_info.get_current_health_status()


class BotExecutionStrategy(ABC):
    """
    Abstract base class for bot execution strategies.
    
    Enables multiple bot execution approaches as equal first-class citizens:
    - StandardDiscordPyStrategy: Vanilla Discord.py bots with zero modifications
    - TemplateBasedStrategy: Template-based bots with convenience features  
    - EnhancedBotStrategy: Bots with injected technical platform features
    
    All strategies integrate with PostgreSQL for process tracking and state management.
    """
    
    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Name of this execution strategy."""
        pass
    
    @property
    @abstractmethod
    def supports_zero_modification(self) -> bool:
        """Whether this strategy supports running unmodified Discord.py bots."""
        pass
    
    @abstractmethod
    async def validate_configuration(self, config: BotConfiguration) -> bool:
        """
        Validate that the configuration is suitable for this strategy.
        
        Args:
            config: Bot configuration to validate
            
        Returns:
            bool: True if configuration is valid for this strategy
        """
        pass
    
    @abstractmethod
    async def prepare_execution_environment(self, config: BotConfiguration) -> Dict[str, Any]:
        """
        Prepare the execution environment for the bot.
        
        Args:
            config: Bot configuration
            
        Returns:
            Dict containing environment variables and setup information
        """
        pass
    
    @abstractmethod
    async def start(self, config: BotConfiguration) -> ProcessHandle:
        """
        Start a bot process using this execution strategy.
        
        Args:
            config: Bot configuration
            
        Returns:
            ProcessHandle: Handle for the running process
            
        Raises:
            ExecutionError: If the bot cannot be started
        """
        pass
    
    @abstractmethod
    async def stop(self, handle: ProcessHandle) -> bool:
        """
        Stop a running bot process.
        
        Args:
            handle: Process handle from start()
            
        Returns:
            bool: True if process was stopped successfully
        """
        pass
    
    @abstractmethod
    async def restart(self, handle: ProcessHandle, config: BotConfiguration) -> ProcessHandle:
        """
        Restart a bot process.
        
        Args:
            handle: Current process handle
            config: Bot configuration (may be updated)
            
        Returns:
            ProcessHandle: Handle for the new process
        """
        pass
    
    @abstractmethod
    async def get_health_status(self, handle: ProcessHandle) -> HealthStatus:
        """
        Get detailed health status for the running bot.
        
        Args:
            handle: Process handle
            
        Returns:
            HealthStatus: Current health information
        """
        pass
    
    @abstractmethod
    async def get_logs(self, handle: ProcessHandle, lines: int = 100) -> List[str]:
        """
        Get recent log lines from the bot process.
        
        Args:
            handle: Process handle
            lines: Number of recent lines to retrieve
            
        Returns:
            List of log line strings
        """
        pass
    
    # Default implementations for common functionality
    
    async def get_process_metrics(self, handle: ProcessHandle) -> Dict[str, Any]:
        """Get basic process metrics (memory, CPU, etc.)."""
        health = await self.get_health_status(handle)
        return {
            "is_running": health.is_running,
            "memory_mb": health.memory_mb,
            "cpu_percent": health.cpu_percent,
            "uptime_seconds": health.uptime_seconds,
            "last_check": health.last_check.isoformat(),
            "error_message": health.error_message
        }
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get information about this strategy."""
        return {
            "name": self.strategy_name,
            "supports_zero_modification": self.supports_zero_modification,
            "description": self.__doc__ or "No description available"
        }


class ExecutionStrategyFactory:
    """
    Factory for creating appropriate bot execution strategies.
    
    Manages registration and selection of execution strategies.
    """
    
    def __init__(self):
        """Initialize strategy factory."""
        self._strategies: Dict[str, BotExecutionStrategy] = {}
    
    def register_strategy(self, strategy: BotExecutionStrategy) -> None:
        """
        Register a bot execution strategy.
        
        Args:
            strategy: Strategy instance to register
        """
        self._strategies[strategy.strategy_name] = strategy
    
    def get_strategy(self, strategy_name: str) -> Optional[BotExecutionStrategy]:
        """
        Get a strategy by name.
        
        Args:
            strategy_name: Name of the strategy to retrieve
            
        Returns:
            BotExecutionStrategy instance or None if not found
        """
        return self._strategies.get(strategy_name)
    
    def list_strategies(self) -> List[Dict[str, Any]]:
        """
        List all registered strategies with their information.
        
        Returns:
            List of strategy information dictionaries
        """
        return [strategy.get_strategy_info() for strategy in self._strategies.values()]
    
    def get_default_strategy(self, config: BotConfiguration) -> Optional[BotExecutionStrategy]:
        """
        Select the most appropriate strategy for a configuration.
        
        Args:
            config: Bot configuration
            
        Returns:
            Best matching strategy or None
        """
        # Simple selection logic - can be enhanced
        requested_strategy = config.execution_strategy
        
        if requested_strategy in self._strategies:
            return self._strategies[requested_strategy]
        
        # Fallback to standard strategy if available
        return self._strategies.get("standard")


class ExecutionError(Exception):
    """Exception raised when bot execution fails."""
    
    def __init__(self, message: str, strategy_name: str, config: Optional[BotConfiguration] = None):
        """
        Initialize execution error.
        
        Args:
            message: Error message
            strategy_name: Name of the strategy that failed
            config: Configuration that failed (optional)
        """
        super().__init__(message)
        self.strategy_name = strategy_name
        self.config = config
        
    def __str__(self) -> str:
        return f"ExecutionError in {self.strategy_name}: {super().__str__()}"