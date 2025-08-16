"""
Database Management Module
=========================

SQLite database abstraction layer for bot data persistence.
"""

import asyncio
import aiosqlite
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from utils.exceptions import DatabaseError, DatabaseConnectionError, DatabaseQueryError


class DatabaseManager:
    """SQLite database manager with connection pooling and migration support."""

    def __init__(self, db_path: Union[str, Path], logger=None):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
            logger: Logger instance
        """
        self.db_path = Path(db_path)
        self.logger = logger
        self._connection_pool = {}
        self._lock = asyncio.Lock()
        self.current_schema_version = 1

    async def initialize(self) -> None:
        """Initialize database and run migrations."""
        try:
            # Ensure database directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Initialize schema and run migrations
            await self._ensure_schema()
            await self._run_migrations()

            if self.logger:
                self.logger.info(f"Database initialized at {self.db_path}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Database initialization failed: {e}")
            raise DatabaseConnectionError(f"Failed to initialize database: {e}")

    @asynccontextmanager
    async def get_connection(self):
        """Get database connection with automatic cleanup."""
        connection = None
        try:
            connection = await aiosqlite.connect(self.db_path)
            connection.row_factory = aiosqlite.Row
            yield connection
        except Exception as e:
            if self.logger:
                self.logger.error(f"Database connection error: {e}")
            raise DatabaseConnectionError(f"Database connection failed: {e}")
        finally:
            if connection:
                await connection.close()

    async def execute(self, query: str, parameters: tuple = ()) -> None:
        """Execute a single query."""
        try:
            async with self.get_connection() as conn:
                await conn.execute(query, parameters)
                await conn.commit()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Query execution failed: {query[:100]}...")
            raise DatabaseQueryError(query, e)

    async def execute_many(self, query: str, parameters_list: List[tuple]) -> None:
        """Execute multiple queries with the same statement."""
        try:
            async with self.get_connection() as conn:
                await conn.executemany(query, parameters_list)
                await conn.commit()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Batch query execution failed: {query[:100]}...")
            raise DatabaseQueryError(query, e)

    async def fetch_one(self, query: str, parameters: tuple = ()) -> Optional[aiosqlite.Row]:
        """Fetch single row from query."""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute(query, parameters)
                return await cursor.fetchone()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Query fetch failed: {query[:100]}...")
            raise DatabaseQueryError(query, e)

    async def fetch_all(self, query: str, parameters: tuple = ()) -> List[aiosqlite.Row]:
        """Fetch all rows from query."""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute(query, parameters)
                return await cursor.fetchall()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Query fetch failed: {query[:100]}...")
            raise DatabaseQueryError(query, e)

    async def _ensure_schema(self) -> None:
        """Ensure basic schema tables exist."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS guild_configs (
            guild_id INTEGER PRIMARY KEY,
            auto_configured BOOLEAN DEFAULT FALSE,
            configured_by INTEGER,
            configured_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS role_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            permission_level INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(guild_id, role_id),
            FOREIGN KEY (guild_id) REFERENCES guild_configs(guild_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS role_classifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            role_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(guild_id, role_id),
            FOREIGN KEY (guild_id) REFERENCES guild_configs(guild_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS command_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            command_node TEXT NOT NULL,
            permission_level INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(guild_id, command_node),
            FOREIGN KEY (guild_id) REFERENCES guild_configs(guild_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS permission_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            permission_node TEXT NOT NULL,
            granted BOOLEAN NOT NULL,
            scope_type TEXT NOT NULL,
            scope_id INTEGER,
            reason TEXT,
            granted_by INTEGER,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            guild_id INTEGER,
            FOREIGN KEY (guild_id) REFERENCES guild_configs(guild_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            permission_data TEXT NOT NULL,
            actor_id INTEGER NOT NULL,
            reason TEXT,
            guild_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (guild_id) REFERENCES guild_configs(guild_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_role_mappings_guild ON role_mappings(guild_id);
        CREATE INDEX IF NOT EXISTS idx_role_classifications_guild ON role_classifications(guild_id);
        CREATE INDEX IF NOT EXISTS idx_command_overrides_guild ON command_overrides(guild_id);
        CREATE INDEX IF NOT EXISTS idx_audit_log_guild ON audit_log(guild_id);
        CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
        """

        async with self.get_connection() as conn:
            await conn.executescript(schema_sql)
            await conn.commit()

    async def _run_migrations(self) -> None:
        """Run any pending database migrations."""
        try:
            # Check current version
            current_version = await self._get_schema_version()

            # Apply migrations if needed
            if current_version < self.current_schema_version:
                await self._apply_migrations(current_version)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Migration failed: {e}")
            raise DatabaseError(f"Migration failed: {e}")

    async def _get_schema_version(self) -> int:
        """Get current schema version."""
        try:
            row = await self.fetch_one("SELECT MAX(version) as version FROM schema_migrations")
            return row["version"] if row and row["version"] else 0
        except:
            return 0

    async def _apply_migrations(self, from_version: int) -> None:
        """Apply migrations from specified version."""
        migrations = {
            1: ("Initial schema", "-- Initial schema already applied")
        }

        for version in range(from_version + 1, self.current_schema_version + 1):
            if version in migrations:
                description, sql = migrations[version]

                if sql.strip() and not sql.strip().startswith("-- "):
                    async with self.get_connection() as conn:
                        await conn.executescript(sql)
                        await conn.commit()

                await self.execute(
                    "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
                    (version, description)
                )

                if self.logger:
                    self.logger.info(f"Applied migration {version}: {description}")

    async def backup_database(self, backup_path: Union[str, Path]) -> None:
        """Create a backup of the database."""
        try:
            backup_path = Path(backup_path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            async with self.get_connection() as conn:
                await conn.execute(f"VACUUM INTO '{backup_path}'")

            if self.logger:
                self.logger.info(f"Database backed up to {backup_path}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Database backup failed: {e}")
            raise DatabaseError(f"Backup failed: {e}")

    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            stats = {}

            # Table row counts
            tables = [
                "guild_configs", "role_mappings", "role_classifications",
                "command_overrides", "permission_overrides", "audit_log"
            ]

            for table in tables:
                row = await self.fetch_one(f"SELECT COUNT(*) as count FROM {table}")
                stats[f"{table}_count"] = row["count"] if row else 0

            # Database size
            try:
                stats["database_size_bytes"] = self.db_path.stat().st_size
                stats["database_size_mb"] = round(stats["database_size_bytes"] / 1024 / 1024, 2)
            except:
                stats["database_size_bytes"] = 0
                stats["database_size_mb"] = 0

            return stats

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get database stats: {e}")
            return {}

    async def cleanup_old_data(self, days: int = 30) -> int:
        """Clean up old audit log entries."""
        try:
            cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None)
            cutoff_timestamp = (cutoff_date.timestamp() - (days * 24 * 60 * 60))

            result = await self.fetch_one(
                "DELETE FROM audit_log WHERE timestamp < datetime(?, 'unixepoch') RETURNING COUNT(*)",
                (cutoff_timestamp,)
            )

            cleaned_count = result["COUNT(*)"] if result else 0

            if self.logger and cleaned_count > 0:
                self.logger.info(f"Cleaned up {cleaned_count} old audit log entries")

            return cleaned_count

        except Exception as e:
            if self.logger:
                self.logger.error(f"Cleanup failed: {e}")
            return 0

    async def close(self) -> None:
        """Close database connections."""
        # aiosqlite connections are automatically closed in context managers
        if self.logger:
            self.logger.info("Database manager closed")
