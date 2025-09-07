"""
OAuth2 Device Flow Authentication Service
=========================================

Implements OAuth2 Device Authorization Grant (RFC 8628) for CLI authentication.
Follows GitHub CLI patterns for user-friendly device code display.
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from uuid import uuid4
import logging

from platform_core.entities.auth import (
    DeviceAuthorizationResponse,
    DeviceCodeData,
    TokenResponse
)


logger = logging.getLogger(__name__)


class DeviceFlowService:
    """OAuth2 device flow authentication service."""
    
    # User-friendly character set (excludes ambiguous characters)
    USER_CODE_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    
    # Device flow configuration
    DEVICE_CODE_LENGTH = 32  # bytes of entropy
    USER_CODE_LENGTH = 8
    CODE_EXPIRATION_MINUTES = 15
    POLLING_INTERVAL_SECONDS = 5
    
    def __init__(self, 
                 base_url: str = "https://multicord.io",
                 client_id: str = "multicord-cli"):
        """
        Initialize device flow service.
        
        Args:
            base_url: Base URL for authentication endpoints
            client_id: OAuth2 client identifier
        """
        self.base_url = base_url
        self.client_id = client_id
        self._device_codes: Dict[str, DeviceCodeData] = {}
    
    def generate_device_code(self) -> str:
        """Generate cryptographically secure device code."""
        return secrets.token_urlsafe(self.DEVICE_CODE_LENGTH)
    
    def generate_user_code(self) -> str:
        """
        Generate user-friendly verification code.
        
        Returns:
            Formatted code like "ABCD-1234"
        """
        code = ''.join(
            secrets.choice(self.USER_CODE_CHARSET) 
            for _ in range(self.USER_CODE_LENGTH)
        )
        # Format with hyphen for readability
        return f"{code[:4]}-{code[4:]}"
    
    async def create_device_authorization(self, 
                                         scopes: Optional[list] = None) -> DeviceAuthorizationResponse:
        """
        Create device authorization request.
        
        Args:
            scopes: Optional OAuth2 scopes to request
            
        Returns:
            Device authorization response with codes and URIs
        """
        device_code = self.generate_device_code()
        user_code = self.generate_user_code()
        
        # Store device code data for verification
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.CODE_EXPIRATION_MINUTES)
        
        device_data = DeviceCodeData(
            device_code=device_code,
            user_code=user_code,
            client_id=self.client_id,
            scopes=scopes or ["bot:read", "bot:write"],
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc)
        )
        
        self._device_codes[device_code] = device_data
        
        return DeviceAuthorizationResponse(
            device_code=device_code,
            user_code=user_code,
            verification_uri=f"{self.base_url}/device",
            verification_uri_complete=f"{self.base_url}/device?code={user_code}",
            expires_in=self.CODE_EXPIRATION_MINUTES * 60,
            interval=self.POLLING_INTERVAL_SECONDS
        )
    
    async def verify_device_code(self, device_code: str) -> Optional[DeviceCodeData]:
        """
        Verify device code is valid and not expired.
        
        Args:
            device_code: Device code to verify
            
        Returns:
            Device code data if valid, None otherwise
        """
        device_data = self._device_codes.get(device_code)
        
        if not device_data:
            return None
        
        # Check expiration
        if datetime.now(timezone.utc) > device_data.expires_at:
            # Clean up expired code
            del self._device_codes[device_code]
            return None
        
        return device_data
    
    async def authorize_device(self, 
                              user_code: str, 
                              user_id: str) -> bool:
        """
        Authorize device with user code.
        
        Args:
            user_code: User-entered verification code
            user_id: ID of authorizing user
            
        Returns:
            True if authorization successful
        """
        # Find device data by user code
        device_data = None
        for data in self._device_codes.values():
            if data.user_code == user_code and not data.authorized:
                device_data = data
                break
        
        if not device_data:
            return False
        
        # Check expiration
        if datetime.now(timezone.utc) > device_data.expires_at:
            return False
        
        # Mark as authorized
        device_data.authorized = True
        device_data.authorized_by = user_id
        device_data.authorized_at = datetime.now(timezone.utc)
        
        logger.info(f"Device authorized for user {user_id}")
        return True
    
    async def poll_for_token(self, device_code: str) -> Tuple[Optional[str], Optional[TokenResponse]]:
        """
        Check if device has been authorized and return tokens.
        
        Args:
            device_code: Device code to check
            
        Returns:
            Tuple of (error_code, token_response)
            Error codes: "authorization_pending", "slow_down", "expired_token", "access_denied"
        """
        device_data = await self.verify_device_code(device_code)
        
        if not device_data:
            return ("expired_token", None)
        
        if not device_data.authorized:
            # Check if we're being polled too frequently
            now = datetime.now(timezone.utc)
            if device_data.last_poll_at:
                time_since_poll = (now - device_data.last_poll_at).total_seconds()
                if time_since_poll < self.POLLING_INTERVAL_SECONDS:
                    return ("slow_down", None)
            
            device_data.last_poll_at = now
            return ("authorization_pending", None)
        
        # Device is authorized, generate tokens
        # This will be handled by token_service
        # For now, return placeholder
        token_response = TokenResponse(
            access_token="placeholder_access_token",
            refresh_token="placeholder_refresh_token",
            token_type="Bearer",
            expires_in=3600,
            scope=" ".join(device_data.scopes)
        )
        
        # Clean up used device code
        del self._device_codes[device_code]
        
        return (None, token_response)
    
    async def cleanup_expired_codes(self) -> int:
        """
        Clean up expired device codes.
        
        Returns:
            Number of codes cleaned up
        """
        now = datetime.now(timezone.utc)
        expired_codes = [
            code for code, data in self._device_codes.items()
            if now > data.expires_at
        ]
        
        for code in expired_codes:
            del self._device_codes[code]
        
        if expired_codes:
            logger.info(f"Cleaned up {len(expired_codes)} expired device codes")
        
        return len(expired_codes)