"""
ProcessInfo Entity - Core Domain Entity
=======================================

Extracted from MultiCordOG with PostgreSQL persistence fields.
Preserves health monitoring capabilities while adding clean architecture design.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from enum import Enum
from uuid import UUID, uuid4
import psutil


class ProcessSource(Enum):
    """Source of process information."""
    DISCOVERED = "discovered"
    LAUNCHED = "launched"


@dataclass
class HealthStatus:
    """Process health status information."""
    is_running: bool
    memory_mb: float
    cpu_percent: float
    uptime_seconds: float
    last_check: datetime
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_running": self.is_running,
            "memory_mb": self.memory_mb,
            "cpu_percent": self.cpu_percent,
            "uptime_seconds": self.uptime_seconds,
            "last_check": self.last_check.isoformat(),
            "error_message": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HealthStatus':
        """Create HealthStatus from dictionary."""
        return cls(
            is_running=data["is_running"],
            memory_mb=data["memory_mb"],
            cpu_percent=data["cpu_percent"],
            uptime_seconds=data["uptime_seconds"],
            last_check=datetime.fromisoformat(data["last_check"]),
            error_message=data.get("error_message")
        )


@dataclass
class ProcessInfo:
    """
    Core process information entity with PostgreSQL integration.
    
    Preserves all health monitoring capabilities from MultiCordOG while
    adding PostgreSQL persistence fields for clean architecture.
    """
    # Core identifiers
    process_id: UUID
    instance_id: UUID
    client_id: str
    pid: int
    
    # Timestamps
    started_at: datetime
    created_at: datetime
    last_restart: Optional[datetime] = None
    
    # Process metadata
    source: ProcessSource = ProcessSource.LAUNCHED
    restart_count: int = 0
    log_file_path: Optional[str] = None
    terminal_instance: Optional[str] = None
    
    # Health monitoring
    memory_usage_mb: float = 0.0
    cpu_percent: float = 0.0
    health_status: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.process_id is None:
            self.process_id = uuid4()
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    @property
    def is_running(self) -> bool:
        """Check if process is actually running using psutil."""
        try:
            proc = psutil.Process(self.pid)
            return proc.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def get_current_health_status(self) -> HealthStatus:
        """Get current health status with live monitoring."""
        try:
            proc = psutil.Process(self.pid)
            
            if not proc.is_running():
                return HealthStatus(
                    is_running=False,
                    memory_mb=0.0,
                    cpu_percent=0.0,
                    uptime_seconds=0.0,
                    last_check=datetime.now(timezone.utc),
                    error_message="Process not running"
                )
            
            # Get current metrics
            memory_info = proc.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            cpu_percent = proc.cpu_percent(interval=0.1)
            uptime_seconds = (datetime.now(timezone.utc) - self.started_at).total_seconds()
            
            # Update instance fields
            self.memory_usage_mb = memory_mb
            self.cpu_percent = cpu_percent
            
            return HealthStatus(
                is_running=True,
                memory_mb=memory_mb,
                cpu_percent=cpu_percent,
                uptime_seconds=uptime_seconds,
                last_check=datetime.now(timezone.utc)
            )
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            return HealthStatus(
                is_running=False,
                memory_mb=0.0,
                cpu_percent=0.0,
                uptime_seconds=0.0,
                last_check=datetime.now(timezone.utc),
                error_message=str(e)
            )
        except Exception as e:
            return HealthStatus(
                is_running=False,
                memory_mb=self.memory_usage_mb,
                cpu_percent=self.cpu_percent,
                uptime_seconds=(datetime.now(timezone.utc) - self.started_at).total_seconds(),
                last_check=datetime.now(timezone.utc),
                error_message=f"Health check error: {str(e)}"
            )

    def update_health_metrics(self) -> None:
        """Update health metrics from current system state."""
        health = self.get_current_health_status()
        self.memory_usage_mb = health.memory_mb
        self.cpu_percent = health.cpu_percent
        self.health_status = health.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "process_id": str(self.process_id),
            "instance_id": str(self.instance_id),
            "client_id": self.client_id,
            "pid": self.pid,
            "started_at": self.started_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "last_restart": self.last_restart.isoformat() if self.last_restart else None,
            "source": self.source.value,
            "restart_count": self.restart_count,
            "log_file_path": self.log_file_path,
            "terminal_instance": self.terminal_instance,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_percent": self.cpu_percent,
            "health_status": self.health_status
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessInfo':
        """Create ProcessInfo from dictionary."""
        return cls(
            process_id=UUID(data["process_id"]),
            instance_id=UUID(data["instance_id"]),
            client_id=data["client_id"],
            pid=data["pid"],
            started_at=datetime.fromisoformat(data["started_at"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_restart=datetime.fromisoformat(data["last_restart"]) if data.get("last_restart") else None,
            source=ProcessSource(data["source"]),
            restart_count=data["restart_count"],
            log_file_path=data.get("log_file_path"),
            terminal_instance=data.get("terminal_instance"),
            memory_usage_mb=data.get("memory_usage_mb", 0.0),
            cpu_percent=data.get("cpu_percent", 0.0),
            health_status=data.get("health_status")
        )

    def for_postgresql(self) -> Dict[str, Any]:
        """Convert to format suitable for PostgreSQL insertion."""
        import json
        return {
            "process_id": self.process_id,
            "instance_id": self.instance_id,
            "pid": self.pid,
            "started_at": self.started_at,
            "source": self.source.value,
            "log_file_path": self.log_file_path,
            "restart_count": self.restart_count,
            "last_restart": self.last_restart,
            "health_status": json.dumps(self.health_status or {}),
            "created_at": self.created_at,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_percent": self.cpu_percent,
            "terminal_instance": self.terminal_instance
        }

    @classmethod
    def from_postgresql(cls, row: Dict[str, Any], client_id: str) -> 'ProcessInfo':
        """Create ProcessInfo from PostgreSQL row."""
        return cls(
            process_id=row["process_id"],
            instance_id=row["instance_id"],
            client_id=client_id,
            pid=row["pid"],
            started_at=row["started_at"],
            created_at=row["created_at"],
            last_restart=row.get("last_restart"),
            source=ProcessSource(row["source"]),
            restart_count=row.get("restart_count", 0),
            log_file_path=row.get("log_file_path"),
            terminal_instance=row.get("terminal_instance"),
            memory_usage_mb=row.get("memory_usage_mb", 0.0),
            cpu_percent=row.get("cpu_percent", 0.0),
            health_status=row.get("health_status", {})
        )