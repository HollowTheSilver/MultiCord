"""
Bot Configuration Module
========================

Centralized configuration management for the Discord bot with environment variable
support, validation, and type safety.
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional, Union
from dataclasses import dataclass, field


@dataclass
class BotConfig:
    """
    Comprehensive bot configuration with environment variable support and validation.
    """

    # // ========================================( Bot Settings )======================================== // #

    # Bot identification
    BOT_NAME: str = field(default_factory=lambda: os.getenv("BOT_NAME", "ProfessionalBot"))
    BOT_VERSION: str = field(default_factory=lambda: os.getenv("BOT_VERSION", "1.0.0"))
    BOT_DESCRIPTION: str = field(default_factory=lambda: os.getenv("BOT_DESCRIPTION", "A professional Discord bot"))

    # Command settings
    COMMAND_PREFIX: str = field(default_factory=lambda: os.getenv("COMMAND_PREFIX", "!"))
    CASE_INSENSITIVE_COMMANDS: bool = field(default_factory=lambda: os.getenv("CASE_INSENSITIVE_COMMANDS", "true").lower() == "true")

    # // ========================================( Discord Intents )======================================== // #

    ENABLE_MEMBER_INTENTS: bool = field(default_factory=lambda: os.getenv("ENABLE_MEMBER_INTENTS", "true").lower() == "true")
    ENABLE_MESSAGE_CONTENT_INTENT: bool = field(default_factory=lambda: os.getenv("ENABLE_MESSAGE_CONTENT_INTENT", "true").lower() == "true")
    ENABLE_PRESENCE_INTENT: bool = field(default_factory=lambda: os.getenv("ENABLE_PRESENCE_INTENT", "false").lower() == "true")

    # // ========================================( Logging Configuration )======================================== // #

    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    LOG_DIR: Optional[str] = field(default_factory=lambda: os.getenv("LOG_DIR", "logs"))
    LOG_ROTATION: str = field(default_factory=lambda: os.getenv("LOG_ROTATION", "10 MB"))
    LOG_RETENTION: str = field(default_factory=lambda: os.getenv("LOG_RETENTION", "1 week"))
    LOG_COMPRESSION: str = field(default_factory=lambda: os.getenv("LOG_COMPRESSION", "zip"))

    # // ========================================( Status & Activity )======================================== // #

    ENABLE_STATUS_CYCLING: bool = field(default_factory=lambda: os.getenv("ENABLE_STATUS_CYCLING", "true").lower() == "true")
    STATUS_CYCLE_INTERVAL: int = field(default_factory=lambda: int(os.getenv("STATUS_CYCLE_INTERVAL", "300")))  # 5 minutes

    # Status messages: List of (message, type) tuples
    # Types: playing, watching, listening, streaming, competing, custom
    STATUS_MESSAGES: List[Tuple[str, str]] = field(default_factory=list)

    # // ========================================( Background Tasks )======================================== // #

    ENABLE_HEALTH_CHECKS: bool = field(default_factory=lambda: os.getenv("ENABLE_HEALTH_CHECKS", "true").lower() == "true")
    HEALTH_CHECK_INTERVAL: int = field(default_factory=lambda: int(os.getenv("HEALTH_CHECK_INTERVAL", "300")))  # 5 minutes

    # // ========================================( Database Configuration )======================================== // #

    DATABASE_URL: Optional[str] = field(default_factory=lambda: os.getenv("DATABASE_URL"))
    DATABASE_POOL_SIZE: int = field(default_factory=lambda: int(os.getenv("DATABASE_POOL_SIZE", "10")))
    DATABASE_TIMEOUT: int = field(default_factory=lambda: int(os.getenv("DATABASE_TIMEOUT", "30")))

    # // ========================================( Cache Configuration )======================================== // #

    REDIS_URL: Optional[str] = field(default_factory=lambda: os.getenv("REDIS_URL"))
    CACHE_TTL: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL", "3600")))  # 1 hour

    # // ========================================( API Configuration )======================================== // #

    API_RATE_LIMIT: int = field(default_factory=lambda: int(os.getenv("API_RATE_LIMIT", "100")))
    API_TIMEOUT: int = field(default_factory=lambda: int(os.getenv("API_TIMEOUT", "30")))

    # // ========================================( Security )======================================== // #

    OWNER_IDS: List[int] = field(default_factory=lambda: [
        int(id_str) for id_str in os.getenv("OWNER_IDS", "").split(",") if id_str.strip()
    ])

    ALLOWED_GUILDS: List[int] = field(default_factory=lambda: [
        int(id_str) for id_str in os.getenv("ALLOWED_GUILDS", "").split(",") if id_str.strip()
    ])

    # // ========================================( Feature Flags )======================================== // #

    ENABLE_SLASH_COMMANDS: bool = field(default_factory=lambda: os.getenv("ENABLE_SLASH_COMMANDS", "true").lower() == "true")
    ENABLE_MESSAGE_COMMANDS: bool = field(default_factory=lambda: os.getenv("ENABLE_MESSAGE_COMMANDS", "true").lower() == "true")
    ENABLE_AUTO_SYNC: bool = field(default_factory=lambda: os.getenv("ENABLE_AUTO_SYNC", "false").lower() == "true")

    # // ========================================( Performance )======================================== // #

    MAX_WORKERS: int = field(default_factory=lambda: int(os.getenv("MAX_WORKERS", "4")))
    MAX_QUEUE_SIZE: int = field(default_factory=lambda: int(os.getenv("MAX_QUEUE_SIZE", "1000")))
    CHUNK_SIZE: int = field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "100")))

    # // ========================================( Development )======================================== // #

    DEBUG_MODE: bool = field(default_factory=lambda: os.getenv("DEBUG_MODE", "false").lower() == "true")
    DEV_GUILD_ID: Optional[int] = field(default_factory=lambda: int(os.getenv("DEV_GUILD_ID")) if os.getenv("DEV_GUILD_ID") else None)

    def __post_init__(self) -> None:
        """Post-initialization validation and setup."""
        self._setup_status_messages()
        self._validate_config()
        self._setup_directories()

    def _setup_status_messages(self) -> None:
        """Setup status messages from environment variable or defaults."""
        env_statuses = os.getenv("STATUS_MESSAGES", "")

        if env_statuses:
            try:
                messages = []
                for status_pair in env_statuses.split(","):
                    if ":" in status_pair:
                        message, status_type = status_pair.split(":", 1)
                        messages.append((message.strip(), status_type.strip()))
                    else:
                        # Default to custom type if no type specified
                        messages.append((status_pair.strip(), "custom"))
                self.STATUS_MESSAGES = messages
            except Exception:
                # Fall back to defaults if parsing fails
                self._set_default_status_messages()
        else:
            # Use defaults if no environment variable set
            self._set_default_status_messages()

    def _set_default_status_messages(self) -> None:
        """Set default status messages."""
        self.STATUS_MESSAGES = [
            ("with Discord.py", "playing"),
            ("for new members", "watching"),
            ("to commands", "listening"),
            ("bot development", "competing"),
            ("🤖 Online and ready!", "custom")
        ]

    def _validate_config(self) -> None:
        """Validate configuration values."""
        # Validate log level
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.LOG_LEVEL.upper() not in valid_levels:
            raise ValueError(f"Invalid LOG_LEVEL. Must be one of: {', '.join(valid_levels)}")

        # Validate intervals
        if self.STATUS_CYCLE_INTERVAL < 30:
            raise ValueError("STATUS_CYCLE_INTERVAL must be at least 30 seconds")

        if self.HEALTH_CHECK_INTERVAL < 60:
            raise ValueError("HEALTH_CHECK_INTERVAL must be at least 60 seconds")

        # Validate performance settings
        if self.MAX_WORKERS < 1:
            raise ValueError("MAX_WORKERS must be at least 1")

        if self.MAX_QUEUE_SIZE < 1:
            raise ValueError("MAX_QUEUE_SIZE must be at least 1")

    def _setup_directories(self) -> None:
        """Create necessary directories."""
        if self.LOG_DIR:
            log_path = Path(self.LOG_DIR)
            log_path.mkdir(parents=True, exist_ok=True)

    def is_owner(self, user_id: int) -> bool:
        """Check if a user ID is in the owner list."""
        return user_id in self.OWNER_IDS

    def is_allowed_guild(self, guild_id: int) -> bool:
        """Check if a guild ID is in the allowed guilds list (if any)."""
        if not self.ALLOWED_GUILDS:
            return True  # No restrictions if list is empty
        return guild_id in self.ALLOWED_GUILDS

    def to_dict(self) -> dict:
        """Convert configuration to dictionary (excluding sensitive data)."""
        config_dict = {}
        for key, value in self.__dict__.items():
            # Exclude sensitive information
            if any(sensitive in key.lower() for sensitive in ["token", "key", "secret", "password"]):
                config_dict[key] = "[REDACTED]"
            else:
                config_dict[key] = value
        return config_dict

    def __repr__(self) -> str:
        """String representation of the configuration."""
        return f"BotConfig(name={self.BOT_NAME}, version={self.BOT_VERSION}, prefix={self.COMMAND_PREFIX})"
