"""
StartBot Use Case - Pure Business Logic
======================================

Core use case for starting bot instances with PostgreSQL transactions.
Coordinates strategy selection, process management, and state persistence.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from uuid import UUID
from pathlib import Path

from ..strategies.bot_execution_strategy import (
    BotExecutionStrategy,
    BotConfiguration,
    ProcessHandle,
    ExecutionStrategyFactory,
    ExecutionError
)
from ..entities.bot_instance import BotInstance, BotStatus
from ..entities.process_info import ProcessInfo
from ..repositories.process_repository import ProcessRepository
from ..infrastructure.postgresql_pool import PostgreSQLConnectionPool


@dataclass
class StartBotRequest:
    """Request to start a bot instance."""
    client_id: str
    execution_strategy: str = "standard"
    environment_config: Optional[Dict[str, Any]] = None
    technical_features: Optional[List[str]] = None
    discord_token: Optional[str] = None
    custom_flags: Optional[Dict[str, Any]] = None
    node_id: Optional[UUID] = None


@dataclass  
class StartBotResponse:
    """Response from starting a bot instance."""
    success: bool
    message: str
    instance_id: Optional[UUID] = None
    process_id: Optional[UUID] = None
    pid: Optional[int] = None
    log_file_path: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


class StartBotUseCase:
    """
    Use case for starting bot instances with clean business logic.
    
    Coordinates:
    1. Bot instance creation/validation  
    2. Execution strategy selection
    3. Process conflict resolution
    4. Bot process startup
    5. PostgreSQL state persistence
    """
    
    def __init__(self,
                 db_pool: PostgreSQLConnectionPool,
                 process_repository: ProcessRepository,
                 strategy_factory: ExecutionStrategyFactory,
                 logger: logging.Logger = None):
        """
        Initialize StartBot use case.
        
        Args:
            db_pool: PostgreSQL connection pool
            process_repository: Process data access
            strategy_factory: Execution strategy factory
            logger: Logger instance
        """
        self.db_pool = db_pool
        self.process_repository = process_repository
        self.strategy_factory = strategy_factory
        self.logger = logger or logging.getLogger(__name__)
    
    async def execute(self, request: StartBotRequest) -> StartBotResponse:
        """
        Execute the start bot use case with PostgreSQL transactions.
        
        Args:
            request: StartBot request parameters
            
        Returns:
            StartBotResponse with success/failure details
        """
        try:
            # Step 1: Validate request
            validation_result = await self._validate_request(request)
            if not validation_result.success:
                return validation_result
            
            # Step 2: Check for process conflicts  
            conflict_result = await self._resolve_process_conflicts(request.client_id)
            if not conflict_result.success:
                return conflict_result
            
            # Step 3: Create/load bot instance
            async with self.db_pool.get_transaction() as conn:
                bot_instance = await self._get_or_create_bot_instance(request, conn)
                
                # Step 4: Select execution strategy
                strategy = self.strategy_factory.get_strategy(request.execution_strategy)
                if not strategy:
                    return StartBotResponse(
                        success=False,
                        message=f"Execution strategy '{request.execution_strategy}' not found",
                        error_details={"available_strategies": self.strategy_factory.list_strategies()}
                    )
                
                # Step 5: Prepare bot configuration
                bot_config = await self._prepare_bot_configuration(request, bot_instance)
                
                # Step 6: Validate configuration with strategy
                if not await strategy.validate_configuration(bot_config):
                    return StartBotResponse(
                        success=False,
                        message=f"Configuration validation failed for strategy '{request.execution_strategy}'",
                        instance_id=bot_instance.instance_id
                    )
                
                # Step 7: Start bot process
                try:
                    bot_instance.update_status(BotStatus.STARTING)
                    await self._update_bot_instance_status(bot_instance, conn)
                    
                    process_handle = await strategy.start(bot_config)
                    
                    bot_instance.update_status(BotStatus.RUNNING)
                    await self._update_bot_instance_status(bot_instance, conn)
                    
                    # Step 8: Save process information (in same transaction)
                    await self.process_repository.save_process(process_handle.process_info, conn)
                    
                except ExecutionError as e:
                    bot_instance.update_status(BotStatus.ERROR)
                    await self._update_bot_instance_status(bot_instance, conn)
                    
                    return StartBotResponse(
                        success=False,
                        message=f"Failed to start bot: {e}",
                        instance_id=bot_instance.instance_id,
                        error_details={"strategy": e.strategy_name, "details": str(e)}
                    )
                
                # Step 9: Return success response
                return StartBotResponse(
                    success=True,
                        message=f"Successfully started bot {request.client_id}",
                        instance_id=bot_instance.instance_id,
                        process_id=process_handle.process_info.process_id,
                        pid=process_handle.process_info.pid,
                        log_file_path=process_handle.process_info.log_file_path
                    )
                
        except Exception as e:
            self.logger.error(f"Unexpected error starting bot {request.client_id}: {e}")
            return StartBotResponse(
                success=False,
                message=f"Unexpected error: {e}",
                error_details={"exception_type": type(e).__name__, "details": str(e)}
            )
    
    async def _validate_request(self, request: StartBotRequest) -> StartBotResponse:
        """Validate the start bot request."""
        if not request.client_id:
            return StartBotResponse(
                success=False,
                message="Client ID is required"
            )
        
        if not request.client_id.replace('_', '').replace('-', '').isalnum():
            return StartBotResponse(
                success=False,
                message="Client ID must contain only alphanumeric characters, hyphens, and underscores"
            )
        
        if request.execution_strategy not in ["standard", "template", "enhanced"]:
            return StartBotResponse(
                success=False,
                message=f"Invalid execution strategy: {request.execution_strategy}"
            )
        
        return StartBotResponse(success=True, message="Validation passed")
    
    async def _resolve_process_conflicts(self, client_id: str) -> StartBotResponse:
        """Check for and resolve process conflicts."""
        try:
            # Check if bot is already running
            existing_process = await self.process_repository.find_by_client_id(client_id)
            
            if existing_process and existing_process.is_running:
                return StartBotResponse(
                    success=False,
                    message=f"Bot {client_id} is already running (PID: {existing_process.pid})",
                    process_id=existing_process.process_id,
                    pid=existing_process.pid
                )
            
            # Clean up any dead processes
            if existing_process and not existing_process.is_running:
                await self.process_repository.remove_process(existing_process.process_id)
                self.logger.info(f"Cleaned up dead process for {client_id}")
            
            return StartBotResponse(success=True, message="No conflicts found")
            
        except Exception as e:
            self.logger.error(f"Failed to resolve conflicts for {client_id}: {e}")
            return StartBotResponse(
                success=False,
                message=f"Failed to check for conflicts: {e}"
            )
    
    async def _get_or_create_bot_instance(self, request: StartBotRequest, conn) -> BotInstance:
        """Get existing bot instance or create a new one."""
        try:
            # Try to find existing instance
            query = "SELECT * FROM bot_instances WHERE client_id = $1 ORDER BY created_at DESC LIMIT 1"
            row = await conn.fetchrow(query, request.client_id)
            
            if row:
                bot_instance = BotInstance.from_postgresql(dict(row))
                # Update with new request data
                bot_instance.execution_strategy = request.execution_strategy
                bot_instance.environment_config.update(request.environment_config or {})
                if request.technical_features:
                    bot_instance.enabled_features = request.technical_features
                bot_instance.update_status(BotStatus.CREATED)
                
                # Update in database
                await self._update_bot_instance(bot_instance, conn)
                return bot_instance
            else:
                # Create new instance
                bot_instance = BotInstance(
                    client_id=request.client_id,
                    node_id=request.node_id,
                    execution_strategy=request.execution_strategy,
                    environment_config=request.environment_config or {},
                    enabled_features=request.technical_features or [],
                    status=BotStatus.CREATED
                )
                
                # Save to database
                await self._create_bot_instance(bot_instance, conn)
                return bot_instance
                
        except Exception as e:
            self.logger.error(f"Failed to get/create bot instance for {request.client_id}: {e}")
            raise
    
    async def _create_bot_instance(self, bot_instance: BotInstance, conn) -> None:
        """Create new bot instance in database."""
        query = """
            INSERT INTO bot_instances (
                instance_id, node_id, client_id, execution_strategy,
                configuration_data, enabled_features, created_at, updated_at,
                discord_token_hash, environment_config
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """
        
        data = bot_instance.for_postgresql()
        await conn.execute(
            query,
            data["instance_id"], data["node_id"], data["client_id"],
            data["execution_strategy"], data["configuration_data"],
            data["enabled_features"], data["created_at"], data["updated_at"],
            data["discord_token_hash"], data["environment_config"]
        )
    
    async def _update_bot_instance(self, bot_instance: BotInstance, conn) -> None:
        """Update existing bot instance in database."""
        query = """
            UPDATE bot_instances SET
                execution_strategy = $2, configuration_data = $3, enabled_features = $4,
                updated_at = $5, environment_config = $6
            WHERE instance_id = $1
        """
        
        data = bot_instance.for_postgresql()
        await conn.execute(
            query,
            data["instance_id"], data["execution_strategy"], data["configuration_data"],
            data["enabled_features"], data["updated_at"], data["environment_config"]
        )
    
    async def _update_bot_instance_status(self, bot_instance: BotInstance, conn) -> None:
        """Update bot instance status (stored separately for real-time updates)."""
        # For now, we track status in memory and via process registry
        # In future, could add a bot_status table for real-time status tracking
        pass
    
    async def _prepare_bot_configuration(self, request: StartBotRequest, bot_instance: BotInstance) -> BotConfiguration:
        """Prepare bot configuration for execution strategy."""
        # Prepare log directory
        log_directory = Path(f"bots/{request.client_id}/logs")
        log_directory.mkdir(parents=True, exist_ok=True)
        
        # Merge environment configuration
        env_config = {}
        env_config.update(bot_instance.environment_config)
        if request.environment_config:
            env_config.update(request.environment_config)
        
        # Add Discord token if provided (support multiple common names)
        if request.discord_token:
            env_config["DISCORD_TOKEN"] = request.discord_token
            env_config["DISCORD_BOT_TOKEN"] = request.discord_token
        
        return BotConfiguration(
            client_id=request.client_id,
            instance_id=bot_instance.instance_id,
            execution_strategy=request.execution_strategy,
            environment_config=env_config,
            technical_features=bot_instance.enabled_features,
            log_directory=log_directory,
            discord_token=request.discord_token,
            custom_flags=request.custom_flags
        )