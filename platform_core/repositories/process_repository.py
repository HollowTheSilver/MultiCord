"""
Process Repository - PostgreSQL Data Access Layer
=================================================

Repository for ProcessInfo entities with PostgreSQL persistence.
Handles process registry operations with health monitoring integration.
"""

from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime, timezone

from ..infrastructure.postgresql_pool import PostgreSQLRepository, PostgreSQLConnectionPool
from ..entities.process_info import ProcessInfo, ProcessSource


class ProcessRepository(PostgreSQLRepository):
    """
    PostgreSQL repository for ProcessInfo entities.
    
    Provides data access operations for the process registry with
    health monitoring and conflict resolution capabilities.
    """
    
    def __init__(self, pool: PostgreSQLConnectionPool, logger=None):
        """Initialize process repository."""
        super().__init__(pool, logger)
    
    async def save_process(self, process_info: ProcessInfo, conn=None) -> None:
        """Save or update a process in the registry."""
        try:
            query = """
                INSERT INTO process_registry (
                    process_id, instance_id, pid, started_at, source, log_file_path,
                    restart_count, last_restart, health_status, created_at,
                    memory_usage_mb, cpu_percent, terminal_instance
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
                )
                ON CONFLICT (process_id) DO UPDATE SET
                    pid = EXCLUDED.pid,
                    restart_count = EXCLUDED.restart_count,
                    last_restart = EXCLUDED.last_restart,
                    health_status = EXCLUDED.health_status,
                    memory_usage_mb = EXCLUDED.memory_usage_mb,
                    cpu_percent = EXCLUDED.cpu_percent,
                    terminal_instance = EXCLUDED.terminal_instance
            """
            
            data = process_info.for_postgresql()
            
            # Use provided connection or get one from pool
            if conn:
                await conn.execute(
                    query,
                    data["process_id"], data["instance_id"], data["pid"],
                    data["started_at"], data["source"], data["log_file_path"],
                    data["restart_count"], data["last_restart"], data["health_status"],
                    data["created_at"], data["memory_usage_mb"], data["cpu_percent"],
                    data["terminal_instance"]
                )
            else:
                await self.pool.execute(
                    query,
                    data["process_id"], data["instance_id"], data["pid"],
                    data["started_at"], data["source"], data["log_file_path"],
                    data["restart_count"], data["last_restart"], data["health_status"],
                    data["created_at"], data["memory_usage_mb"], data["cpu_percent"],
                    data["terminal_instance"]
                )
            
            self.logger.info(f"Saved process {process_info.client_id} (PID: {process_info.pid})")
            
        except Exception as e:
            self.logger.error(f"Failed to save process {process_info.client_id}: {e}")
            raise
    
    async def find_by_client_id(self, client_id: str) -> Optional[ProcessInfo]:
        """Find process by client ID."""
        try:
            query = """
                SELECT pr.*, bi.client_id
                FROM process_registry pr
                JOIN bot_instances bi ON pr.instance_id = bi.instance_id
                WHERE bi.client_id = $1
                ORDER BY pr.created_at DESC
                LIMIT 1
            """
            
            row = await self.pool.fetch_one(query, client_id)
            if row:
                return ProcessInfo.from_postgresql(row, client_id)
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to find process for client {client_id}: {e}")
            return None
    
    async def find_by_instance_id(self, instance_id: UUID) -> Optional[ProcessInfo]:
        """Find process by instance ID."""
        try:
            query = """
                SELECT pr.*, bi.client_id
                FROM process_registry pr
                JOIN bot_instances bi ON pr.instance_id = bi.instance_id
                WHERE pr.instance_id = $1
            """
            
            row = await self.pool.fetch_one(query, instance_id)
            if row:
                return ProcessInfo.from_postgresql(row, row["client_id"])
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to find process for instance {instance_id}: {e}")
            return None
    
    async def find_by_pid(self, pid: int) -> Optional[ProcessInfo]:
        """Find process by PID."""
        try:
            query = """
                SELECT pr.*, bi.client_id
                FROM process_registry pr
                JOIN bot_instances bi ON pr.instance_id = bi.instance_id
                WHERE pr.pid = $1
            """
            
            row = await self.pool.fetch_one(query, pid)
            if row:
                return ProcessInfo.from_postgresql(row, row["client_id"])
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to find process for PID {pid}: {e}")
            return None
    
    async def find_active_processes(self, node_id: Optional[UUID] = None) -> List[ProcessInfo]:
        """Find all active processes, optionally filtered by node."""
        try:
            if node_id:
                query = """
                    SELECT pr.*, bi.client_id
                    FROM process_registry pr
                    JOIN bot_instances bi ON pr.instance_id = bi.instance_id
                    WHERE bi.node_id = $1
                    ORDER BY pr.started_at DESC
                """
                rows = await self.pool.fetch_all(query, node_id)
            else:
                query = """
                    SELECT pr.*, bi.client_id
                    FROM process_registry pr
                    JOIN bot_instances bi ON pr.instance_id = bi.instance_id
                    ORDER BY pr.started_at DESC
                """
                rows = await self.pool.fetch_all(query)
            
            processes = []
            for row in rows:
                process_info = ProcessInfo.from_postgresql(row, row["client_id"])
                # Only include processes that are actually running
                if process_info.is_running:
                    processes.append(process_info)
            
            return processes
            
        except Exception as e:
            self.logger.error(f"Failed to find active processes: {e}")
            return []
    
    async def find_all_processes(self, node_id: Optional[UUID] = None) -> List[ProcessInfo]:
        """Find all registered processes (both running and stopped), optionally filtered by node."""
        try:
            if node_id:
                query = """
                    SELECT pr.*, bi.client_id
                    FROM process_registry pr
                    JOIN bot_instances bi ON pr.instance_id = bi.instance_id
                    WHERE bi.node_id = $1
                    ORDER BY pr.started_at DESC
                """
                rows = await self.pool.fetch_all(query, node_id)
            else:
                query = """
                    SELECT pr.*, bi.client_id
                    FROM process_registry pr
                    JOIN bot_instances bi ON pr.instance_id = bi.instance_id
                    ORDER BY pr.started_at DESC
                """
                rows = await self.pool.fetch_all(query)
            
            processes = []
            for row in rows:
                process_info = ProcessInfo.from_postgresql(row, row["client_id"])
                processes.append(process_info)  # Include all processes, regardless of running status
            
            return processes
            
        except Exception as e:
            self.logger.error(f"Failed to find all processes: {e}")
            return []
    
    async def find_processes_by_source(self, source: ProcessSource, node_id: Optional[UUID] = None) -> List[ProcessInfo]:
        """Find processes by source (discovered/launched)."""
        try:
            if node_id:
                query = """
                    SELECT pr.*, bi.client_id
                    FROM process_registry pr
                    JOIN bot_instances bi ON pr.instance_id = bi.instance_id
                    WHERE pr.source = $1 AND bi.node_id = $2
                    ORDER BY pr.started_at DESC
                """
                rows = await self.pool.fetch_all(query, source.value, node_id)
            else:
                query = """
                    SELECT pr.*, bi.client_id
                    FROM process_registry pr
                    JOIN bot_instances bi ON pr.instance_id = bi.instance_id
                    WHERE pr.source = $1
                    ORDER BY pr.started_at DESC
                """
                rows = await self.pool.fetch_all(query, source.value)
            
            return [ProcessInfo.from_postgresql(row, row["client_id"]) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Failed to find processes by source {source}: {e}")
            return []
    
    async def remove_process(self, process_id: UUID) -> bool:
        """Remove a process from the registry."""
        try:
            query = "DELETE FROM process_registry WHERE process_id = $1"
            await self.pool.execute(query, process_id)
            self.logger.info(f"Removed process {process_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove process {process_id}: {e}")
            return False
    
    async def remove_process_by_client_id(self, client_id: str) -> bool:
        """Remove process by client ID."""
        try:
            query = """
                DELETE FROM process_registry 
                WHERE instance_id IN (
                    SELECT instance_id FROM bot_instances WHERE client_id = $1
                )
            """
            await self.pool.execute(query, client_id)
            self.logger.info(f"Removed process for client {client_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove process for client {client_id}: {e}")
            return False
    
    async def update_health_metrics(self, process_id: UUID, health_status: Dict[str, Any],
                                  memory_mb: float, cpu_percent: float) -> bool:
        """Update health metrics for a process."""
        try:
            query = """
                UPDATE process_registry 
                SET health_status = $2, memory_usage_mb = $3, cpu_percent = $4
                WHERE process_id = $1
            """
            await self.pool.execute(query, process_id, health_status, memory_mb, cpu_percent)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update health metrics for process {process_id}: {e}")
            return False
    
    async def increment_restart_count(self, process_id: UUID) -> bool:
        """Increment restart count for a process."""
        try:
            query = """
                UPDATE process_registry 
                SET restart_count = restart_count + 1, last_restart = $2
                WHERE process_id = $1
            """
            await self.pool.execute(query, process_id, datetime.now(timezone.utc))
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to increment restart count for process {process_id}: {e}")
            return False
    
    async def cleanup_dead_processes(self) -> int:
        """Remove dead processes from registry and return count."""
        try:
            # First, get all processes to check their status
            processes = await self.find_active_processes()
            dead_process_ids = []
            
            for process_info in processes:
                if not process_info.is_running:
                    dead_process_ids.append(process_info.process_id)
            
            if dead_process_ids:
                # Remove dead processes in batch
                query = "DELETE FROM process_registry WHERE process_id = ANY($1)"
                await self.pool.execute(query, dead_process_ids)
                
                self.logger.info(f"Cleaned up {len(dead_process_ids)} dead processes")
            
            return len(dead_process_ids)
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup dead processes: {e}")
            return 0
    
    async def get_process_statistics(self, node_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get process registry statistics."""
        try:
            base_query = """
                SELECT 
                    COUNT(*) as total_processes,
                    COUNT(CASE WHEN source = 'launched' THEN 1 END) as launched_count,
                    COUNT(CASE WHEN source = 'discovered' THEN 1 END) as discovered_count,
                    AVG(restart_count) as avg_restart_count,
                    AVG(memory_usage_mb) as avg_memory_mb,
                    AVG(cpu_percent) as avg_cpu_percent
                FROM process_registry pr
                JOIN bot_instances bi ON pr.instance_id = bi.instance_id
            """
            
            if node_id:
                query = base_query + " WHERE bi.node_id = $1"
                row = await self.pool.fetch_one(query, node_id)
            else:
                row = await self.pool.fetch_one(base_query)
            
            if row:
                return {
                    "total_processes": row["total_processes"],
                    "launched_count": row["launched_count"],
                    "discovered_count": row["discovered_count"],
                    "average_restart_count": float(row["avg_restart_count"] or 0),
                    "average_memory_mb": float(row["avg_memory_mb"] or 0),
                    "average_cpu_percent": float(row["avg_cpu_percent"] or 0),
                    "node_id": str(node_id) if node_id else "all_nodes"
                }
            
            return {"error": "No data available"}
            
        except Exception as e:
            self.logger.error(f"Failed to get process statistics: {e}")
            return {"error": str(e)}