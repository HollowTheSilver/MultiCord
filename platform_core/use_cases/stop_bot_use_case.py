"""
StopBot Use Case - Clean Business Logic
======================================

Core use case for stopping bot instances with PostgreSQL transactions.
Coordinates strategy selection, graceful shutdown, and state cleanup.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional
from uuid import UUID

from ..strategies.bot_execution_strategy import (
    BotExecutionStrategy,
    ProcessHandle,
    ExecutionStrategyFactory
)
from ..entities.process_info import ProcessInfo
from ..repositories.process_repository import ProcessRepository
from ..infrastructure.postgresql_pool import PostgreSQLConnectionPool


@dataclass
class StopBotRequest:
    """Request to stop a bot instance."""
    client_id: str
    force_kill: bool = False
    cleanup_workspace: bool = False
    reason: Optional[str] = None


@dataclass
class StopBotResponse:
    """Response from stopping a bot instance."""
    success: bool
    message: str
    client_id: str
    process_id: Optional[UUID] = None
    was_running: bool = False
    shutdown_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None


class StopBotUseCase:
    """
    Use case for stopping bot instances with clean business logic.
    
    Coordinates:
    1. Bot instance lookup and validation
    2. Process handle creation
    3. Strategy-specific graceful shutdown
    4. PostgreSQL state cleanup
    5. Optional workspace cleanup
    """
    
    def __init__(self,
                 db_pool: PostgreSQLConnectionPool,
                 process_repository: ProcessRepository,
                 strategy_factory: ExecutionStrategyFactory,
                 logger: logging.Logger = None):
        """
        Initialize StopBot use case.
        
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
    
    async def execute(self, request: StopBotRequest) -> StopBotResponse:
        """
        Execute the stop bot use case with PostgreSQL transactions.
        
        Args:
            request: StopBot request parameters
            
        Returns:
            StopBotResponse with success/failure details
        """
        try:
            # Step 1: Validate request
            validation_result = await self._validate_request(request)
            if not validation_result.success:
                return validation_result
            
            # Step 2: Find running process
            process_info = await self.process_repository.find_by_client_id(request.client_id)
            if not process_info:
                return StopBotResponse(
                    success=False,
                    message=f"No process found for bot {request.client_id}",
                    client_id=request.client_id
                )
            
            # Step 3: Check if already stopped
            was_running = process_info.is_running
            if not was_running:
                # Clean up dead process record
                async with self.db_pool.get_transaction() as conn:
                    await self.process_repository.remove_process(process_info.process_id)
                
                return StopBotResponse(
                    success=True,
                    message=f"Bot {request.client_id} was already stopped (cleaned up)",
                    client_id=request.client_id,
                    process_id=process_info.process_id,
                    was_running=False
                )
            
            # Step 4: Determine strategy for stopping
            strategy = await self._get_appropriate_strategy(process_info)
            if not strategy:
                return StopBotResponse(
                    success=False,
                    message=f"No strategy available for stopping bot {request.client_id}",
                    client_id=request.client_id,
                    process_id=process_info.process_id,
                    error_details={"available_strategies": self.strategy_factory.list_strategies()}
                )
            
            # Step 5: Execute shutdown
            shutdown_result = await self._execute_shutdown(strategy, process_info, request)
            
            # Step 6: Cleanup database records
            async with self.db_pool.get_transaction() as conn:
                await self.process_repository.remove_process(process_info.process_id)
                self.logger.info(f"Cleaned up process record for {request.client_id}")
            
            # Step 7: Optional workspace cleanup
            if request.cleanup_workspace and shutdown_result.success:
                await self._cleanup_workspace(request.client_id)
            
            return shutdown_result
            
        except Exception as e:
            self.logger.error(f"Unexpected error stopping bot {request.client_id}: {e}")
            return StopBotResponse(
                success=False,
                message=f"Unexpected error during shutdown: {e}",
                client_id=request.client_id,
                error_details={"exception_type": type(e).__name__, "details": str(e)}
            )
    
    async def _validate_request(self, request: StopBotRequest) -> StopBotResponse:
        """Validate the stop bot request."""
        if not request.client_id:
            return StopBotResponse(
                success=False,
                message="Client ID is required",
                client_id=""
            )
        
        if not request.client_id.replace('_', '').replace('-', '').isalnum():
            return StopBotResponse(
                success=False,
                message="Client ID must contain only alphanumeric characters, hyphens, and underscores",
                client_id=request.client_id
            )
        
        return StopBotResponse(success=True, message="Validation passed", client_id=request.client_id)
    
    async def _get_appropriate_strategy(self, process_info: ProcessInfo) -> Optional[BotExecutionStrategy]:
        """Get the appropriate strategy for stopping this process."""
        # Try to determine strategy from terminal instance or default to standard
        terminal_instance = process_info.terminal_instance or ""
        
        if "template_" in terminal_instance:
            strategy = self.strategy_factory.get_strategy("template")
            if strategy:
                return strategy
        elif "standard_" in terminal_instance:
            strategy = self.strategy_factory.get_strategy("standard")
            if strategy:
                return strategy
        
        # Fallback to standard strategy for generic stop operations
        return self.strategy_factory.get_strategy("standard")
    
    async def _execute_shutdown(self, 
                              strategy: BotExecutionStrategy, 
                              process_info: ProcessInfo,
                              request: StopBotRequest) -> StopBotResponse:
        """Execute the actual shutdown process."""
        import time
        
        try:
            # Create process handle for shutdown
            process_handle = ProcessHandle(
                process_info=process_info,
                subprocess_handle=None  # We'll use psutil for external processes
            )
            
            start_time = time.time()
            
            # Execute strategy-specific shutdown
            if request.force_kill:
                self.logger.info(f"Force killing bot {request.client_id}")
                success = await self._force_kill_process(process_info)
            else:
                self.logger.info(f"Gracefully stopping bot {request.client_id}")
                success = await strategy.stop(process_handle)
            
            shutdown_time = time.time() - start_time
            
            if success:
                reason_msg = f" (Reason: {request.reason})" if request.reason else ""
                return StopBotResponse(
                    success=True,
                    message=f"Successfully stopped bot {request.client_id}{reason_msg}",
                    client_id=request.client_id,
                    process_id=process_info.process_id,
                    was_running=True,
                    shutdown_time_seconds=shutdown_time
                )
            else:
                return StopBotResponse(
                    success=False,
                    message=f"Failed to stop bot {request.client_id}",
                    client_id=request.client_id,
                    process_id=process_info.process_id,
                    was_running=True,
                    error_details={"strategy": strategy.strategy_name}
                )
                
        except Exception as e:
            self.logger.error(f"Error during shutdown of {request.client_id}: {e}")
            return StopBotResponse(
                success=False,
                message=f"Shutdown execution failed: {e}",
                client_id=request.client_id,
                process_id=process_info.process_id,
                was_running=True,
                error_details={"exception": str(e)}
            )
    
    async def _force_kill_process(self, process_info: ProcessInfo) -> bool:
        """Force kill a process using psutil."""
        try:
            import psutil
            
            proc = psutil.Process(process_info.pid)
            proc.kill()
            proc.wait(timeout=5)
            return True
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.logger.warning(f"Process {process_info.pid} not accessible: {e}")
            return True  # Process likely already dead
        except psutil.TimeoutExpired:
            self.logger.error(f"Process {process_info.pid} did not respond to force kill")
            return False
        except Exception as e:
            self.logger.error(f"Error force killing process {process_info.pid}: {e}")
            return False
    
    async def _cleanup_workspace(self, client_id: str) -> None:
        """Clean up bot workspace directory."""
        try:
            import shutil
            from pathlib import Path
            
            workspace_path = Path(f"bots/{client_id}")
            if workspace_path.exists():
                shutil.rmtree(workspace_path)
                self.logger.info(f"Cleaned up workspace for {client_id}")
            
        except Exception as e:
            self.logger.warning(f"Failed to cleanup workspace for {client_id}: {e}")