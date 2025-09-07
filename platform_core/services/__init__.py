"""
Platform Services Package
=========================

Application services for MultiCord Platform.
Provides process orchestration and feature management.
"""

from .process_orchestrator import (
    ProcessOrchestrator, 
    ProcessConflictResolver, 
    FileLockingManager,
    ProcessConflictResult
)
from .template_discovery_service import (
    TemplateDiscoveryService,
    TemplateMetadata
)
from .log_aggregation_service import (
    LogAggregationService,
    StructuredLogEntry,
    LogLevel,
    LogSource
)
from .health_monitoring_service import (
    HealthMonitoringService,
    HealthCheckResult,
    HealthAlert,
    HealthMetric,
    AlertSeverity
)
from .auth_service import DeviceFlowService
from .token_service import TokenService

__all__ = [
    "ProcessOrchestrator",
    "ProcessConflictResolver", 
    "FileLockingManager",
    "ProcessConflictResult",
    "TemplateDiscoveryService",
    "TemplateMetadata",
    "LogAggregationService",
    "StructuredLogEntry",
    "LogLevel",
    "LogSource",
    "HealthMonitoringService",
    "HealthCheckResult",
    "HealthAlert",
    "HealthMetric",
    "AlertSeverity",
    "DeviceFlowService",
    "TokenService"
]