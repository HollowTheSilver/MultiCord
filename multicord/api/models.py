"""
API request/response models for MultiCord CLI.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# Authentication Models

class DeviceAuthResponse(BaseModel):
    """Response from device flow initiation."""
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


class TokenResponse(BaseModel):
    """Response from token exchange."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRequest(BaseModel):
    """Request for token exchange."""
    device_code: str
    grant_type: str = "urn:ietf:params:oauth:grant-type:device_code"


class RefreshTokenRequest(BaseModel):
    """Request for token refresh."""
    refresh_token: str
    grant_type: str = "refresh_token"


# Bot Models

class BotConfig(BaseModel):
    """Bot configuration."""
    token: Optional[str] = Field(None, description="Discord bot token (encrypted)")
    prefix: str = Field(default="!", description="Command prefix")
    intents: List[str] = Field(default=["guilds", "messages"])
    settings: Dict[str, Any] = Field(default_factory=dict)


class BotResponse(BaseModel):
    """Bot information from API."""
    id: str
    name: str
    description: Optional[str] = None
    status: str  # stopped, starting, running, stopping, error
    template: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_heartbeat: Optional[datetime] = None
    guild_count: int = 0
    message_count: int = 0
    config: BotConfig


class BotListResponse(BaseModel):
    """List of bots from API."""
    bots: List[BotResponse]
    total: int
    page: int
    per_page: int


class CreateBotRequest(BaseModel):
    """Request to create a new bot."""
    name: str
    description: Optional[str] = None
    template: Optional[str] = None
    config: BotConfig


class UpdateBotRequest(BaseModel):
    """Request to update bot."""
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[BotConfig] = None


class BotStatusResponse(BaseModel):
    """Bot status information."""
    id: str
    status: str
    message: Optional[str] = None
    node: Optional[Dict[str, Any]] = None


class BotLogsResponse(BaseModel):
    """Bot logs response."""
    bot_id: str
    logs: List[Dict[str, Any]]
    lines: int
    since: Optional[datetime] = None


# User Models

class UserProfile(BaseModel):
    """User profile information."""
    id: str
    email: str
    username: str
    created_at: datetime
    subscription_tier: str  # free, pro, enterprise
    is_active: bool
    is_verified: bool
    bot_limit: int
    bots_used: int
    clients: List[Dict[str, Any]] = []


class UsageStats(BaseModel):
    """User usage statistics."""
    total_bots: int
    active_bots: int
    total_runtime_hours: float
    api_calls_this_month: int
    storage_used_mb: float
    last_activity: Optional[datetime] = None
    by_bot: List[Dict[str, Any]] = []


class SubscriptionInfo(BaseModel):
    """Subscription information."""
    tier: str
    bot_limit: int
    api_rate_limit: int
    features: List[str]
    next_billing_date: Optional[datetime] = None
    amount: Optional[float] = None
    currency: Optional[str] = None


# Error Models

class ErrorResponse(BaseModel):
    """API error response."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None


class ValidationError(BaseModel):
    """Validation error details."""
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    """Validation error response."""
    error: str = "validation_error"
    message: str = "Request validation failed"
    details: Dict[str, List[ValidationError]]