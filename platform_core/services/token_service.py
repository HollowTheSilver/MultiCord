"""
JWT Token Management Service
============================

Handles JWT token creation, validation, and rotation with RS256 signing.
Implements refresh token rotation with breach detection.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from platform_core.entities.auth import JWTClaims, StoredToken, TokenResponse


logger = logging.getLogger(__name__)


class TokenService:
    """JWT token management with RS256 signing."""
    
    # Token configuration
    ACCESS_TOKEN_EXPIRE_HOURS = 1
    REFRESH_TOKEN_EXPIRE_DAYS = 30
    ALGORITHM = "RS256"
    ISSUER = "https://multicord.io"
    AUDIENCE = ["multicord-api"]
    
    def __init__(self, 
                 private_key_path: Optional[Path] = None,
                 public_key_path: Optional[Path] = None):
        """
        Initialize token service with RSA keys.
        
        Args:
            private_key_path: Path to RSA private key (PEM format)
            public_key_path: Path to RSA public key (PEM format)
        """
        self.private_key = None
        self.public_key = None
        
        if private_key_path and private_key_path.exists():
            self._load_keys(private_key_path, public_key_path)
        else:
            # Generate keys if not provided (development only)
            logger.warning("Generating RSA keys - use proper keys in production")
            self._generate_keys()
        
        # In-memory token storage (replace with database in production)
        self._stored_tokens: Dict[str, StoredToken] = {}
        self._token_families: Dict[str, set] = {}  # family_id -> set of JTIs
    
    def _load_keys(self, private_key_path: Path, public_key_path: Optional[Path]):
        """Load RSA keys from files."""
        with open(private_key_path, 'rb') as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
        
        if public_key_path and public_key_path.exists():
            with open(public_key_path, 'rb') as f:
                self.public_key = serialization.load_pem_public_key(
                    f.read(),
                    backend=default_backend()
                )
        else:
            # Extract public key from private key
            self.public_key = self.private_key.public_key()
    
    def _generate_keys(self):
        """Generate RSA key pair for development."""
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
    
    def create_access_token(self, 
                          user_id: str, 
                          scopes: list,
                          client_id: Optional[str] = None) -> str:
        """
        Create access token with short expiration.
        
        Args:
            user_id: User identifier
            scopes: List of permission scopes
            client_id: Optional client identifier
            
        Returns:
            Encoded JWT access token
        """
        now = datetime.now(timezone.utc)
        jti = str(uuid4())
        exp = now + timedelta(hours=self.ACCESS_TOKEN_EXPIRE_HOURS)
        
        claims = {
            "iss": self.ISSUER,
            "sub": user_id,
            "aud": self.AUDIENCE,
            "exp": exp,
            "iat": now,
            "jti": jti,
            "scopes": scopes,
            "token_type": "access"
        }
        
        if client_id:
            claims["client_id"] = client_id
        
        # Store token metadata
        stored = StoredToken(
            id=uuid4(),
            jti=jti,
            token_type="access",
            user_id=user_id,
            expires_at=exp,
            issued_at=now
        )
        self._stored_tokens[jti] = stored
        
        # Encode with private key
        token = jwt.encode(claims, self.private_key, algorithm=self.ALGORITHM)
        return token
    
    def create_refresh_token(self, 
                           user_id: str,
                           family_id: Optional[str] = None) -> str:
        """
        Create refresh token with rotation support.
        
        Args:
            user_id: User identifier
            family_id: Token family for rotation tracking
            
        Returns:
            Encoded JWT refresh token
        """
        now = datetime.now(timezone.utc)
        jti = str(uuid4())
        exp = now + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        family_id = family_id or str(uuid4())
        
        claims = {
            "iss": self.ISSUER,
            "sub": user_id,
            "aud": self.AUDIENCE,
            "exp": exp,
            "iat": now,
            "jti": jti,
            "family_id": family_id,
            "token_type": "refresh"
        }
        
        # Store token metadata
        stored = StoredToken(
            id=uuid4(),
            jti=jti,
            token_type="refresh",
            user_id=user_id,
            expires_at=exp,
            issued_at=now,
            family_id=family_id
        )
        self._stored_tokens[jti] = stored
        
        # Track token family
        if family_id not in self._token_families:
            self._token_families[family_id] = set()
        self._token_families[family_id].add(jti)
        
        # Encode with private key
        token = jwt.encode(claims, self.private_key, algorithm=self.ALGORITHM)
        return token
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """
        Verify and decode JWT token.
        
        Args:
            token: Encoded JWT token
            
        Returns:
            Decoded claims if valid, None otherwise
        """
        try:
            # Decode and verify signature
            claims = jwt.decode(
                token,
                self.public_key,
                algorithms=[self.ALGORITHM],
                audience=self.AUDIENCE,
                issuer=self.ISSUER
            )
            
            # Check if token is revoked
            jti = claims.get("jti")
            if jti and self.is_token_revoked(jti):
                logger.warning(f"Attempted use of revoked token: {jti}")
                return None
            
            return claims
            
        except jwt.ExpiredSignatureError:
            logger.debug("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    def rotate_refresh_token(self, old_refresh_token: str) -> Optional[Tuple[str, str]]:
        """
        Rotate refresh token with breach detection.
        
        Args:
            old_refresh_token: Current refresh token
            
        Returns:
            Tuple of (new_access_token, new_refresh_token) if successful
        """
        # Verify old token
        old_claims = self.verify_token(old_refresh_token)
        if not old_claims:
            return None
        
        if old_claims.get("token_type") != "refresh":
            logger.warning("Attempted to rotate non-refresh token")
            return None
        
        jti = old_claims["jti"]
        family_id = old_claims.get("family_id")
        user_id = old_claims["sub"]
        
        # Check if token was already used (breach detection)
        stored = self._stored_tokens.get(jti)
        if stored and stored.used:
            logger.error(f"Refresh token reuse detected for family {family_id}")
            # Revoke entire token family
            self.revoke_token_family(family_id)
            return None
        
        # Mark old token as used
        if stored:
            stored.used = True
        
        # Generate new tokens
        # Get scopes from a user service (placeholder for now)
        scopes = ["bot:read", "bot:write"]
        
        new_access = self.create_access_token(user_id, scopes)
        new_refresh = self.create_refresh_token(user_id, family_id)
        
        logger.info(f"Rotated refresh token for user {user_id}")
        return (new_access, new_refresh)
    
    def revoke_token(self, jti: str) -> bool:
        """
        Revoke a specific token.
        
        Args:
            jti: JWT ID to revoke
            
        Returns:
            True if revoked successfully
        """
        if jti in self._stored_tokens:
            self._stored_tokens[jti].revoked = True
            self._stored_tokens[jti].revoked_at = datetime.now(timezone.utc)
            logger.info(f"Revoked token: {jti}")
            return True
        return False
    
    def revoke_token_family(self, family_id: str) -> int:
        """
        Revoke all tokens in a family (breach response).
        
        Args:
            family_id: Token family to revoke
            
        Returns:
            Number of tokens revoked
        """
        if family_id not in self._token_families:
            return 0
        
        revoked_count = 0
        for jti in self._token_families[family_id]:
            if self.revoke_token(jti):
                revoked_count += 1
        
        logger.warning(f"Revoked {revoked_count} tokens in family {family_id}")
        return revoked_count
    
    def is_token_revoked(self, jti: str) -> bool:
        """Check if token is revoked."""
        stored = self._stored_tokens.get(jti)
        return stored.revoked if stored else False
    
    def create_token_pair(self, user_id: str, scopes: list) -> TokenResponse:
        """
        Create access and refresh token pair.
        
        Args:
            user_id: User identifier
            scopes: Permission scopes
            
        Returns:
            Token response with both tokens
        """
        access_token = self.create_access_token(user_id, scopes)
        refresh_token = self.create_refresh_token(user_id)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=self.ACCESS_TOKEN_EXPIRE_HOURS * 3600,
            scope=" ".join(scopes)
        )