"""
Database Management Module
==================================

DatabaseManager with multi-backend support.
CRITICAL FIX: Added missing cleanup_old_data method that core.application expects.
"""

import asyncio
import aiosqlite
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from abc import ABC, abstractmethod

from .exceptions import DatabaseError, DatabaseConnectionError, DatabaseQueryError


class BackendHandler(ABC):
    """Abstract backend handler for database operations."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize backend connection."""
        pass

    @abstractmethod
    async def execute(self, query: str, parameters: tuple = ()) -> None:
        """Execute a query."""
        pass

    @abstractmethod
    async def fetch_one(self, query: str, parameters: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch single row."""
        pass

    @abstractmethod
    async def fetch_all(self, query: str, parameters: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        pass

    @abstractmethod
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connections."""
        pass

    @abstractmethod
    async def cleanup_old_data(self, days_old: int = 30) -> int:
        """Clean up old data entries."""
        pass


class SQLiteHandler(BackendHandler):
    """SQLite backend handler - preserves all existing functionality."""

    def __init__(self, config: Dict[str, Any], logger=None):
        self.db_path = Path(config.get('path', 'client_data.db'))
        self.logger = logger
        self.connection = None
        self._connection_pool = {}
        self._lock = asyncio.Lock()
        self.current_schema_version = 1

    async def initialize(self) -> None:
        """Initialize SQLite database with existing sophisticated functionality."""
        try:
            # Ensure database directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Initialize schema and run migrations
            await self._ensure_schema()
            await self._run_migrations()

            if self.logger:
                self.logger.info(f"SQLite database initialized at {self.db_path}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"SQLite initialization failed: {e}")
            raise DatabaseConnectionError(f"Failed to initialize SQLite database: {e}")

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
                self.logger.error(f"SQLite connection error: {e}")
            raise DatabaseConnectionError(f"SQLite connection failed: {e}")
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
                self.logger.error(f"SQLite query execution failed: {query[:100]}...")
            raise DatabaseQueryError(query, e)

    async def execute_many(self, query: str, parameters_list: List[tuple]) -> None:
        """Execute multiple queries with the same statement."""
        try:
            async with self.get_connection() as conn:
                await conn.executemany(query, parameters_list)
                await conn.commit()
        except Exception as e:
            if self.logger:
                self.logger.error(f"SQLite batch query execution failed: {query[:100]}...")
            raise DatabaseQueryError(query, e)

    async def fetch_one(self, query: str, parameters: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch single row from query."""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute(query, parameters)
                row = await cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            if self.logger:
                self.logger.error(f"SQLite query fetch failed: {query[:100]}...")
            raise DatabaseQueryError(query, e)

    async def fetch_all(self, query: str, parameters: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows from query."""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute(query, parameters)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            if self.logger:
                self.logger.error(f"SQLite query fetch failed: {query[:100]}...")
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
            FOREIGN KEY (guild_id) REFERENCES guild_configs(guild_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS permission_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER,
            role_id INTEGER,
            permission_level INTEGER NOT NULL,
            expires_at TIMESTAMP,
            reason TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (guild_id) REFERENCES guild_configs(guild_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id INTEGER,
            old_value TEXT,
            new_value TEXT,
            reason TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (guild_id) REFERENCES guild_configs(guild_id) ON DELETE CASCADE
        );
        """

        async with self.get_connection() as conn:
            await conn.executescript(schema_sql)
            await conn.commit()

    async def _run_migrations(self) -> None:
        """Run database migrations."""
        try:
            # Check current version
            current_version = await self._get_schema_version()

            # Apply migrations if needed
            if current_version < self.current_schema_version:
                await self._apply_migrations(current_version)

        except Exception as e:
            if self.logger:
                self.logger.error(f"SQLite migration failed: {e}")
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
                self.logger.info(f"SQLite database backed up to {backup_path}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"SQLite database backup failed: {e}")
            raise DatabaseError(f"Backup failed: {e}")

    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            stats = {
                "backend": "sqlite",
                "database_path": str(self.db_path),
                "file_size_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
            }

            # Get table information
            tables = await self.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            stats["tables"] = len(tables)

            # Get row counts for main tables
            for table in tables:
                try:
                    count_result = await self.fetch_one(f"SELECT COUNT(*) as count FROM {table['name']}")
                    stats[f"{table['name']}_count"] = count_result["count"] if count_result else 0
                except:
                    stats[f"{table['name']}_count"] = 0

            return stats

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get SQLite database stats: {e}")
            return {"backend": "sqlite", "error": str(e)}

    async def close(self) -> None:
        """Close database connections."""
        # SQLite connections are managed per-operation
        pass

    async def cleanup_old_data(self, days_old: int = 30) -> int:
        """Clean up old database entries."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
            cutoff_iso = cutoff_date.isoformat()

            # Count entries to be deleted
            count_result = await self.fetch_one(
                "SELECT COUNT(*) as count FROM audit_log WHERE timestamp < ?",
                (cutoff_iso,)
            )
            count = count_result["count"] if count_result else 0

            if count > 0:
                # Delete old audit log entries
                await self.execute(
                    "DELETE FROM audit_log WHERE timestamp < ?",
                    (cutoff_iso,)
                )

                if self.logger:
                    self.logger.info(f"Cleaned up {count} old audit log entries (older than {days_old} days)")

            return count

        except Exception as e:
            if self.logger:
                self.logger.error(f"SQLite cleanup failed: {e}")
            return 0


class FirestoreHandler(BackendHandler):
    """Firestore backend handler for real-time, cloud-native storage."""

    def __init__(self, config: Dict[str, Any], logger=None):
        """Initialize Firestore backend."""
        self.project_id = config.get('project_id', 'default-project')
        self.collection_prefix = config.get('collection_prefix', 'discord_bot')
        self.real_time_enabled = config.get('real_time_updates', True)
        self.credentials_path = config.get('credentials_path')

        self.db = None
        self.logger = logger
        self.firestore = None  # Will be set during initialize()

    async def initialize(self) -> None:
        """Initialize Firestore client."""
        try:
            # Import Firestore client
            try:
                from google.cloud import firestore
                from google.auth import default
                self.firestore = firestore
            except ImportError:
                error_msg = "Firestore client not installed. Run: pip install google-cloud-firestore"
                if self.logger:
                    self.logger.error(error_msg)
                raise DatabaseConnectionError(error_msg)

            # Initialize credentials
            if self.credentials_path:
                import os
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.credentials_path

            # Create Firestore client
            self.db = self.firestore.Client(project=self.project_id)

            # Test connection
            test_doc = self.db.collection('_connection_test').document('test')
            test_doc.set({
                'timestamp': self.firestore.SERVER_TIMESTAMP,
                'platform': 'discord_cloud_platform'
            })

            if self.logger:
                self.logger.info(f"Firestore initialized: project={self.project_id}")

        except Exception as e:
            error_msg = f"Failed to initialize Firestore: {e}"
            if self.logger:
                self.logger.error(error_msg)
            raise DatabaseConnectionError(error_msg)

    async def execute(self, query: str, parameters: tuple = ()) -> None:
        """Execute query translated to Firestore operations."""
        if not self.db:
            raise DatabaseConnectionError("Firestore not initialized")

        try:
            # Basic SQL-to-Firestore translation for Phase 2
            query_upper = query.upper().strip()

            if query_upper.startswith('INSERT'):
                await self._handle_insert(query, parameters)
            elif query_upper.startswith('UPDATE'):
                await self._handle_update(query, parameters)
            elif query_upper.startswith('DELETE'):
                await self._handle_delete(query, parameters)
            elif query_upper.startswith('CREATE TABLE'):
                await self._handle_create_table(query, parameters)
            else:
                if self.logger:
                    self.logger.warning(f"Unsupported Firestore operation: {query[:50]}...")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Firestore execute failed: {e}")
            raise DatabaseQueryError(query, e)

    async def fetch_one(self, query: str, parameters: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch single row from Firestore."""
        if not self.db:
            raise DatabaseConnectionError("Firestore not initialized")

        try:
            # Extract table name and basic WHERE conditions
            table_name = self._extract_table_name(query)
            collection_name = f"{self.collection_prefix}_{table_name}"

            # Basic query execution
            query_ref = self.db.collection(collection_name)

            # Apply simple WHERE conditions if present
            where_conditions = self._parse_where_conditions(query, parameters)
            for field, operator, value in where_conditions:
                query_ref = query_ref.where(field, operator, value)

            # Get first document
            docs = query_ref.limit(1).stream()

            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                return data

            return None

        except Exception as e:
            if self.logger:
                self.logger.error(f"Firestore fetch_one failed: {e}")
            raise DatabaseQueryError(query, e)

    async def fetch_all(self, query: str, parameters: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows from Firestore."""
        if not self.db:
            raise DatabaseConnectionError("Firestore not initialized")

        try:
            # Extract table name
            table_name = self._extract_table_name(query)
            collection_name = f"{self.collection_prefix}_{table_name}"

            # Basic query execution
            query_ref = self.db.collection(collection_name)

            # Apply simple WHERE conditions if present
            where_conditions = self._parse_where_conditions(query, parameters)
            for field, operator, value in where_conditions:
                query_ref = query_ref.where(field, operator, value)

            # Get all documents
            docs = query_ref.stream()
            results = []

            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)

            return results

        except Exception as e:
            if self.logger:
                self.logger.error(f"Firestore fetch_all failed: {e}")
            raise DatabaseQueryError(query, e)

    async def _handle_insert(self, query: str, parameters: tuple) -> None:
        """Handle INSERT operations."""
        if not self.firestore:
            raise DatabaseConnectionError("Firestore not properly initialized")

        table_name = self._extract_table_name(query)
        collection_name = f"{self.collection_prefix}_{table_name}"

        # Parse INSERT values (basic implementation)
        doc_data = self._parse_insert_values(query, parameters)
        doc_data['created_at'] = self.firestore.SERVER_TIMESTAMP
        doc_data['updated_at'] = self.firestore.SERVER_TIMESTAMP

        # Add document
        self.db.collection(collection_name).add(doc_data)

    async def _handle_update(self, query: str, parameters: tuple) -> None:
        """Handle UPDATE operations."""
        if not self.firestore:
            raise DatabaseConnectionError("Firestore not properly initialized")

        table_name = self._extract_table_name(query)
        collection_name = f"{self.collection_prefix}_{table_name}"

        # Basic implementation - update first matching document
        query_ref = self.db.collection(collection_name)
        docs = query_ref.limit(1).stream()

        update_data = self._parse_update_values(query, parameters)
        update_data['updated_at'] = self.firestore.SERVER_TIMESTAMP

        for doc in docs:
            doc.reference.update(update_data)
            break

    async def _handle_delete(self, query: str, parameters: tuple) -> None:
        """Handle DELETE operations."""
        table_name = self._extract_table_name(query)
        collection_name = f"{self.collection_prefix}_{table_name}"

        # Basic implementation - delete first matching document
        query_ref = self.db.collection(collection_name)
        docs = query_ref.limit(1).stream()

        for doc in docs:
            doc.reference.delete()
            break

    async def _handle_create_table(self, query: str, parameters: tuple) -> None:
        """Handle CREATE TABLE operations."""
        if not self.firestore:
            raise DatabaseConnectionError("Firestore not properly initialized")

        table_name = self._extract_table_name(query)
        collection_name = f"{self.collection_prefix}_{table_name}"

        # Create metadata document for collection
        metadata_doc = self.db.collection(collection_name).document('_metadata')
        metadata_doc.set({
            'table_name': table_name,
            'created_at': self.firestore.SERVER_TIMESTAMP,
            'schema': self._parse_create_table_schema(query)
        })

    def _extract_table_name(self, query: str) -> str:
        """Extract table name from SQL query."""
        query_upper = query.upper()

        if "FROM" in query_upper:
            parts = query_upper.split("FROM")[1].strip().split()
            return parts[0].lower()
        elif "INSERT INTO" in query_upper:
            parts = query_upper.split("INSERT INTO")[1].strip().split()
            return parts[0].lower()
        elif "UPDATE" in query_upper:
            parts = query_upper.split("UPDATE")[1].strip().split()
            return parts[0].lower()
        elif "CREATE TABLE" in query_upper:
            parts = query_upper.split("CREATE TABLE")[1].strip().split()
            table_name = parts[0].replace("IF", "").replace("NOT", "").replace("EXISTS", "").strip()
            return table_name.lower()

        return "default_table"

    def _parse_where_conditions(self, query: str, parameters: tuple) -> List[Tuple[str, str, Any]]:
        """Parse basic WHERE conditions for Firestore queries."""
        # Basic implementation for Phase 2
        conditions = []

        if "WHERE" in query.upper():
            # This is a simplified parser - would be enhanced in Phase 3
            where_part = query.upper().split("WHERE")[1]
            if "=" in where_part and parameters:
                # Simple equality condition
                field_part = where_part.split("=")[0].strip()
                if "." not in field_part:  # Avoid complex conditions for now
                    conditions.append((field_part.lower(), "==", parameters[0]))

        return conditions

    def _parse_insert_values(self, query: str, parameters: tuple) -> Dict[str, Any]:
        """Parse INSERT VALUES for Firestore document."""
        # Basic implementation - would be enhanced in Phase 3
        return {f"field_{i}": param for i, param in enumerate(parameters)}

    def _parse_update_values(self, query: str, parameters: tuple) -> Dict[str, Any]:
        """Parse UPDATE SET values for Firestore document."""
        # Basic implementation - would be enhanced in Phase 3
        return {f"field_{i}": param for i, param in enumerate(parameters)}

    def _parse_create_table_schema(self, query: str) -> Dict[str, str]:
        """Parse CREATE TABLE schema for metadata."""
        # Basic implementation - would be enhanced in Phase 3
        return {"schema": "parsed_from_sql", "original_query": query}

    async def get_database_stats(self) -> Dict[str, Any]:
        """Get Firestore database statistics."""
        try:
            stats = {
                "backend": "firestore",
                "project_id": self.project_id,
                "collection_prefix": self.collection_prefix,
                "real_time_enabled": self.real_time_enabled,
                "collections": []
            }

            # List collections (basic implementation)
            collections = self.db.collections()
            for collection in collections:
                if collection.id.startswith(self.collection_prefix):
                    stats["collections"].append(collection.id)

            return stats

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get Firestore stats: {e}")
            return {"backend": "firestore", "error": str(e)}

    async def close(self) -> None:
        """Close Firestore connections."""
        # Firestore client handles connection management automatically
        self.db = None

    async def cleanup_old_data(self, days_old: int = 30) -> int:
        """Clean up old Firestore data entries."""
        if not self.db or not self.firestore:
            return 0

        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

            # Clean up audit log collection
            audit_collection = f"{self.collection_prefix}_audit_log"
            query = self.db.collection(audit_collection).where('timestamp', '<', cutoff_date)

            count = 0
            docs = query.stream()

            for doc in docs:
                doc.reference.delete()
                count += 1

            if self.logger and count > 0:
                self.logger.info(f"Cleaned up {count} old Firestore audit entries (older than {days_old} days)")

            return count

        except Exception as e:
            if self.logger:
                self.logger.error(f"Firestore cleanup failed: {e}")
            return 0


class PostgreSQLHandler(BackendHandler):
    """PostgreSQL backend handler for enterprise deployments."""

    def __init__(self, config: Dict[str, Any], logger=None):
        """Initialize PostgreSQL backend."""
        self.host = config.get('host', 'localhost')
        self.port = config.get('port', 5432)
        self.database = config.get('database', 'discord_bot')
        self.user = config.get('user', 'postgres')
        self.password = config.get('password', '')

        self.connection = None
        self.logger = logger
        self.asyncpg = None  # Will be set during initialize()

    async def initialize(self) -> None:
        """Initialize PostgreSQL connection."""
        try:
            try:
                import asyncpg
                self.asyncpg = asyncpg
            except ImportError:
                error_msg = "asyncpg not installed. Run: pip install asyncpg"
                if self.logger:
                    self.logger.error(error_msg)
                raise DatabaseConnectionError(error_msg)

            # Create connection
            self.connection = await self.asyncpg.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )

            if self.logger:
                self.logger.info(f"PostgreSQL connected: {self.host}:{self.port}/{self.database}")

        except Exception as e:
            error_msg = f"Failed to connect to PostgreSQL: {e}"
            if self.logger:
                self.logger.error(error_msg)
            raise DatabaseConnectionError(error_msg)

    async def execute(self, query: str, parameters: tuple = ()) -> None:
        """Execute PostgreSQL query."""
        if not self.connection:
            raise DatabaseConnectionError("PostgreSQL not connected")

        try:
            # Convert SQLite ? parameters to PostgreSQL $1, $2, etc.
            pg_query = self._convert_query_parameters(query, parameters)

            await self.connection.execute(pg_query, *parameters)

        except Exception as e:
            if self.logger:
                self.logger.error(f"PostgreSQL execute failed: {e}")
            raise DatabaseQueryError(query, e)

    async def fetch_one(self, query: str, parameters: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch single row from PostgreSQL."""
        if not self.connection:
            raise DatabaseConnectionError("PostgreSQL not connected")

        try:
            pg_query = self._convert_query_parameters(query, parameters)

            row = await self.connection.fetchrow(pg_query, *parameters)
            return dict(row) if row else None

        except Exception as e:
            if self.logger:
                self.logger.error(f"PostgreSQL fetch_one failed: {e}")
            raise DatabaseQueryError(query, e)

    async def fetch_all(self, query: str, parameters: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows from PostgreSQL."""
        if not self.connection:
            raise DatabaseConnectionError("PostgreSQL not connected")

        try:
            pg_query = self._convert_query_parameters(query, parameters)

            rows = await self.connection.fetch(pg_query, *parameters)
            return [dict(row) for row in rows]

        except Exception as e:
            if self.logger:
                self.logger.error(f"PostgreSQL fetch_all failed: {e}")
            raise DatabaseQueryError(query, e)

    def _convert_query_parameters(self, query: str, parameters: tuple) -> str:
        """Convert SQLite ? parameters to PostgreSQL $1, $2, etc."""
        if not parameters:
            return query

        param_count = 0
        converted_query = ""

        for char in query:
            if char == '?':
                param_count += 1
                converted_query += f"${param_count}"
            else:
                converted_query += char

        return converted_query

    async def get_database_stats(self) -> Dict[str, Any]:
        """Get PostgreSQL database statistics."""
        try:
            stats = {
                "backend": "postgresql",
                "host": self.host,
                "port": self.port,
                "database": self.database,
                "user": self.user
            }

            # Get database size
            size_query = "SELECT pg_size_pretty(pg_database_size(current_database())) as size"
            result = await self.fetch_one(size_query)
            stats["database_size"] = result["size"] if result else "Unknown"

            # Get table count
            table_query = "SELECT count(*) as table_count FROM information_schema.tables WHERE table_schema = 'public'"
            result = await self.fetch_one(table_query)
            stats["table_count"] = result["table_count"] if result else 0

            return stats

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get PostgreSQL stats: {e}")
            return {"backend": "postgresql", "error": str(e)}

    async def close(self) -> None:
        """Close PostgreSQL connection."""
        if self.connection:
            await self.connection.close()
            self.connection = None

    async def cleanup_old_data(self, days_old: int = 30) -> int:
        """Clean up old PostgreSQL data entries."""
        if not self.connection:
            return 0

        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

            # Count entries to be deleted
            count_query = "SELECT COUNT(*) as count FROM audit_log WHERE timestamp < $1"
            result = await self.fetch_one(count_query, (cutoff_date,))
            count = result["count"] if result else 0

            if count > 0:
                # Delete old audit log entries
                delete_query = "DELETE FROM audit_log WHERE timestamp < $1"
                await self.execute(delete_query, (cutoff_date,))

                if self.logger:
                    self.logger.info(f"Cleaned up {count} old PostgreSQL audit entries (older than {days_old} days)")

            return count

        except Exception as e:
            if self.logger:
                self.logger.error(f"PostgreSQL cleanup failed: {e}")
            return 0


class DatabaseManager:
    """
    Enhanced SQLite database manager with multi-backend support.

    Preserves all existing sophisticated functionality while adding
    support for Firestore and PostgreSQL backends.

    Backward compatible: existing code using path-based initialization continues to work.
    New functionality: pass dict config for multi-backend support.
    """

    def __init__(self, config: Union[str, Path, Dict[str, Any]], logger=None):
        """
        Initialize database manager.

        Args:
            config: Either path to SQLite database (backward compatible)
                   or dict with backend configuration
            logger: Logger instance

        Examples:
            # Backward compatible SQLite
            db = DatabaseManager("client_data.db")

            # Multi-backend configuration
            db = DatabaseManager({
                "backend": "firestore",
                "config": {"project_id": "my-project"}
            })
        """
        self.logger = logger

        # Determine configuration format and backend
        if isinstance(config, (str, Path)):
            # Backward compatible: SQLite with path
            self.backend_name = "sqlite"
            self.backend_config = {"path": str(config)}
        else:
            # New format: dict with backend specification
            self.backend_name = config.get("backend", "sqlite")
            self.backend_config = config.get("config", {})

        # Initialize appropriate backend handler
        self.backend = self._create_backend_handler()

    def _create_backend_handler(self) -> BackendHandler:
        """Create appropriate backend handler."""
        try:
            if self.backend_name == "sqlite":
                return SQLiteHandler(self.backend_config, self.logger)
            elif self.backend_name == "firestore":
                return FirestoreHandler(self.backend_config, self.logger)
            elif self.backend_name == "postgresql":
                return PostgreSQLHandler(self.backend_config, self.logger)
            else:
                # Fallback to SQLite for unknown backends
                if self.logger:
                    self.logger.warning(f"Unknown backend '{self.backend_name}', falling back to SQLite")
                return SQLiteHandler({"path": "fallback.db"}, self.logger)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to create {self.backend_name} backend: {e}")
            # Final fallback to SQLite
            return SQLiteHandler({"path": "error_fallback.db"}, self.logger)

    # Public API - preserves all existing sophisticated functionality

    async def initialize(self) -> None:
        """Initialize the database backend."""
        await self.backend.initialize()

    async def execute(self, query: str, parameters: tuple = ()) -> None:
        """Execute a single query."""
        await self.backend.execute(query, parameters)

    async def execute_many(self, query: str, parameters_list: List[tuple]) -> None:
        """Execute multiple queries with the same statement."""
        # Use backend-specific implementation for SQLite, fallback for others
        if isinstance(self.backend, SQLiteHandler):
            await self.backend.execute_many(query, parameters_list)
        else:
            # For non-SQLite backends, execute individually
            for parameters in parameters_list:
                await self.execute(query, parameters)

    async def fetch_one(self, query: str, parameters: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch single row from query."""
        return await self.backend.fetch_one(query, parameters)

    async def fetch_all(self, query: str, parameters: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows from query."""
        return await self.backend.fetch_all(query, parameters)

    @asynccontextmanager
    async def get_connection(self):
        """Get database connection with automatic cleanup (SQLite only)."""
        if isinstance(self.backend, SQLiteHandler):
            async with self.backend.get_connection() as conn:
                yield conn
        else:
            # For non-SQLite backends, this method is not applicable
            raise DatabaseError(f"get_connection() is only supported for SQLite backend, not {self.backend_name}")

    async def backup_database(self, backup_path: Union[str, Path]) -> None:
        """Create a backup of the database (SQLite only)."""
        if isinstance(self.backend, SQLiteHandler):
            await self.backend.backup_database(backup_path)
        else:
            if self.logger:
                self.logger.warning(f"Backup not supported for {self.backend_name} backend")
            raise DatabaseError(f"Backup is only supported for SQLite backend, not {self.backend_name}")

    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return await self.backend.get_database_stats()

    async def close(self) -> None:
        """Close database connections."""
        await self.backend.close()

    async def cleanup_old_data(self, days_old: int = 30) -> int:
        """Clean up old data entries."""
        return await self.backend.cleanup_old_data(days_old)

    # Additional properties for backward compatibility
    @property
    def db_path(self) -> Optional[Path]:
        """Get database path (SQLite only, for backward compatibility)."""
        if isinstance(self.backend, SQLiteHandler):
            return self.backend.db_path
        return None

    @property
    def current_schema_version(self) -> int:
        """Get current schema version (SQLite only, for backward compatibility)."""
        if isinstance(self.backend, SQLiteHandler):
            return self.backend.current_schema_version
        return 1


# Configuration examples for different backends
DATABASE_CONFIG_EXAMPLES = {
    "sqlite": {
        "backend": "sqlite",
        "config": {
            "path": "client_data.db"
        }
    },
    "firestore": {
        "backend": "firestore",
        "config": {
            "project_id": "my-discord-project",
            "collection_prefix": "discord_bot",
            "real_time_updates": True,
            "credentials_path": "/path/to/service-account.json"  # Optional
        }
    },
    "postgresql": {
        "backend": "postgresql",
        "config": {
            "host": "localhost",
            "port": 5432,
            "database": "discord_bot",
            "user": "discord_user",
            "password": "your_password"
        }
    }
}
