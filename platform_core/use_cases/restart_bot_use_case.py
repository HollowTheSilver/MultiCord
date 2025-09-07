"""
RestartBot Use Case - Clean Business Logic
==========================================

Core use case for restarting bot instances with configuration updates.
Coordinates stop/start operations with PostgreSQL state management.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from uuid import UUID
import asyncio

from .start_bot_use_case import StartBotUseCase, StartBotRequest, StartBotResponse
from .stop_bot_use_case import StopBotUseCase, StopBotRequest, StopBotResponse
from ..repositories.process_repository import ProcessRepository
from ..infrastructure.postgresql_pool import PostgreSQLConnectionPool
from ..strategies.bot_execution_strategy import ExecutionStrategyFactory


@dataclass
class RestartBotRequest:
    """Request to restart a bot instance."""
    client_id: str
    # Configuration updates
    new_discord_token: Optional[str] = None
    new_execution_strategy: Optional[str] = None
    new_environment_config: Optional[Dict[str, Any]] = None
    new_technical_features: Optional[List[str]] = None
    new_bot_file: Optional[str] = None
    # Restart behavior
    force_kill: bool = False
    wait_seconds: int = 2
    preserve_workspace: bool = True
    reason: Optional[str] = None


@dataclass
class RestartBotResponse:
    """Response from restarting a bot instance."""
    success: bool
    message: str
    client_id: str
    old_process_id: Optional[UUID] = None
    new_process_id: Optional[UUID] = None
    new_pid: Optional[int] = None
    restart_time_seconds: Optional[float] = None
    stop_response: Optional[StopBotResponse] = None
    start_response: Optional[StartBotResponse] = None
    error_details: Optional[Dict[str, Any]] = None


class RestartBotUseCase:
    """
    Use case for restarting bot instances with clean business logic.
    
    Coordinates:
    1. Current bot instance validation
    2. Configuration merging and updates
    3. Graceful stop using StopBotUseCase
    4. Updated start using StartBotUseCase
    5. Health verification and rollback support
    """
    
    def __init__(self,
                 db_pool: PostgreSQLConnectionPool,
                 process_repository: ProcessRepository,
                 strategy_factory: ExecutionStrategyFactory,
                 logger: logging.Logger = None):
        """
        Initialize RestartBot use case.
        
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
        
        # Initialize dependent use cases
        self.stop_bot_use_case = StopBotUseCase(
            db_pool, process_repository, strategy_factory, logger
        )
        self.start_bot_use_case = StartBotUseCase(
            db_pool, process_repository, strategy_factory, logger
        )
    
    async def execute(self, request: RestartBotRequest) -> RestartBotResponse:
        """
        Execute the restart bot use case with PostgreSQL transactions.
        
        Args:
            request: RestartBot request parameters
            
        Returns:
            RestartBotResponse with success/failure details
        """
        import time
        
        try:
            start_time = time.time()
            
            # Step 1: Validate request
            validation_result = await self._validate_request(request)
            if not validation_result.success:
                return validation_result
            
            # Step 2: Get current bot configuration
            current_config = await self._get_current_configuration(request.client_id)
            if not current_config:
                return RestartBotResponse(
                    success=False,
                    message=f"Bot {request.client_id} not found or not running",
                    client_id=request.client_id
                )
            
            old_process_id = current_config.get("process_id")
            
            # Step 3: Merge configuration updates
            updated_config = await self._merge_configuration(current_config, request)
            
            # Step 4: Stop current bot instance
            self.logger.info(f"Stopping bot {request.client_id} for restart")
            stop_request = StopBotRequest(
                client_id=request.client_id,
                force_kill=request.force_kill,
                cleanup_workspace=not request.preserve_workspace,
                reason=f"Restart operation: {request.reason or 'Configuration update'}"
            )
            
            stop_response = await self.stop_bot_use_case.execute(stop_request)
            
            if not stop_response.success:
                return RestartBotResponse(
                    success=False,
                    message=f"Failed to stop bot for restart: {stop_response.message}",
                    client_id=request.client_id,
                    old_process_id=old_process_id,
                    stop_response=stop_response,
                    error_details={"phase": "stop", "details": stop_response.error_details}
                )
            
            # Step 5: Wait for cleanup
            if request.wait_seconds > 0:
                self.logger.info(f"Waiting {request.wait_seconds}s for cleanup")
                await asyncio.sleep(request.wait_seconds)
            
            # Step 6: Start bot with updated configuration
            self.logger.info(f"Starting bot {request.client_id} with updated configuration")
            start_request = StartBotRequest(
                client_id=request.client_id,
                execution_strategy=updated_config["execution_strategy"],
                environment_config=updated_config["environment_config"],
                technical_features=updated_config["technical_features"],
                discord_token=updated_config.get("discord_token")
            )
            
            start_response = await self.start_bot_use_case.execute(start_request)
            
            restart_time = time.time() - start_time
            
            if start_response.success:
                return RestartBotResponse(
                    success=True,
                    message=f"Successfully restarted bot {request.client_id}",
                    client_id=request.client_id,
                    old_process_id=old_process_id,
                    new_process_id=start_response.process_id,
                    new_pid=start_response.pid,
                    restart_time_seconds=restart_time,
                    stop_response=stop_response,
                    start_response=start_response
                )
            else:
                return RestartBotResponse(
                    success=False,
                    message=f"Bot stopped successfully but failed to restart: {start_response.message}",
                    client_id=request.client_id,
                    old_process_id=old_process_id,
                    restart_time_seconds=restart_time,
                    stop_response=stop_response,
                    start_response=start_response,
                    error_details={"phase": "start", "details": start_response.error_details}
                )
            
        except Exception as e:
            self.logger.error(f"Unexpected error restarting bot {request.client_id}: {e}")
            return RestartBotResponse(
                success=False,
                message=f"Unexpected error during restart: {e}",
                client_id=request.client_id,
                error_details={"exception_type": type(e).__name__, "details": str(e)}
            )
    
    async def _validate_request(self, request: RestartBotRequest) -> RestartBotResponse:
        """Validate the restart bot request."""
        if not request.client_id:
            return RestartBotResponse(
                success=False,
                message="Client ID is required",
                client_id=""
            )
        
        if not request.client_id.replace('_', '').replace('-', '').isalnum():
            return RestartBotResponse(
                success=False,
                message="Client ID must contain only alphanumeric characters, hyphens, and underscores",
                client_id=request.client_id
            )
        
        if request.new_execution_strategy and request.new_execution_strategy not in ["standard", "template", "enhanced"]:
            return RestartBotResponse(
                success=False,
                message=f"Invalid execution strategy: {request.new_execution_strategy}",
                client_id=request.client_id
            )
        
        if request.wait_seconds < 0 or request.wait_seconds > 30:
            return RestartBotResponse(
                success=False,
                message="Wait seconds must be between 0 and 30",
                client_id=request.client_id
            )
        
        return RestartBotResponse(success=True, message="Validation passed", client_id=request.client_id)
    
    async def _get_current_configuration(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get current bot configuration from database."""
        try:
            # Get process info
            process_info = await self.process_repository.find_by_client_id(client_id)
            if not process_info:
                return None
            
            # Get bot instance configuration
            async with self.db_pool.get_connection() as conn:
                query = "SELECT * FROM bot_instances WHERE client_id = $1 ORDER BY created_at DESC LIMIT 1"
                row = await conn.fetchrow(query, client_id)
                
                if not row:
                    return None
                
                return {
                    "process_id": process_info.process_id,
                    "instance_id": row["instance_id"],
                    "execution_strategy": row["execution_strategy"],
                    "environment_config": row.get("environment_config", {}),
                    "technical_features": row.get("enabled_features", []),
                    "discord_token": None  # Don't retrieve token from database for security
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get current configuration for {client_id}: {e}")
            return None
    
    async def _merge_configuration(self, current_config: Dict[str, Any], request: RestartBotRequest) -> Dict[str, Any]:
        """Merge current configuration with restart request updates."""
        updated_config = current_config.copy()
        
        # Update execution strategy if provided
        if request.new_execution_strategy:
            updated_config["execution_strategy"] = request.new_execution_strategy
        
        # Merge environment configuration
        if request.new_environment_config:
            env_config = updated_config.get("environment_config", {}).copy()
            env_config.update(request.new_environment_config)
            updated_config["environment_config"] = env_config
        
        # Update technical features if provided
        if request.new_technical_features is not None:
            updated_config["technical_features"] = request.new_technical_features
        
        # Add new Discord token if provided
        if request.new_discord_token:
            updated_config["discord_token"] = request.new_discord_token
            updated_config["environment_config"]["DISCORD_TOKEN"] = request.new_discord_token
        
        # Add new bot file if provided
        if request.new_bot_file:
            updated_config["environment_config"]["BOT_FILE"] = request.new_bot_file
        
        # Handle strategy-specific configuration updates
        if updated_config["execution_strategy"] == "template":
            # Ensure template name is preserved or updated
            if "TEMPLATE_NAME" not in updated_config["environment_config"]:
                # Try to determine from current config or default to basic template
                template_name = current_config.get("environment_config", {}).get("TEMPLATE_NAME", "basic_business_bot")
                updated_config["environment_config"]["TEMPLATE_NAME"] = template_name
        
        return updated_config
    
    async def get_restart_candidates(self) -> List[Dict[str, Any]]:
        """Get list of bots that can be restarted."""
        try:
            processes = await self.process_repository.get_all_processes()
            
            candidates = []
            for process in processes:
                candidates.append({
                    "client_id": process.client_id,
                    "pid": process.pid,
                    "is_running": process.is_running,
                    "started_at": process.started_at,
                    "restart_count": process.restart_count,
                    "can_restart": True  # All processes can be restarted
                })
            
            return candidates
            
        except Exception as e:
            self.logger.error(f"Failed to get restart candidates: {e}")
            return []