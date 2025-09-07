"""
FastAPI Dependency Injection
============================

Provides dependency injection for repositories, services, and security components.
Manages database connections, authentication, and rate limiting dependencies.
"""

from typing import AsyncGenerator, Optional, Dict, Any
from datetime import datetime, timezone
import logging

from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from platform_core.infrastructure.postgresql_pool import PostgreSQLConnectionPool
from platform_core.repositories.bot_repository import BotInstanceRepository
from platform_core.repositories.process_repository import ProcessRepository
from platform_core.repositories.security_repository import SecurityRepository
from platform_core.services.token_service import TokenService
from platform_core.services.auth_service import DeviceFlowService
from platform_core.use_cases.start_bot import StartBotUseCase
from platform_core.use_cases.stop_bot import StopBotUseCase
from platform_core.use_cases.restart_bot import RestartBotUseCase
from platform_core.container.container import Container
from platform_core.strategies.factory import ExecutionStrategyFactory


logger = logging.getLogger(__name__)

# Global instances (initialized in app startup)
_db_pool: Optional[PostgreSQLConnectionPool] = None
_token_service: Optional[TokenService] = None
_device_flow_service: Optional[DeviceFlowService] = None
_container: Optional[Container] = None
_strategy_factory: Optional[ExecutionStrategyFactory] = None

# Security scheme
security = HTTPBearer()


async def initialize_dependencies(
    db_host: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_password: str,
    ssl_mode: str = "require"
) -> None:
    """
    Initialize global dependencies during app startup.
    
    Args:
        db_host: PostgreSQL host
        db_port: PostgreSQL port
        db_name: Database name
        db_user: Database user
        db_password: Database password
        ssl_mode: SSL/TLS mode for database connection
    """
    global _db_pool, _token_service, _device_flow_service, _container, _strategy_factory
    
    # Initialize database pool
    _db_pool = PostgreSQLConnectionPool(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password,
        ssl_mode=ssl_mode,
        min_connections=5,
        max_connections=20
    )
    await _db_pool.initialize()
    
    # Initialize services
    _token_service = TokenService()
    _device_flow_service = DeviceFlowService(
        base_url="https://multicord.io",
        client_id="multicord-cli"
    )
    
    # Initialize container and factory
    _container = Container()
    _strategy_factory = ExecutionStrategyFactory()
    
    logger.info("Dependencies initialized successfully")


async def cleanup_dependencies() -> None:
    """Cleanup dependencies during app shutdown."""
    global _db_pool
    
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
    
    logger.info("Dependencies cleaned up successfully")


async def get_db_pool() -> PostgreSQLConnectionPool:
    """Get database connection pool dependency."""
    if not _db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return _db_pool


async def get_bot_repository(
    pool: PostgreSQLConnectionPool = Depends(get_db_pool)
) -> BotInstanceRepository:
    """Get bot instance repository dependency."""
    return BotInstanceRepository(pool)


async def get_process_repository(
    pool: PostgreSQLConnectionPool = Depends(get_db_pool)
) -> ProcessRepository:
    """Get process repository dependency."""
    return ProcessRepository(pool)


async def get_security_repository(
    pool: PostgreSQLConnectionPool = Depends(get_db_pool)
) -> SecurityRepository:
    """Get security repository dependency."""
    return SecurityRepository(pool)


async def get_token_service() -> TokenService:
    """Get token service dependency."""
    if not _token_service:
        raise HTTPException(status_code=500, detail="Token service not initialized")
    return _token_service


async def get_device_flow_service() -> DeviceFlowService:
    """Get device flow service dependency."""
    if not _device_flow_service:
        raise HTTPException(status_code=500, detail="Device flow service not initialized")
    return _device_flow_service


async def get_container() -> Container:
    """Get dependency injection container."""
    if not _container:
        raise HTTPException(status_code=500, detail="Container not initialized")
    return _container


async def get_strategy_factory() -> ExecutionStrategyFactory:
    """Get execution strategy factory."""
    if not _strategy_factory:
        raise HTTPException(status_code=500, detail="Strategy factory not initialized")
    return _strategy_factory


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security),
    token_service: TokenService = Depends(get_token_service),
    security_repo: SecurityRepository = Depends(get_security_repository)
) -> Dict[str, Any]:
    """
    Validate JWT token and return current user information.
    
    Args:
        request: FastAPI request object
        credentials: Bearer token from Authorization header
        token_service: Token service for JWT validation
        security_repo: Security repository for revocation checks
        
    Returns:
        User information from validated token
        
    Raises:
        HTTPException: If token is invalid or revoked
    """
    token = credentials.credentials
    
    try:
        # Validate token signature and expiration
        payload = token_service.validate_access_token(token)
        
        # Check if token is revoked
        jti = payload.get("jti")
        if jti and await security_repo.is_token_revoked(jti):
            raise HTTPException(
                status_code=401,
                detail="Token has been revoked"
            )
        
        # Log successful authentication
        await security_repo.log_api_request({
            "request_id": request.state.request_id,
            "api_key_id": payload.get("key_id"),
            "endpoint": str(request.url.path),
            "http_method": request.method,
            "client_ip": request.client.host,
            "user_agent": request.headers.get("user-agent"),
            "response_status": 200,
            "timestamp": datetime.now(timezone.utc)
        })
        
        return {
            "user_id": payload.get("sub"),
            "scopes": payload.get("scopes", []),
            "client_id": payload.get("client_id"),
            "key_id": payload.get("key_id")
        }
        
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Authentication service error"
        )


async def require_scope(required_scope: str):
    """
    Dependency to require specific OAuth2 scope.
    
    Args:
        required_scope: Required scope string
        
    Returns:
        Dependency function that validates scope
    """
    async def scope_validator(user: Dict[str, Any] = Depends(get_current_user)):
        scopes = user.get("scopes", [])
        if required_scope not in scopes:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required scope: {required_scope}"
            )
        return user
    
    return scope_validator


async def check_rate_limit(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
    security_repo: SecurityRepository = Depends(get_security_repository)
) -> Dict[str, Any]:
    """
    Check rate limit for authenticated user.
    
    Args:
        request: FastAPI request object
        user: Current user information
        security_repo: Security repository for rate limiting
        
    Returns:
        Rate limit information
        
    Raises:
        HTTPException: If rate limit exceeded
    """
    # Use API key ID for rate limiting
    identifier = str(user.get("key_id", user.get("user_id")))
    endpoint = str(request.url.path)
    
    allowed, rate_info = await security_repo.check_rate_limit(
        identifier=identifier,
        bucket_type="api_key",
        endpoint=endpoint
    )
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(rate_info.get("limit")),
                "X-RateLimit-Remaining": str(rate_info.get("remaining", 0)),
                "X-RateLimit-Reset": rate_info.get("reset_at").isoformat() if rate_info.get("reset_at") else "",
                "Retry-After": str(rate_info.get("retry_after", 60))
            }
        )
    
    return rate_info


class UseCaseDependencies:
    """Dependency injection for use cases."""
    
    @staticmethod
    async def get_start_bot_use_case(
        bot_repo: BotInstanceRepository = Depends(get_bot_repository),
        process_repo: ProcessRepository = Depends(get_process_repository),
        container: Container = Depends(get_container),
        factory: ExecutionStrategyFactory = Depends(get_strategy_factory)
    ) -> StartBotUseCase:
        """Get start bot use case with dependencies."""
        return StartBotUseCase(
            bot_repository=bot_repo,
            process_repository=process_repo,
            strategy_factory=factory,
            feature_container=container
        )
    
    @staticmethod
    async def get_stop_bot_use_case(
        bot_repo: BotInstanceRepository = Depends(get_bot_repository),
        process_repo: ProcessRepository = Depends(get_process_repository),
        factory: ExecutionStrategyFactory = Depends(get_strategy_factory)
    ) -> StopBotUseCase:
        """Get stop bot use case with dependencies."""
        return StopBotUseCase(
            bot_repository=bot_repo,
            process_repository=process_repo,
            strategy_factory=factory
        )
    
    @staticmethod
    async def get_restart_bot_use_case(
        start_use_case: StartBotUseCase = Depends(get_start_bot_use_case),
        stop_use_case: StopBotUseCase = Depends(get_stop_bot_use_case)
    ) -> RestartBotUseCase:
        """Get restart bot use case with dependencies."""
        return RestartBotUseCase(
            start_use_case=start_use_case,
            stop_use_case=stop_use_case
        )


async def get_use_cases() -> UseCaseDependencies:
    """Get use case dependencies helper."""
    return UseCaseDependencies()