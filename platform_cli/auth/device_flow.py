"""
CLI OAuth2 Device Flow Client
=============================

Handles device flow authentication for the MultiCord CLI.
Provides user-friendly prompts and automatic token polling.
"""

import asyncio
import webbrowser
from typing import Optional, Dict
import logging

import httpx

from platform_core.entities.auth import TokenResponse


logger = logging.getLogger(__name__)


class DeviceFlowClient:
    """OAuth2 device flow client for CLI authentication."""
    
    def __init__(self,
                 client_id: str = "multicord-cli",
                 base_url: str = "https://multicord.io",
                 api_base_url: Optional[str] = None):
        """
        Initialize device flow client.
        
        Args:
            client_id: OAuth2 client identifier
            base_url: Base URL for authentication
            api_base_url: API base URL (defaults to base_url + /api/v1)
        """
        self.client_id = client_id
        self.base_url = base_url
        self.api_base_url = api_base_url or f"{base_url}/api/v1"
        
        # Endpoints
        self.device_endpoint = f"{self.api_base_url}/auth/device"
        self.token_endpoint = f"{self.api_base_url}/auth/token"
    
    async def authenticate(self, 
                          scopes: Optional[list] = None,
                          auto_open_browser: bool = True) -> Optional[TokenResponse]:
        """
        Complete device flow authentication.
        
        Args:
            scopes: OAuth2 scopes to request
            auto_open_browser: Whether to automatically open browser
            
        Returns:
            Token response if successful, None otherwise
        """
        try:
            # Request device code
            device_response = await self._request_device_code(scopes)
            if not device_response:
                return None
            
            # Display authentication prompt
            self._display_auth_prompt(device_response, auto_open_browser)
            
            # Poll for token
            token = await self._poll_for_token(
                device_response["device_code"],
                device_response["interval"],
                device_response["expires_in"]
            )
            
            if token:
                print("\n✓ Authentication successful!")
            else:
                print("\n✗ Authentication failed or timed out.")
            
            return token
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            print(f"\n✗ Authentication error: {e}")
            return None
    
    async def _request_device_code(self, scopes: Optional[list]) -> Optional[Dict]:
        """Request device code from server."""
        async with httpx.AsyncClient() as client:
            try:
                data = {"client_id": self.client_id}
                if scopes:
                    data["scope"] = " ".join(scopes)
                
                response = await client.post(self.device_endpoint, json=data)
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPError as e:
                logger.error(f"Failed to request device code: {e}")
                return None
    
    def _display_auth_prompt(self, device_response: Dict, auto_open_browser: bool):
        """Display authentication prompt to user."""
        print("\n" + "="*50)
        print("🔐 MultiCord Authentication Required")
        print("="*50)
        print(f"\nPlease visit: {device_response['verification_uri']}")
        print(f"\nAnd enter code: {device_response['user_code']}")
        print("\n" + "="*50)
        
        if auto_open_browser:
            try:
                # Try to open browser automatically
                webbrowser.open(device_response.get(
                    'verification_uri_complete',
                    device_response['verification_uri']
                ))
                print("✓ Browser opened automatically")
            except Exception:
                print("! Could not open browser automatically")
        else:
            print("\nPress Enter after you've authorized the application...")
            # Don't actually wait for Enter, just continue polling
    
    async def _poll_for_token(self, 
                             device_code: str,
                             interval: int,
                             expires_in: int) -> Optional[TokenResponse]:
        """Poll token endpoint until authorization or timeout."""
        timeout = asyncio.get_event_loop().time() + expires_in
        poll_interval = interval
        
        print("\nWaiting for authorization", end="", flush=True)
        
        async with httpx.AsyncClient() as client:
            while asyncio.get_event_loop().time() < timeout:
                try:
                    # Poll token endpoint
                    response = await client.post(
                        self.token_endpoint,
                        data={
                            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                            "device_code": device_code,
                            "client_id": self.client_id
                        }
                    )
                    
                    if response.status_code == 200:
                        # Success!
                        data = response.json()
                        return TokenResponse(
                            access_token=data["access_token"],
                            refresh_token=data["refresh_token"],
                            token_type=data.get("token_type", "Bearer"),
                            expires_in=data.get("expires_in", 3600),
                            scope=data.get("scope", "")
                        )
                    
                    # Check error response
                    if response.status_code == 400:
                        data = response.json()
                        error = data.get("error")
                        
                        if error == "authorization_pending":
                            # Still waiting for user
                            print(".", end="", flush=True)
                            await asyncio.sleep(poll_interval)
                            
                        elif error == "slow_down":
                            # Rate limited, increase interval
                            poll_interval += 5
                            print("!", end="", flush=True)
                            await asyncio.sleep(poll_interval)
                            
                        elif error == "access_denied":
                            print("\n✗ Authorization denied by user")
                            return None
                            
                        elif error == "expired_token":
                            print("\n✗ Device code expired")
                            return None
                        else:
                            print(f"\n✗ Unknown error: {error}")
                            return None
                    
                except httpx.HTTPError as e:
                    logger.error(f"Polling error: {e}")
                    print("!", end="", flush=True)
                    await asyncio.sleep(poll_interval)
        
        print("\n✗ Authentication timed out")
        return None
    
    async def refresh_token(self, refresh_token: str) -> Optional[TokenResponse]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Current refresh token
            
        Returns:
            New token response if successful
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.token_endpoint,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": self.client_id
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                return TokenResponse(
                    access_token=data["access_token"],
                    refresh_token=data["refresh_token"],
                    token_type=data.get("token_type", "Bearer"),
                    expires_in=data.get("expires_in", 3600),
                    scope=data.get("scope", "")
                )
                
            except httpx.HTTPError as e:
                logger.error(f"Token refresh failed: {e}")
                return None