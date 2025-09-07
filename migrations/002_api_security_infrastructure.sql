-- =============================================================================
-- MultiCord Platform - API Security Infrastructure Migration
-- =============================================================================
-- File: 002_api_security_infrastructure.sql
-- Purpose: Create security tables for API authentication and authorization
-- Dependencies: 001_initial_platform_schema.sql
-- =============================================================================

-- API Keys Table
-- Stores hashed API keys with Argon2 for authentication
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_name VARCHAR(100) NOT NULL,
    key_hash VARCHAR(200) NOT NULL, -- Argon2 hash of the API key
    key_prefix VARCHAR(20) NOT NULL, -- First few chars for identification
    permissions JSONB NOT NULL DEFAULT '[]'::jsonb, -- Array of permission strings
    is_active BOOLEAN NOT NULL DEFAULT true,
    expires_at TIMESTAMP WITH TIME ZONE, -- NULL for non-expiring keys
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER NOT NULL DEFAULT 0,
    rate_limit_per_hour INTEGER DEFAULT 1000, -- Per-key rate limiting
    created_by VARCHAR(100), -- Username or system identifier
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for API key lookups
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_active ON api_keys(is_active) WHERE is_active = true;
CREATE INDEX idx_api_keys_expires ON api_keys(expires_at) WHERE expires_at IS NOT NULL;

-- JWT Tokens Table
-- Manages JWT token lifecycle and revocation
CREATE TABLE jwt_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_jti VARCHAR(100) NOT NULL UNIQUE, -- JWT ID claim for revocation
    api_key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    token_type VARCHAR(20) NOT NULL DEFAULT 'access', -- 'access' or 'refresh'
    permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    issued_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMP WITH TIME ZONE,
    is_revoked BOOLEAN NOT NULL DEFAULT false,
    client_ip INET,
    user_agent TEXT
);

-- Indexes for JWT token management
CREATE INDEX idx_jwt_tokens_jti ON jwt_tokens(token_jti);
CREATE INDEX idx_jwt_tokens_api_key ON jwt_tokens(api_key_id);
CREATE INDEX idx_jwt_tokens_active ON jwt_tokens(is_revoked, expires_at) WHERE is_revoked = false;
CREATE INDEX idx_jwt_tokens_cleanup ON jwt_tokens(expires_at) WHERE is_revoked = false;

-- Audit Log Table
-- Comprehensive API request tracking for security monitoring
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    request_id VARCHAR(100) NOT NULL, -- Unique request identifier
    endpoint VARCHAR(200) NOT NULL,
    http_method VARCHAR(10) NOT NULL,
    client_ip INET NOT NULL,
    user_agent TEXT,
    request_payload JSONB, -- Sanitized request data (no secrets)
    response_status INTEGER NOT NULL,
    response_size_bytes INTEGER,
    execution_time_ms NUMERIC(10,3),
    error_message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for audit log queries
CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX idx_audit_log_api_key ON audit_log(api_key_id);
CREATE INDEX idx_audit_log_endpoint ON audit_log(endpoint);
CREATE INDEX idx_audit_log_client_ip ON audit_log(client_ip);
CREATE INDEX idx_audit_log_status ON audit_log(response_status);

-- Rate Limiting Buckets Table
-- Token bucket algorithm for API rate limiting
CREATE TABLE rate_limit_buckets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier VARCHAR(200) NOT NULL, -- API key ID, IP address, or custom identifier
    bucket_type VARCHAR(50) NOT NULL, -- 'api_key', 'ip_address', 'endpoint'
    endpoint VARCHAR(200), -- Specific endpoint for granular limiting
    current_tokens INTEGER NOT NULL DEFAULT 0,
    max_tokens INTEGER NOT NULL,
    refill_rate INTEGER NOT NULL, -- Tokens per time window
    time_window_seconds INTEGER NOT NULL DEFAULT 3600, -- 1 hour default
    last_refill_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for rate limiting lookups
CREATE UNIQUE INDEX idx_rate_limit_identifier ON rate_limit_buckets(identifier, bucket_type, COALESCE(endpoint, ''));
CREATE INDEX idx_rate_limit_refill ON rate_limit_buckets(last_refill_at);

-- =============================================================================
-- Security Functions
-- =============================================================================

-- Function to clean up expired JWT tokens
CREATE OR REPLACE FUNCTION cleanup_expired_jwt_tokens()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM jwt_tokens 
    WHERE expires_at < NOW() - INTERVAL '7 days'
    AND is_revoked = true;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- Function to clean up old audit logs (configurable retention)
CREATE OR REPLACE FUNCTION cleanup_audit_logs(retention_days INTEGER DEFAULT 90)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM audit_log 
    WHERE timestamp < NOW() - (retention_days || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- Function to update API key last used timestamp
CREATE OR REPLACE FUNCTION update_api_key_usage(key_id UUID)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE api_keys 
    SET 
        last_used_at = NOW(),
        usage_count = usage_count + 1,
        updated_at = NOW()
    WHERE id = key_id;
END;
$$;

-- =============================================================================
-- Security Views
-- =============================================================================

-- Active API Keys View (exclude sensitive data)
CREATE VIEW active_api_keys AS
SELECT 
    id,
    key_name,
    key_prefix,
    permissions,
    expires_at,
    last_used_at,
    usage_count,
    rate_limit_per_hour,
    created_by,
    created_at
FROM api_keys 
WHERE is_active = true 
AND (expires_at IS NULL OR expires_at > NOW());

-- Recent API Activity View
CREATE VIEW recent_api_activity AS
SELECT 
    al.timestamp,
    ak.key_name,
    al.endpoint,
    al.http_method,
    al.client_ip,
    al.response_status,
    al.execution_time_ms
FROM audit_log al
LEFT JOIN api_keys ak ON al.api_key_id = ak.id
WHERE al.timestamp > NOW() - INTERVAL '24 hours'
ORDER BY al.timestamp DESC;

-- Rate Limiting Status View
CREATE VIEW rate_limiting_status AS
SELECT 
    identifier,
    bucket_type,
    endpoint,
    current_tokens,
    max_tokens,
    ROUND((current_tokens::NUMERIC / max_tokens::NUMERIC) * 100, 2) AS usage_percentage,
    last_refill_at
FROM rate_limit_buckets
WHERE current_tokens < max_tokens;

-- =============================================================================
-- Initial Security Data
-- =============================================================================

-- Create default system API key for internal platform operations
-- Note: In production, this should be generated with a proper random key
INSERT INTO api_keys (
    key_name,
    key_hash,
    key_prefix,
    permissions,
    rate_limit_per_hour,
    created_by
) VALUES (
    'system-internal',
    '$argon2id$v=19$m=65536,t=3,p=4$placeholder_hash', -- Replace with actual Argon2 hash
    'sys_',
    '["admin", "system", "health_check", "metrics"]'::jsonb,
    10000,
    'system'
);

-- =============================================================================
-- Triggers for Automatic Timestamps
-- =============================================================================

-- Update timestamps on api_keys
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_api_keys_updated_at 
    BEFORE UPDATE ON api_keys 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_rate_limit_buckets_updated_at 
    BEFORE UPDATE ON rate_limit_buckets 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Comments for Documentation
-- =============================================================================

COMMENT ON TABLE api_keys IS 'Stores API keys with Argon2 hashing for FastAPI authentication';
COMMENT ON TABLE jwt_tokens IS 'JWT token lifecycle management with revocation support';
COMMENT ON TABLE audit_log IS 'Comprehensive API request audit trail for security monitoring';
COMMENT ON TABLE rate_limit_buckets IS 'Token bucket rate limiting for API endpoints';

COMMENT ON FUNCTION cleanup_expired_jwt_tokens() IS 'Maintenance function to clean up expired and revoked JWT tokens';
COMMENT ON FUNCTION cleanup_audit_logs(INTEGER) IS 'Maintenance function to clean up old audit logs';
COMMENT ON FUNCTION update_api_key_usage(UUID) IS 'Updates API key usage statistics';

-- =============================================================================
-- Migration Complete
-- =============================================================================

-- Log successful migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 002_api_security_infrastructure.sql completed successfully';
    RAISE NOTICE 'Tables created: api_keys, jwt_tokens, audit_log, rate_limit_buckets';
    RAISE NOTICE 'Functions created: cleanup_expired_jwt_tokens, cleanup_audit_logs, update_api_key_usage';
    RAISE NOTICE 'Views created: active_api_keys, recent_api_activity, rate_limiting_status';
END;
$$;