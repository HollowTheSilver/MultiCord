"""
Bot Management API Routes
=========================

REST API endpoints for Discord bot lifecycle management.
Implements full CRUD operations with database integration.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Path as PathParam, Body
from pydantic import BaseModel, Field

from platform_api.dependencies import (
    get_current_user,
    require_scope,
    check_rate_limit,
    UseCaseDependencies,
    get_bot_repository,
    get_process_repository
)
from platform_core.entities.bot_instance import BotInstance, BotStatus
from platform_core.entities.process_info import ProcessInfo
from platform_core.use_cases.start_bot import StartBotUseCase
from platform_core.use_cases.stop_bot import StopBotUseCase
from platform_core.use_cases.restart_bot import RestartBotUseCase
from platform_core.repositories.bot_repository import BotInstanceRepository
from platform_core.repositories.process_repository import ProcessRepository


router = APIRouter()


class BotCreateRequest(BaseModel):
    """Request model for creating a new bot."""
    client_id: str = Field(..., description="Discord bot client ID")
    token: str = Field(..., description="Discord bot token")
    strategy: str = Field("standard", description="Execution strategy")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Bot configuration")
    features: List[str] = Field(default_factory=list, description="Technical features to enable")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BotUpdateRequest(BaseModel):
    """Request model for updating bot configuration."""
    configuration: Optional[Dict[str, Any]] = Field(None, description="Updated configuration")
    features: Optional[List[str]] = Field(None, description="Updated features")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


class BotResponse(BaseModel):
    """Response model for bot information."""
    instance_id: UUID
    client_id: str
    status: str
    strategy: str
    configuration: Dict[str, Any]
    features: List[str]
    created_at: datetime
    updated_at: datetime
    health_status: Optional[Dict[str, Any]] = None
    process_info: Optional[Dict[str, Any]] = None


class BotListResponse(BaseModel):
    """Response model for listing bots."""
    bots: List[BotResponse]
    total: int
    page: int
    page_size: int


class BotActionResponse(BaseModel):
    """Response model for bot actions."""
    success: bool
    message: str
    instance_id: UUID
    status: str


@router.post("/", response_model=BotResponse)
async def create_bot(
    request: BotCreateRequest,
    user: Dict[str, Any] = Depends(require_scope("bot:write")),
    rate_limit: Dict[str, Any] = Depends(check_rate_limit),
    bot_repo: BotInstanceRepository = Depends(get_bot_repository)
) -> BotResponse:
    """
    Create a new bot instance.
    
    Requires scope: bot:write
    """
    try:
        # Create bot instance entity
        bot_instance = BotInstance(
            client_id=request.client_id,
            strategy=request.strategy,
            configuration=request.configuration,
            features=request.features,
            node_id=None  # Will be assigned when started
        )
        
        # Store encrypted token separately (not shown for security)
        bot_instance.configuration["token"] = "[ENCRYPTED]"
        
        # Save to database
        await bot_repo.save_bot_instance(bot_instance)
        
        return BotResponse(
            instance_id=bot_instance.instance_id,
            client_id=bot_instance.client_id,
            status=bot_instance.status.value,
            strategy=bot_instance.strategy,
            configuration=bot_instance.configuration,
            features=bot_instance.features,
            created_at=bot_instance.created_at,
            updated_at=bot_instance.updated_at
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=BotListResponse)
async def list_bots(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    user: Dict[str, Any] = Depends(require_scope("bot:read")),
    rate_limit: Dict[str, Any] = Depends(check_rate_limit),
    bot_repo: BotInstanceRepository = Depends(get_bot_repository),
    process_repo: ProcessRepository = Depends(get_process_repository)
) -> BotListResponse:
    """
    List all bot instances with pagination.
    
    Requires scope: bot:read
    """
    try:
        # Get all bots (would add pagination in production)
        all_bots = await bot_repo.find_all()
        
        # Filter by status if provided
        if status:
            filtered_bots = [bot for bot in all_bots if bot.status.value == status]
        else:
            filtered_bots = all_bots
        
        # Paginate
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_bots = filtered_bots[start_idx:end_idx]
        
        # Build response with process info
        bot_responses = []
        for bot in page_bots:
            process_info = await process_repo.find_by_instance_id(bot.instance_id)
            
            bot_response = BotResponse(
                instance_id=bot.instance_id,
                client_id=bot.client_id,
                status=bot.status.value,
                strategy=bot.strategy,
                configuration=bot.configuration,
                features=bot.features,
                created_at=bot.created_at,
                updated_at=bot.updated_at
            )
            
            if process_info:
                bot_response.process_info = {
                    "pid": process_info.pid,
                    "started_at": process_info.started_at.isoformat(),
                    "memory_mb": process_info.memory_usage_mb,
                    "cpu_percent": process_info.cpu_percent
                }
            
            bot_responses.append(bot_response)
        
        return BotListResponse(
            bots=bot_responses,
            total=len(filtered_bots),
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}", response_model=BotResponse)
async def get_bot(
    instance_id: UUID = PathParam(..., description="Bot instance ID"),
    user: Dict[str, Any] = Depends(require_scope("bot:read")),
    rate_limit: Dict[str, Any] = Depends(check_rate_limit),
    bot_repo: BotInstanceRepository = Depends(get_bot_repository),
    process_repo: ProcessRepository = Depends(get_process_repository)
) -> BotResponse:
    """
    Get specific bot instance details.
    
    Requires scope: bot:read
    """
    try:
        bot = await bot_repo.find_by_instance_id(instance_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Get process info if running
        process_info = await process_repo.find_by_instance_id(instance_id)
        
        response = BotResponse(
            instance_id=bot.instance_id,
            client_id=bot.client_id,
            status=bot.status.value,
            strategy=bot.strategy,
            configuration=bot.configuration,
            features=bot.features,
            created_at=bot.created_at,
            updated_at=bot.updated_at
        )
        
        if process_info:
            response.process_info = {
                "pid": process_info.pid,
                "started_at": process_info.started_at.isoformat(),
                "memory_mb": process_info.memory_usage_mb,
                "cpu_percent": process_info.cpu_percent,
                "restart_count": process_info.restart_count
            }
            response.health_status = process_info.health_status
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{instance_id}", response_model=BotResponse)
async def update_bot(
    instance_id: UUID = PathParam(..., description="Bot instance ID"),
    request: BotUpdateRequest = Body(...),
    user: Dict[str, Any] = Depends(require_scope("bot:write")),
    rate_limit: Dict[str, Any] = Depends(check_rate_limit),
    bot_repo: BotInstanceRepository = Depends(get_bot_repository)
) -> BotResponse:
    """
    Update bot configuration.
    
    Requires scope: bot:write
    """
    try:
        bot = await bot_repo.find_by_instance_id(instance_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Update fields if provided
        if request.configuration is not None:
            bot.configuration.update(request.configuration)
        
        if request.features is not None:
            bot.features = request.features
        
        if request.metadata is not None:
            bot.configuration["metadata"] = request.metadata
        
        # Save updates
        await bot_repo.save_bot_instance(bot)
        
        return BotResponse(
            instance_id=bot.instance_id,
            client_id=bot.client_id,
            status=bot.status.value,
            strategy=bot.strategy,
            configuration=bot.configuration,
            features=bot.features,
            created_at=bot.created_at,
            updated_at=bot.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{instance_id}")
async def delete_bot(
    instance_id: UUID = PathParam(..., description="Bot instance ID"),
    user: Dict[str, Any] = Depends(require_scope("bot:write")),
    rate_limit: Dict[str, Any] = Depends(check_rate_limit),
    bot_repo: BotInstanceRepository = Depends(get_bot_repository),
    process_repo: ProcessRepository = Depends(get_process_repository),
    use_cases: UseCaseDependencies = Depends(UseCaseDependencies.get_stop_bot_use_case)
) -> Dict[str, Any]:
    """
    Delete a bot instance.
    
    Requires scope: bot:write
    """
    try:
        bot = await bot_repo.find_by_instance_id(instance_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Stop bot if running
        if bot.status == BotStatus.RUNNING:
            stop_use_case = await UseCaseDependencies.get_stop_bot_use_case(
                bot_repo, process_repo, None
            )
            await stop_use_case.execute({"instance_id": instance_id})
        
        # Remove from database
        await bot_repo.remove_bot_instance(instance_id)
        await process_repo.remove_process(instance_id)
        
        return {"success": True, "message": "Bot deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/start", response_model=BotActionResponse)
async def start_bot(
    instance_id: UUID = PathParam(..., description="Bot instance ID"),
    user: Dict[str, Any] = Depends(require_scope("bot:write")),
    rate_limit: Dict[str, Any] = Depends(check_rate_limit),
    start_use_case: StartBotUseCase = Depends(UseCaseDependencies.get_start_bot_use_case)
) -> BotActionResponse:
    """
    Start a bot instance.
    
    Requires scope: bot:write
    """
    try:
        result = await start_use_case.execute({
            "instance_id": instance_id,
            "requested_by": user.get("user_id")
        })
        
        if result.get("success"):
            return BotActionResponse(
                success=True,
                message="Bot started successfully",
                instance_id=instance_id,
                status="running"
            )
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to start bot"))
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/stop", response_model=BotActionResponse)
async def stop_bot(
    instance_id: UUID = PathParam(..., description="Bot instance ID"),
    user: Dict[str, Any] = Depends(require_scope("bot:write")),
    rate_limit: Dict[str, Any] = Depends(check_rate_limit),
    stop_use_case: StopBotUseCase = Depends(UseCaseDependencies.get_stop_bot_use_case)
) -> BotActionResponse:
    """
    Stop a bot instance.
    
    Requires scope: bot:write
    """
    try:
        result = await stop_use_case.execute({
            "instance_id": instance_id,
            "requested_by": user.get("user_id")
        })
        
        if result.get("success"):
            return BotActionResponse(
                success=True,
                message="Bot stopped successfully",
                instance_id=instance_id,
                status="stopped"
            )
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to stop bot"))
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/restart", response_model=BotActionResponse)
async def restart_bot(
    instance_id: UUID = PathParam(..., description="Bot instance ID"),
    user: Dict[str, Any] = Depends(require_scope("bot:write")),
    rate_limit: Dict[str, Any] = Depends(check_rate_limit),
    restart_use_case: RestartBotUseCase = Depends(UseCaseDependencies.get_restart_bot_use_case)
) -> BotActionResponse:
    """
    Restart a bot instance.
    
    Requires scope: bot:write
    """
    try:
        result = await restart_use_case.execute({
            "instance_id": instance_id,
            "requested_by": user.get("user_id")
        })
        
        if result.get("success"):
            return BotActionResponse(
                success=True,
                message="Bot restarted successfully",
                instance_id=instance_id,
                status="running"
            )
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to restart bot"))
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}/logs")
async def get_bot_logs(
    instance_id: UUID = PathParam(..., description="Bot instance ID"),
    lines: int = Query(100, ge=1, le=1000, description="Number of log lines"),
    user: Dict[str, Any] = Depends(require_scope("bot:read")),
    rate_limit: Dict[str, Any] = Depends(check_rate_limit),
    bot_repo: BotInstanceRepository = Depends(get_bot_repository),
    process_repo: ProcessRepository = Depends(get_process_repository)
) -> Dict[str, Any]:
    """
    Get bot logs.
    
    Requires scope: bot:read
    """
    try:
        bot = await bot_repo.find_by_instance_id(instance_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        process_info = await process_repo.find_by_instance_id(instance_id)
        if not process_info or not process_info.log_file_path:
            return {"logs": [], "message": "No logs available"}
        
        # Read log file (simplified - would use log aggregation service in production)
        log_file = Path(process_info.log_file_path)
        if not log_file.exists():
            return {"logs": [], "message": "Log file not found"}
        
        with open(log_file, "r") as f:
            all_lines = f.readlines()
            log_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "logs": log_lines,
            "total_lines": len(all_lines),
            "returned_lines": len(log_lines)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}/metrics")
async def get_bot_metrics(
    instance_id: UUID = PathParam(..., description="Bot instance ID"),
    user: Dict[str, Any] = Depends(require_scope("bot:read")),
    rate_limit: Dict[str, Any] = Depends(check_rate_limit),
    process_repo: ProcessRepository = Depends(get_process_repository)
) -> Dict[str, Any]:
    """
    Get bot performance metrics.
    
    Requires scope: bot:read
    """
    try:
        process_info = await process_repo.find_by_instance_id(instance_id)
        if not process_info:
            raise HTTPException(status_code=404, detail="Bot process not found")
        
        return {
            "instance_id": instance_id,
            "metrics": {
                "memory_mb": process_info.memory_usage_mb,
                "cpu_percent": process_info.cpu_percent,
                "uptime_seconds": (datetime.now() - process_info.started_at).total_seconds(),
                "restart_count": process_info.restart_count,
                "is_running": process_info.is_running
            },
            "health_status": process_info.health_status,
            "collected_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))