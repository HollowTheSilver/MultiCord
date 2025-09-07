"""
MultiCord Platform Core - Clean Architecture Foundation
======================================================

PostgreSQL-centered technical infrastructure for Discord bot management.
Supports any Discord.py development approach with zero learning curve.

Architecture:
- Entities: Core domain objects (ProcessInfo, BotInstance)
- Infrastructure: PostgreSQL connection pools and external interfaces
- Strategies: Multi-path bot execution (standard, template, enhanced)
- Use Cases: Pure business logic for bot management operations
- Repositories: Data access layer with PostgreSQL integration
- Services: Application services for orchestration

Phase 1 Components Complete:
✅ PostgreSQL Schema (migrations/001_initial_platform_schema.sql)
✅ ProcessInfo & BotInstance entities with health monitoring
✅ PostgreSQL Connection Pool with transaction management
✅ Bot Execution Strategy interface for multi-path execution
✅ Standard Discord.py Strategy for zero-modification bots
✅ ProcessRepository for PostgreSQL data access
✅ StartBot Use Case with complete business logic
"""

# Core entities
from .entities import ProcessInfo, ProcessSource, HealthStatus, BotInstance, BotStatus

# Infrastructure components  
from .infrastructure import PostgreSQLConnectionPool, PostgreSQLRepository

# Strategy pattern interfaces
from .strategies import (
    BotExecutionStrategy,
    BotConfiguration,
    ProcessHandle,
    ExecutionStrategyFactory,
    ExecutionError,
    StandardDiscordPyStrategy
)

# Repositories
from .repositories import ProcessRepository

# Use cases
from .use_cases import StartBotUseCase, StartBotRequest, StartBotResponse

__version__ = "2.0.0-alpha.1"

__all__ = [
    # Entities
    "ProcessInfo",
    "ProcessSource", 
    "HealthStatus",
    "BotInstance",
    "BotStatus",
    
    # Infrastructure
    "PostgreSQLConnectionPool",
    "PostgreSQLRepository",
    
    # Strategies
    "BotExecutionStrategy",
    "BotConfiguration", 
    "ProcessHandle",
    "ExecutionStrategyFactory",
    "ExecutionError",
    "StandardDiscordPyStrategy",
    
    # Repositories
    "ProcessRepository",
    
    # Use Cases
    "StartBotUseCase",
    "StartBotRequest",
    "StartBotResponse"
]