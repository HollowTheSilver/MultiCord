"""
Platform Launcher
================================================

Professional multi-client Discord bot launcher with comprehensive
auto-detection, health monitoring, and auto-healing capabilities.

This is the complete, consolidated launcher that replaces both the
original launcher.py and enhanced_launcher.py files.
"""

import asyncio
import os
import sys
import signal
import subprocess
import psutil
import json
import time
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.utils.loguruConfig import configure_logger


@dataclass
class ClientProcess:
    """Information about a running client bot instance."""
    client_id: str
    process: subprocess.Popen = None
    started_at: datetime = None
    restart_count: int = 0
    last_restart: Optional[datetime] = None
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    status: str = "running"
    health_check_failures: int = 0
    pid: Optional[int] = None

    def __post_init__(self):
        if self.process and not self.pid:
            self.pid = self.process.pid
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc)


@dataclass
class ClientConfig:
    """Basic client configuration for launcher."""
    client_id: str
    display_name: str
    enabled: bool = True
    auto_restart: bool = True
    max_restarts: int = 5
    restart_delay: int = 30
    memory_limit_mb: int = 512
    custom_env: Dict[str, str] = field(default_factory=dict)


class PlatformLauncher:
    """Professional multi-client Discord bot launcher with comprehensive features."""

    def __init__(self, config_path: str = "platform_config.json"):
        """Initialize the platform launcher with all capabilities."""
        self.config_path = Path(config_path)
        self.clients_dir = Path("clients")
        self.core_dir = Path("core")

        # Process tracking files
        self.runtime_dir = Path("bot_platform/runtime")
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.process_registry = self.runtime_dir / "client_processes.json"

        # Client manager database for synchronization
        self.client_manager_db = Path("bot_platform/clients.json")

        # Process management
        self.client_processes: Dict[str, ClientProcess] = {}
        self.client_configs: Dict[str, ClientConfig] = {}
        self.shutdown_requested = False

        # Monitoring
        self.start_time = datetime.now(timezone.utc)
        self.total_restarts = 0
        self.last_health_check = None

        # Setup logging
        self.logger = configure_logger(
            log_dir="bot_platform/logs",
            level="INFO",
            format_extra=True,
            discord_compat=True
        )

        # Auto-healing configuration and tracking
        self.auto_healing_config = self._load_auto_healing_config()
        self.client_health_status = {}
        self.auto_fix_log = []

        # Load configuration with comprehensive discovery and auto-healing
        self._load_synchronized_config()
        self._discover_running_clients()
        self._setup_signal_handlers()

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

    def set_auto_healing_enabled(self, enabled: bool, source: str = "manual") -> None:
        """Set auto-healing enabled state with proper logging."""
        old_state = self.auto_healing_config["enabled"]
        self.auto_healing_config["enabled"] = enabled

        if old_state != enabled:
            action = "enabled" if enabled else "disabled"
            self.logger.info(f"🔧 Auto-healing {action} via {source}")

            # Log for debugging
            self.logger.debug(f"🔍 Auto-healing state changed: {old_state} -> {enabled} (source: {source})")

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
        discovery_results_summary = {
            'directories': len(discovery_results.get('directories', {})),
            'database': len(discovery_results.get('database', {})),
            'config': len(discovery_results.get('config', {})),
            'running': len(discovery_results.get('running', {}))
        }

        self.logger.info(f"📊 Discovery results: {discovery_results_summary['directories']} directories, "
                        f"{discovery_results_summary['database']} in database, "
                        f"{discovery_results_summary['config']} in config, "
                        f"{discovery_results_summary['running']} running")

        if fixed_count > 0:
            self.logger.info(f"✅ Platform ready with {total_clients} clients (auto-fixed {fixed_count} issues)")
        else:
            self.logger.info(f"✅ Platform ready with {total_clients} clients")

    def _comprehensive_client_discovery(self) -> Dict[str, Dict[str, Any]]:
        """Enhanced comprehensive client discovery from all sources."""
        discovery_results = {
            'directories': {},
            'database': {},
            'config': {},
            'running': {}
        }

        # 1. Discover from client directories - FIXED LOGIC
        if self.clients_dir.exists():
            for client_dir in self.clients_dir.iterdir():
                if client_dir.is_dir() and not client_dir.name.startswith('_'):
                    # Check for required files
                    required_files = ['config.json', '.env']
                    existing_files = []
                    missing_files = []

                    for req_file in required_files:
                        file_path = client_dir / req_file
                        if file_path.exists():
                            existing_files.append(req_file)
                        else:
                            missing_files.append(req_file)

                    discovery_results['directories'][client_dir.name] = {
                        'source': 'directory',
                        'path': str(client_dir),
                        'existing_files': existing_files,
                        'missing_files': missing_files,
                        'is_complete': len(missing_files) == 0,
                        'last_modified': client_dir.stat().st_mtime
                    }

        # 2. Discover from client manager database
        if self.client_manager_db.exists():
            try:
                with open(self.client_manager_db, 'r', encoding='utf-8') as f:
                    db_data = json.load(f)
                for client_id, client_data in db_data.get('clients', {}).items():
                    discovery_results['database'][client_id] = {
                        'source': 'database',
                        'data': client_data,
                        'last_updated': client_data.get('last_updated')
                    }
            except Exception as e:
                self.logger.debug(f"Could not read client database: {e}")

        # 3. Discover from platform config
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    platform_config = json.load(f)
                for client_data in platform_config.get('clients', []):
                    client_id = client_data.get('client_id')
                    if client_id:
                        discovery_results['config'][client_id] = {
                            'source': 'config',
                            'data': client_data
                        }
            except Exception as e:
                self.logger.debug(f"Could not read platform config: {e}")

        # 4. Discover running processes
        discovery_results['running'] = self._discover_running_client_processes()

        return discovery_results

    def _discover_running_client_processes(self) -> Dict[str, Dict[str, Any]]:
        """Discover running client processes."""
        running_clients = {}

        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and len(cmdline) >= 2:
                        # Look for client runner processes
                        if 'client_runner.py' in ' '.join(cmdline):
                            for arg in cmdline:
                                if arg.startswith('--client='):
                                    client_id = arg.split('=', 1)[1]
                                    running_clients[client_id] = {
                                        'source': 'running',
                                        'pid': proc.info['pid'],
                                        'started_at': proc.info['create_time'],
                                        'cmdline': cmdline
                                    }
                                    break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            self.logger.debug(f"Error discovering running processes: {e}")

        return running_clients

    def _analyze_client_inconsistencies(self, discovery_results: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enhanced analysis of client inconsistencies."""
        inconsistencies = []

        # Get all unique client IDs
        all_client_ids = set()
        for source in discovery_results.values():
            all_client_ids.update(source.keys())

        for client_id in all_client_ids:
            issues = []

            # Check if client exists in different sources
            in_directories = client_id in discovery_results['directories']
            in_database = client_id in discovery_results['database']
            in_config = client_id in discovery_results['config']
            in_running = client_id in discovery_results['running']

            # Check for missing directory
            if not in_directories and (in_database or in_config):
                issues.append({
                    'type': 'missing_directory',
                    'description': f"Client {client_id} exists in database/config but missing directory",
                    'fix_action': 'create_complete_client_from_template'
                })

            # Check for incomplete directory (missing files) - THIS IS THE KEY FIX
            elif in_directories:
                dir_info = discovery_results['directories'][client_id]
                if not dir_info['is_complete']:
                    missing_files = dir_info['missing_files']
                    issues.append({
                        'type': 'missing_critical_files',
                        'description': f"Client {client_id} missing files: {missing_files}",
                        'fix_action': 'complete_client_files_from_template',
                        'missing_files': missing_files
                    })

            # Check for database sync issues
            if in_directories and not in_database:
                issues.append({
                    'type': 'missing_database_entry',
                    'description': f"Client {client_id} has directory but not in database",
                    'fix_action': 'add_to_database'
                })

            if issues:
                inconsistencies.append({
                    'client_id': client_id,
                    'issues': issues,
                    'sources': {
                        'directories': in_directories,
                        'database': in_database,
                        'config': in_config,
                        'running': in_running
                    }
                })

        return inconsistencies

    def _auto_heal_inconsistencies(self, inconsistencies: List[Dict[str, Any]]) -> int:
        """Auto-heal detected inconsistencies."""
        fixed_count = 0
        max_fixes = self.auto_healing_config.get('max_auto_fixes_per_startup', 10)

        for inconsistency in inconsistencies:
            if fixed_count >= max_fixes:
                self.logger.warning(f"⚠️ Reached max auto-fixes limit ({max_fixes}), skipping remaining issues")
                break

            client_id = inconsistency['client_id']

            for issue in inconsistency['issues']:
                if fixed_count >= max_fixes:
                    break

                try:
                    if self._apply_auto_fix(client_id, issue):
                        fixed_count += 1
                        self.auto_fix_log.append({
                            'timestamp': datetime.now().isoformat(),
                            'client_id': client_id,
                            'issue_type': issue['type'],
                            'description': issue['description'],
                            'fix_applied': issue['fix_action']
                        })
                except Exception as e:
                    self.logger.error(f"❌ Auto-fix failed for {client_id} ({issue['type']}): {e}")

        return fixed_count

    def _apply_auto_fix(self, client_id: str, issue: Dict[str, Any]) -> bool:
        """Apply comprehensive auto-fixes."""
        fix_action = issue['fix_action']

        try:
            if fix_action == 'create_complete_client_from_template':
                return self._create_complete_client_from_template(client_id)
            elif fix_action == 'complete_client_files_from_template':
                return self._complete_client_files_from_template(client_id, issue.get('missing_files', []))
            elif fix_action == 'add_to_database':
                return self._add_client_to_database(client_id)

            return False
        except Exception as e:
            self.logger.error(f"Auto-fix failed for {client_id} ({fix_action}): {e}")
            return False

    def _create_client_directory_from_template(self, client_id: str) -> bool:
        """Create client directory from template."""
        if not self.auto_healing_config.get('create_missing_directories', True):
            return False

        template_dir = self.clients_dir / "_template"
        client_dir = self.clients_dir / client_id

        if not template_dir.exists():
            self.logger.error(f"❌ Template directory not found: {template_dir}")
            return False

        if client_dir.exists():
            self.logger.debug(f"Client directory already exists: {client_dir}")
            return True

        try:
            # Create backup if enabled
            if self.auto_healing_config.get('backup_before_changes', True):
                self._create_backup(f"before_create_{client_id}")

            # Copy template
            shutil.copytree(template_dir, client_dir)

            # Fix template substitutions
            self._fix_template_substitution(client_id)

            self.logger.info(f"✅ Auto-created client directory: {client_id}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to create client directory {client_id}: {e}")
            return False

    def _add_client_to_database(self, client_id: str) -> bool:
        """Add client to database."""
        if not self.auto_healing_config.get('sync_directory_to_database', True):
            return False

        try:
            # Import here to avoid circular imports
            from bot_platform.client_manager import ClientManager

            client_manager = ClientManager()

            # Create basic client configuration
            client_config = {
                'client_id': client_id,
                'display_name': client_id.replace('_', ' ').title(),
                'enabled': True,
                'auto_restart': True,
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }

            success = client_manager.create_client(**client_config)
            if success:
                self.logger.info(f"✅ Auto-added client to database: {client_id}")
                return True
            else:
                self.logger.error(f"❌ Failed to add client to database: {client_id}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Error adding client to database {client_id}: {e}")
            return False

    def _fix_template_substitution(self, client_id: str) -> bool:
        """Fix template substitution in client files."""
        if not self.auto_healing_config.get('fix_template_substitution', True):
            return False

        client_dir = self.clients_dir / client_id
        if not client_dir.exists():
            return False

        try:
            fixed_files = []

            # Process all files in client directory
            for file_path in client_dir.rglob('*'):
                if file_path.is_file() and file_path.suffix in ['.json', '.py', '.txt', '.md']:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        original_content = content

                        # Replace template placeholders
                        content = content.replace('{{CLIENT_ID}}', client_id)
                        content = content.replace('{{CLIENT_NAME}}', client_id.replace('_', ' ').title())

                        if content != original_content:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            fixed_files.append(str(file_path.relative_to(client_dir)))

                    except Exception as e:
                        self.logger.debug(f"Could not process file {file_path}: {e}")

            if fixed_files:
                self.logger.info(f"✅ Auto-fixed template substitution in {client_id}: {', '.join(fixed_files)}")
                return True

            return True  # No fixes needed, but no error

        except Exception as e:
            self.logger.error(f"❌ Failed to fix template substitution for {client_id}: {e}")
            return False

    def _complete_client_files_from_template(self, client_id: str, missing_files: List[str]) -> bool:
        """Complete missing files in existing client directory with Smart Configuration Sync."""
        template_dir = self.clients_dir / "_template"
        client_dir = self.clients_dir / client_id

        if not template_dir.exists():
            self.logger.error(f"❌ Template directory not found: {template_dir}")
            return False

        if not client_dir.exists():
            return self._create_complete_client_from_template(client_id)

        try:
            # Create backup if enabled
            if self.auto_healing_config.get('backup_before_changes', True):
                self._create_backup(f"before_complete_{client_id}")

            files_created = []

            for missing_file in missing_files:
                if missing_file == 'config.json':
                    # Look for config.json.template first, then config.json
                    template_file = template_dir / 'config.json.template'
                    if not template_file.exists():
                        template_file = template_dir / 'config.json'

                    if template_file.exists():
                        target_file = client_dir / 'config.json'
                        shutil.copy2(template_file, target_file)

                        # Apply template substitution
                        self._process_template_file(target_file, client_id)

                        # CRITICAL ENHANCEMENT: Apply Smart Configuration Sync
                        self._sync_configuration_from_env(client_id, target_file)

                        files_created.append('config.json')
                        self.logger.info(f"✅ Created {missing_file} for {client_id}")
                    else:
                        # Create from scratch (includes Smart Config Sync)
                        self._create_config_json_from_scratch(client_id)
                        files_created.append('config.json')

            if files_created:
                self.logger.info(f"✅ Auto-completed client files for {client_id}: {files_created}")
                return True
            else:
                self.logger.warning(f"⚠️ No files could be created for {client_id}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Failed to complete client files for {client_id}: {e}")
            return False

    def _create_complete_client_from_template(self, client_id: str) -> bool:
        """Create complete client directory from template with all files."""
        if not self.auto_healing_config.get('create_missing_directories', True):
            return False

        template_dir = self.clients_dir / "_template"
        client_dir = self.clients_dir / client_id

        if not template_dir.exists():
            self.logger.error(f"❌ Template directory not found: {template_dir}")
            return False

        if client_dir.exists():
            self.logger.debug(f"Client directory already exists: {client_dir}")
            # If directory exists, just complete missing files
            return self._complete_client_files_from_template(client_id, ['config.json'])

        try:
            # Create backup if enabled
            if self.auto_healing_config.get('backup_before_changes', True):
                self._create_backup(f"before_create_{client_id}")

            # Copy entire template directory
            shutil.copytree(template_dir, client_dir)

            # Process all template files
            self._process_all_template_files(client_dir, client_id)

            self.logger.info(f"✅ Auto-created complete client: {client_id}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to create complete client {client_id}: {e}")
            return False

    def _create_config_json_from_scratch(self, client_id: str) -> bool:
        """Create config.json from scratch with Smart Configuration Sync."""
        client_dir = self.clients_dir / client_id
        config_file = client_dir / 'config.json'

        try:
            config_data = {
                "client_id": client_id,
                "display_name": client_id.replace('_', ' ').title(),
                "enabled": True,
                "discord": {
                    "token": "YOUR_DISCORD_TOKEN_HERE",
                    "intents": {
                        "guilds": True,
                        "guild_messages": True,
                        "message_content": True
                    }
                },
                "features": {
                    "auto_restart": True,
                    "logging_level": "INFO",
                    "command_prefix": "!"
                },
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }

            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"✅ Created config.json from scratch for {client_id}")

            # CRITICAL ENHANCEMENT: Apply Smart Configuration Sync
            self._sync_configuration_from_env(client_id, config_file)

            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to create config.json for {client_id}: {e}")
            return False

    def _process_template_file(self, file_path: Path, client_id: str) -> None:
        """Process template substitution for a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Template substitution variables
            substitutions = {
                '{CLIENT_ID}': client_id,
                '{DISPLAY_NAME}': client_id.replace('_', ' ').title(),
                '{CREATED_AT}': datetime.now().isoformat(),
                '{PLAN}': 'basic'  # Default plan
            }

            # Apply substitutions
            for template_var, replacement in substitutions.items():
                content = content.replace(template_var, replacement)

            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.logger.debug(f"Applied template substitution to {file_path.name}")

        except Exception as e:
            self.logger.error(f"Failed to process template file {file_path}: {e}")

    def _process_all_template_files(self, client_dir: Path, client_id: str) -> None:
        """Process template substitution for all files in client directory."""

        # Template substitution variables
        substitutions = {
            '{CLIENT_ID}': client_id,
            '{DISPLAY_NAME}': client_id.replace('_', ' ').title(),
            '{CREATED_AT}': datetime.now().isoformat(),
            '{PLAN}': 'basic'  # Default plan
        }

        # Process all files recursively
        for file_path in client_dir.rglob('*'):
            if file_path.is_file():
                # Handle .template files (rename and substitute)
                if file_path.suffix == '.template':
                    # Determine target filename (config.json.template -> config.json)
                    base_name = file_path.stem  # filename without .template
                    target_file = file_path.parent / base_name

                    try:
                        # Read template content
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # Apply substitutions
                        for template_var, replacement in substitutions.items():
                            content = content.replace(template_var, replacement)

                        # Write to target file
                        with open(target_file, 'w', encoding='utf-8') as f:
                            f.write(content)

                        # Remove the .template file
                        file_path.unlink()

                        self.logger.debug(f"Processed template: {file_path.name} -> {target_file.name}")

                    except Exception as e:
                        self.logger.error(f"Failed to process template {file_path}: {e}")

                # Handle regular files that might contain template variables
                elif file_path.suffix in ['.json', '.py', '.env', '.txt', '.md']:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        original_content = content

                        # Apply substitutions
                        for template_var, replacement in substitutions.items():
                            content = content.replace(template_var, replacement)

                        # Write back if changed
                        if content != original_content:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)

                            self.logger.debug(f"Applied template substitution to {file_path.relative_to(client_dir)}")

                    except Exception as e:
                        self.logger.debug(f"Could not process template file {file_path}: {e}")

    def _sync_configuration_from_env(self, client_id: str, config_file: Path) -> bool:
        """
        Smart Configuration Sync with DEBUG LOGGING
        """
        try:
            client_dir = self.clients_dir / client_id
            env_file = client_dir / '.env'

            self.logger.info(f"🔍 DEBUG: Starting Smart Config Sync for {client_id}")
            self.logger.info(f"🔍 DEBUG: Looking for .env at: {env_file}")
            self.logger.info(f"🔍 DEBUG: .env exists: {env_file.exists()}")

            if not env_file.exists():
                self.logger.warning(f"❌ DEBUG: No .env file found for {client_id} at {env_file}")
                return False

            # Read current config.json
            self.logger.info(f"🔍 DEBUG: Looking for config.json at: {config_file}")
            self.logger.info(f"🔍 DEBUG: config.json exists: {config_file.exists()}")

            if not config_file.exists():
                self.logger.warning(f"❌ DEBUG: Config file doesn't exist: {config_file}")
                return False

            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # Read .env file and extract real values
            env_values = {}
            with open(env_file, 'r', encoding='utf-8') as f:
                content = f.read()
                self.logger.info(f"🔍 DEBUG: .env file content length: {len(content)} chars")

                for line_num, line in enumerate(content.split('\n'), 1):
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        try:
                            key, value = line.split('=', 1)
                            env_values[key.strip()] = value.strip().strip('"').strip("'")

                            # LOG TOKENS SAFELY (hide actual values)
                            if 'TOKEN' in key:
                                safe_value = value[:10] + "..." if len(value) > 10 else "SHORT_VALUE"
                                self.logger.info(f"🔍 DEBUG: Found {key}={safe_value}")
                            else:
                                self.logger.info(f"🔍 DEBUG: Found {key}={value}")
                        except Exception as e:
                            self.logger.warning(f"⚠️ DEBUG: Error parsing line {line_num}: {line} - {e}")

            self.logger.info(f"🔍 DEBUG: Extracted {len(env_values)} values from .env")

            # Configuration sync mappings
            sync_mappings = {
                'DISCORD_TOKEN': ('discord', 'token'),
                'BOT_NAME': ('bot_name',),
                'COMMAND_PREFIX': ('features', 'command_prefix'),
                'LOG_LEVEL': ('features', 'logging_level'),
                'OWNER_IDS': ('owner_ids',)
            }

            config_updated = False
            synced_values = []

            # Sync real values from .env to config.json
            for env_key, config_path in sync_mappings.items():
                self.logger.info(f"🔍 DEBUG: Checking {env_key}...")

                if env_key in env_values:
                    env_value = env_values[env_key]

                    # Log what we found (safely)
                    if 'TOKEN' in env_key:
                        safe_value = env_value[:10] + "..." if len(env_value) > 10 else "SHORT_VALUE"
                        self.logger.info(f"🔍 DEBUG: Found {env_key}={safe_value}")
                    else:
                        self.logger.info(f"🔍 DEBUG: Found {env_key}={env_value}")

                    # Skip placeholder values
                    if env_value in ['your_token_here', 'YOUR_DISCORD_TOKEN_HERE', 'your_user_id_here', '']:
                        self.logger.warning(f"⚠️ DEBUG: Skipping placeholder value for {env_key}")
                        continue

                    # Apply real value to config.json
                    current_obj = config_data
                    for i, path_segment in enumerate(config_path[:-1]):
                        if path_segment not in current_obj:
                            current_obj[path_segment] = {}
                        current_obj = current_obj[path_segment]

                    # Set the final value
                    final_key = config_path[-1]
                    old_value = current_obj.get(final_key, '')

                    self.logger.info(f"🔍 DEBUG: Config path: {' -> '.join(config_path)}")
                    self.logger.info(f"🔍 DEBUG: Old value: {old_value}")

                    # Only update if we're replacing a placeholder or empty value
                    if old_value in ['YOUR_DISCORD_TOKEN_HERE', 'your_token_here', '', None]:
                        current_obj[final_key] = env_value
                        config_updated = True
                        synced_values.append(f"{env_key} -> {final_key}")
                        self.logger.info(f"✅ DEBUG: Updated {env_key} -> {final_key}")
                    else:
                        self.logger.info(f"ℹ️ DEBUG: Skipped {env_key} (already has non-placeholder value)")
                else:
                    self.logger.info(f"❌ DEBUG: {env_key} not found in .env")

            # Save updated config.json
            if config_updated:
                config_data['last_updated'] = datetime.now().isoformat()

                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)

                self.logger.info(f"🔄 Smart Config Sync for {client_id}: {', '.join(synced_values)}")
                return True
            else:
                self.logger.warning(f"❌ DEBUG: No config sync performed for {client_id} - no updates needed")
                return False

        except Exception as e:
            self.logger.error(f"❌ Failed to sync configuration for {client_id}: {e}")
            import traceback
            self.logger.error(f"❌ DEBUG: Full traceback: {traceback.format_exc()}")
            return False

    def _create_backup(self, backup_name: str) -> None:
        """Create backup of current state."""
        try:
            backup_dir = Path("bot_platform/backups") / f"{backup_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Backup configuration files
            if self.config_path.exists():
                shutil.copy2(self.config_path, backup_dir / "platform_config.json")

            if self.client_manager_db.exists():
                shutil.copy2(self.client_manager_db, backup_dir / "clients.json")

            self.logger.debug(f"Created backup: {backup_dir}")

        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")

    def _report_remaining_issues(self, inconsistencies: List[Dict[str, Any]], fixed_count: int) -> None:
        """Report issues that couldn't be auto-fixed."""
        remaining_issues = []

        for inconsistency in inconsistencies[fixed_count:]:
            for issue in inconsistency['issues']:
                remaining_issues.append(f"{inconsistency['client_id']}: {issue['description']}")

        if remaining_issues:
            self.logger.warning(f"⚠️ {len(remaining_issues)} issues could not be auto-fixed:")
            for issue in remaining_issues[:5]:  # Show first 5
                self.logger.warning(f"  • {issue}")
            if len(remaining_issues) > 5:
                self.logger.warning(f"  • ... and {len(remaining_issues) - 5} more")

    def _merge_all_client_sources(self, discovery_results: Dict[str, Dict[str, Any]]) -> Dict[str, ClientConfig]:
        """Merge client information from all sources into final configuration."""
        merged_configs = {}

        # Get all unique client IDs
        all_client_ids = set()
        for source in discovery_results.values():
            all_client_ids.update(source.keys())

        for client_id in all_client_ids:
            # Start with defaults
            config_data = {
                'client_id': client_id,
                'display_name': client_id.replace('_', ' ').title(),
                'enabled': True,
                'auto_restart': True,
                'max_restarts': 5,
                'restart_delay': 30,
                'memory_limit_mb': 512,
                'custom_env': {}
            }

            # Merge data from different sources (priority: database > config > directory)
            if client_id in discovery_results['directories']:
                dir_config = discovery_results['directories'][client_id].get('config', {})
                config_data.update(dir_config)

            if client_id in discovery_results['config']:
                platform_config = discovery_results['config'][client_id].get('data', {})
                config_data.update(platform_config)

            if client_id in discovery_results['database']:
                db_config = discovery_results['database'][client_id].get('data', {})
                config_data.update(db_config)

            # Create ClientConfig object
            merged_configs[client_id] = ClientConfig(**{
                k: v for k, v in config_data.items()
                if k in ['client_id', 'display_name', 'enabled', 'auto_restart',
                        'max_restarts', 'restart_delay', 'memory_limit_mb', 'custom_env']
            })

        return merged_configs

    def _initialize_health_tracking(self) -> None:
        """Initialize health tracking for all clients."""
        for client_id in self.client_configs:
            self.client_health_status[client_id] = {
                'config_health': 'healthy',
                'last_check': datetime.now().isoformat(),
                'issues': [],
                'auto_fixes_applied': 0
            }

    def _save_platform_config(self) -> None:
        """Save current platform configuration."""
        try:
            config_data = {
                'platform': {
                    'name': 'Multi-Client Discord Bot Platform',
                    'version': '2.0.2',
                    'last_updated': datetime.now().isoformat()
                },
                'auto_healing': self.auto_healing_config,
                'logging': {
                    'startup_verbosity': 'INFO',
                    'show_config_validation': True,
                    'show_auto_healing_actions': True
                },
                'clients': [asdict(config) for config in self.client_configs.values()]
            }

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"Failed to save platform config: {e}")

    def get_enhanced_platform_stats(self) -> Dict[str, Any]:
        """Get enhanced platform statistics with health information."""
        base_stats = self.get_platform_stats()

        # Get current auto-healing state
        current_auto_healing = self.auto_healing_config["enabled"]

        # Add health information
        health_summary = {
            "healthy_clients": 0,
            "clients_with_issues": 0,
            "total_auto_fixes": len(self.auto_fix_log),
            "auto_healing_enabled": current_auto_healing
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
        self.logger.info(f"🚀 Starting client: {client_id}")
        return self.start_client(client_id)

    def _force_smart_config_sync_on_existing_files(self) -> None:
        """
        Force Smart Configuration Sync on all existing config.json files.
        This ensures existing files get updated with real tokens from .env
        """
        if not self.auto_healing_config.get("enabled", True):
            return

        self.logger.info("🔄 Running Smart Config Sync on existing files...")

        sync_count = 0
        for client_id in self.client_configs:
            client_dir = self.clients_dir / client_id
            config_file = client_dir / 'config.json'

            if config_file.exists():
                try:
                    # Check if config has placeholder tokens
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)

                    # Check if discord token is a placeholder
                    discord_token = config_data.get('discord', {}).get('token', '')

                    if discord_token in ['YOUR_DISCORD_TOKEN_HERE', 'your_token_here', '']:
                        self.logger.info(f"🔍 Found placeholder token in {client_id}, running Smart Config Sync...")

                        if self._sync_configuration_from_env(client_id, config_file):
                            sync_count += 1
                            self.logger.info(f"✅ Updated config.json for {client_id}")
                        else:
                            self.logger.warning(f"⚠️ Could not sync config for {client_id}")
                    else:
                        self.logger.debug(f"✅ {client_id} already has real token, skipping")

                except Exception as e:
                    self.logger.error(f"❌ Error checking config for {client_id}: {e}")

        if sync_count > 0:
            self.logger.info(f"🔄 Smart Config Sync completed: updated {sync_count} config files")
        else:
            self.logger.info("ℹ️ Smart Config Sync: no updates needed")

    # ====================================================================
    # ORIGINAL LAUNCHER METHODS (Preserved from original launcher.py)
    # ====================================================================

    def _load_synchronized_config(self) -> None:
        """Load configuration with auto-detection and auto-healing."""
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

        # Step 6: Force Smart Config Sync on existing files
        self._force_smart_config_sync_on_existing_files()

        # Step 7: Initialize health tracking
        self._initialize_health_tracking()

        # Step 8: Save updated configuration
        self._save_platform_config()

        # Step 9: Success summary
        total_clients = len(self.client_configs)
        discovery_results_summary = {
            'directories': len(discovery_results.get('directories', {})),
            'database': len(discovery_results.get('database', {})),
            'config': len(discovery_results.get('config', {})),
            'running': len(discovery_results.get('running', {}))
        }

        self.logger.info(f"📊 Discovery results: {discovery_results_summary['directories']} directories, "
                         f"{discovery_results_summary['database']} in database, "
                         f"{discovery_results_summary['config']} in config, "
                         f"{discovery_results_summary['running']} running")

        if fixed_count > 0:
            self.logger.info(f"✅ Platform ready with {total_clients} clients (auto-fixed {fixed_count} issues)")
        else:
            self.logger.info(f"✅ Platform ready with {total_clients} clients")

    def get_platform_stats(self) -> Dict[str, Any]:
        """Get comprehensive platform statistics."""
        current_time = datetime.now(timezone.utc)
        uptime = (current_time - self.start_time).total_seconds() / 3600

        # Collect client statistics
        client_stats = {}
        for client_id, client_config in self.client_configs.items():
            process_info = self.client_processes.get(client_id)

            if process_info and process_info.process:
                try:
                    # Get process information
                    proc = psutil.Process(process_info.process.pid)
                    memory_mb = proc.memory_info().rss / 1024 / 1024
                    cpu_percent = proc.cpu_percent(interval=0.1)

                    process_uptime = (current_time - process_info.started_at).total_seconds() / 3600

                    client_stats[client_id] = {
                        "running": True,
                        "pid": process_info.process.pid,
                        "uptime_hours": round(process_uptime, 1),
                        "memory_mb": round(memory_mb, 1),
                        "cpu_percent": round(cpu_percent, 1),
                        "restart_count": process_info.restart_count,
                        "last_restart": process_info.last_restart.isoformat() if process_info.last_restart else None,
                        "status": process_info.status
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    client_stats[client_id] = {
                        "running": False,
                        "status": "process_not_found",
                        "restart_count": process_info.restart_count
                    }
            else:
                client_stats[client_id] = {
                    "running": False,
                    "status": "stopped",
                    "restart_count": 0
                }

        return {
            "platform": {
                "uptime_hours": round(uptime, 1),
                "total_clients": len(self.client_configs),
                "running_clients": len([c for c in client_stats.values() if c.get("running")]),
                "total_restarts": self.total_restarts,
                "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None
            },
            "clients": client_stats
        }

    def _discover_running_clients(self) -> None:
        """Discover and register already running client processes."""
        discovered_count = 0

        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and len(cmdline) >= 2:
                        # Look for client runner processes
                        if 'client_runner.py' in ' '.join(cmdline):
                            for arg in cmdline:
                                if arg.startswith('--client='):
                                    client_id = arg.split('=', 1)[1]

                                    # Create a mock subprocess.Popen object
                                    mock_process = type('MockProcess', (), {
                                        'pid': proc.info['pid'],
                                        'poll': lambda: None,  # Process is running
                                        'terminate': lambda: proc.terminate(),
                                        'kill': lambda: proc.kill()
                                    })()

                                    self.client_processes[client_id] = ClientProcess(
                                        client_id=client_id,
                                        process=mock_process,
                                        started_at=datetime.fromtimestamp(proc.info['create_time'], tz=timezone.utc),
                                        pid=proc.info['pid']
                                    )
                                    discovered_count += 1
                                    break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            self.logger.error(f"Error discovering running clients: {e}")

        if discovered_count > 0:
            self.logger.info(f"Discovered {discovered_count} running client processes")

    def start_client(self, client_id: str) -> bool:
        """Start a specific client."""
        if client_id not in self.client_configs:
            self.logger.error(f"Client {client_id} not found in configuration")
            return False

        if client_id in self.client_processes:
            process_info = self.client_processes[client_id]
            if process_info.process and process_info.process.poll() is None:
                self.logger.warning(f"Client {client_id} is already running")
                return True

        config = self.client_configs[client_id]
        if not config.enabled:
            self.logger.warning(f"Client {client_id} is disabled")
            return False

        try:
            # Build command to start the client - FIXED ARGUMENTS
            cmd = [
                sys.executable,
                str(Path("bot_platform/client_runner.py").resolve()),
                f"--client-id={client_id}"  # FIXED: Use --client-id
            ]

            # Set up environment
            env = os.environ.copy()
            env.update(config.custom_env)

            # Start the process with better error capture
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Capture both stdout and stderr
                cwd=Path.cwd(),
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Register the process
            self.client_processes[client_id] = ClientProcess(
                client_id=client_id,
                process=process,
                pid=process.pid
            )

            self.logger.info(f"Started client {client_id} (PID: {process.pid})")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start client {client_id}: {e}")
            return False

    def stop_client(self, client_id: str) -> bool:
        """Stop a specific client."""
        if client_id not in self.client_processes:
            self.logger.warning(f"Client {client_id} is not running")
            return True

        process_info = self.client_processes[client_id]
        try:
            if process_info.process and process_info.process.poll() is None:
                self.logger.info(f"Stopping client {client_id}...")
                process_info.process.terminate()

                # Wait for graceful shutdown
                try:
                    process_info.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.logger.warning(f"Force killing client {client_id}")
                    process_info.process.kill()
                    process_info.process.wait()

            del self.client_processes[client_id]
            self.logger.info(f"Stopped client {client_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error stopping client {client_id}: {e}")
            return False

    def restart_client(self, client_id: str) -> bool:
        """Restart a specific client."""
        self.logger.info(f"Restarting client {client_id}")

        if self.stop_client(client_id):
            time.sleep(2)  # Brief pause
            return self.start_client(client_id)
        return False

    async def start_all_clients(self) -> None:
        """Start all enabled clients."""
        enabled_clients = [
            client_id for client_id, config in self.client_configs.items()
            if config.enabled
        ]

        if not enabled_clients:
            self.logger.warning("No enabled clients found")
            return

        self.logger.info(f"Starting {len(enabled_clients)} clients...")

        started_clients = []
        for client_id in enabled_clients:
            if self.start_client(client_id):
                started_clients.append(client_id)

            # Brief pause between starts
            await asyncio.sleep(0.5)

        if started_clients:
            self.logger.info(f"Started {len(started_clients)} clients: {', '.join(started_clients)}")
        else:
            self.logger.error("Failed to start any clients")

    async def stop_all_clients(self) -> None:
        """Stop all running clients."""
        if not self.client_processes:
            self.logger.info("No clients are currently running")
            return

        self.logger.info(f"Stopping {len(self.client_processes)} clients...")

        stopped_clients = []
        for client_id in list(self.client_processes.keys()):
            if self.stop_client(client_id):
                stopped_clients.append(client_id)

        if stopped_clients:
            self.logger.info(f"Stopped {len(stopped_clients)} clients: {', '.join(stopped_clients)}")

    async def health_check(self) -> None:
        """Perform health check on all clients."""
        self.last_health_check = datetime.now(timezone.utc)

        for client_id, process_info in self.client_processes.items():
            try:
                if process_info.process.poll() is not None:
                    # Process has died
                    self.logger.warning(f"Client {client_id} process has died")

                    config = self.client_configs.get(client_id)
                    if config and config.auto_restart and process_info.restart_count < config.max_restarts:
                        self.logger.info(f"Auto-restarting client {client_id}")
                        process_info.restart_count += 1
                        process_info.last_restart = datetime.now(timezone.utc)
                        self.total_restarts += 1

                        await asyncio.sleep(config.restart_delay)
                        self.start_client(client_id)
                    else:
                        self.logger.error(f"Client {client_id} exceeded max restarts or auto-restart disabled")

            except Exception as e:
                self.logger.error(f"Health check error for client {client_id}: {e}")

    async def run(self) -> None:
        """Main event loop for the platform."""
        self.logger.info("Platform launcher started")

        # Start all enabled clients
        await self.start_all_clients()

        try:
            while not self.shutdown_requested:
                await self.health_check()
                await asyncio.sleep(30)  # Health check every 30 seconds

        except KeyboardInterrupt:
            self.logger.info("Shutdown requested")
        finally:
            self.shutdown_requested = True
            await self.stop_all_clients()
            self.logger.info("Platform launcher stopped")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
