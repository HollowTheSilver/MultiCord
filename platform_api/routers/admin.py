"""
Admin Router
===========

Administrative endpoints for platform management.
"""

from fastapi import APIRouter, Request

from platform_api.exceptions import AuthorizationError


router = APIRouter()


@router.get("/stats")
async def platform_stats(request: Request):
    """Get platform statistics (admin only)."""
    # Check admin permission
    if "admin" not in request.state.scopes:
        raise AuthorizationError("Admin access required")
    
    # TODO: Implement platform statistics
    return {
        "total_bots": 0,
        "active_bots": 0,
        "total_users": 0,
        "api_calls_today": 0
    }