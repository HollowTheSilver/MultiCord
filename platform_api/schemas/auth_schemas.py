"""
Authentication Schemas
=====================

Pydantic models for authentication requests and responses.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, validator


class DeviceCodeRequest(BaseModel):
    """Request for device code."""
    client_id: str = Field(..., description="OAuth2 client identifier")
    scope: Optional[str] = Field(None, description="Space-separated scopes")
    
    @validator('scope')
    def validate_scope(cls, v):
        if v:
            allowed_scopes = {"bot:read", "bot:write", "bot:admin", "metrics:read"}
            requested = set(v.split())
            invalid = requested - allowed_scopes
            if invalid:
                raise ValueError(f"Invalid scopes: {invalid}")
        return v


class DeviceCodeResponse(BaseModel):
    """Device code authorization response."""
    device_code: str = Field(..., description="Device verification code")
    user_code: str = Field(..., description="User-friendly code to enter")
    verification_uri: str = Field(..., description="URL for user verification")
    verification_uri_complete: str = Field(..., description="URL with embedded code")
    expires_in: int = Field(..., description="Expiration in seconds")
    interval: int = Field(..., description="Minimum polling interval")


class TokenRequest(BaseModel):
    """Token exchange request."""
    grant_type: str = Field(..., description="OAuth2 grant type")
    device_code: Optional[str] = Field(None, description="Device code for exchange")
    refresh_token: Optional[str] = Field(None, description="Refresh token for rotation")
    client_id: str = Field(..., description="Client identifier")
    
    @validator('grant_type')
    def validate_grant_type(cls, v):
        allowed = {
            "urn:ietf:params:oauth:grant-type:device_code",
            "refresh_token"
        }
        if v not in allowed:
            raise ValueError(f"Unsupported grant type: {v}")
        return v


class TokenResponse(BaseModel):
    """OAuth2 token response."""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")
    scope: str = Field(..., description="Granted scopes")


class TokenErrorResponse(BaseModel):
    """Token error response."""
    error: str = Field(..., description="Error code")
    error_description: Optional[str] = Field(None, description="Human-readable error")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "authorization_pending",
                "error_description": "The authorization request is still pending"
            }
        }


class TokenIntrospectionRequest(BaseModel):
    """Token introspection request."""
    token: str = Field(..., description="Token to introspect")
    token_type_hint: Optional[str] = Field(None, description="Token type hint")


class TokenIntrospectionResponse(BaseModel):
    """Token introspection response."""
    active: bool = Field(..., description="Whether token is active")
    scope: Optional[str] = Field(None, description="Token scopes")
    client_id: Optional[str] = Field(None, description="Client identifier")
    username: Optional[str] = Field(None, description="Username")
    exp: Optional[int] = Field(None, description="Expiration timestamp")
    iat: Optional[int] = Field(None, description="Issued at timestamp")
    sub: Optional[str] = Field(None, description="Subject (user ID)")
    aud: Optional[List[str]] = Field(None, description="Audience")
    jti: Optional[str] = Field(None, description="JWT ID")


class UserInfo(BaseModel):
    """User information from token."""
    user_id: str = Field(..., description="User identifier")
    username: str = Field(..., description="Username")
    scopes: List[str] = Field(..., description="Granted permissions")
    client_id: Optional[str] = Field(None, description="Client identifier")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "username": "john.doe",
                "scopes": ["bot:read", "bot:write"],
                "client_id": "multicord-cli"
            }
        }