"""
Discord OAuth2 authentication for MultiCord CLI.
Browser-based flow - THE ONLY authentication method.
"""

import webbrowser
import asyncio
import httpx
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json
import time
from typing import Optional, Dict, Any
from urllib.parse import parse_qs
import keyring


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for Discord OAuth2 callback."""

    def do_GET(self):
        """Handle GET request with authorization code."""
        # Parse query parameters
        query = parse_qs(self.path.split('?')[1] if '?' in self.path else '')

        if 'code' in query:
            # Store the code for the main thread to retrieve
            self.server.auth_code = query['code'][0]
            self.server.state = query.get('state', [None])[0]

            # Send success response
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <head><title>Authentication Successful</title></head>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #5865F2;">Authentication Successful!</h1>
                    <p>You can now close this window and return to the CLI.</p>
                    <script>setTimeout(function() { window.close(); }, 2000);</script>
                </body>
                </html>
            """)
        else:
            # Handle error
            error = query.get('error', ['Unknown error'])[0]
            self.server.auth_error = error

            self.send_response(400)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(f"""
                <html>
                <head><title>Authentication Failed</title></head>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #ff4757;">Authentication Failed</h1>
                    <p>Error: {error}</p>
                    <p>Please return to the CLI and try again.</p>
                </body>
                </html>
            """.encode())

    def do_POST(self):
        """Handle POST request from success page with tokens."""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(post_data)
            self.server.tokens = data

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode())
        except Exception as e:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())

    def log_message(self, format, *args):
        """Suppress request logging."""
        pass


class DiscordAuth:
    """Discord OAuth2 authentication - THE ONLY way to authenticate."""

    SERVICE_NAME = "multicord"
    ACCESS_TOKEN_KEY = "access_token"
    REFRESH_TOKEN_KEY = "refresh_token"
    USER_INFO_KEY = "discord_user"

    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.callback_port = 8899  # Local port for callback server

    def authenticate(self) -> bool:
        """
        Perform Discord OAuth2 authentication.
        Opens browser, captures callback, exchanges code for tokens.

        Returns:
            True if authentication successful
        """
        try:
            # Start local callback server
            server = HTTPServer(('localhost', self.callback_port), CallbackHandler)
            server.auth_code = None
            server.auth_error = None
            server.tokens = None
            server.state = None

            # Start server in background thread
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.daemon = True
            server_thread.start()

            # Open Discord auth in browser
            auth_url = f"{self.api_url}/v1/auth/discord?redirect_port={self.callback_port}"
            print("\n[AUTH] Opening Discord in your browser for authentication...")
            print(f"   If the browser doesn't open, visit: {auth_url}\n")
            webbrowser.open(auth_url)

            # Wait for callback (timeout after 5 minutes)
            start_time = time.time()
            timeout = 300  # 5 minutes

            while time.time() - start_time < timeout:
                if server.auth_code:
                    # Exchange code for tokens
                    print("[OK] Authorization received, exchanging for tokens...")
                    success = self._exchange_code(server.auth_code, server.state)

                    # Shutdown server
                    server.shutdown()
                    return success

                elif server.tokens:
                    # Tokens received directly from success page
                    print("[OK] Authentication successful!")
                    self._store_tokens(server.tokens)

                    # Shutdown server
                    server.shutdown()
                    return True

                elif server.auth_error:
                    print(f"[ERROR] Authentication failed: {server.auth_error}")

                    # Shutdown server
                    server.shutdown()
                    return False

                time.sleep(0.5)

            # Timeout
            print("[ERROR] Authentication timed out")
            server.shutdown()
            return False

        except Exception as e:
            print(f"[ERROR] Authentication error: {e}")
            return False

    def _exchange_code(self, code: str, state: Optional[str]) -> bool:
        """
        Exchange authorization code for tokens with our API.

        Args:
            code: Discord authorization code
            state: CSRF state parameter

        Returns:
            True if exchange successful
        """
        try:
            with httpx.Client() as client:
                # Send code to our API for exchange
                response = client.post(
                    f"{self.api_url}/v1/auth/discord/exchange",
                    json={
                        "code": code,
                        "state": state,
                        "redirect_uri": f"http://localhost:{self.callback_port}/callback"
                    }
                )

                if response.status_code == 200:
                    tokens = response.json()
                    self._store_tokens(tokens)
                    return True
                else:
                    print(f"[ERROR] Token exchange failed: {response.text}")
                    return False

        except Exception as e:
            print(f"[ERROR] Failed to exchange code: {e}")
            return False

    def _store_tokens(self, token_data: Dict[str, Any]) -> None:
        """
        Store tokens securely in keyring.

        Args:
            token_data: Dictionary containing tokens and user info
        """
        keyring.set_password(self.SERVICE_NAME, self.ACCESS_TOKEN_KEY, token_data["access_token"])
        keyring.set_password(self.SERVICE_NAME, self.REFRESH_TOKEN_KEY, token_data["refresh_token"])

        # Store user info
        if "user" in token_data:
            user_json = json.dumps(token_data["user"])
            keyring.set_password(self.SERVICE_NAME, self.USER_INFO_KEY, user_json)

            # Display user info
            user = token_data["user"]
            print(f"\n[USER] Logged in as: {user['discord_username']} (ID: {user['discord_id']})")

    def get_tokens(self) -> Optional[Dict[str, str]]:
        """
        Retrieve stored tokens from keyring.

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
        """
        Retrieve stored Discord user info.

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

        print("Successfully logged out")