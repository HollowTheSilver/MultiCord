"""
Permission Persistence Module
============================

Database persistence layer for the permission system.
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from utils.permissions import (
    GuildPermissionConfig, PermissionLevel, RoleType,
    PermissionOverride, PermissionAuditEntry, PermissionScope
)
from utils.database import DatabaseManager


class PermissionPersistence:
    """Handles saving and loading permission data to/from database."""

    def __init__(self, db_manager: DatabaseManager, logger=None):
        """
        Initialize persistence layer.

        Args:
            db_manager: Database manager instance
            logger: Logger instance
        """
        self.db = db_manager
        self.logger = logger

    # // ========================================( Guild Configuration )======================================== // #

    async def save_guild_config(self, guild_id: int, config: GuildPermissionConfig) -> None:
        """Save guild configuration to database."""
        try:
            # Upsert guild config
            await self.db.execute("""
                INSERT OR REPLACE INTO guild_configs 
                (guild_id, auto_configured, configured_by, configured_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                guild_id,
                config.auto_configured,
                config.configured_by,
                config.configured_at.isoformat() if config.configured_at else None,
                datetime.now(timezone.utc).isoformat()
            ))

            # Save role mappings
            await self._save_role_mappings(guild_id, config.role_mappings)

            # Save role classifications
            await self._save_role_classifications(guild_id, config.role_classifications)

            # Save command overrides
            await self._save_command_overrides(guild_id, config.node_overrides)

            if self.logger:
                self.logger.debug(f"Saved guild config for {guild_id}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save guild config {guild_id}: {e}")
            raise

    async def load_guild_config(self, guild_id: int) -> Optional[GuildPermissionConfig]:
        """Load guild configuration from database."""
        try:
            # Load basic config
            row = await self.db.fetch_one(
                "SELECT * FROM guild_configs WHERE guild_id = ?",
                (guild_id,)
            )

            if not row:
                return None

            # Create config object
            config = GuildPermissionConfig(guild_id=guild_id)
            config.auto_configured = bool(row["auto_configured"])
            config.configured_by = row["configured_by"]

            if row["configured_at"]:
                config.configured_at = datetime.fromisoformat(row["configured_at"])

            # Load role mappings
            config.role_mappings = await self._load_role_mappings(guild_id)

            # Load role classifications
            config.role_classifications = await self._load_role_classifications(guild_id)

            # Load command overrides
            config.node_overrides = await self._load_command_overrides(guild_id)

            if self.logger:
                self.logger.debug(f"Loaded guild config for {guild_id}")

            return config

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load guild config {guild_id}: {e}")
            return None

    async def delete_guild_config(self, guild_id: int) -> None:
        """Delete guild configuration from database."""
        try:
            await self.db.execute(
                "DELETE FROM guild_configs WHERE guild_id = ?",
                (guild_id,)
            )

            if self.logger:
                self.logger.info(f"Deleted guild config for {guild_id}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to delete guild config {guild_id}: {e}")
            raise

    # // ========================================( Role Mappings )======================================== // #

    async def _save_role_mappings(self, guild_id: int, role_mappings: Dict[int, PermissionLevel]) -> None:
        """Save role permission mappings."""
        # Clear existing mappings
        await self.db.execute(
            "DELETE FROM role_mappings WHERE guild_id = ?",
            (guild_id,)
        )

        if not role_mappings:
            return

        # Insert new mappings
        mappings_data = [
            (guild_id, role_id, level.value, datetime.now(timezone.utc).isoformat())
            for role_id, level in role_mappings.items()
        ]

        await self.db.execute_many("""
            INSERT INTO role_mappings (guild_id, role_id, permission_level, updated_at)
            VALUES (?, ?, ?, ?)
        """, mappings_data)

    async def _load_role_mappings(self, guild_id: int) -> Dict[int, PermissionLevel]:
        """Load role permission mappings."""
        rows = await self.db.fetch_all(
            "SELECT role_id, permission_level FROM role_mappings WHERE guild_id = ?",
            (guild_id,)
        )

        return {
            row["role_id"]: PermissionLevel(row["permission_level"])
            for row in rows
        }

    # // ========================================( Role Classifications )======================================== // #

    async def _save_role_classifications(self, guild_id: int, role_classifications: Dict[int, RoleType]) -> None:
        """Save role classifications."""
        # Clear existing classifications
        await self.db.execute(
            "DELETE FROM role_classifications WHERE guild_id = ?",
            (guild_id,)
        )

        if not role_classifications:
            return

        # Insert new classifications
        classifications_data = [
            (guild_id, role_id, role_type.value, datetime.now(timezone.utc).isoformat())
            for role_id, role_type in role_classifications.items()
        ]

        await self.db.execute_many("""
            INSERT INTO role_classifications (guild_id, role_id, role_type, updated_at)
            VALUES (?, ?, ?, ?)
        """, classifications_data)

    async def _load_role_classifications(self, guild_id: int) -> Dict[int, RoleType]:
        """Load role classifications."""
        rows = await self.db.fetch_all(
            "SELECT role_id, role_type FROM role_classifications WHERE guild_id = ?",
            (guild_id,)
        )

        return {
            row["role_id"]: RoleType(row["role_type"])
            for row in rows
        }

    # // ========================================( Command Overrides )======================================== // #

    async def _save_command_overrides(self, guild_id: int, node_overrides: Dict[str, PermissionLevel]) -> None:
        """Save command permission overrides."""
        # Clear existing overrides
        await self.db.execute(
            "DELETE FROM command_overrides WHERE guild_id = ?",
            (guild_id,)
        )

        if not node_overrides:
            return

        # Insert new overrides
        overrides_data = [
            (guild_id, node, level.value, datetime.now(timezone.utc).isoformat())
            for node, level in node_overrides.items()
        ]

        await self.db.execute_many("""
            INSERT INTO command_overrides (guild_id, command_node, permission_level, updated_at)
            VALUES (?, ?, ?, ?)
        """, overrides_data)

    async def _load_command_overrides(self, guild_id: int) -> Dict[str, PermissionLevel]:
        """Load command permission overrides."""
        rows = await self.db.fetch_all(
            "SELECT command_node, permission_level FROM command_overrides WHERE guild_id = ?",
            (guild_id,)
        )

        return {
            row["command_node"]: PermissionLevel(row["permission_level"])
            for row in rows
        }

    # // ========================================( Permission Overrides )======================================== // #

    async def save_permission_override(self, override: PermissionOverride) -> None:
        """Save permission override to database."""
        try:
            await self.db.execute("""
                INSERT OR REPLACE INTO permission_overrides 
                (target_type, target_id, permission_node, granted, scope_type, scope_id, 
                 reason, granted_by, expires_at, guild_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                override.target_type,
                override.target_id,
                override.permission_node,
                override.granted,
                override.scope_type.value,
                override.scope_id,
                override.reason,
                override.granted_by,
                override.expires_at.isoformat() if override.expires_at else None,
                getattr(override, 'guild_id', None)
            ))

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save permission override: {e}")
            raise

    async def load_permission_overrides(self, guild_id: Optional[int] = None) -> List[PermissionOverride]:
        """Load permission overrides from database."""
        try:
            if guild_id:
                rows = await self.db.fetch_all(
                    "SELECT * FROM permission_overrides WHERE guild_id = ? OR guild_id IS NULL",
                    (guild_id,)
                )
            else:
                rows = await self.db.fetch_all("SELECT * FROM permission_overrides")

            overrides = []
            for row in rows:
                override = PermissionOverride(
                    target_type=row["target_type"],
                    target_id=row["target_id"],
                    permission_node=row["permission_node"],
                    granted=bool(row["granted"]),
                    scope_type=PermissionScope(row["scope_type"]),
                    scope_id=row["scope_id"],
                    reason=row["reason"],
                    granted_by=row["granted_by"],
                    expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
                )

                # Add guild_id attribute
                if row["guild_id"]:
                    override.guild_id = row["guild_id"]

                overrides.append(override)

            return overrides

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load permission overrides: {e}")
            return []

    async def delete_permission_override(self, override_id: int) -> None:
        """Delete permission override from database."""
        try:
            await self.db.execute(
                "DELETE FROM permission_overrides WHERE id = ?",
                (override_id,)
            )

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to delete permission override: {e}")
            raise

    # // ========================================( Audit Log )======================================== // #

    async def save_audit_entry(self, entry: PermissionAuditEntry) -> None:
        """Save audit log entry to database."""
        try:
            await self.db.execute("""
                INSERT INTO audit_log 
                (action, target_type, target_id, permission_data, actor_id, reason, guild_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.action,
                entry.target_type,
                str(entry.target_id),
                entry.permission_data,
                entry.actor_id,
                entry.reason,
                entry.guild_id,
                entry.timestamp.isoformat()
            ))

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save audit entry: {e}")
            # Don't raise - audit logging shouldn't break functionality

    async def load_audit_entries(
            self,
            guild_id: Optional[int] = None,
            limit: int = 100,
            actor_id: Optional[int] = None
    ) -> List[PermissionAuditEntry]:
        """Load audit log entries from database."""
        try:
            query = "SELECT * FROM audit_log"
            params = []

            conditions = []
            if guild_id:
                conditions.append("guild_id = ?")
                params.append(guild_id)

            if actor_id:
                conditions.append("actor_id = ?")
                params.append(actor_id)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = await self.db.fetch_all(query, tuple(params))

            entries = []
            for row in rows:
                entry = PermissionAuditEntry(
                    action=row["action"],
                    target_type=row["target_type"],
                    target_id=row["target_id"],
                    permission_data=row["permission_data"],
                    actor_id=row["actor_id"],
                    reason=row["reason"],
                    guild_id=row["guild_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"])
                )
                entries.append(entry)

            return entries

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load audit entries: {e}")
            return []

    # // ========================================( Bulk Operations )======================================== // #

    async def load_all_guild_configs(self) -> Dict[int, GuildPermissionConfig]:
        """Load all guild configurations from database."""
        try:
            rows = await self.db.fetch_all("SELECT guild_id FROM guild_configs")
            configs = {}

            for row in rows:
                guild_id = row["guild_id"]
                config = await self.load_guild_config(guild_id)
                if config:
                    configs[guild_id] = config

            if self.logger:
                self.logger.info(f"Loaded {len(configs)} guild configurations")

            return configs

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load all guild configs: {e}")
            return {}

    async def get_guild_list(self) -> List[int]:
        """Get list of guild IDs with stored configurations."""
        try:
            rows = await self.db.fetch_all("SELECT guild_id FROM guild_configs ORDER BY guild_id")
            return [row["guild_id"] for row in rows]

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get guild list: {e}")
            return []

    async def cleanup_expired_overrides(self) -> int:
        """Remove expired permission overrides."""
        try:
            now = datetime.now(timezone.utc).isoformat()

            result = await self.db.fetch_one("""
                DELETE FROM permission_overrides 
                WHERE expires_at IS NOT NULL AND expires_at < ?
                RETURNING COUNT(*)
            """, (now,))

            count = result["COUNT(*)"] if result else 0

            if self.logger and count > 0:
                self.logger.info(f"Cleaned up {count} expired permission overrides")

            return count

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to cleanup expired overrides: {e}")
            return 0
