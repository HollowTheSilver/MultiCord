"""
Secure token storage for Discord bot tokens.

Provides hybrid storage approach:
- Primary: System keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- Fallback: Encrypted file storage using Fernet (AES-128)

Automatically migrates plain-text tokens from .env files to secure storage.
"""

import os
import json
import keyring
from pathlib import Path
from typing import Optional, Dict
from cryptography.fernet import Fernet
from dotenv import dotenv_values


class TokenManager:
    """
    Manages secure storage of Discord bot tokens.

    Uses system keyring when available, falls back to encrypted file storage
    for headless environments (SSH, Docker, CI/CD).
    """

    SERVICE_NAME = "multicord-bot"

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize TokenManager with hybrid storage.

        Args:
            config_dir: MultiCord configuration directory (defaults to ~/.multicord)
        """
        self.config_dir = config_dir or Path.home() / ".multicord"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.key_file = self.config_dir / ".token_key"
        self.tokens_file = self.config_dir / "tokens.enc"

        # Detect keyring availability
        self.use_keyring = self._check_keyring_available()

        # Initialize encryption for fallback
        if not self.use_keyring:
            self._init_encryption()

    def _check_keyring_available(self) -> bool:
        """
        Check if system keyring is available and functional.

        Returns:
            True if keyring can be used, False otherwise
        """
        try:
            # Test keyring access with a dummy operation
            test_key = f"{self.SERVICE_NAME}_test"
            keyring.set_password(self.SERVICE_NAME, test_key, "test")
            keyring.delete_password(self.SERVICE_NAME, test_key)
            return True
        except Exception:
            # Keyring unavailable (headless server, no desktop session, etc.)
            return False

    def _init_encryption(self):
        """
        Initialize Fernet encryption for file-based token storage.

        Generates or loads encryption key from .token_key file.
        Sets restrictive file permissions on Unix systems.
        """
        if self.key_file.exists():
            # Load existing key
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)

            # Set restrictive permissions on Unix systems
            if os.name != 'nt':  # Not Windows
                os.chmod(self.key_file, 0o600)

        self.cipher = Fernet(key)

    def get_storage_method(self) -> str:
        """
        Get description of current storage method.

        Returns:
            Human-readable description of storage method
        """
        if self.use_keyring:
            if os.name == 'nt':
                return "Windows Credential Manager"
            elif os.name == 'posix':
                import platform
                if platform.system() == 'Darwin':
                    return "macOS Keychain"
                else:
                    return "Linux Secret Service"
            else:
                return "System Keyring"
        else:
            return "Encrypted file"

    def store_token(self, bot_name: str, token: str) -> bool:
        """
        Store Discord bot token securely.

        Args:
            bot_name: Name of the bot
            token: Discord bot token

        Returns:
            True if token stored successfully

        Raises:
            ValueError: If token format is invalid
        """
        # Validate token format
        if not self._validate_discord_token(token):
            raise ValueError(
                "Invalid Discord token format. "
                "Token should be ~72 characters and contain periods."
            )

        if self.use_keyring:
            # Store in system keyring
            keyring.set_password(self.SERVICE_NAME, bot_name, token)
        else:
            # Store in encrypted file
            self._store_token_encrypted(bot_name, token)

        return True

    def get_token(self, bot_name: str) -> Optional[str]:
        """
        Retrieve Discord bot token from secure storage.

        Args:
            bot_name: Name of the bot

        Returns:
            Discord token if found, None otherwise
        """
        if self.use_keyring:
            # Retrieve from system keyring
            try:
                return keyring.get_password(self.SERVICE_NAME, bot_name)
            except Exception:
                return None
        else:
            # Retrieve from encrypted file
            return self._get_token_encrypted(bot_name)

    def delete_token(self, bot_name: str) -> bool:
        """
        Delete Discord bot token from secure storage.

        Args:
            bot_name: Name of the bot

        Returns:
            True if token deleted successfully
        """
        if self.use_keyring:
            try:
                keyring.delete_password(self.SERVICE_NAME, bot_name)
                return True
            except keyring.errors.PasswordDeleteError:
                return False
        else:
            return self._delete_token_encrypted(bot_name)

    def list_bots_with_tokens(self) -> list[str]:
        """
        List all bots that have stored tokens.

        Returns:
            List of bot names with stored tokens
        """
        if self.use_keyring:
            # Keyring doesn't support listing, return empty
            # User would need to check individual bots
            return []
        else:
            # List from encrypted file
            tokens = self._load_encrypted_tokens()
            return list(tokens.keys())

    def migrate_from_env(self, bot_path: Path, bot_name: str) -> bool:
        """
        Migrate plain-text token from .env file to secure storage.

        Args:
            bot_path: Path to bot directory
            bot_name: Name of the bot

        Returns:
            True if migration successful, False if no token to migrate
        """
        env_file = bot_path / ".env"

        if not env_file.exists():
            return False

        # Read and parse .env file
        try:
            env_vars = dotenv_values(env_file)
            token = env_vars.get('DISCORD_TOKEN')

            # Check if valid token exists
            if not token or token == 'your_token_here' or not self._validate_discord_token(token):
                return False

            # Store token securely
            self.store_token(bot_name, token)

            # Create backup of original .env
            backup_file = bot_path / ".env.backup"
            if not backup_file.exists():
                env_file.rename(backup_file)

            # Create new .env without DISCORD_TOKEN
            self._create_env_without_token(bot_path, env_vars)

            return True

        except Exception:
            return False

    def _validate_discord_token(self, token: str) -> bool:
        """
        Validate Discord token format.

        Discord bot tokens have specific format:
        - Approximately 72 characters (59-84 typical range)
        - Contains 2-3 periods separating base64-encoded segments
        - Format: user_id.timestamp.hmac

        Args:
            token: Token to validate

        Returns:
            True if token format appears valid
        """
        if not token or not isinstance(token, str):
            return False

        # Check minimum length
        if len(token) < 50:
            return False

        # Check for placeholder value
        if token == 'your_token_here':
            return False

        # Discord tokens contain periods
        if '.' not in token:
            return False

        # Check for reasonable segment count (2-3 periods = 3-4 segments)
        segments = token.split('.')
        if len(segments) < 3 or len(segments) > 4:
            return False

        return True

    def _store_token_encrypted(self, bot_name: str, token: str):
        """Store token in encrypted file."""
        tokens = self._load_encrypted_tokens()
        tokens[bot_name] = token
        self._save_encrypted_tokens(tokens)

    def _get_token_encrypted(self, bot_name: str) -> Optional[str]:
        """Retrieve token from encrypted file."""
        tokens = self._load_encrypted_tokens()
        return tokens.get(bot_name)

    def _delete_token_encrypted(self, bot_name: str) -> bool:
        """Delete token from encrypted file."""
        tokens = self._load_encrypted_tokens()
        if bot_name in tokens:
            del tokens[bot_name]
            self._save_encrypted_tokens(tokens)
            return True
        return False

    def _load_encrypted_tokens(self) -> Dict[str, str]:
        """Load all tokens from encrypted file."""
        if not self.tokens_file.exists():
            return {}

        try:
            with open(self.tokens_file, 'rb') as f:
                encrypted_data = f.read()

            if not encrypted_data:
                return {}

            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode('utf-8'))
        except Exception:
            # Corrupted file or decryption failure
            return {}

    def _save_encrypted_tokens(self, tokens: Dict[str, str]):
        """Save all tokens to encrypted file."""
        json_data = json.dumps(tokens, indent=2)
        encrypted_data = self.cipher.encrypt(json_data.encode('utf-8'))

        with open(self.tokens_file, 'wb') as f:
            f.write(encrypted_data)

        # Set restrictive permissions on Unix systems
        if os.name != 'nt':
            os.chmod(self.tokens_file, 0o600)

    def _create_env_without_token(self, bot_path: Path, original_env: Dict[str, str]):
        """
        Create new .env file without DISCORD_TOKEN.

        Preserves other environment variables from original .env file.
        """
        env_file = bot_path / ".env"

        # Filter out DISCORD_TOKEN
        filtered_vars = {k: v for k, v in original_env.items() if k != 'DISCORD_TOKEN'}

        # Write new .env file
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write("# MultiCord Bot Environment Variables\n")
            f.write("# Discord token is stored securely via 'multicord bot set-token'\n\n")

            for key, value in filtered_vars.items():
                f.write(f"{key}={value}\n")
