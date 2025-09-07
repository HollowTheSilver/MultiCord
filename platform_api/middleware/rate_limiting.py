"""
Rate Limiting Middleware
========================

Token bucket rate limiting for API endpoints.
"""

import time
import logging
from typing import Dict, Tuple

from fastapi import FastAPI, Request, HTTPException, status

from platform_api.config import settings


logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket for rate limiting."""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
    
    def consume(self, tokens: int = 1) -> Tuple[bool, float]:
        """
        Try to consume tokens from bucket.
        
        Returns:
            Tuple of (success, wait_time_if_failed)
        """
        now = time.time()
        elapsed = now - self.last_refill
        
        # Refill tokens
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return (True, 0)
        else:
            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.refill_rate
            return (False, wait_time)


class RateLimiter:
    """Rate limiting middleware."""
    
    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = {}
        self.rate_per_minute = settings.RATE_LIMIT_PER_MINUTE
        self.rate_per_hour = settings.RATE_LIMIT_PER_HOUR
    
    def get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Use user ID if authenticated, otherwise IP
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"
        else:
            return f"ip:{request.client.host}"
    
    async def __call__(self, request: Request, call_next):
        """Apply rate limiting."""
        # Skip rate limiting for health checks
        if request.url.path.startswith("/api/health"):
            return await call_next(request)
        
        client_id = self.get_client_id(request)
        
        # Get or create bucket
        if client_id not in self.buckets:
            self.buckets[client_id] = TokenBucket(
                capacity=self.rate_per_minute,
                refill_rate=self.rate_per_minute / 60.0
            )
        
        bucket = self.buckets[client_id]
        allowed, wait_time = bucket.consume()
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {wait_time:.1f} seconds",
                headers={"Retry-After": str(int(wait_time) + 1)}
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.rate_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + 60))
        
        return response


def setup_rate_limiting(app: FastAPI):
    """Setup rate limiting middleware."""
    limiter = RateLimiter()
    app.middleware("http")(limiter)