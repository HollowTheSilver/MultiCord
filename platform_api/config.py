"""
API Configuration Management
============================

Environment-based configuration for the MultiCord API.
"""

from typing import List, Optional
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """API configuration settings."""
    
    # Application
    APP_NAME: str = "MultiCord Platform API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # API Settings
    API_PREFIX: str = "/api/v1"
    DOCS_URL: str = "/api/docs"
    REDOC_URL: str = "/api/redoc"
    
    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "multicord_platform"
    DB_USER: str = "multicord_user"
    DB_PASSWORD: str = "multicord_secure_pass"
    DB_SSL_MODE: str = "require"
    
    # Security
    SECRET_KEY: str = "change-this-in-production"
    JWT_ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "https://multicord.io"]
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    KEYS_DIR: Path = BASE_DIR / "keys"
    LOGS_DIR: Path = BASE_DIR / "logs"
    
    # OAuth2
    OAUTH2_CLIENT_ID: str = "multicord-cli"
    OAUTH2_BASE_URL: str = "https://multicord.io"
    DEVICE_CODE_EXPIRE_MINUTES: int = 15
    DEVICE_POLL_INTERVAL: int = 5
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # External Services
    REDIS_URL: Optional[str] = None
    SENTRY_DSN: Optional[str] = None
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    def get_jwt_private_key_path(self) -> Path:
        """Get path to JWT private key."""
        return self.KEYS_DIR / "jwt_private.pem"
    
    def get_jwt_public_key_path(self) -> Path:
        """Get path to JWT public key."""
        return self.KEYS_DIR / "jwt_public.pem"


# Singleton instance
settings = Settings()