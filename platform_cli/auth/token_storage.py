"""
Secure Token Storage for CLI
============================

Cross-platform secure storage for OAuth2 tokens.
Uses system keyring when available, falls back to encrypted file storage.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict
import os

try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False
    keyring = None

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

from platform_core.entities.auth import TokenResponse


logger = logging.getLogger(__name__)


class SecureTokenStorage:
    """Cross-platform secure token storage."""
    
    SERVICE_NAME = "multicord-cli"
    TOKEN_KEY = "auth_tokens"
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize token storage.
        
        Args:
            config_dir: Directory for fallback storage (defaults to ~/.multicord)
        """
        self.config_dir = config_dir or Path.home() / ".multicord"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Fallback encrypted file path
        self.token_file = self.config_dir / "tokens.enc"
        self.key_file = self.config_dir / ".key"
        
        # Initialize encryption for fallback
        self._init_encryption()
        
        # Check keyring availability
        self.use_keyring = self._check_keyring_available()
        if self.use_keyring:
            logger.info("Using system keyring for token storage")
        else:
            logger.info("Using encrypted file for token storage")
    
    def _check_keyring_available(self) -> bool:
        """Check if system keyring is available and working."""
        if not HAS_KEYRING:
            return False
        
        try:
            # Try to access keyring
            keyring.get_password(self.SERVICE_NAME, "test")
            return True
        except Exception as e:
            logger.debug(f"Keyring not available: {e}")
            return False
    
    def _init_encryption(self):
        """Initialize encryption for fallback storage."""
        if self.key_file.exists():
            # Load existing key
            with open(self.key_file, 'rb') as f:
                self.encryption_key = f.read()
        else:
            # Generate new key
            self.encryption_key = Fernet.generate_key()
            # Save key (with restricted permissions)
            with open(self.key_file, 'wb') as f:
                f.write(self.encryption_key)
            # Set restrictive permissions on key file
            if os.name != 'nt':  # Unix-like systems
                os.chmod(self.key_file, 0o600)
        
        self.cipher = Fernet(self.encryption_key)
    
    def store_tokens(self, token_response: TokenResponse) -> bool:
        """
        Store tokens securely.
        
        Args:
            token_response: Token response to store
            
        Returns:
            True if stored successfully
        """
        # Prepare token data
        token_data = {
            "access_token": token_response.access_token,
            "refresh_token": token_response.refresh_token,
            "token_type": token_response.token_type,
            "expires_in": token_response.expires_in,
            "scope": token_response.scope,
            "stored_at": datetime.now(timezone.utc).isoformat()
        }
        
        token_json = json.dumps(token_data)
        
        try:
            if self.use_keyring:
                # Store in system keyring
                keyring.set_password(
                    self.SERVICE_NAME,
                    self.TOKEN_KEY,
                    token_json
                )
            else:
                # Store in encrypted file
                encrypted_data = self.cipher.encrypt(token_json.encode())
                with open(self.token_file, 'wb') as f:
                    f.write(encrypted_data)
                # Set restrictive permissions
                if os.name != 'nt':
                    os.chmod(self.token_file, 0o600)
            
            logger.info("Tokens stored successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store tokens: {e}")
            return False
    
    def get_tokens(self) -> Optional[Dict]:
        """
        Retrieve stored tokens.
        
        Returns:
            Token data if available, None otherwise
        """
        try:
            if self.use_keyring:
                # Get from system keyring
                token_json = keyring.get_password(
                    self.SERVICE_NAME,
                    self.TOKEN_KEY
                )
                if token_json:
                    return json.loads(token_json)
            else:
                # Get from encrypted file
                if self.token_file.exists():
                    with open(self.token_file, 'rb') as f:
                        encrypted_data = f.read()
                    decrypted_data = self.cipher.decrypt(encrypted_data)
                    return json.loads(decrypted_data.decode())
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve tokens: {e}")
            return None
    
    def get_access_token(self) -> Optional[str]:
        """Get stored access token."""
        tokens = self.get_tokens()
        return tokens.get("access_token") if tokens else None
    
    def get_refresh_token(self) -> Optional[str]:
        """Get stored refresh token."""
        tokens = self.get_tokens()
        return tokens.get("refresh_token") if tokens else None
    
    def is_token_expired(self) -> bool:
        """
        Check if stored access token is expired.
        
        Returns:
            True if expired or no token stored
        """
        tokens = self.get_tokens()
        if not tokens:
            return True
        
        # Check if we have stored_at and expires_in
        stored_at = tokens.get("stored_at")
        expires_in = tokens.get("expires_in")
        
        if not stored_at or not expires_in:
            # Can't determine, assume expired
            return True
        
        try:
            # Parse stored time
            stored_time = datetime.fromisoformat(stored_at)
            current_time = datetime.now(timezone.utc)
            
            # Calculate expiration
            elapsed = (current_time - stored_time).total_seconds()
            
            # Add some buffer (5 minutes) to avoid edge cases
            return elapsed >= (expires_in - 300)
            
        except Exception as e:
            logger.error(f"Error checking token expiration: {e}")
            return True
    
    def clear_tokens(self) -> bool:
        """
        Clear stored tokens (logout).
        
        Returns:
            True if cleared successfully
        """
        try:
            if self.use_keyring:
                # Remove from keyring
                try:
                    keyring.delete_password(
                        self.SERVICE_NAME,
                        self.TOKEN_KEY
                    )
                except keyring.errors.PasswordDeleteError:
                    # Already deleted or doesn't exist
                    pass
            else:
                # Remove encrypted file
                if self.token_file.exists():
                    self.token_file.unlink()
            
            logger.info("Tokens cleared successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear tokens: {e}")
            return False
    
    def has_tokens(self) -> bool:
        """Check if tokens are stored."""
        return self.get_tokens() is not None