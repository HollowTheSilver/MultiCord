"""
Authentication Middleware
=========================

JWT token validation middleware for protected endpoints.
"""

import logging
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from platform_core.services.token_service import TokenService
from platform_api.config import settings


logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


class AuthMiddleware:
    """JWT authentication middleware."""
    
    def __init__(self):
        self.token_service = TokenService(
            private_key_path=settings.get_jwt_private_key_path(),
            public_key_path=settings.get_jwt_public_key_path()
        )
        # Public endpoints that don't require authentication
        self.public_paths = {
            "/",
            "/api/health",
            "/api/health/ready",
            "/api/v1/auth/device",
            "/api/v1/auth/token",
            "/api/docs",
            "/api/redoc",
            "/api/v1/openapi.json"
        }
    
    async def __call__(self, request: Request, call_next):
        """Validate JWT token for protected endpoints."""
        # Skip auth for public endpoints
        if request.url.path in self.public_paths:
            return await call_next(request)
        
        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header"
            )
        
        token = auth_header.replace("Bearer ", "")
        
        # Validate token
        claims = self.token_service.verify_token(token)
        if not claims:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Attach user info to request state
        request.state.user_id = claims.get("sub")
        request.state.scopes = claims.get("scopes", [])
        request.state.token_jti = claims.get("jti")
        
        return await call_next(request)


def setup_auth_middleware(app: FastAPI):
    """Setup authentication middleware."""
    middleware = AuthMiddleware()
    app.middleware("http")(middleware)