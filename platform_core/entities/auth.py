"""
Authentication Entity Models
============================

Domain entities for OAuth2 device flow and JWT token management.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from uuid import UUID


@dataclass
class DeviceCodeData:
    """Internal representation of device authorization data."""
    device_code: str
    user_code: str
    client_id: str
    scopes: List[str]
    expires_at: datetime
    created_at: datetime
    authorized: bool = False
    authorized_by: Optional[str] = None
    authorized_at: Optional[datetime] = None
    last_poll_at: Optional[datetime] = None


@dataclass
class DeviceAuthorizationResponse:
    """Response for device authorization request."""
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int  # seconds
    interval: int  # minimum polling interval in seconds


@dataclass
class TokenResponse:
    """OAuth2 token response."""
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int  # seconds
    scope: str


@dataclass
class JWTClaims:
    """JWT token claims."""
    iss: str  # Issuer
    sub: str  # Subject (user ID)
    aud: List[str]  # Audience
    exp: datetime  # Expiration
    iat: datetime  # Issued at
    jti: str  # JWT ID
    scopes: List[str]  # Permissions
    token_type: str  # "access" or "refresh"
    family_id: Optional[str] = None  # For refresh token rotation


@dataclass
class StoredToken:
    """Token stored in database."""
    id: UUID
    jti: str
    token_type: str
    user_id: str
    expires_at: datetime
    issued_at: datetime
    revoked: bool = False
    revoked_at: Optional[datetime] = None
    family_id: Optional[str] = None
    used: bool = False  # For refresh token rotation