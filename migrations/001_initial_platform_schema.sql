-- PostgreSQL Schema for MultiCord Platform
-- Core technical infrastructure tables
-- Version: 001_initial_platform_schema

BEGIN;

-- Core platform node management
CREATE TABLE server_nodes (
    node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hostname VARCHAR(255) NOT NULL,
    platform_version VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'active',
    
    -- Node metadata
    os_info JSONB DEFAULT '{}'::jsonb,
    resource_limits JSONB DEFAULT '{}'::jsonb,
    
    -- Indexing
    CONSTRAINT valid_status CHECK (status IN ('active', 'inactive', 'maintenance', 'error'))
);

-- Bot instance management 
CREATE TABLE bot_instances (
    instance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID REFERENCES server_nodes(node_id) ON DELETE CASCADE,
    client_id VARCHAR(255) NOT NULL,
    execution_strategy VARCHAR(50) NOT NULL,
    configuration_data JSONB NOT NULL,
    enabled_features JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Bot metadata
    discord_token_hash VARCHAR(128), -- For conflict detection only
    environment_config JSONB DEFAULT '{}'::jsonb,
    
    -- Constraints
    CONSTRAINT valid_strategy CHECK (execution_strategy IN ('standard', 'template', 'enhanced')),
    UNIQUE(node_id, client_id)
);

-- Process registry for technical orchestration
CREATE TABLE process_registry (
    process_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id UUID REFERENCES bot_instances(instance_id) ON DELETE CASCADE,
    pid INTEGER NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    source VARCHAR(50) NOT NULL,
    log_file_path TEXT,
    restart_count INTEGER DEFAULT 0,
    last_restart TIMESTAMP WITH TIME ZONE,
    health_status JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Process metadata
    memory_usage_mb FLOAT DEFAULT 0,
    cpu_percent FLOAT DEFAULT 0,
    terminal_instance VARCHAR(50),
    
    -- Constraints
    CONSTRAINT valid_source CHECK (source IN ('discovered', 'launched')),
    CONSTRAINT positive_pid CHECK (pid > 0)
);

-- Platform technical features (no business logic)
CREATE TABLE platform_features (
    feature_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_name VARCHAR(100) NOT NULL UNIQUE,
    feature_type VARCHAR(50) NOT NULL,
    configuration_schema JSONB,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Feature metadata
    description TEXT,
    version VARCHAR(20) DEFAULT '1.0.0',
    dependencies JSONB DEFAULT '[]'::jsonb,
    
    -- Constraints
    CONSTRAINT valid_feature_type CHECK (feature_type IN ('technical', 'monitoring', 'enhancement'))
);

-- Feature assignments to bot instances
CREATE TABLE instance_feature_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id UUID REFERENCES bot_instances(instance_id) ON DELETE CASCADE,
    feature_id UUID REFERENCES platform_features(feature_id) ON DELETE CASCADE,
    configuration JSONB DEFAULT '{}'::jsonb,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Assignment metadata
    assigned_by VARCHAR(100),
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    UNIQUE(instance_id, feature_id)
);

-- Template management (technical only)
CREATE TABLE bot_templates (
    template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_name VARCHAR(100) NOT NULL UNIQUE,
    template_type VARCHAR(50) NOT NULL,
    template_path TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Template versioning
    version VARCHAR(20) DEFAULT '1.0.0',
    author VARCHAR(100),
    description TEXT,
    
    -- Constraints
    CONSTRAINT valid_template_type CHECK (template_type IN ('builtin', 'community', 'custom'))
);

-- Configuration history for audit trails
CREATE TABLE configuration_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id UUID REFERENCES bot_instances(instance_id) ON DELETE CASCADE,
    changed_by VARCHAR(100),
    change_type VARCHAR(50) NOT NULL,
    old_config JSONB,
    new_config JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Change metadata
    reason TEXT,
    rollback_id UUID REFERENCES configuration_history(history_id),
    
    -- Constraints
    CONSTRAINT valid_change_type CHECK (change_type IN ('create', 'update', 'delete', 'rollback'))
);

-- Performance metrics for monitoring
CREATE TABLE performance_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id UUID REFERENCES bot_instances(instance_id) ON DELETE CASCADE,
    node_id UUID REFERENCES server_nodes(node_id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    metric_unit VARCHAR(50),
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Metric metadata
    tags JSONB DEFAULT '{}'::jsonb,
    
    -- Partitioning ready
    CONSTRAINT valid_metric_name CHECK (metric_name ~ '^[a-z_]+$')
);

-- Create indexes for performance
CREATE INDEX idx_server_nodes_status ON server_nodes(status);
CREATE INDEX idx_server_nodes_heartbeat ON server_nodes(last_heartbeat);

CREATE INDEX idx_bot_instances_client_id ON bot_instances(client_id);
CREATE INDEX idx_bot_instances_strategy ON bot_instances(execution_strategy);
CREATE INDEX idx_bot_instances_node ON bot_instances(node_id);

CREATE INDEX idx_process_registry_pid ON process_registry(pid);
CREATE INDEX idx_process_registry_instance ON process_registry(instance_id);
CREATE INDEX idx_process_registry_started ON process_registry(started_at);

CREATE INDEX idx_platform_features_type ON platform_features(feature_type);
CREATE INDEX idx_platform_features_enabled ON platform_features(enabled);

CREATE INDEX idx_performance_metrics_instance ON performance_metrics(instance_id);
CREATE INDEX idx_performance_metrics_recorded ON performance_metrics(recorded_at);
CREATE INDEX idx_performance_metrics_name ON performance_metrics(metric_name);

-- Insert default platform features
INSERT INTO platform_features (feature_name, feature_type, description, configuration_schema) VALUES 
('branding_enhancement', 'technical', 'Optional branding and visual customization', '{"embed_colors": {"type": "object"}, "bot_name": {"type": "string"}}'),
('monitoring_service', 'monitoring', 'Health monitoring and metrics collection', '{"check_interval": {"type": "integer"}, "alert_thresholds": {"type": "object"}}'),
('logging_enhancement', 'technical', 'Structured logging with retention policies', '{"log_level": {"type": "string"}, "retention_days": {"type": "integer"}}'),
('permission_management', 'technical', 'Advanced permission system', '{"role_hierarchies": {"type": "object"}, "permission_overrides": {"type": "array"}}');

COMMIT;