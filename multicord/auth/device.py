"""
Device Flow Authentication for MultiCord CLI.

For browserless environments (SSH, Docker, EC2) where Discord browser flow isn't available.
Uses OAuth2 Device Authorization Grant (RFC 8628) similar to GitHub CLI.
"""

import time
import json
import asyncio
import webbrowser
from typing import Optional, Dict, Any
import httpx
import keyring


class DeviceFlowClient:
    """OAuth2 device flow client for browserless authentication."""

    SERVICE_NAME = "multicord"
    ACCESS_TOKEN_KEY = "access_token"
    REFRESH_TOKEN_KEY = "refresh_token"
    USER_INFO_KEY = "discord_user"

    def __init__(self, api_url: Optional[str] = None):
        """Initialize device flow client.

        Args:
            api_url: Base URL for MultiCord API
        """
        from multicord.constants import DEFAULT_API_URL
        self.api_url = api_url or DEFAULT_API_URL
        self.device_endpoint = f"{api_url}/v1/auth/device"
        self.token_endpoint = f"{api_url}/v1/auth/device/token"

    def authenticate(self) -> bool:
        """
        Complete device flow authentication.

        Returns:
            True if authentication successful
        """
        try:
            # Request device code
            device_response = self._request_device_code()
            if not device_response:
                return False

            # Display authentication prompt
            self._display_auth_prompt(device_response)

            # Poll for token
            token_response = self._poll_for_token(
                device_response["device_code"],
                device_response["interval"],
                device_response["expires_in"]
            )

            if token_response:
                print("\n[OK] Authentication successful!")
                self._store_tokens(token_response)
                return True
            else:
                print("\n[ERROR] Authentication failed or timed out.")
                return False

        except Exception as e:
            print(f"\n[ERROR] Authentication error: {e}")
            return False

    def _request_device_code(self) -> Optional[Dict]:
        """Request device code from server."""
        try:
            with httpx.Client() as client:
                response = client.post(
                    self.device_endpoint,
                    json={"client_id": "multicord-cli"}
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            print(f"[ERROR] Failed to request device code: {e}")
            return None

    def _display_auth_prompt(self, device_response: Dict) -> None:
        """Display authentication prompt to user."""
        print("\n" + "="*60)
        print("[AUTH] MultiCord Device Authentication")
        print("="*60)
        print(f"\n1. Visit this URL on any device with a browser:")
        print(f"   {device_response['verification_uri']}")
        print(f"\n2. Enter this code:")
        print(f"   {device_response['user_code']}")
        print(f"\n3. Login with Discord to authorize your device")
        print("\n" + "="*60)

        # Try to open browser if available (won't work in SSH)
        try:
            if device_response.get('verification_uri_complete'):
                webbrowser.open(device_response['verification_uri_complete'])
                print("\n[OK] Attempted to open browser (may not work in SSH)")
        except:
            # Browser not available, that's fine
            pass

    def _poll_for_token(self, device_code: str, interval: int, expires_in: int) -> Optional[Dict]:
        """Poll token endpoint until authorization or timeout."""
        timeout = time.time() + expires_in
        poll_interval = interval

        print("\nWaiting for authorization", end="", flush=True)

        with httpx.Client() as client:
            while time.time() < timeout:
                try:
                    # Poll token endpoint
                    response = client.post(
                        self.token_endpoint,
                        data={
                            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                            "device_code": device_code,
                            "client_id": "multicord-cli"
                        }
                    )

                    if response.status_code == 200:
                        # Success!
                        data = response.json()
                        return data

                    # Check error response
                    if response.status_code == 400:
                        try:
                            data = response.json()
                            # Handle nested error format from FastAPI
                            if "detail" in data and isinstance(data["detail"], dict):
                                error = data["detail"].get("error")
                            else:
                                error = data.get("error")

                            if error == "authorization_pending":
                                # Still waiting for user
                                print(".", end="", flush=True)
                                time.sleep(poll_interval)

                            elif error == "slow_down":
                                # Rate limited, increase interval
                                poll_interval += 5
                                print("!", end="", flush=True)
                                time.sleep(poll_interval)

                            elif error == "access_denied":
                                print("\n[ERROR] Authorization denied by user")
                                return None

                            elif error == "expired_token":
                                print("\n[ERROR] Device code expired")
                                return None
                            else:
                                print(f"\n[ERROR] Unknown error: {error}")
                                return None
                        except:
                            # Failed to parse error response
                            print("x", end="", flush=True)
                            time.sleep(poll_interval)

                except httpx.HTTPError as e:
                    print("!", end="", flush=True)
                    time.sleep(poll_interval)

        print("\n[ERROR] Authentication timed out")
        return None

    def _store_tokens(self, token_data: Dict[str, Any]) -> None:
        """Store tokens securely in keyring.

        Args:
            token_data: Dictionary containing tokens and user info
        """
        keyring.set_password(self.SERVICE_NAME, self.ACCESS_TOKEN_KEY, token_data["access_token"])
        keyring.set_password(self.SERVICE_NAME, self.REFRESH_TOKEN_KEY, token_data["refresh_token"])

        # Skip profile fetch - the /v1/auth/profile endpoint needs JWT validation
        # The token response should already include basic user info
        # if "user" not in token_data:
        #     # Make API call to get user profile
        #     user_info = self._get_user_profile(token_data["access_token"])
        #     if user_info:
        #         token_data["user"] = user_info

        # Store user info
        if "user" in token_data:
            user_json = json.dumps(token_data["user"])
            keyring.set_password(self.SERVICE_NAME, self.USER_INFO_KEY, user_json)

            # Display user info
            user = token_data["user"]
            if "discord_username" in user:
                print(f"\n[USER] Logged in as: {user['discord_username']}")
            elif "username" in user:
                print(f"\n[USER] Logged in as: {user['username']}")

    def _get_user_profile(self, access_token: str) -> Optional[Dict]:
        """Fetch user profile using access token."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.api_url}/v1/auth/profile",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if response.status_code == 200:
                    return response.json()
        except:
            pass
        return None

    def get_tokens(self) -> Optional[Dict[str, str]]:
        """Retrieve stored tokens from keyring.

        Returns:
            Dictionary with access and refresh tokens, or None
        """
        access_token = keyring.get_password(self.SERVICE_NAME, self.ACCESS_TOKEN_KEY)
        refresh_token = keyring.get_password(self.SERVICE_NAME, self.REFRESH_TOKEN_KEY)

        if access_token and refresh_token:
            return {
                "access_token": access_token,
                "refresh_token": refresh_token
            }
        return None

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Retrieve stored Discord user info.

        Returns:
            User info dictionary or None
        """
        user_json = keyring.get_password(self.SERVICE_NAME, self.USER_INFO_KEY)
        if user_json:
            return json.loads(user_json)
        return None

    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.get_tokens() is not None

    def logout(self) -> None:
        """Clear all stored authentication data."""
        try:
            keyring.delete_password(self.SERVICE_NAME, self.ACCESS_TOKEN_KEY)
        except:
            pass

        try:
            keyring.delete_password(self.SERVICE_NAME, self.REFRESH_TOKEN_KEY)
        except:
            pass

        try:
            keyring.delete_password(self.SERVICE_NAME, self.USER_INFO_KEY)
        except:
            pass

        print("[OK] Successfully logged out")