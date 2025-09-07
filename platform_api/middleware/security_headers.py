"""
Security Headers Middleware
===========================

Adds security headers to all API responses.
"""

from fastapi import FastAPI, Request
from fastapi.responses import Response


async def security_headers_middleware(request: Request, call_next):
    """Add security headers to response."""
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # Remove server header
    response.headers.pop("Server", None)
    
    return response


def setup_security_headers(app: FastAPI):
    """Setup security headers middleware."""
    app.middleware("http")(security_headers_middleware)