"""
Health Check Router
==================

Health and readiness endpoints for monitoring.
"""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, status

from platform_api.config import settings


router = APIRouter()


@router.get("/", response_model=Dict[str, Any])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.APP_VERSION
    }


@router.get("/ready", response_model=Dict[str, Any])
async def readiness_check():
    """Readiness check with dependency status."""
    checks = {
        "api": True,
        "database": False,  # TODO: Check database connection
        "auth_service": True
    }
    
    all_ready = all(checks.values())
    
    return {
        "ready": all_ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }