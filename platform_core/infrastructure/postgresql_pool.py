"""
PostgreSQL Connection Pool Infrastructure
========================================

Extracted database patterns from MultiCordOG and adapted for pure PostgreSQL.
Provides async connection pooling with health checks and transaction management.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, AsyncGenerator, List, Set
from datetime import datetime, timezone
import json
import re

try:
    import asyncpg
    from asyncpg import Pool, Connection
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    asyncpg = None
    Pool = None
    Connection = None


class SecureQueryBuilder:
    """Secure query builder to prevent SQL injection attacks."""
    
    # Whitelisted table names that are allowed for dynamic queries
    ALLOWED_TABLES: Set[str] = {
        'server_nodes',
        'bot_instances', 
        'process_registry',
        'platform_features',
        'instance_feature_assignments',
        'bot_templates',
        'configuration_history',
        'performance_metrics'
    }
    
    # Whitelisted column names for cleanup operations
    ALLOWED_TIMESTAMP_COLUMNS: Set[str] = {
        'created_at',
        'updated_at', 
        'started_at',
        'last_heartbeat',
        'last_used',
        'recorded_at',
        'timestamp'
    }
    
    @classmethod
    def validate_identifier(cls, identifier: str, identifier_type: str = "identifier") -> str:
        """Validate and sanitize database identifiers to prevent SQL injection."""
        if not identifier:
            raise ValueError(f"Empty {identifier_type} not allowed")
        
        # Check for valid PostgreSQL identifier format
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
            raise ValueError(f"Invalid {identifier_type} format: {identifier}")
        
        # Prevent reserved words and suspicious patterns
        suspicious_patterns = {
            'drop', 'delete', 'truncate', 'alter', 'create', 
            'insert', 'update', 'grant', 'revoke', 'exec',
            '--', '/*', '*/', ';', 'union', 'select'
        }
        
        identifier_lower = identifier.lower()
        if any(pattern in identifier_lower for pattern in suspicious_patterns):
            raise ValueError(f"Suspicious {identifier_type} contains reserved words: {identifier}")
        
        return identifier
    
    @classmethod
    def validate_table_name(cls, table_name: str) -> str:
        """Validate table name against whitelist."""
        validated = cls.validate_identifier(table_name, "table name")
        
        if validated not in cls.ALLOWED_TABLES:
            raise ValueError(
                f"Table '{validated}' not in allowed tables. "
                f"Allowed: {sorted(cls.ALLOWED_TABLES)}"
            )
        
        return validated
    
    @classmethod
    def validate_column_name(cls, column_name: str, allowed_columns: Optional[Set[str]] = None) -> str:
        """Validate column name, optionally against a whitelist."""
        validated = cls.validate_identifier(column_name, "column name")
        
        if allowed_columns and validated not in allowed_columns:
            raise ValueError(
                f"Column '{validated}' not in allowed columns. "
                f"Allowed: {sorted(allowed_columns)}"
            )
        
        return validated
    
    @classmethod
    def build_cleanup_query(cls, table_name: str, timestamp_column: str, days_old: int) -> tuple[str, tuple]:
        """Build a safe cleanup query with parameterized values."""
        # Validate inputs
        safe_table = cls.validate_table_name(table_name)
        safe_column = cls.validate_column_name(timestamp_column, cls.ALLOWED_TIMESTAMP_COLUMNS)
        
        if not isinstance(days_old, int) or days_old < 1 or days_old > 3650:  # Max 10 years
            raise ValueError(f"Invalid days_old value: {days_old}. Must be 1-3650.")
        
        # Build query with validated identifiers (safe to use in f-string after validation)
        query = f"DELETE FROM {safe_table} WHERE {safe_column} < NOW() - INTERVAL '%s days'"
        params = (days_old,)
        
        return query, params
    
    @classmethod
    def build_exists_query(cls, table_name: str, conditions: Dict[str, Any]) -> tuple[str, List[Any]]:
        """Build a safe EXISTS query with validated identifiers."""
        safe_table = cls.validate_table_name(table_name)
        
        if not conditions:
            raise ValueError("At least one condition is required for EXISTS query")
        
        where_clauses = []
        params = []
        
        for i, (column, value) in enumerate(conditions.items(), 1):
            # Validate column name
            safe_column = cls.validate_column_name(column)
            where_clauses.append(f"{safe_column} = ${i}")
            params.append(value)
        
        query = f"SELECT EXISTS(SELECT 1 FROM {safe_table} WHERE {' AND '.join(where_clauses)})"
        
        return query, params
    
    @classmethod 
    def build_count_query(cls, table_name: str, conditions: Optional[Dict[str, Any]] = None) -> tuple[str, List[Any]]:
        """Build a safe COUNT query with validated identifiers."""
        safe_table = cls.validate_table_name(table_name)
        params = []
        
        if conditions:
            where_clauses = []
            for i, (column, value) in enumerate(conditions.items(), 1):
                safe_column = cls.validate_column_name(column)
                where_clauses.append(f"{safe_column} = ${i}")
                params.append(value)
            
            query = f"SELECT COUNT(*) as count FROM {safe_table} WHERE {' AND '.join(where_clauses)}"
        else:
            query = f"SELECT COUNT(*) as count FROM {safe_table}"
        
        return query, params


class PostgreSQLConnectionPool:
    """
    PostgreSQL connection pool with health monitoring and transaction management.
    
    Extracted from MultiCordOG database patterns and enhanced for platform infrastructure.
    """
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 5432,
                 database: str = "multicord_platform",
                 user: str = "postgres",
                 password: str = "",
                 min_connections: int = 5,
                 max_connections: int = 20,
                 ssl_mode: str = "require",
                 logger: Optional[logging.Logger] = None):
        """
        Initialize PostgreSQL connection pool.
        
        Args:
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            user: Database user
            password: Database password
            min_connections: Minimum pool connections
            max_connections: Maximum pool connections
            ssl_mode: SSL/TLS mode ('require', 'prefer', 'disable')
            logger: Logger instance
        """
        if not HAS_ASYNCPG:
            raise ImportError("asyncpg is required. Install with: pip install asyncpg")
        
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.ssl_mode = ssl_mode
        self.logger = logger or logging.getLogger(__name__)
        
        self._pool: Optional[Pool] = None
        self._connected = False
        
    async def initialize(self) -> None:
        """Initialize the connection pool."""
        try:
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=self.min_connections,
                max_size=self.max_connections,
                command_timeout=30,
                ssl=self.ssl_mode,  # Configurable SSL/TLS encryption
                server_settings={
                    'application_name': 'MultiCord Platform',
                    'jit': 'off'  # Disable JIT for better startup performance
                }
            )
            
            # Test connection
            async with self._pool.acquire() as conn:
                await conn.execute('SELECT 1')
            
            self._connected = True
            self.logger.info(f"PostgreSQL pool initialized: {self.host}:{self.port}/{self.database}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            raise
    
    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._connected = False
            self.logger.info("PostgreSQL pool closed")
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[Connection, None]:
        """
        Get a connection from the pool with automatic cleanup.
        
        Yields:
            Connection: PostgreSQL connection
        """
        if not self._connected or not self._pool:
            raise RuntimeError("Connection pool not initialized")
        
        conn = None
        try:
            conn = await self._pool.acquire()
            yield conn
        finally:
            if conn:
                await self._pool.release(conn)
    
    @asynccontextmanager
    async def get_transaction(self) -> AsyncGenerator[Connection, None]:
        """
        Get a connection with an active transaction.
        
        Yields:
            Connection: PostgreSQL connection with active transaction
        """
        async with self.get_connection() as conn:
            async with conn.transaction():
                yield conn
    
    async def execute(self, query: str, *args, timeout: float = 30.0) -> None:
        """Execute a query without returning results."""
        async with self.get_connection() as conn:
            await conn.execute(query, *args, timeout=timeout)
    
    async def fetch_one(self, query: str, *args, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Fetch a single row as dictionary."""
        async with self.get_connection() as conn:
            row = await conn.fetchrow(query, *args, timeout=timeout)
            return dict(row) if row else None
    
    async def fetch_all(self, query: str, *args, timeout: float = 30.0) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dictionaries."""
        async with self.get_connection() as conn:
            rows = await conn.fetch(query, *args, timeout=timeout)
            return [dict(row) for row in rows]
    
    async def execute_many(self, query: str, args_list: List[tuple], timeout: float = 30.0) -> None:
        """Execute query multiple times with different parameters."""
        async with self.get_transaction() as conn:
            await conn.executemany(query, args_list, timeout=timeout)
    
    async def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        if not self._pool:
            return {"error": "Pool not initialized"}
        
        return {
            "size": self._pool.get_size(),
            "min_size": self._pool.get_min_size(),
            "max_size": self._pool.get_max_size(),
            "idle_connections": self._pool.get_idle_size(),
            "connected": self._connected,
            "database": self.database,
            "host": self.host,
            "port": self.port
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the connection pool."""
        try:
            start_time = datetime.now()
            
            async with self.get_connection() as conn:
                # Test basic query
                result = await conn.fetchval('SELECT 1')
                
                # Test database timestamp
                db_time = await conn.fetchval('SELECT NOW()')
                
                # Calculate response time
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time, 2),
                    "database_time": db_time.isoformat(),
                    "test_query_result": result,
                    "pool_stats": await self.get_pool_stats()
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "pool_stats": await self.get_pool_stats()
            }
    
    async def run_migration(self, migration_sql: str) -> bool:
        """Run a database migration script."""
        try:
            async with self.get_transaction() as conn:
                # Split migration into individual statements
                statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
                
                for statement in statements:
                    if statement.upper().startswith(('CREATE', 'ALTER', 'INSERT', 'UPDATE')):
                        await conn.execute(statement)
                
                self.logger.info("Database migration completed successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            return False
    
    async def cleanup_old_data(self, table: str, timestamp_column: str, days_old: int = 30) -> int:
        """Clean up old data from a table using secure query builder."""
        try:
            # Use secure query builder to prevent SQL injection
            query, params = SecureQueryBuilder.build_cleanup_query(table, timestamp_column, days_old)
            
            async with self.get_connection() as conn:
                result = await conn.execute(query, *params)
                # Extract number from result string like "DELETE 42"
                deleted_count = int(result.split()[-1]) if result.split()[-1].isdigit() else 0
                
                if deleted_count > 0:
                    self.logger.info(f"Cleaned up {deleted_count} old records from {table}")
                
                return deleted_count
                
        except ValueError as e:
            self.logger.error(f"Invalid parameters for cleanup: {e}")
            return 0
        except Exception as e:
            self.logger.error(f"Failed to cleanup {table}: {e}")
            return 0


class PostgreSQLRepository:
    """
    Base repository class with common PostgreSQL operations.
    
    Provides shared functionality for all PostgreSQL-based repositories.
    """
    
    def __init__(self, pool: PostgreSQLConnectionPool, logger: Optional[logging.Logger] = None):
        """
        Initialize repository with connection pool.
        
        Args:
            pool: PostgreSQL connection pool
            logger: Logger instance
        """
        self.pool = pool
        self.logger = logger or logging.getLogger(__name__)
    
    async def exists(self, table: str, conditions: Dict[str, Any]) -> bool:
        """Check if a record exists with given conditions using secure query builder."""
        try:
            # Use secure query builder to prevent SQL injection
            query, params = SecureQueryBuilder.build_exists_query(table, conditions)
            
            result = await self.pool.fetch_one(query, *params)
            return result["exists"] if result else False
        except ValueError as e:
            self.logger.error(f"Invalid parameters for exists query: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error checking existence in {table}: {e}")
            return False
    
    async def count(self, table: str, conditions: Optional[Dict[str, Any]] = None) -> int:
        """Count records in table with optional conditions using secure query builder."""
        try:
            # Use secure query builder to prevent SQL injection
            query, params = SecureQueryBuilder.build_count_query(table, conditions)
            
            result = await self.pool.fetch_one(query, *params)
            return result["count"] if result else 0
        except ValueError as e:
            self.logger.error(f"Invalid parameters for count query: {e}")
            return 0
        except Exception as e:
            self.logger.error(f"Error counting records in {table}: {e}")
            return 0