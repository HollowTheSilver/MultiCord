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
from multicord.utils.cache import CacheManager
from multicord.utils.validation import validate_api_url_https


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

        # Enforce HTTPS for non-localhost API URLs
        is_valid, error_msg = validate_api_url_https(self.api_url)
        if not is_valid:
            raise ValueError(f"Insecure API URL: {error_msg}")

        # Explicitly verify SSL certificates (never disable)
        self.client = httpx.Client(timeout=30.0, verify=True)
        self._offline_mode = False
        self._last_network_check = 0
        self._network_check_interval = 60  # Check network every 60 seconds
        self.cache = CacheManager()  # Initialize cache manager
        
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
    
    def discord_login(self) -> str:
        """Get Discord OAuth2 login URL."""
        try:
            response = self.client.get(
                f"{self.api_url}/v1/auth/discord",
                follow_redirects=False
            )
            # Return the redirect URL to Discord
            if response.status_code in [302, 307]:
                return response.headers.get("Location", "")
            return f"{self.api_url}/v1/auth/discord"
        except httpx.RequestError as e:
            raise Exception(f"Failed to connect to API: {e}")

    def exchange_discord_code(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange Discord authorization code for tokens."""
        try:
            response = self.client.post(
                f"{self.api_url}/v1/auth/discord/exchange",
                json={
                    "code": code,
                    "state": state
                },
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                tokens = response.json()
                self._store_tokens(tokens)
                return tokens
            else:
                raise Exception(f"Failed to exchange code: {response.text}")

        except httpx.RequestError as e:
            raise Exception(f"Failed to connect to API: {e}")
        except httpx.HTTPStatusError as e:
            raise Exception(f"API error: {e.response.text}")
    
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
        except (ValueError, TypeError, KeyError):
            # Invalid expiry format, treat as expired
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
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, KeyError):
            # Network error, invalid response, or missing keys
            pass

        return False
    
    def logout(self) -> bool:
        """Clear stored credentials."""
        try:
            keyring.delete_password(self.SERVICE_NAME, self.ACCESS_TOKEN_KEY)
            keyring.delete_password(self.SERVICE_NAME, self.REFRESH_TOKEN_KEY)
            keyring.delete_password(self.SERVICE_NAME, self.TOKEN_EXPIRY_KEY)
            return True
        except (keyring.errors.PasswordDeleteError, keyring.errors.KeyringError):
            # Token might not exist or keyring unavailable
            return False
    
    @handle_network_errors(offline_return=None)
    def list_bots(self, status: Optional[str] = None, use_cache: bool = True) -> List[Dict[str, Any]]:
        """List cloud bots with caching support."""
        # Try to get from API first
        try:
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
            bots = data.get("bots", [])

            # Cache the result
            if use_cache:
                self.cache.set_bots(bots)

            return bots
        except Exception:
            # If API fails and cache is enabled, try cache
            if use_cache:
                cached_bots = self.cache.get_bots()
                if cached_bots is not None:
                    return cached_bots
            return []
    
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
        except (httpx.RequestError, httpx.TimeoutException):
            # Network unavailable or timeout
            self._set_offline_mode(True)
            return False
    
    def require_online(self) -> bool:
        """Check if online, raise exception if not."""
        if not self.is_online():
            raise ConnectionError("API is not reachable. Please check your internet connection or use local commands.")
        return True

    def deploy_bot(self, bot_name: str, bot_config: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy a local bot to the cloud."""
        try:
            # First check if bot exists
            existing_bot = self.get_bot(bot_name)

            if existing_bot:
                # Update existing bot
                response = self.client.put(
                    f"{self.api_url}/v1/bots/{existing_bot['id']}",
                    json=bot_config,
                    headers=self._get_headers()
                )
            else:
                # Create new bot
                response = self.client.post(
                    f"{self.api_url}/v1/bots",
                    json={
                        "name": bot_name,
                        **bot_config
                    },
                    headers=self._get_headers()
                )

            response.raise_for_status()
            result = response.json()

            # Invalidate bot cache after deployment
            self.cache.invalidate("bots")

            return result
        except Exception as e:
            raise Exception(f"Failed to deploy bot: {e}")

    def pull_bot_config(self, bot_name: str) -> Optional[Dict[str, Any]]:
        """Pull bot configuration from cloud."""
        try:
            bot = self.get_bot(bot_name)
            if not bot:
                return None

            # Cache the config
            config = bot.get("config", {})
            self.cache.set_bot_config(bot_name, config)

            return config
        except Exception:
            # Try cache if API fails
            cached_config = self.cache.get_bot_config(bot_name)
            return cached_config

    def sync_bot_config(self, bot_name: str, local_config: Dict[str, Any]) -> Dict[str, Any]:
        """Sync bot configuration with cloud."""
        try:
            # Get cloud config
            cloud_bot = self.get_bot(bot_name)
            if not cloud_bot:
                # Bot doesn't exist in cloud, create it
                return self.deploy_bot(bot_name, {"config": local_config})

            # Get cloud config
            cloud_config = cloud_bot.get("config", {})

            # For now, we'll just update cloud with local
            # In future, we could implement more sophisticated merging
            response = self.client.patch(
                f"{self.api_url}/v1/bots/{cloud_bot['id']}/config",
                json=local_config,
                headers=self._get_headers()
            )
            response.raise_for_status()

            result = response.json()

            # Update cache
            self.cache.set_bot_config(bot_name, local_config)

            return result
        except Exception as e:
            raise Exception(f"Failed to sync bot config: {e}")

    def get_templates(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Get available bot templates."""
        try:
            response = self.client.get(
                f"{self.api_url}/v1/templates",
                headers=self._get_headers()
            )
            response.raise_for_status()

            templates = response.json().get("templates", [])

            # Cache the result
            if use_cache:
                self.cache.set_templates(templates)

            return templates
        except Exception:
            # Try cache if API fails
            if use_cache:
                cached_templates = self.cache.get_templates()
                if cached_templates is not None:
                    return cached_templates
            return []