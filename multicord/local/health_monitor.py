"""
Health monitoring service for local bot processes.
Provides real-time monitoring, alerting, and resource tracking.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from collections import deque

import psutil
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .process_orchestrator import ProcessOrchestrator, HealthStatus


class HealthLevel(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DEAD = "dead"


@dataclass
class HealthThresholds:
    """Configurable health thresholds."""
    memory_warning_mb: float = 512
    memory_critical_mb: float = 1024
    cpu_warning_percent: float = 80
    cpu_critical_percent: float = 95
    response_time_warning_ms: float = 1000
    response_time_critical_ms: float = 5000


@dataclass
class HealthAlert:
    """Health alert information."""
    bot_name: str
    level: HealthLevel
    message: str
    timestamp: datetime
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    
    def format(self) -> str:
        """Format alert for display."""
        level_colors = {
            HealthLevel.WARNING: "yellow",
            HealthLevel.CRITICAL: "red",
            HealthLevel.DEAD: "red bold"
        }
        color = level_colors.get(self.level, "white")
        return f"[{color}][{self.level.value.upper()}][/{color}] {self.bot_name}: {self.message}"


@dataclass
class BotHealthHistory:
    """Health history for a bot."""
    bot_name: str
    max_history: int = 100
    memory_history: deque = field(default_factory=lambda: deque(maxlen=100))
    cpu_history: deque = field(default_factory=lambda: deque(maxlen=100))
    status_history: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def add_sample(self, health: HealthStatus):
        """Add a health sample to history."""
        timestamp = datetime.now()
        self.memory_history.append((timestamp, health.memory_mb))
        self.cpu_history.append((timestamp, health.cpu_percent))
        self.status_history.append((timestamp, health.is_running))
    
    def get_average_memory(self, seconds: int = 60) -> float:
        """Get average memory usage over time window."""
        if not self.memory_history:
            return 0.0
        
        cutoff = datetime.now() - timedelta(seconds=seconds)
        recent = [mem for ts, mem in self.memory_history if ts > cutoff]
        return sum(recent) / len(recent) if recent else 0.0
    
    def get_average_cpu(self, seconds: int = 60) -> float:
        """Get average CPU usage over time window."""
        if not self.cpu_history:
            return 0.0
        
        cutoff = datetime.now() - timedelta(seconds=seconds)
        recent = [cpu for ts, cpu in self.cpu_history if ts > cutoff]
        return sum(recent) / len(recent) if recent else 0.0
    
    def get_uptime_percentage(self) -> float:
        """Get uptime percentage from history."""
        if not self.status_history:
            return 0.0
        
        running_count = sum(1 for _, is_running in self.status_history if is_running)
        return (running_count / len(self.status_history)) * 100


class HealthMonitor:
    """Monitors health of bot processes with alerting."""
    
    def __init__(self, 
                 orchestrator: ProcessOrchestrator,
                 thresholds: Optional[HealthThresholds] = None,
                 check_interval: float = 30.0):
        """Initialize health monitor."""
        self.orchestrator = orchestrator
        self.thresholds = thresholds or HealthThresholds()
        self.check_interval = check_interval
        
        self.console = Console()
        self.logger = logging.getLogger(__name__)
        
        self.health_history: Dict[str, BotHealthHistory] = {}
        self.active_alerts: Dict[str, List[HealthAlert]] = {}
        self.alert_callbacks: List[Callable[[HealthAlert], None]] = []
        
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    def evaluate_health_level(self, health: HealthStatus) -> HealthLevel:
        """Evaluate health level based on thresholds."""
        if not health.is_running:
            return HealthLevel.DEAD
        
        if (health.memory_mb > self.thresholds.memory_critical_mb or
            health.cpu_percent > self.thresholds.cpu_critical_percent):
            return HealthLevel.CRITICAL
        
        if (health.memory_mb > self.thresholds.memory_warning_mb or
            health.cpu_percent > self.thresholds.cpu_warning_percent):
            return HealthLevel.WARNING
        
        return HealthLevel.HEALTHY
    
    def create_alert(self, 
                    bot_name: str, 
                    health: HealthStatus, 
                    level: HealthLevel) -> Optional[HealthAlert]:
        """Create health alert if needed."""
        alerts = []
        
        if level == HealthLevel.DEAD:
            alerts.append(HealthAlert(
                bot_name=bot_name,
                level=level,
                message="Bot process is not running",
                timestamp=datetime.now()
            ))
        
        if health.memory_mb > self.thresholds.memory_critical_mb:
            alerts.append(HealthAlert(
                bot_name=bot_name,
                level=HealthLevel.CRITICAL,
                message=f"Memory usage critical: {health.memory_mb:.1f}MB",
                timestamp=datetime.now(),
                metric_value=health.memory_mb,
                threshold=self.thresholds.memory_critical_mb
            ))
        elif health.memory_mb > self.thresholds.memory_warning_mb:
            alerts.append(HealthAlert(
                bot_name=bot_name,
                level=HealthLevel.WARNING,
                message=f"Memory usage high: {health.memory_mb:.1f}MB",
                timestamp=datetime.now(),
                metric_value=health.memory_mb,
                threshold=self.thresholds.memory_warning_mb
            ))
        
        if health.cpu_percent > self.thresholds.cpu_critical_percent:
            alerts.append(HealthAlert(
                bot_name=bot_name,
                level=HealthLevel.CRITICAL,
                message=f"CPU usage critical: {health.cpu_percent:.1f}%",
                timestamp=datetime.now(),
                metric_value=health.cpu_percent,
                threshold=self.thresholds.cpu_critical_percent
            ))
        elif health.cpu_percent > self.thresholds.cpu_warning_percent:
            alerts.append(HealthAlert(
                bot_name=bot_name,
                level=HealthLevel.WARNING,
                message=f"CPU usage high: {health.cpu_percent:.1f}%",
                timestamp=datetime.now(),
                metric_value=health.cpu_percent,
                threshold=self.thresholds.cpu_warning_percent
            ))
        
        return alerts
    
    async def check_bot_health(self, bot_name: str) -> Optional[HealthStatus]:
        """Check health of a single bot."""
        health = self.orchestrator.get_bot_health(bot_name)
        if not health:
            return None
        
        # Update history
        if bot_name not in self.health_history:
            self.health_history[bot_name] = BotHealthHistory(bot_name)
        self.health_history[bot_name].add_sample(health)
        
        # Check for alerts
        level = self.evaluate_health_level(health)
        if level != HealthLevel.HEALTHY:
            alerts = self.create_alert(bot_name, health, level)
            if alerts:
                if bot_name not in self.active_alerts:
                    self.active_alerts[bot_name] = []
                
                for alert in alerts:
                    # Deduplicate alerts
                    if not any(a.message == alert.message for a in self.active_alerts[bot_name][-5:]):
                        self.active_alerts[bot_name].append(alert)
                        
                        # Trigger callbacks
                        for callback in self.alert_callbacks:
                            try:
                                callback(alert)
                            except Exception as e:
                                self.logger.error(f"Alert callback error: {e}")
        
        return health
    
    async def monitor_all_bots(self):
        """Monitor all registered bots."""
        running_bots = self.orchestrator.list_running_bots()
        
        for bot_info in running_bots:
            await self.check_bot_health(bot_info['name'])
    
    async def start_monitoring(self):
        """Start background health monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Health monitoring started")
    
    async def stop_monitoring(self):
        """Stop background health monitoring."""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Health monitoring stopped")
    
    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                await self.monitor_all_bots()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(5)
    
    def add_alert_callback(self, callback: Callable[[HealthAlert], None]):
        """Add callback for health alerts."""
        self.alert_callbacks.append(callback)
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get summary of all bot health."""
        summary = {
            'total_bots': 0,
            'healthy': 0,
            'warning': 0,
            'critical': 0,
            'dead': 0,
            'total_memory_mb': 0.0,
            'average_cpu_percent': 0.0,
            'bots': []
        }
        
        running_bots = self.orchestrator.list_running_bots()
        summary['total_bots'] = len(running_bots)
        
        cpu_samples = []
        
        for bot_info in running_bots:
            health = self.orchestrator.get_bot_health(bot_info['name'])
            if health:
                level = self.evaluate_health_level(health)
                
                if level == HealthLevel.HEALTHY:
                    summary['healthy'] += 1
                elif level == HealthLevel.WARNING:
                    summary['warning'] += 1
                elif level == HealthLevel.CRITICAL:
                    summary['critical'] += 1
                elif level == HealthLevel.DEAD:
                    summary['dead'] += 1
                
                summary['total_memory_mb'] += health.memory_mb
                cpu_samples.append(health.cpu_percent)
                
                bot_summary = {
                    'name': bot_info['name'],
                    'level': level.value,
                    'memory_mb': round(health.memory_mb, 2),
                    'cpu_percent': round(health.cpu_percent, 2),
                    'uptime_seconds': round(health.uptime_seconds)
                }
                
                # Add historical data if available
                if bot_info['name'] in self.health_history:
                    history = self.health_history[bot_info['name']]
                    bot_summary['avg_memory_mb'] = round(history.get_average_memory(), 2)
                    bot_summary['avg_cpu_percent'] = round(history.get_average_cpu(), 2)
                    bot_summary['uptime_percentage'] = round(history.get_uptime_percentage(), 2)
                
                summary['bots'].append(bot_summary)
        
        if cpu_samples:
            summary['average_cpu_percent'] = round(sum(cpu_samples) / len(cpu_samples), 2)
        
        summary['total_memory_mb'] = round(summary['total_memory_mb'], 2)
        
        return summary
    
    def display_health_dashboard(self):
        """Display live health dashboard."""
        summary = self.get_health_summary()
        
        # Create table
        table = Table(title="Bot Health Dashboard")
        table.add_column("Bot Name", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Memory (MB)", justify="right")
        table.add_column("CPU (%)", justify="right")
        table.add_column("Uptime", justify="right")
        table.add_column("Alerts", style="yellow")
        
        for bot in summary['bots']:
            # Status color
            status_colors = {
                'healthy': 'green',
                'warning': 'yellow',
                'critical': 'red',
                'dead': 'red bold'
            }
            status_color = status_colors.get(bot['level'], 'white')
            
            # Format uptime
            uptime = bot['uptime_seconds']
            if uptime > 3600:
                uptime_str = f"{uptime // 3600}h {(uptime % 3600) // 60}m"
            elif uptime > 60:
                uptime_str = f"{uptime // 60}m {uptime % 60}s"
            else:
                uptime_str = f"{uptime}s"
            
            # Get recent alerts
            alerts = self.active_alerts.get(bot['name'], [])
            alert_count = len(alerts)
            alert_str = f"{alert_count} alerts" if alert_count > 0 else "-"
            
            table.add_row(
                bot['name'],
                f"[{status_color}]{bot['level'].upper()}[/{status_color}]",
                str(bot['memory_mb']),
                str(bot['cpu_percent']),
                uptime_str,
                alert_str
            )
        
        # Summary panel
        summary_text = (
            f"Total Bots: {summary['total_bots']} | "
            f"[green]Healthy: {summary['healthy']}[/green] | "
            f"[yellow]Warning: {summary['warning']}[/yellow] | "
            f"[red]Critical: {summary['critical']}[/red] | "
            f"Total Memory: {summary['total_memory_mb']}MB | "
            f"Avg CPU: {summary['average_cpu_percent']}%"
        )
        
        self.console.print(Panel(summary_text, title="System Summary"))
        self.console.print(table)
        
        # Show recent alerts if any
        if self.active_alerts:
            self.console.print("\n[bold]Recent Alerts:[/bold]")
            for bot_name, alerts in self.active_alerts.items():
                for alert in alerts[-3:]:  # Show last 3 alerts per bot
                    self.console.print(f"  {alert.format()}")