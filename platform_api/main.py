"""
MultiCord Platform API
======================

Enterprise-grade REST API for Discord bot infrastructure management.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from platform_api.config import settings
from platform_api.exceptions import setup_exception_handlers
from platform_api.middleware import (
    setup_auth_middleware,
    setup_rate_limiting,
    setup_audit_logging,
    setup_security_headers
)
from platform_api.routers import auth, bots, health, admin
from platform_api.dependencies import initialize_dependencies, cleanup_dependencies


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    logger.info("Starting MultiCord API")
    
    # Initialize all dependencies
    await initialize_dependencies(
        db_host=settings.DB_HOST,
        db_port=settings.DB_PORT,
        db_name=settings.DB_NAME,
        db_user=settings.DB_USER,
        db_password=settings.DB_PASSWORD,
        ssl_mode=settings.DB_SSL_MODE
    )
    
    yield
    
    # Cleanup
    logger.info("Shutting down MultiCord API")
    await cleanup_dependencies()


app = FastAPI(
    title="MultiCord Platform API",
    description="Enterprise Discord Bot Infrastructure Management",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan
)

# Configure CORS (configure for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)

# Custom middleware (order matters!)
setup_security_headers(app)
setup_rate_limiting(app)
setup_audit_logging(app)
setup_auth_middleware(app)

# Exception handlers
setup_exception_handlers(app)

# Include routers
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(bots.router, prefix="/api/v1/bots", tags=["bots"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MultiCord Platform API",
        "version": "1.0.0",
        "status": "operational"
    }