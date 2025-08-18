"""
Enhanced Platform Launcher
==========================

Enhanced launcher with auto-detection, smart logging, and health tracking.
This extends the original launcher with Phase 1 improvements.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from datetime import datetime, timezone

# Import the base launcher
from bot_platform.launcher import PlatformLauncher


class EnhancedPlatformLauncher(PlatformLauncher):
    """Enhanced launcher with auto-detection and smart logging."""

    def __init__(self, config_path: str = "platform_config.json"):
        """Initialize with enhanced features."""
        # Initialize parent class first (this calls the original __init__)
        super().__init__(config_path)

        # Load auto-healing settings
        self.auto_healing_config = self._load_auto_healing_config()

        # Enhanced status tracking
        self.client_health_status = {}
        self.auto_fix_log = []

        # Override parent's config loading with enhanced version
        self._load_synchronized_config_enhanced()

    def _load_auto_healing_config(self) -> Dict[str, Any]:
        """Load auto-healing configuration with sensible defaults."""
        defaults = {
            "enabled": True,
            "sync_directory_to_database": True,
            "create_missing_directories": True,
            "fix_template_substitution": True,
            "register_orphaned_processes": True,
            "backup_before_changes": True,
            "max_auto_fixes_per_startup": 10
        }

        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    auto_healing = config.get("auto_healing", {})
                    # Merge with defaults
                    for key, value in defaults.items():
                        if key not in auto_healing:
                            auto_healing[key] = value
                    return auto_healing
        except Exception as e:
            self.logger.debug(f"Could not load auto-healing config: {e}")

        return defaults

    def _load_synchronized_config_enhanced(self) -> None:
        """Enhanced config loading with auto-detection and auto-healing."""
        self.logger.info("🔍 Discovering clients from all sources...")

        # Step 1: Discover from all sources
        discovery_results = self._comprehensive_client_discovery()

        # Step 2: Analyze inconsistencies
        inconsistencies = self._analyze_client_inconsistencies(discovery_results)

        # Step 3: Auto-heal if enabled
        fixed_count = 0
        if self.auto_healing_config["enabled"] and inconsistencies:
            fixed_count = self._auto_heal_inconsistencies(inconsistencies)

        # Step 4: Report issues that couldn't be auto-fixed
        self._report_remaining_issues(inconsistencies, fixed_count)

        # Step 5: Final configuration merge
        self.client_configs = self._merge_all_client_sources(discovery_results)

        # Step 6: Initialize health tracking
        self._initialize_health_tracking()

        # Step 7: Save updated configuration
        self._save_platform_config()

        # Step 8: Success summary
        total_clients = len(self.client_configs)
        if fixed_count > 0:
            self.logger.info(f"✅ Platform ready with {total_clients} clients (auto-fixed {fixed_count} issues)")
        else:
            self.logger.info(f"✅ Platform ready with {total_clients} clients")

    def _comprehensive_client_discovery(self) -> Dict[str, Dict[str, Any]]:
        """Comprehensive client discovery from all sources."""
        discovery_results = {
            "directory_clients": {},
            "database_clients": {},
            "config_clients": {},
            "running_clients": {}
        }

        # Directory scan
        self.logger.debug("Scanning client directories...")
        discovery_results["directory_clients"] = self._scan_client_directories()

        # Database scan
        self.logger.debug("Loading client database...")
        discovery_results["database_clients"] = self._load_from_client_manager_db()

        # Config scan
        self.logger.debug("Loading platform configuration...")
        discovery_results["config_clients"] = self._load_existing_platform_config()

        # Running process scan
        self.logger.debug("Scanning for running client processes...")
        running_processes = {}
        try:
            discovered_count = self._scan_running_processes()
            # Convert the discovered processes to the expected format
            for client_id in self.client_processes.keys():
                running_processes[client_id] = {"running": True}
        except Exception as e:
            self.logger.debug(f"Error scanning running processes: {e}")
        discovery_results["running_clients"] = running_processes

        # Log discovery summary
        dir_count = len(discovery_results["directory_clients"])
        db_count = len(discovery_results["database_clients"])
        config_count = len(discovery_results["config_clients"])
        running_count = len(discovery_results["running_clients"])

        self.logger.info(f"📊 Discovery results: {dir_count} directories, {db_count} in database, "
                        f"{config_count} in config, {running_count} running")

        return discovery_results

    def _merge_all_client_sources(self, discovery_results: Dict[str, Dict]) -> Dict[str, Any]:
        """Merge all client sources into final configuration."""
        all_client_ids = set()
        for source in discovery_results.values():
            all_client_ids.update(source.keys())

        merged_configs = {}
        for client_id in all_client_ids:
            # Start with directory-based config (most authoritative)
            if client_id in discovery_results["directory_clients"]:
                merged_configs[client_id] = discovery_results["directory_clients"][client_id]
            # Override with database info if available
            elif client_id in discovery_results["database_clients"]:
                merged_configs[client_id] = discovery_results["database_clients"][client_id]
            # Fall back to config file
            elif client_id in discovery_results["config_clients"]:
                merged_configs[client_id] = discovery_results["config_clients"][client_id]

        return merged_configs

    def _analyze_client_inconsistencies(self, discovery_results: Dict[str, Dict]) -> Dict[str, List]:
        """Analyze inconsistencies between client sources."""
        dir_clients = set(discovery_results["directory_clients"].keys())
        db_clients = set(discovery_results["database_clients"].keys())
        config_clients = set(discovery_results["config_clients"].keys())
        running_clients = set(discovery_results["running_clients"].keys())

        inconsistencies = {
            "missing_from_database": list(dir_clients - db_clients),
            "missing_directories": list(db_clients - dir_clients),
            "missing_from_config": list(dir_clients - config_clients),
            "orphaned_processes": list(running_clients - dir_clients),
            "template_issues": [],
            "config_validation_errors": [],
            "missing_directories_list": []
        }

        # Check for template substitution issues
        for client_id in dir_clients:
            template_issues = self._check_template_substitution(client_id)
            if template_issues:
                inconsistencies["template_issues"].append({
                    "client_id": client_id,
                    "issues": template_issues
                })

        # Check for missing directories
        for client_id in dir_clients:
            missing_dirs = self._check_required_directories(client_id)
            if missing_dirs:
                inconsistencies["missing_directories_list"].append({
                    "client_id": client_id,
                    "missing": missing_dirs
                })

        return inconsistencies

    def _auto_heal_inconsistencies(self, inconsistencies: Dict[str, List]) -> int:
        """Auto-heal detected inconsistencies with detailed logging."""
        fixed_count = 0

        # Auto-sync missing database entries
        if (inconsistencies["missing_from_database"] and
            self.auto_healing_config["sync_directory_to_database"]):

            for client_id in inconsistencies["missing_from_database"]:
                self.logger.info(f"🔄 Auto-syncing {client_id} to client database...")
                if self._auto_add_client_to_database(client_id):
                    fixed_count += 1
                    self._log_auto_fix(f"Synced {client_id} to database")
                    self.logger.info(f"✅ Successfully synced {client_id} to database")
                else:
                    self.logger.warning(f"⚠️ Failed to sync {client_id} to database")

        # Auto-fix template substitution issues
        if (inconsistencies["template_issues"] and
            self.auto_healing_config["fix_template_substitution"]):

            for issue_info in inconsistencies["template_issues"]:
                client_id = issue_info["client_id"]
                issues = issue_info["issues"]

                self.logger.info(f"🔧 Auto-fixing template issues in {client_id}: {', '.join(issues)}")
                if self._auto_fix_template_substitution(client_id, issues):
                    fixed_count += 1
                    self._log_auto_fix(f"Fixed template substitution for {client_id}: {issues}")
                    self.logger.info(f"✅ Fixed template substitution for {client_id}")
                else:
                    self.logger.warning(f"⚠️ Could not auto-fix template issues for {client_id}")

        # Create missing directories
        if (inconsistencies["missing_directories_list"] and
            self.auto_healing_config["create_missing_directories"]):

            for dir_info in inconsistencies["missing_directories_list"]:
                client_id = dir_info["client_id"]
                missing_dirs = dir_info["missing"]

                self.logger.info(f"📁 Creating missing directories for {client_id}: {', '.join(missing_dirs)}")
                created_dirs = self._ensure_client_directories(client_id)
                if created_dirs:
                    fixed_count += len(created_dirs)
                    self._log_auto_fix(f"Created directories for {client_id}: {created_dirs}")

        return fixed_count

    def _check_template_substitution(self, client_id: str) -> List[str]:
        """Check for template substitution issues in client configuration."""
        issues = []
        client_dir = self.clients_dir / client_id
        env_file = client_dir / ".env"

        if not env_file.exists():
            issues.append("Missing .env file")
            return issues

        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for unsubstituted template variables
            template_vars = re.findall(r'\{([^}]+)\}', content)
            if template_vars:
                issues.append(f"Unsubstituted variables: {template_vars}")

            # Check for specific critical variables
            if f'CLIENT_ID="{client_id}"' not in content and 'CLIENT_ID={CLIENT_ID}' in content:
                issues.append("CLIENT_ID not properly substituted")

            if f'clients/{client_id}' not in content and 'clients/{CLIENT_ID}' in content:
                issues.append("CLIENT_PATH not properly substituted")

        except Exception as e:
            issues.append(f"Error reading .env file: {e}")

        return issues

    def _auto_fix_template_substitution(self, client_id: str, issues: List[str]) -> bool:
        """Auto-fix template substitution issues with backup."""
        client_dir = self.clients_dir / client_id
        env_file = client_dir / ".env"

        if not env_file.exists():
            return False

        try:
            # Create backup if enabled
            if self.auto_healing_config["backup_before_changes"]:
                backup_file = env_file.with_suffix(f".env.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                with open(env_file, 'r', encoding='utf-8') as src, open(backup_file, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
                self.logger.debug(f"Created backup: {backup_file}")

            # Read and fix content
            with open(env_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Apply common fixes
            content = content.replace('{CLIENT_ID}', f'"{client_id}"')
            content = content.replace('clients/{CLIENT_ID}', f'clients/{client_id}')
            content = content.replace('client: {CLIENT_NAME}', f'client: {client_id}')
            content = re.sub(r'CLIENT_ID=\{CLIENT_ID\}', f'CLIENT_ID="{client_id}"', content)
            content = re.sub(r'CLIENT_PATH=.*\{CLIENT_ID\}', f'CLIENT_PATH="clients/{client_id}"', content)

            # Write fixed content
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(content)

            return True

        except Exception as e:
            self.logger.error(f"Failed to auto-fix template substitution for {client_id}: {e}")
            return False

    def _check_required_directories(self, client_id: str) -> List[str]:
        """Check for missing required directories."""
        client_dir = self.clients_dir / client_id
        required_dirs = ["data", "logs", "custom_cogs"]
        missing = []

        for dir_name in required_dirs:
            dir_path = client_dir / dir_name
            if not dir_path.exists():
                missing.append(dir_name)

        return missing

    def _ensure_client_directories(self, client_id: str) -> List[str]:
        """Ensure required directories exist for a client."""
        client_dir = self.clients_dir / client_id
        required_dirs = ["data", "logs", "custom_cogs"]
        created = []

        for dir_name in required_dirs:
            dir_path = client_dir / dir_name
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    created.append(dir_name)
                except Exception as e:
                    self.logger.warning(f"Could not create directory {dir_path}: {e}")

        return created

    def _auto_add_client_to_database(self, client_id: str) -> bool:
        """Auto-add discovered client to client manager database."""
        try:
            from bot_platform.client_manager import ClientManager, ClientInfo

            client_manager = ClientManager()

            # Extract basic info from client directory
            client_dir = self.clients_dir / client_id
            display_name = client_id.replace('_', ' ').title()

            # Try to extract more info from .env file
            env_file = client_dir / ".env"
            bot_name = display_name
            if env_file.exists():
                try:
                    with open(env_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    bot_name_match = re.search(r'BOT_NAME="?([^"]*)"?', content)
                    if bot_name_match:
                        bot_name = bot_name_match.group(1)
                except Exception:
                    pass

            # Create client info
            client_info = ClientInfo(
                client_id=client_id,
                display_name=display_name,
                plan="basic",  # Default plan
                branding={"bot_name": bot_name},
                notes=f"Auto-discovered from directory on {datetime.now().strftime('%Y-%m-%d')}"
            )

            # Add to database
            client_manager.clients[client_id] = client_info
            client_manager._save_clients_db()

            return True

        except Exception as e:
            self.logger.error(f"Failed to auto-add {client_id} to database: {e}")
            return False

    def _initialize_health_tracking(self) -> None:
        """Initialize health tracking for all clients."""
        for client_id in self.client_configs.keys():
            self.client_health_status[client_id] = {
                "config_health": "unknown",
                "last_health_check": None,
                "issues": [],
                "auto_fixes_applied": []
            }

            # Perform initial health check
            self._update_client_health_status(client_id)

    def _update_client_health_status(self, client_id: str) -> None:
        """Update health status for a specific client."""
        health_status = {
            "config_health": "healthy",
            "last_health_check": datetime.now(timezone.utc),
            "issues": [],
            "auto_fixes_applied": [fix for fix in self.auto_fix_log if client_id in fix]
        }

        # Check configuration health
        config_issues = self._validate_client_configuration(client_id)
        if config_issues:
            health_status["config_health"] = "issues_detected"
            health_status["issues"] = config_issues

        self.client_health_status[client_id] = health_status

    def _validate_client_configuration(self, client_id: str) -> List[str]:
        """Validate client configuration and return issues."""
        issues = []
        client_dir = self.clients_dir / client_id

        # Check .env file
        env_file = client_dir / ".env"
        if not env_file.exists():
            issues.append("Missing .env file")
        else:
            env_issues = self._validate_env_file(env_file, client_id)
            issues.extend(env_issues)

        # Check required directories
        missing_dirs = self._check_required_directories(client_id)
        if missing_dirs:
            issues.append(f"Missing directories: {', '.join(missing_dirs)}")

        return issues

    def _validate_env_file(self, env_file: Path, client_id: str) -> List[str]:
        """Validate .env file for common issues."""
        issues = []

        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for template substitution issues
            if re.search(r'\{[^}]+\}', content):
                issues.append("Contains unsubstituted template variables")

            # Check for required variables
            required_vars = ['DISCORD_TOKEN', 'CLIENT_ID', 'CLIENT_PATH', 'BOT_NAME']
            for var in required_vars:
                if f'{var}=' not in content:
                    issues.append(f"Missing required variable: {var}")

            # Check CLIENT_ID matches directory
            client_id_match = re.search(r'CLIENT_ID="?([^"]*)"?', content)
            if client_id_match and client_id_match.group(1) != client_id:
                issues.append(f"CLIENT_ID mismatch: expected {client_id}, found {client_id_match.group(1)}")

        except Exception as e:
            issues.append(f"Error reading .env file: {e}")

        return issues

    def _log_auto_fix(self, action: str) -> None:
        """Log auto-fix action for audit trail."""
        fix_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action
        }
        self.auto_fix_log.append(fix_entry)

    def _report_remaining_issues(self, inconsistencies: Dict[str, List], fixed_count: int) -> None:
        """Report issues that couldn't be auto-fixed."""
        remaining_issues = []

        if inconsistencies["missing_directories"]:
            clients = inconsistencies["missing_directories"]
            self.logger.error(f"🚨 {len(clients)} clients in database but missing directories: {clients}")
            remaining_issues.extend(clients)

        # Count unfixed template issues
        unfixed_template = [item for item in inconsistencies["template_issues"]
                           if not any(item["client_id"] in fix for fix in self.auto_fix_log)]
        if unfixed_template:
            clients = [item["client_id"] for item in unfixed_template]
            self.logger.warning(f"⚠️ {len(clients)} clients still have template issues: {clients}")
            self.logger.info(f"💡 Run: python validate_clients.py --fix")

        if remaining_issues:
            self.logger.info(f"💡 {len(remaining_issues)} issues require manual attention")

    def get_enhanced_platform_stats(self) -> Dict[str, Any]:
        """Get enhanced platform statistics including health information."""
        base_stats = self.get_platform_stats()

        # Add health information
        health_summary = {
            "healthy_clients": 0,
            "clients_with_issues": 0,
            "total_auto_fixes": len(self.auto_fix_log),
            "auto_healing_enabled": self.auto_healing_config["enabled"]
        }

        for client_id, health_info in self.client_health_status.items():
            if health_info["config_health"] == "healthy":
                health_summary["healthy_clients"] += 1
            else:
                health_summary["clients_with_issues"] += 1

        # Enhanced client information
        enhanced_clients = {}
        for client_id, client_stats in base_stats.get("clients", {}).items():
            enhanced_clients[client_id] = {
                **client_stats,
                "health_status": self.client_health_status.get(client_id, {}),
                "config_issues": self.client_health_status.get(client_id, {}).get("issues", []),
                "auto_fixes_applied": len([fix for fix in self.auto_fix_log if client_id in fix])
            }

        return {
            **base_stats,
            "health": health_summary,
            "clients": enhanced_clients,
            "auto_fix_log": self.auto_fix_log[-10:]  # Last 10 auto-fixes
        }

    def start_client_enhanced(self, client_id: str) -> bool:
        """Enhanced client startup with comprehensive validation and logging."""

        # Pre-startup logging
        self.logger.info(f"🚀 Starting client: {client_id}")

        # Step 1: Health check
        self._update_client_health_status(client_id)
        health_info = self.client_health_status.get(client_id, {})

        if health_info.get("config_health") != "healthy":
            issues = health_info.get("issues", [])
            self.logger.error(f"❌ Configuration issues prevent startup of {client_id}:")
            for issue in issues:
                self.logger.error(f"   • {issue}")
            self.logger.info(f"💡 Run: python validate_clients.py --client {client_id} --fix")
            return False

        # Step 2: Final directory check
        missing_dirs = self._check_required_directories(client_id)
        if missing_dirs:
            self.logger.error(f"❌ Missing required directories for {client_id}: {missing_dirs}")
            return False

        # Step 3: Start the client process (use parent's method)
        try:
            success = super().start_client(client_id)

            if success:
                # Enhanced success logging
                process = self.client_processes.get(client_id)
                if process:
                    self.logger.info(f"✅ Client {client_id} started successfully")
                    self.logger.info(f"   Process ID: {process.pid}")
                    self.logger.info(f"   Health Status: {health_info.get('config_health', 'unknown')}")
                    self.logger.info(f"   Log directory: clients/{client_id}/logs/")

            return success

        except Exception as e:
            self.logger.error(f"❌ Failed to start client process for {client_id}: {e}")
            self.logger.info(f"💡 Check client logs: clients/{client_id}/logs/")
            return False

    # Override the start_client method to use enhanced version
    def start_client(self, client_id: str) -> bool:
        """Use enhanced client startup."""
        return self.start_client_enhanced(client_id)
