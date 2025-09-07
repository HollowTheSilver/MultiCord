"""
Log Aggregation Service
======================

Centralized logging service for MultiCord platform.
Provides structured log collection, aggregation, and PostgreSQL persistence.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import UUID, uuid4
from enum import Enum
import re

from ..infrastructure.postgresql_pool import PostgreSQLConnectionPool
from ..entities.process_info import ProcessInfo


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogSource(Enum):
    """Log source enumeration."""
    BOT_PROCESS = "bot_process"
    PLATFORM = "platform"
    STRATEGY = "strategy"
    FEATURE = "feature"
    HEALTH_CHECK = "health_check"


@dataclass
class StructuredLogEntry:
    """Structured log entry with metadata."""
    
    log_id: UUID
    timestamp: datetime
    level: LogLevel
    source: LogSource
    instance_id: Optional[UUID]
    client_id: Optional[str]
    process_id: Optional[int]
    message: str
    metadata: Dict[str, Any]
    raw_log_line: Optional[str] = None
    parsed_fields: Optional[Dict[str, Any]] = None
    tags: List[str] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}
    
    @classmethod
    def from_raw_log(cls, 
                    raw_line: str,
                    source: LogSource,
                    instance_id: UUID = None,
                    client_id: str = None,
                    process_id: int = None) -> 'StructuredLogEntry':
        """Create structured log entry from raw log line."""
        
        # Parse log level and message
        level, message, parsed_fields = cls._parse_log_line(raw_line)
        
        return cls(
            log_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            level=level,
            source=source,
            instance_id=instance_id,
            client_id=client_id,
            process_id=process_id,
            message=message,
            metadata=parsed_fields.get('metadata', {}),
            raw_log_line=raw_line,
            parsed_fields=parsed_fields,
            tags=parsed_fields.get('tags', [])
        )
    
    @staticmethod
    def _parse_log_line(raw_line: str) -> tuple[LogLevel, str, Dict[str, Any]]:
        """Parse raw log line to extract level, message, and fields."""
        try:
            # Common log patterns
            patterns = [
                # Discord.py pattern: YYYY-MM-DD HH:MM:SS,mmm LEVEL    discord.client Message
                r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+(\w+)\s+(\w+(?:\.\w+)*)\s+(.+)',
                # Python logging: LEVEL:logger_name:Message
                r'(\w+):([^:]+):(.+)',
                # Simple format: [LEVEL] Message
                r'\[(\w+)\]\s*(.+)',
                # Timestamp + level: 2024-01-01 12:00:00 ERROR Message
                r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\w+)\s+(.+)'
            ]
            
            for pattern in patterns:
                match = re.match(pattern, raw_line.strip())
                if match:
                    groups = match.groups()
                    if len(groups) >= 3:
                        level_str = groups[1] if len(groups) >= 3 else groups[0]
                        message = groups[-1]  # Last group is usually the message
                        
                        # Extract metadata
                        parsed_fields = {
                            'pattern_matched': pattern,
                            'groups': groups,
                            'tags': []
                        }
                        
                        # Try to parse log level
                        try:
                            level = LogLevel(level_str.upper())
                        except ValueError:
                            level = LogLevel.INFO
                        
                        return level, message, parsed_fields
            
            # Fallback - couldn't parse, treat as INFO
            return LogLevel.INFO, raw_line, {'pattern_matched': 'fallback'}
            
        except Exception:
            return LogLevel.INFO, raw_line, {'parse_error': True}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'log_id': str(self.log_id),
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value,
            'source': self.source.value,
            'instance_id': str(self.instance_id) if self.instance_id else None,
            'client_id': self.client_id,
            'process_id': self.process_id,
            'message': self.message,
            'metadata': self.metadata,
            'raw_log_line': self.raw_log_line,
            'parsed_fields': self.parsed_fields,
            'tags': self.tags
        }


class LogAggregationService:
    """
    Service for collecting, parsing, and aggregating logs from bot processes.
    
    Provides structured logging with PostgreSQL persistence following
    MultiCord's clean architecture principles.
    """
    
    def __init__(self,
                 db_pool: PostgreSQLConnectionPool = None,
                 log_retention_days: int = 30,
                 max_log_entries_per_batch: int = 1000,
                 logger: logging.Logger = None):
        """
        Initialize log aggregation service.
        
        Args:
            db_pool: PostgreSQL connection pool for persistence
            log_retention_days: Days to retain logs before cleanup
            max_log_entries_per_batch: Maximum entries to process per batch
            logger: Logger instance for service operations
        """
        self.db_pool = db_pool
        self.log_retention_days = log_retention_days
        self.max_log_entries_per_batch = max_log_entries_per_batch
        self.logger = logger or logging.getLogger(__name__)
        
        # In-memory log buffer for batching
        self._log_buffer: List[StructuredLogEntry] = []
        self._buffer_lock = asyncio.Lock()
        
        # Background tasks
        self._batch_processor_task: Optional[asyncio.Task] = None
        self._retention_cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start the log aggregation service."""
        if self._running:
            return
        
        self._running = True
        self.logger.info("Starting log aggregation service")
        
        # Start background tasks
        self._batch_processor_task = asyncio.create_task(self._batch_processor())
        self._retention_cleanup_task = asyncio.create_task(self._retention_cleanup())
    
    async def stop(self) -> None:
        """Stop the log aggregation service."""
        if not self._running:
            return
        
        self._running = False
        self.logger.info("Stopping log aggregation service")
        
        # Cancel background tasks
        if self._batch_processor_task:
            self._batch_processor_task.cancel()
            try:
                await self._batch_processor_task
            except asyncio.CancelledError:
                pass
        
        if self._retention_cleanup_task:
            self._retention_cleanup_task.cancel()
            try:
                await self._retention_cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Process remaining logs
        await self._process_log_batch()
    
    async def collect_logs_from_file(self, 
                                   log_file_path: Path,
                                   source: LogSource,
                                   instance_id: UUID = None,
                                   client_id: str = None,
                                   process_id: int = None,
                                   tail_lines: int = None) -> int:
        """
        Collect logs from a file and add to aggregation.
        
        Args:
            log_file_path: Path to log file
            source: Source of the logs
            instance_id: Bot instance ID
            client_id: Bot client ID  
            process_id: Process ID
            tail_lines: Number of recent lines to read (None for all)
            
        Returns:
            Number of log entries collected
        """
        try:
            if not log_file_path.exists():
                self.logger.warning(f"Log file does not exist: {log_file_path}")
                return 0
            
            # Read log file
            with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
                if tail_lines:
                    lines = f.readlines()[-tail_lines:]
                else:
                    lines = f.readlines()
            
            # Process each line
            entries_collected = 0
            for line in lines:
                line = line.strip()
                if line:  # Skip empty lines
                    log_entry = StructuredLogEntry.from_raw_log(
                        raw_line=line,
                        source=source,
                        instance_id=instance_id,
                        client_id=client_id,
                        process_id=process_id
                    )
                    await self.add_log_entry(log_entry)
                    entries_collected += 1
            
            self.logger.debug(f"Collected {entries_collected} log entries from {log_file_path}")
            return entries_collected
            
        except Exception as e:
            self.logger.error(f"Failed to collect logs from {log_file_path}: {e}")
            return 0
    
    async def add_log_entry(self, log_entry: StructuredLogEntry) -> None:
        """Add a structured log entry to the aggregation buffer."""
        async with self._buffer_lock:
            self._log_buffer.append(log_entry)
            
            # Trigger batch processing if buffer is full
            if len(self._log_buffer) >= self.max_log_entries_per_batch:
                await self._process_log_batch()
    
    async def get_recent_logs(self,
                            instance_id: UUID = None,
                            client_id: str = None,
                            source: LogSource = None,
                            level: LogLevel = None,
                            limit: int = 100,
                            since: datetime = None) -> List[StructuredLogEntry]:
        """
        Get recent log entries with filtering.
        
        Args:
            instance_id: Filter by bot instance ID
            client_id: Filter by client ID
            source: Filter by log source
            level: Minimum log level
            limit: Maximum entries to return
            since: Only logs after this timestamp
            
        Returns:
            List of structured log entries
        """
        try:
            # For now, return from memory buffer
            # In production, this would query PostgreSQL
            async with self._buffer_lock:
                filtered_logs = []
                
                for log_entry in reversed(self._log_buffer):  # Most recent first
                    # Apply filters
                    if instance_id and log_entry.instance_id != instance_id:
                        continue
                    if client_id and log_entry.client_id != client_id:
                        continue
                    if source and log_entry.source != source:
                        continue
                    if level and log_entry.level.value < level.value:
                        continue
                    if since and log_entry.timestamp < since:
                        continue
                    
                    filtered_logs.append(log_entry)
                    
                    if len(filtered_logs) >= limit:
                        break
                
                return filtered_logs
                
        except Exception as e:
            self.logger.error(f"Failed to get recent logs: {e}")
            return []
    
    async def get_log_statistics(self) -> Dict[str, Any]:
        """Get aggregated log statistics."""
        try:
            async with self._buffer_lock:
                total_logs = len(self._log_buffer)
                
                # Count by level
                level_counts = {}
                source_counts = {}
                client_counts = {}
                
                for log_entry in self._log_buffer:
                    level_counts[log_entry.level.value] = level_counts.get(log_entry.level.value, 0) + 1
                    source_counts[log_entry.source.value] = source_counts.get(log_entry.source.value, 0) + 1
                    if log_entry.client_id:
                        client_counts[log_entry.client_id] = client_counts.get(log_entry.client_id, 0) + 1
                
                return {
                    'total_logs': total_logs,
                    'level_distribution': level_counts,
                    'source_distribution': source_counts,
                    'client_distribution': client_counts,
                    'buffer_size': total_logs,
                    'retention_days': self.log_retention_days
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get log statistics: {e}")
            return {'error': str(e)}
    
    async def _batch_processor(self) -> None:
        """Background task to process log batches."""
        while self._running:
            try:
                await asyncio.sleep(10)  # Process every 10 seconds
                await self._process_log_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in batch processor: {e}")
    
    async def _retention_cleanup(self) -> None:
        """Background task for log retention cleanup."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Check every hour
                await self._cleanup_old_logs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in retention cleanup: {e}")
    
    async def _process_log_batch(self) -> None:
        """Process current log batch."""
        if not self.db_pool:
            return  # No database configured
        
        async with self._buffer_lock:
            if not self._log_buffer:
                return
            
            batch_to_process = self._log_buffer.copy()
            self._log_buffer.clear()
        
        try:
            # In production, this would insert logs into PostgreSQL
            # For now, just log the batch processing
            self.logger.debug(f"Processing log batch with {len(batch_to_process)} entries")
            
            # Placeholder for PostgreSQL insertion
            await self._insert_logs_to_database(batch_to_process)
            
        except Exception as e:
            self.logger.error(f"Failed to process log batch: {e}")
            # Re-add logs to buffer on failure
            async with self._buffer_lock:
                self._log_buffer.extend(batch_to_process)
    
    async def _insert_logs_to_database(self, log_entries: List[StructuredLogEntry]) -> None:
        """Insert log entries into PostgreSQL database."""
        # Placeholder implementation - would use actual PostgreSQL queries
        self.logger.debug(f"Would insert {len(log_entries)} log entries to PostgreSQL")
    
    async def _cleanup_old_logs(self) -> None:
        """Clean up old log entries based on retention policy."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.log_retention_days)
            
            # In production, this would delete from PostgreSQL
            async with self._buffer_lock:
                original_count = len(self._log_buffer)
                self._log_buffer = [
                    log for log in self._log_buffer 
                    if log.timestamp > cutoff_date
                ]
                removed_count = original_count - len(self._log_buffer)
                
                if removed_count > 0:
                    self.logger.info(f"Cleaned up {removed_count} old log entries")
                    
        except Exception as e:
            self.logger.error(f"Failed to cleanup old logs: {e}")