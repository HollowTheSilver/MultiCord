"""
Audit Logging Middleware
========================

Logs all API requests and responses for security monitoring.
"""

import time
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request

from platform_api.config import settings


logger = logging.getLogger(__name__)


class AuditLogger:
    """Audit logging middleware."""
    
    def __init__(self):
        self.enabled = settings.LOG_LEVEL != "DEBUG"  # Disable in debug mode
        self.sensitive_paths = {"/api/v1/auth/token"}  # Don't log request body
    
    async def __call__(self, request: Request, call_next):
        """Log API requests and responses."""
        if not self.enabled:
            return await call_next(request)
        
        # Start timing
        start_time = time.time()
        
        # Get request info
        request_id = request.headers.get("X-Request-ID", str(time.time()))
        client_ip = request.client.host
        user_id = getattr(request.state, "user_id", None)
        
        # Get request body (if not sensitive)
        request_body = None
        if request.url.path not in self.sensitive_paths:
            try:
                body = await request.body()
                if body:
                    request_body = body.decode('utf-8')[:1000]  # Limit size
                # Reset body for the actual handler
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            except Exception:
                pass
        
        # Process request
        response = await call_next(request)
        
        # Calculate execution time
        execution_time = (time.time() - start_time) * 1000  # ms
        
        # Log audit entry
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": client_ip,
            "user_id": user_id,
            "status_code": response.status_code,
            "execution_time_ms": round(execution_time, 2),
            "user_agent": request.headers.get("User-Agent")
        }
        
        if request_body and settings.DEBUG:
            audit_entry["request_body"] = request_body
        
        # Log based on status code
        if response.status_code >= 500:
            logger.error(f"API Error: {json.dumps(audit_entry)}")
        elif response.status_code >= 400:
            logger.warning(f"API Warning: {json.dumps(audit_entry)}")
        else:
            logger.info(f"API Request: {json.dumps(audit_entry)}")
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


def setup_audit_logging(app: FastAPI):
    """Setup audit logging middleware."""
    audit_logger = AuditLogger()
    app.middleware("http")(audit_logger)