"""
Health Monitoring Service
========================

Real-time health monitoring service for MultiCord platform.
Provides comprehensive health checks, alerting, and performance tracking.
"""

import asyncio
import psutil
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from enum import Enum
import logging

from ..infrastructure.postgresql_pool import PostgreSQLConnectionPool
from ..entities.process_info import ProcessInfo, HealthStatus
from ..strategies.bot_execution_strategy import ProcessHandle


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"
    DOWN = "down"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    URGENT = "urgent"


@dataclass
class HealthMetric:
    """Individual health metric with thresholds."""
    
    name: str
    current_value: float
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    unit: str = ""
    description: str = ""
    is_higher_better: bool = False  # False means lower values are better
    
    @property
    def status(self) -> HealthStatus:
        """Determine health status based on thresholds."""
        if self.threshold_critical is not None:
            if self.is_higher_better:
                if self.current_value <= self.threshold_critical:
                    return HealthStatus.CRITICAL
            else:
                if self.current_value >= self.threshold_critical:
                    return HealthStatus.CRITICAL
        
        if self.threshold_warning is not None:
            if self.is_higher_better:
                if self.current_value <= self.threshold_warning:
                    return HealthStatus.WARNING
            else:
                if self.current_value >= self.threshold_warning:
                    return HealthStatus.WARNING
        
        return HealthStatus.HEALTHY


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    
    check_id: UUID
    instance_id: Optional[UUID]
    client_id: Optional[str]
    process_id: Optional[int]
    timestamp: datetime
    overall_status: HealthStatus
    metrics: Dict[str, HealthMetric]
    alerts: List['HealthAlert']
    check_duration_ms: float
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'check_id': str(self.check_id),
            'instance_id': str(self.instance_id) if self.instance_id else None,
            'client_id': self.client_id,
            'process_id': self.process_id,
            'timestamp': self.timestamp.isoformat(),
            'overall_status': self.overall_status.value,
            'metrics': {name: asdict(metric) for name, metric in self.metrics.items()},
            'alerts': [asdict(alert) for alert in self.alerts],
            'check_duration_ms': self.check_duration_ms,
            'error_message': self.error_message
        }


@dataclass
class HealthAlert:
    """Health monitoring alert."""
    
    alert_id: UUID
    timestamp: datetime
    severity: AlertSeverity
    title: str
    message: str
    instance_id: Optional[UUID] = None
    client_id: Optional[str] = None
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    acknowledged: bool = False
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class HealthMonitoringService:
    """
    Service for real-time health monitoring of bot processes.
    
    Provides comprehensive health checks, alerting, and performance tracking
    following MultiCord's clean architecture principles.
    """
    
    def __init__(self,
                 db_pool: PostgreSQLConnectionPool = None,
                 check_interval_seconds: int = 30,
                 alert_cooldown_seconds: int = 300,
                 logger: logging.Logger = None):
        """
        Initialize health monitoring service.
        
        Args:
            db_pool: PostgreSQL connection pool for persistence
            check_interval_seconds: Interval between health checks
            alert_cooldown_seconds: Cooldown period for duplicate alerts
            logger: Logger instance for service operations
        """
        self.db_pool = db_pool
        self.check_interval_seconds = check_interval_seconds
        self.alert_cooldown_seconds = alert_cooldown_seconds
        self.logger = logger or logging.getLogger(__name__)
        
        # Health check registry
        self._monitored_processes: Dict[str, ProcessHandle] = {}  # client_id -> ProcessHandle
        self._health_history: Dict[str, List[HealthCheckResult]] = {}  # client_id -> results
        self._active_alerts: Dict[str, HealthAlert] = {}  # alert_key -> alert
        self._alert_callbacks: List[Callable[[HealthAlert], None]] = []
        
        # Background monitoring
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Default health metric thresholds
        self._default_thresholds = {
            'memory_mb': HealthMetric('memory_mb', 0, 512, 1024, 'MB', 'Memory usage'),
            'cpu_percent': HealthMetric('cpu_percent', 0, 80, 95, '%', 'CPU usage'),
            'uptime_seconds': HealthMetric('uptime_seconds', 0, 0, 0, 's', 'Process uptime', True),
            'response_time_ms': HealthMetric('response_time_ms', 0, 1000, 5000, 'ms', 'Response time'),
            'error_rate': HealthMetric('error_rate', 0, 0.05, 0.1, '%', 'Error rate'),
            'restart_count': HealthMetric('restart_count', 0, 3, 5, '', 'Restart count')
        }
    
    async def start(self) -> None:
        """Start the health monitoring service."""
        if self._running:
            return
        
        self._running = True
        self.logger.info("Starting health monitoring service")
        
        # Start background monitoring task
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
    
    async def stop(self) -> None:
        """Stop the health monitoring service."""
        if not self._running:
            return
        
        self._running = False
        self.logger.info("Stopping health monitoring service")
        
        # Cancel monitoring task
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
    
    def register_process(self, process_handle: ProcessHandle) -> None:
        """Register a process for health monitoring."""
        client_id = process_handle.process_info.client_id
        self._monitored_processes[client_id] = process_handle
        self._health_history[client_id] = []
        
        self.logger.info(f"Registered process {client_id} for health monitoring")
    
    def unregister_process(self, client_id: str) -> None:
        """Unregister a process from health monitoring."""
        if client_id in self._monitored_processes:
            del self._monitored_processes[client_id]
            self.logger.info(f"Unregistered process {client_id} from health monitoring")
    
    def add_alert_callback(self, callback: Callable[[HealthAlert], None]) -> None:
        """Add callback function to receive health alerts."""
        self._alert_callbacks.append(callback)
    
    async def perform_health_check(self, process_handle: ProcessHandle) -> HealthCheckResult:
        """
        Perform comprehensive health check on a process.
        
        Args:
            process_handle: Process handle to check
            
        Returns:
            Health check result with metrics and status
        """
        start_time = datetime.now(timezone.utc)
        check_id = uuid4()
        
        try:
            process_info = process_handle.process_info
            metrics = {}
            alerts = []
            
            # Check if process is running
            if not process_handle.is_running:
                return HealthCheckResult(
                    check_id=check_id,
                    instance_id=process_info.instance_id,
                    client_id=process_info.client_id,
                    process_id=process_info.pid,
                    timestamp=start_time,
                    overall_status=HealthStatus.DOWN,
                    metrics={},
                    alerts=[HealthAlert(
                        alert_id=uuid4(),
                        timestamp=start_time,
                        severity=AlertSeverity.CRITICAL,
                        title="Process Down",
                        message=f"Bot process {process_info.client_id} is not running",
                        instance_id=process_info.instance_id,
                        client_id=process_info.client_id
                    )],
                    check_duration_ms=0,
                    error_message="Process not running"
                )
            
            # Get current health status from process info
            current_health = process_info.get_current_health_status()
            
            # Memory usage check
            if current_health.memory_mb is not None:
                memory_metric = HealthMetric(
                    name='memory_mb',
                    current_value=current_health.memory_mb,
                    threshold_warning=512,  # 512MB warning
                    threshold_critical=1024,  # 1GB critical
                    unit='MB',
                    description='Memory usage'
                )
                metrics['memory_mb'] = memory_metric
                
                if memory_metric.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
                    alerts.append(HealthAlert(
                        alert_id=uuid4(),
                        timestamp=start_time,
                        severity=AlertSeverity.WARNING if memory_metric.status == HealthStatus.WARNING else AlertSeverity.CRITICAL,
                        title="High Memory Usage",
                        message=f"Process {process_info.client_id} using {current_health.memory_mb:.1f}MB memory",
                        instance_id=process_info.instance_id,
                        client_id=process_info.client_id,
                        metric_name='memory_mb',
                        metric_value=current_health.memory_mb,
                        threshold=memory_metric.threshold_warning if memory_metric.status == HealthStatus.WARNING else memory_metric.threshold_critical
                    ))
            
            # CPU usage check
            if current_health.cpu_percent is not None:
                cpu_metric = HealthMetric(
                    name='cpu_percent',
                    current_value=current_health.cpu_percent,
                    threshold_warning=80,  # 80% warning
                    threshold_critical=95,  # 95% critical
                    unit='%',
                    description='CPU usage'
                )
                metrics['cpu_percent'] = cpu_metric
                
                if cpu_metric.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
                    alerts.append(HealthAlert(
                        alert_id=uuid4(),
                        timestamp=start_time,
                        severity=AlertSeverity.WARNING if cpu_metric.status == HealthStatus.WARNING else AlertSeverity.CRITICAL,
                        title="High CPU Usage",
                        message=f"Process {process_info.client_id} using {current_health.cpu_percent:.1f}% CPU",
                        instance_id=process_info.instance_id,
                        client_id=process_info.client_id,
                        metric_name='cpu_percent',
                        metric_value=current_health.cpu_percent,
                        threshold=cpu_metric.threshold_warning if cpu_metric.status == HealthStatus.WARNING else cpu_metric.threshold_critical
                    ))
            
            # Uptime check
            if current_health.uptime_seconds is not None:
                uptime_metric = HealthMetric(
                    name='uptime_seconds',
                    current_value=current_health.uptime_seconds,
                    unit='s',
                    description='Process uptime',
                    is_higher_better=True
                )
                metrics['uptime_seconds'] = uptime_metric
            
            # Restart count check
            restart_count = process_info.restart_count
            restart_metric = HealthMetric(
                name='restart_count',
                current_value=restart_count,
                threshold_warning=3,
                threshold_critical=5,
                unit='',
                description='Number of restarts'
            )
            metrics['restart_count'] = restart_metric
            
            if restart_metric.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
                alerts.append(HealthAlert(
                    alert_id=uuid4(),
                    timestamp=start_time,
                    severity=AlertSeverity.WARNING if restart_metric.status == HealthStatus.WARNING else AlertSeverity.CRITICAL,
                    title="High Restart Count",
                    message=f"Process {process_info.client_id} has restarted {restart_count} times",
                    instance_id=process_info.instance_id,
                    client_id=process_info.client_id,
                    metric_name='restart_count',
                    metric_value=restart_count,
                    threshold=restart_metric.threshold_warning if restart_metric.status == HealthStatus.WARNING else restart_metric.threshold_critical
                ))
            
            # Determine overall status
            overall_status = HealthStatus.HEALTHY
            for metric in metrics.values():
                if metric.status == HealthStatus.CRITICAL:
                    overall_status = HealthStatus.CRITICAL
                    break
                elif metric.status == HealthStatus.WARNING and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.WARNING
            
            # Calculate check duration
            end_time = datetime.now(timezone.utc)
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            return HealthCheckResult(
                check_id=check_id,
                instance_id=process_info.instance_id,
                client_id=process_info.client_id,
                process_id=process_info.pid,
                timestamp=start_time,
                overall_status=overall_status,
                metrics=metrics,
                alerts=alerts,
                check_duration_ms=duration_ms
            )
            
        except Exception as e:
            self.logger.error(f"Health check failed for {process_handle.process_info.client_id}: {e}")
            
            end_time = datetime.now(timezone.utc)
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            return HealthCheckResult(
                check_id=check_id,
                instance_id=process_handle.process_info.instance_id,
                client_id=process_handle.process_info.client_id,
                process_id=process_handle.process_info.pid,
                timestamp=start_time,
                overall_status=HealthStatus.UNKNOWN,
                metrics={},
                alerts=[HealthAlert(
                    alert_id=uuid4(),
                    timestamp=start_time,
                    severity=AlertSeverity.CRITICAL,
                    title="Health Check Failed",
                    message=f"Failed to perform health check: {str(e)}",
                    instance_id=process_handle.process_info.instance_id,
                    client_id=process_handle.process_info.client_id
                )],
                check_duration_ms=duration_ms,
                error_message=str(e)
            )
    
    async def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary of all monitored processes."""
        try:
            total_processes = len(self._monitored_processes)
            healthy_count = 0
            warning_count = 0
            critical_count = 0
            down_count = 0
            
            # Get latest health status for each process
            for client_id, history in self._health_history.items():
                if history:
                    latest_check = history[-1]
                    if latest_check.overall_status == HealthStatus.HEALTHY:
                        healthy_count += 1
                    elif latest_check.overall_status == HealthStatus.WARNING:
                        warning_count += 1
                    elif latest_check.overall_status == HealthStatus.CRITICAL:
                        critical_count += 1
                    elif latest_check.overall_status == HealthStatus.DOWN:
                        down_count += 1
            
            active_alerts_count = len([alert for alert in self._active_alerts.values() if not alert.resolved])
            
            return {
                'total_processes': total_processes,
                'healthy': healthy_count,
                'warning': warning_count,
                'critical': critical_count,
                'down': down_count,
                'active_alerts': active_alerts_count,
                'check_interval_seconds': self.check_interval_seconds,
                'last_check': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get health summary: {e}")
            return {'error': str(e)}
    
    async def get_process_health_history(self, client_id: str, limit: int = 50) -> List[HealthCheckResult]:
        """Get health check history for a specific process."""
        history = self._health_history.get(client_id, [])
        return history[-limit:]  # Return most recent entries
    
    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                # Perform health checks for all registered processes
                for client_id, process_handle in self._monitored_processes.items():
                    try:
                        health_result = await self.perform_health_check(process_handle)
                        
                        # Store health result
                        if client_id not in self._health_history:
                            self._health_history[client_id] = []
                        
                        self._health_history[client_id].append(health_result)
                        
                        # Limit history size
                        if len(self._health_history[client_id]) > 100:
                            self._health_history[client_id] = self._health_history[client_id][-100:]
                        
                        # Process alerts
                        for alert in health_result.alerts:
                            await self._process_alert(alert)
                        
                    except Exception as e:
                        self.logger.error(f"Error checking health for {client_id}: {e}")
                
                # Wait for next check
                await asyncio.sleep(self.check_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval_seconds)
    
    async def _process_alert(self, alert: HealthAlert) -> None:
        """Process a health alert."""
        try:
            # Create alert key for deduplication
            alert_key = f"{alert.client_id}_{alert.metric_name}_{alert.severity.value}"
            
            # Check if we already have an active alert of this type
            if alert_key in self._active_alerts:
                existing_alert = self._active_alerts[alert_key]
                # Check cooldown period
                if (alert.timestamp - existing_alert.timestamp).total_seconds() < self.alert_cooldown_seconds:
                    return  # Skip duplicate alert
            
            # Store active alert
            self._active_alerts[alert_key] = alert
            
            # Notify callbacks
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    self.logger.error(f"Error in alert callback: {e}")
            
            # Log alert
            self.logger.warning(f"Health alert: {alert.title} - {alert.message}")
            
        except Exception as e:
            self.logger.error(f"Failed to process alert: {e}")
    
    async def acknowledge_alert(self, alert_id: UUID) -> bool:
        """Acknowledge an alert."""
        try:
            for alert in self._active_alerts.values():
                if alert.alert_id == alert_id:
                    alert.acknowledged = True
                    self.logger.info(f"Acknowledged alert: {alert.title}")
                    return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to acknowledge alert: {e}")
            return False
    
    async def resolve_alert(self, alert_id: UUID) -> bool:
        """Mark an alert as resolved."""
        try:
            for alert in self._active_alerts.values():
                if alert.alert_id == alert_id:
                    alert.resolved = True
                    self.logger.info(f"Resolved alert: {alert.title}")
                    return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to resolve alert: {e}")
            return False