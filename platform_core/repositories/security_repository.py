"""
Security Repository
==================

PostgreSQL repository for authentication, authorization, and security operations.
Implements enterprise-grade security practices with comprehensive audit trails.
"""

import hashlib
import secrets
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID, uuid4

import argon2
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from platform_core.infrastructure.postgresql_pool import PostgreSQLConnectionPool


logger = logging.getLogger(__name__)


class SecurityRepository:
    """Repository for security and authentication operations."""
    
    # Argon2 configuration for production
    ARGON2_CONFIG = {
        'time_cost': 3,        # iterations
        'memory_cost': 65536,  # 64 MB
        'parallelism': 4,      # threads
        'hash_len': 32,        # bytes
        'salt_len': 16         # bytes
    }
    
    # Sensitive fields to exclude from audit logs
    SENSITIVE_FIELDS = {
        'password', 'token', 'api_key', 'secret', 'auth', 
        'authorization', 'x-api-key', 'bearer', 'refresh_token'
    }
    
    def __init__(self, pool: PostgreSQLConnectionPool):
        """Initialize security repository with connection pool."""
        self.pool = pool
        self.logger = logger
        self._ph = PasswordHasher(**self.ARGON2_CONFIG)
    
    async def create_api_key(self, 
                           key_name: str,
                           permissions: List[str],
                           created_by: str,
                           expires_at: Optional[datetime] = None,
                           rate_limit_per_hour: int = 1000) -> Tuple[str, UUID]:
        """
        Create new API key with Argon2 hashing.
        
        Args:
            key_name: Descriptive name for the key
            permissions: List of permission strings
            created_by: User or system creating the key
            expires_at: Optional expiration timestamp
            rate_limit_per_hour: Rate limit for this key
            
        Returns:
            Tuple of (raw_api_key, key_id)
            Note: raw_api_key is only returned once - store securely!
        """
        try:
            # Generate cryptographically secure API key
            raw_key = secrets.token_urlsafe(32)
            api_key = f"mcp_{secrets.token_urlsafe(6)}.{raw_key}"
            
            # Create prefix for identification without exposing hash
            key_prefix = api_key[:12]  # "mcp_" + first 8 chars
            
            # Hash with Argon2
            key_hash = self._ph.hash(api_key)
            
            # Store in database
            query = """
                INSERT INTO api_keys (
                    key_name, key_hash, key_prefix, permissions, 
                    expires_at, rate_limit_per_hour, created_by,
                    created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
                RETURNING id
            """
            
            result = await self.pool.fetch_one(
                query, key_name, key_hash, key_prefix, 
                json.dumps(permissions), expires_at, 
                rate_limit_per_hour, created_by
            )
            
            key_id = result["id"]
            self.logger.info(f"Created API key '{key_name}' for {created_by}")
            
            return api_key, key_id
            
        except Exception as e:
            self.logger.error(f"Failed to create API key: {e}")
            raise
    
    async def verify_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Verify API key and return key information.
        
        Args:
            api_key: Raw API key to verify
            
        Returns:
            Key information dict if valid, None if invalid
        """
        try:
            # Validate format and extract prefix
            if not api_key.startswith('mcp_'):
                return None
            
            key_prefix = api_key[:12]
            
            # Lookup by prefix (efficient index lookup)
            query = """
                SELECT id, key_hash, permissions, expires_at, is_active, 
                       rate_limit_per_hour, key_name
                FROM api_keys 
                WHERE key_prefix = $1 AND is_active = true
            """
            
            row = await self.pool.fetch_one(query, key_prefix)
            if not row:
                return None
            
            # Verify hash (constant-time comparison)
            try:
                self._ph.verify(row["key_hash"], api_key)
            except VerifyMismatchError:
                self.logger.warning(f"Invalid API key attempt for prefix {key_prefix}")
                return None
            
            # Check expiration
            if row["expires_at"] and datetime.now(timezone.utc) > row["expires_at"]:
                self.logger.info(f"Expired API key used: {row['key_name']}")
                return None
            
            # Update usage statistics
            await self._update_key_usage(row["id"])
            
            return {
                "key_id": row["id"],
                "key_name": row["key_name"],
                "permissions": json.loads(row["permissions"]),
                "rate_limit_per_hour": row["rate_limit_per_hour"]
            }
            
        except Exception as e:
            self.logger.error(f"API key verification error: {e}")
            return None
    
    async def store_jwt_token(self, 
                             jti: str,
                             api_key_id: UUID,
                             token_type: str,
                             permissions: List[str],
                             expires_at: datetime,
                             client_info: Optional[Dict] = None) -> bool:
        """
        Store JWT token for revocation tracking.
        
        Args:
            jti: JWT ID (unique identifier)
            api_key_id: Associated API key
            token_type: 'access' or 'refresh'
            permissions: Token permissions
            expires_at: Token expiration
            client_info: Optional client IP and user agent
            
        Returns:
            True if stored successfully
        """
        try:
            query = """
                INSERT INTO jwt_tokens (
                    token_jti, api_key_id, token_type, permissions,
                    expires_at, issued_at, client_ip, user_agent
                ) VALUES ($1, $2, $3, $4, $5, NOW(), $6, $7)
            """
            
            await self.pool.execute(
                query,
                jti,
                api_key_id,
                token_type,
                json.dumps(permissions),
                expires_at,
                client_info.get("client_ip") if client_info else None,
                client_info.get("user_agent") if client_info else None
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store JWT token: {e}")
            return False
    
    async def is_token_revoked(self, jti: str) -> bool:
        """
        Check if JWT token is revoked.
        
        Args:
            jti: JWT ID to check
            
        Returns:
            True if revoked or not found (fail secure)
        """
        try:
            query = """
                SELECT is_revoked FROM jwt_tokens 
                WHERE token_jti = $1
            """
            
            result = await self.pool.fetch_one(query, jti)
            # Fail secure - assume revoked if not found
            return result["is_revoked"] if result else True
            
        except Exception as e:
            self.logger.error(f"Token revocation check failed: {e}")
            return True  # Fail secure
    
    async def revoke_token_family(self, family_id: str) -> int:
        """
        Revoke all tokens in a family (breach response).
        
        Args:
            family_id: Token family identifier
            
        Returns:
            Number of tokens revoked
        """
        try:
            # Find all tokens in family
            query = """
                UPDATE jwt_tokens 
                SET is_revoked = true, revoked_at = NOW()
                WHERE permissions::jsonb @> %s
                AND is_revoked = false
            """
            
            family_filter = json.dumps({"family_id": family_id})
            result = await self.pool.execute(query, family_filter)
            
            count = result.get("rows_affected", 0)
            if count > 0:
                self.logger.warning(f"Revoked {count} tokens in family {family_id} (breach detected)")
            
            return count
            
        except Exception as e:
            self.logger.error(f"Failed to revoke token family: {e}")
            return 0
    
    async def log_api_request(self, 
                             request_data: Dict[str, Any]) -> bool:
        """
        Log API request for audit trail.
        
        Args:
            request_data: Request information to log
            
        Returns:
            True if logged successfully
        """
        try:
            # Sanitize sensitive data
            sanitized_payload = None
            if "request_payload" in request_data:
                sanitized_payload = self._sanitize_payload(
                    request_data["request_payload"]
                )
            
            query = """
                INSERT INTO audit_log (
                    api_key_id, request_id, endpoint, http_method,
                    client_ip, user_agent, request_payload, response_status,
                    response_size_bytes, execution_time_ms, error_message,
                    timestamp
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
            """
            
            await self.pool.execute(
                query,
                request_data.get("api_key_id"),
                request_data["request_id"],
                request_data["endpoint"],
                request_data["http_method"],
                request_data["client_ip"],
                request_data.get("user_agent"),
                json.dumps(sanitized_payload) if sanitized_payload else None,
                request_data["response_status"],
                request_data.get("response_size_bytes"),
                request_data.get("execution_time_ms"),
                request_data.get("error_message")
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to log API request: {e}")
            return False
    
    async def check_rate_limit(self, 
                              identifier: str,
                              bucket_type: str = "api_key",
                              endpoint: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Check and update rate limit using token bucket algorithm.
        
        Args:
            identifier: Unique identifier (API key ID, IP address)
            bucket_type: Type of rate limit bucket
            endpoint: Optional specific endpoint
            
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        try:
            # Get or create bucket
            bucket = await self._get_or_create_bucket(
                identifier, bucket_type, endpoint
            )
            
            now = datetime.now(timezone.utc)
            time_elapsed = (now - bucket["last_refill_at"]).total_seconds()
            
            # Calculate tokens to add
            refill_per_second = bucket["refill_rate"] / bucket["time_window_seconds"]
            tokens_to_add = int(time_elapsed * refill_per_second)
            
            # Update token count
            new_tokens = min(
                bucket["max_tokens"],
                bucket["current_tokens"] + tokens_to_add
            )
            
            # Check if request allowed
            allowed = new_tokens > 0
            if allowed:
                new_tokens -= 1
            
            # Update bucket state
            await self._update_bucket(
                bucket["id"], 
                new_tokens,
                now if tokens_to_add > 0 else bucket["last_refill_at"]
            )
            
            # Calculate reset time
            tokens_needed = bucket["max_tokens"] - new_tokens
            seconds_until_reset = tokens_needed / refill_per_second
            
            return allowed, {
                "allowed": allowed,
                "limit": bucket["max_tokens"],
                "remaining": max(0, new_tokens),
                "reset_at": now + timedelta(seconds=seconds_until_reset),
                "retry_after": int(seconds_until_reset) if not allowed else None
            }
            
        except Exception as e:
            self.logger.error(f"Rate limit check failed: {e}")
            # Fail open for availability
            return True, {"error": "Rate limiting unavailable"}
    
    def _sanitize_payload(self, payload: Any) -> Any:
        """Remove sensitive fields from payload."""
        if isinstance(payload, dict):
            sanitized = {}
            for key, value in payload.items():
                key_lower = key.lower()
                
                # Check for sensitive field names
                if any(sensitive in key_lower for sensitive in self.SENSITIVE_FIELDS):
                    sanitized[key] = "[REDACTED]"
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_payload(value)
                elif isinstance(value, str) and len(value) > 1000:
                    sanitized[key] = value[:1000] + "...[TRUNCATED]"
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(payload, list):
            return [self._sanitize_payload(item) for item in payload]
        else:
            return payload
    
    async def _update_key_usage(self, key_id: UUID) -> None:
        """Update API key usage statistics."""
        query = "SELECT update_api_key_usage($1)"
        await self.pool.execute(query, key_id)
    
    async def _get_or_create_bucket(self,
                                  identifier: str,
                                  bucket_type: str,
                                  endpoint: Optional[str]) -> Dict[str, Any]:
        """Get existing bucket or create new one."""
        # Try to get existing
        query = """
            SELECT * FROM rate_limit_buckets 
            WHERE identifier = $1 
            AND bucket_type = $2 
            AND COALESCE(endpoint, '') = COALESCE($3, '')
        """
        
        bucket = await self.pool.fetch_one(query, identifier, bucket_type, endpoint or '')
        
        if bucket:
            return bucket
        
        # Create new bucket with defaults
        defaults = {
            "api_key": {"max": 1000, "rate": 1000, "window": 3600},
            "ip_address": {"max": 100, "rate": 100, "window": 3600},
            "endpoint": {"max": 500, "rate": 500, "window": 3600}
        }
        
        config = defaults.get(bucket_type, defaults["ip_address"])
        
        query = """
            INSERT INTO rate_limit_buckets (
                identifier, bucket_type, endpoint, current_tokens,
                max_tokens, refill_rate, time_window_seconds,
                last_refill_at, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW(), NOW())
            RETURNING *
        """
        
        return await self.pool.fetch_one(
            query, identifier, bucket_type, endpoint,
            config["max"], config["max"], config["rate"], config["window"]
        )
    
    async def _update_bucket(self,
                           bucket_id: UUID,
                           current_tokens: int,
                           last_refill: datetime) -> None:
        """Update rate limit bucket state."""
        query = """
            UPDATE rate_limit_buckets 
            SET current_tokens = $2, 
                last_refill_at = $3,
                updated_at = NOW()
            WHERE id = $1
        """
        
        await self.pool.execute(query, bucket_id, current_tokens, last_refill)