"""
HTTP client for MultiCord API integration with network detection and offline fallbacks.
"""

import httpx
import asyncio
import time
import socket
from typing import Optional, Dict, Any, List
import keyring
import json
from functools import wraps


def handle_network_errors(offline_return=None):
    """Decorator to handle network errors and provide offline fallbacks."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except (httpx.ConnectError, httpx.TimeoutException, socket.gaierror):
                # Network unavailable, return offline fallback
                if hasattr(self, '_set_offline_mode'):
                    self._set_offline_mode(True)
                return offline_return
            except httpx.HTTPStatusError as e:
                # Server error, but network is available
                if e.response.status_code >= 500:
                    return offline_return
                raise  # Re-raise client errors (4xx)
            except Exception:
                # Unknown error, assume offline
                return offline_return
        return wrapper
    return decorator


class APIClient:
    """Client for interacting with MultiCord cloud services."""
    
    SERVICE_NAME = "multicord"
    ACCESS_TOKEN_KEY = "access_token"
    REFRESH_TOKEN_KEY = "refresh_token"
    TOKEN_EXPIRY_KEY = "token_expiry"
    
    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or "http://localhost:8000"  # Default to local dev
        self.client = httpx.Client(timeout=30.0)
        self._offline_mode = False
        self._last_network_check = 0
        self._network_check_interval = 60  # Check network every 60 seconds
        
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication if available."""
        headers = {"Content-Type": "application/json"}
        
        token = keyring.get_password(self.SERVICE_NAME, self.ACCESS_TOKEN_KEY)
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        return headers
    
    def _store_tokens(self, tokens: Dict[str, Any]) -> None:
        """Store tokens securely in keyring."""
        keyring.set_password(self.SERVICE_NAME, self.ACCESS_TOKEN_KEY, tokens["access_token"])
        keyring.set_password(self.SERVICE_NAME, self.REFRESH_TOKEN_KEY, tokens["refresh_token"])
        
        # Store expiry time
        expiry = int(time.time()) + tokens.get("expires_in", 3600)
        keyring.set_password(self.SERVICE_NAME, self.TOKEN_EXPIRY_KEY, str(expiry))
    
    def start_device_flow(self) -> Dict[str, Any]:
        """Initiate OAuth2 device flow authentication."""
        try:
            response = self.client.post(
                f"{self.api_url}/v1/auth/device",
                json={"client_id": "multicord-cli"},
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise Exception(f"Failed to connect to API: {e}")
        except httpx.HTTPStatusError as e:
            raise Exception(f"API error: {e.response.text}")
    
    def poll_for_token(self, device_code: str, interval: int) -> Optional[Dict[str, Any]]:
        """Poll for token completion."""
        max_attempts = 60  # Max 5 minutes at 5-second intervals
        attempts = 0
        
        while attempts < max_attempts:
            time.sleep(interval)
            
            try:
                response = self.client.post(
                    f"{self.api_url}/v1/auth/token",
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        "device_code": device_code,
                        "client_id": "multicord-cli"
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    tokens = response.json()
                    self._store_tokens(tokens)
                    return tokens
                elif response.status_code == 400:
                    error = response.json().get("error")
                    if error == "authorization_pending":
                        # User hasn't authorized yet, keep polling
                        attempts += 1
                        continue
                    elif error == "slow_down":
                        # Increase polling interval
                        interval += 5
                        continue
                    else:
                        # Other error (expired, denied, etc.)
                        return None
                else:
                    return None
                    
            except Exception:
                attempts += 1
                continue
        
        return None
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        token = keyring.get_password(self.SERVICE_NAME, self.ACCESS_TOKEN_KEY)
        if not token:
            return False
            
        # Check if token is expired
        try:
            expiry = keyring.get_password(self.SERVICE_NAME, self.TOKEN_EXPIRY_KEY)
            if expiry and int(expiry) < int(time.time()):
                # Token expired, try to refresh
                return self._refresh_token()
        except:
            pass
            
        return True
    
    def _refresh_token(self) -> bool:
        """Refresh access token using refresh token."""
        refresh_token = keyring.get_password(self.SERVICE_NAME, self.REFRESH_TOKEN_KEY)
        if not refresh_token:
            return False
            
        try:
            response = self.client.post(
                f"{self.api_url}/v1/auth/refresh",
                json={"refresh_token": refresh_token},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                tokens = response.json()
                self._store_tokens(tokens)
                return True
        except:
            pass
            
        return False
    
    def logout(self) -> bool:
        """Clear stored credentials."""
        try:
            keyring.delete_password(self.SERVICE_NAME, self.ACCESS_TOKEN_KEY)
            keyring.delete_password(self.SERVICE_NAME, self.REFRESH_TOKEN_KEY)
            keyring.delete_password(self.SERVICE_NAME, self.TOKEN_EXPIRY_KEY)
            return True
        except:
            return False
    
    @handle_network_errors(offline_return=[])
    def list_bots(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List cloud bots (returns empty list if offline)."""
        params = {}
        if status:
            params["status"] = status
            
        response = self.client.get(
            f"{self.api_url}/v1/bots",
            params=params,
            headers=self._get_headers()
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("bots", [])
    
    def create_bot(self, name: str, template: str) -> Dict[str, Any]:
        """Create a cloud bot."""
        try:
            response = self.client.post(
                f"{self.api_url}/v1/bots",
                json={
                    "name": name,
                    "template": template,
                    "config": {
                        "token": "",  # User will need to set this
                        "prefix": "!",
                        "intents": ["guilds", "messages"]
                    }
                },
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to create bot: {e}")
    
    def start_bot(self, bot_id: str) -> Dict[str, Any]:
        """Start a cloud bot."""
        try:
            response = self.client.post(
                f"{self.api_url}/v1/bots/{bot_id}/start",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to start bot: {e}")
    
    def stop_bot(self, bot_id: str) -> None:
        """Stop a cloud bot."""
        try:
            response = self.client.post(
                f"{self.api_url}/v1/bots/{bot_id}/stop",
                headers=self._get_headers()
            )
            response.raise_for_status()
        except Exception as e:
            raise Exception(f"Failed to stop bot: {e}")
    
    def restart_bot(self, bot_id: str) -> Dict[str, Any]:
        """Restart a cloud bot."""
        try:
            response = self.client.post(
                f"{self.api_url}/v1/bots/{bot_id}/restart",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to restart bot: {e}")
    
    def get_bot(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get bot details."""
        try:
            response = self.client.get(
                f"{self.api_url}/v1/bots/{bot_id}",
                headers=self._get_headers()
            )
            
            if response.status_code == 404:
                return None
                
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to get bot: {e}")
    
    def _set_offline_mode(self, offline: bool):
        """Set offline mode status."""
        self._offline_mode = offline
        self._last_network_check = time.time()
    
    def is_online(self) -> bool:
        """Check if API is reachable (with caching)."""
        current_time = time.time()
        
        # Use cached result if recent
        if current_time - self._last_network_check < self._network_check_interval:
            return not self._offline_mode
        
        # Perform actual network check
        is_reachable = self.check_health()
        self._set_offline_mode(not is_reachable)
        return is_reachable
    
    def check_health(self) -> bool:
        """Check API health."""
        try:
            response = self.client.get(f"{self.api_url}/health", timeout=5.0)
            self._set_offline_mode(False)
            return response.status_code == 200
        except:
            self._set_offline_mode(True)
            return False
    
    def require_online(self) -> bool:
        """Check if online, raise exception if not."""
        if not self.is_online():
            raise ConnectionError("API is not reachable. Please check your internet connection or use local commands.")
        return True