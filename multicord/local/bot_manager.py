"""
Local bot process management with advanced orchestration.
"""

import json
import shutil
import toml
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from .process_orchestrator import ProcessOrchestrator, ProcessStatus
from .health_monitor import HealthMonitor
from multicord.utils.sync import ConfigSync
from multicord.utils.venv_manager import VenvManager
from multicord.utils.cog_manager import CogManager
from multicord.utils.token_manager import TokenManager
from multicord.utils.validation import validate_path_containment


class BotManager:
    """Manages local Discord bot processes with health monitoring."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".multicord"
        self.bots_dir = self.config_dir / "bots"

        # Ensure directories exist
        self.bots_dir.mkdir(parents=True, exist_ok=True)

        # Initialize orchestrator and health monitor
        self.orchestrator = ProcessOrchestrator(bots_dir=self.bots_dir)
        self.health_monitor = HealthMonitor(self.orchestrator)

        # Initialize virtual environment manager
        self.venv_manager = VenvManager(bots_dir=self.bots_dir)

        # Initialize secure token manager
        self.token_manager = TokenManager(config_dir=self.config_dir)
    
    def list_bots(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all local bots with orchestrator status."""
        bots = []
        
        # Get running bots from orchestrator
        running_bots = self.orchestrator.list_running_bots()
        running_names = {bot['name'] for bot in running_bots}
        
        # Scan directory for all bots
        if self.bots_dir.exists():
            for bot_dir in self.bots_dir.iterdir():
                if bot_dir.is_dir():
                    bot_name = bot_dir.name
                    
                    # Get status from orchestrator or mark as stopped
                    if bot_name in running_names:
                        bot_data = next(b for b in running_bots if b['name'] == bot_name)
                        bot_status = "running"
                        pid = bot_data.get('pid')
                        port = bot_data.get('port')
                        memory_mb = bot_data.get('memory_mb', 0)
                        cpu_percent = bot_data.get('cpu_percent', 0)
                    else:
                        bot_status = "stopped"
                        pid = None
                        port = None
                        memory_mb = 0
                        cpu_percent = 0
                    
                    # Check if source metadata exists
                    source = "unknown"
                    meta_file = bot_dir / ".multicord_meta.json"
                    if meta_file.exists():
                        try:
                            with open(meta_file, encoding='utf-8') as f:
                                meta = json.load(f)
                                source = meta.get("source", "unknown")
                        except:
                            pass

                    if status is None or status == "all" or status == bot_status:
                        bots.append({
                            "name": bot_name,
                            "status": bot_status,
                            "template": source,
                            "pid": pid,
                            "port": port,
                            "memory_mb": memory_mb,
                            "cpu_percent": cpu_percent
                        })
        return bots
    
    def create_bot_from_path(self, name: str, source_path: Path, source_name: str = "unknown") -> Path:
        """
        Create a new bot from a pre-resolved source path.

        This method works with the SourceResolver pattern, where the source
        (bot source or imported repo) has already been resolved to a local path.

        Args:
            name: Bot name to create
            source_path: Path to the source directory (bot or repo)
            source_name: Name of the source for metadata tracking

        Returns:
            Path to created bot directory
        """
        bot_path = self.bots_dir / name
        is_contained, error = validate_path_containment(bot_path, self.bots_dir)
        if not is_contained:
            raise ValueError(f"Invalid bot name: {error}")
        if bot_path.exists():
            raise ValueError(f"Bot '{name}' already exists")

        try:
            # Discover bot structure dynamically
            from multicord.utils.source_resolver import SourceResolver, discover_bot_structure

            bot_files_path, metadata_path, entry_point = discover_bot_structure(source_path, source_name)

            # Copy bot files from discovered location
            SourceResolver.copy_source_files(bot_files_path, bot_path)

            # Copy metadata if found and not already copied
            if metadata_path and not (bot_path / metadata_path.name).exists():
                shutil.copy2(metadata_path, bot_path / metadata_path.name)

            # Auto-create .env file from .env.example
            env_example = bot_path / ".env.example"
            env_file = bot_path / ".env"
            if env_example.exists() and not env_file.exists():
                shutil.copy(env_example, env_file)
                print(f"✓ Created .env file from template")
                print(f"⚠ IMPORTANT: Add your DISCORD_TOKEN to {env_file.name} before starting the bot")

            # Create isolated virtual environment for bot
            venv_success, venv_msg = self.venv_manager.create_venv(bot_path)
            if not venv_success:
                raise RuntimeError(f"Failed to create virtual environment: {venv_msg}")

            # Install bot requirements into isolated venv
            requirements_file = bot_path / "requirements.txt"
            if requirements_file.exists():
                install_success, install_msg = self.venv_manager.install_requirements(bot_path)
                if not install_success:
                    raise RuntimeError(f"Failed to install requirements: {install_msg}")

            # Read source metadata from discovered manifest
            source_version = "unknown"
            requires_cogs = []

            if metadata_path and metadata_path.exists():
                try:
                    with open(metadata_path, encoding='utf-8') as f:
                        manifest_data = json.load(f)
                        source_version = manifest_data.get("version", "unknown")
                        requires_cogs = manifest_data.get("requires_cogs", [])
                except (json.JSONDecodeError, IOError):
                    pass

            # Detect and store entry point for downstream consumers
            from multicord.utils.bot_detector import detect_entry_point
            try:
                detected_entry = detect_entry_point(bot_path)
            except ValueError:
                detected_entry = entry_point  # fall back to discovery result

            # Create metadata file with version tracking
            from multicord import __version__
            meta_file = bot_path / ".multicord_meta.json"
            meta_data = {
                "source": source_name,
                "source_version": source_version,
                "entry_point": detected_entry,
                "created_at": datetime.now().isoformat(),
                "multicord_version": __version__
            }
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(meta_data, f, indent=2)

            # Auto-install required cogs if specified
            if requires_cogs:
                print(f"\nAuto-installing cogs for '{source_name}'...")
                from multicord.utils.source_resolver import SourceResolver, discover_cog_structure
                resolver = SourceResolver()

                for cog_spec in requires_cogs:
                    # Handle both string and dict formats
                    if isinstance(cog_spec, str):
                        cog_id = cog_spec
                        required = True
                        reason = ""
                    else:
                        cog_id = cog_spec.get("id")
                        required = cog_spec.get("required", True)
                        reason = cog_spec.get("reason", "")

                    try:
                        print(f"  Installing cog '{cog_id}'... ", end="", flush=True)
                        # Resolve cog source path
                        cog_source_path = resolver.resolve_source(cog_id)
                        # Discover cog structure dynamically
                        cog_package_path, cog_metadata_path = discover_cog_structure(cog_source_path, cog_id)
                        # Copy cog package to bot's cogs directory
                        cog_dest = bot_path / "cogs" / cog_id
                        SourceResolver.copy_source_files(cog_package_path, cog_dest)
                        # Copy cog metadata if found
                        if cog_metadata_path:
                            shutil.copy2(cog_metadata_path, cog_dest / cog_metadata_path.name)
                        # Install cog requirements if any
                        cog_requirements = cog_dest / "requirements.txt"
                        if cog_requirements.exists():
                            self.venv_manager.install_requirements(bot_path, cog_requirements)
                        msg = f"✓ Installed"
                        if reason:
                            msg += f" ({reason})"
                        print(msg)
                    except Exception as cog_error:
                        if required:
                            raise RuntimeError(f"Failed to install required cog '{cog_id}': {cog_error}")
                        else:
                            print(f"⚠ Failed (optional): {cog_error}")

            # Create logs directory
            (bot_path / "logs").mkdir(exist_ok=True)

            # Create data directory for bot data
            (bot_path / "data").mkdir(exist_ok=True)

            return bot_path

        except Exception as e:
            # Clean up on failure
            if bot_path.exists():
                shutil.rmtree(bot_path)
            raise RuntimeError(f"Failed to create bot from source: {e}")

    def start_bot(self, name: str, env_vars: Optional[Dict[str, str]] = None) -> int:
        """
        Start a bot process using orchestrator.

        Args:
            name: Bot name to start
            env_vars: Optional environment variables to inject into the bot process

        Returns:
            PID of the started process
        """
        success, message = self.orchestrator.start_bot(name, env_vars=env_vars)
        if not success:
            raise ValueError(message)

        # Extract PID from success message
        process_info = self.orchestrator.registry.get_process(name)
        if process_info:
            return process_info.pid
        return 0
    
    def stop_bot(self, name: str, force: bool = False) -> None:
        """Stop a bot process using orchestrator."""
        success, message = self.orchestrator.stop_bot(name, force=force)
        if not success:
            raise ValueError(message)
    
    def restart_bot(self, name: str) -> int:
        """Restart a bot process."""
        success, message = self.orchestrator.restart_bot(name)
        if not success:
            raise ValueError(message)
        
        # Return new PID
        process_info = self.orchestrator.registry.get_process(name)
        if process_info:
            return process_info.pid
        return 0
    
    def get_bot_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a bot with health information."""
        bot_path = self.bots_dir / name
        if not bot_path.exists():
            return None
        
        # Get process info from orchestrator
        process_info = self.orchestrator.registry.get_process(name)
        health = self.orchestrator.get_bot_health(name) if process_info else None
        
        status = {
            "name": name,
            "path": str(bot_path),
            "status": "running" if process_info and health and health.is_running else "stopped"
        }
        
        if process_info:
            status["pid"] = process_info.pid
            status["port"] = process_info.port
            status["started_at"] = process_info.started_at.isoformat()
            status["restart_count"] = process_info.restart_count
            
            if health:
                status["memory_mb"] = round(health.memory_mb, 2)
                status["cpu_percent"] = round(health.cpu_percent, 2)
                status["uptime_seconds"] = round(health.uptime_seconds)
                status["is_healthy"] = health.is_healthy
        
        return status
    
    def get_health_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive health dashboard data."""
        return self.health_monitor.get_health_summary()
    
    def display_health_dashboard(self):
        """Display live health dashboard in console."""
        self.health_monitor.display_health_dashboard()
    
    def get_logs(self, name: str, lines: int = 50) -> List[str]:
        """Get bot logs."""
        log_file = self.bots_dir / name / "logs" / "bot.log"
        if not log_file.exists():
            return ["No logs available"]
        
        with open(log_file, "r", encoding='utf-8') as f:
            all_lines = f.readlines()
            return all_lines[-lines:]
    
    def follow_logs(self, name: str) -> None:
        """Follow bot logs in real-time."""
        # TODO: Implement log following
        print(f"Following logs for {name}...")
    
    def export_bot_for_deploy(self, bot_name: str) -> Optional[Dict[str, Any]]:
        """Export bot configuration and metadata for cloud deployment."""
        bot_path = self.bots_dir / bot_name
        if not bot_path.exists():
            return None

        # Initialize sync manager
        sync_manager = ConfigSync(self.bots_dir)

        # Get bot configuration
        config = sync_manager.get_local_config(bot_name)
        if not config:
            return None

        # Get source info from metadata
        source = "custom"
        meta_file = bot_path / ".multicord_meta.json"
        if meta_file.exists():
            try:
                with open(meta_file, encoding='utf-8') as f:
                    meta = json.load(f)
                    source = meta.get("source", "custom")
            except:
                pass

        # Build deployment package
        deploy_package = {
            "name": bot_name,
            "template": source,
            "config": config,
            "metadata": {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "source": "local",
                "path": str(bot_path)
            }
        }

        # Remove sensitive data (token should be handled separately)
        if "token" in deploy_package["config"]:
            deploy_package["config"]["token"] = ""
            deploy_package["metadata"]["token_removed"] = True

        return deploy_package

    def import_bot_from_cloud(self, bot_name: str, cloud_config: Dict[str, Any]) -> bool:
        """Import bot configuration from cloud."""
        # Initialize sync manager
        sync_manager = ConfigSync(self.bots_dir)

        # Check if bot exists locally
        bot_path = self.bots_dir / bot_name
        if not bot_path.exists():
            # Create bot directory
            bot_path.mkdir(parents=True, exist_ok=True)

            # Create basic bot.py if it doesn't exist
            bot_file = bot_path / "bot.py"
            if not bot_file.exists():
                # Use basic template
                template_bot = Path(__file__).parent.parent.parent / "templates" / "basic" / "bot.py"
                if template_bot.exists():
                    import shutil
                    shutil.copy(template_bot, bot_file)

        # Save configuration
        return sync_manager.save_local_config(bot_name, cloud_config)

    def sync_bot_with_cloud(self, bot_name: str, cloud_config: Dict[str, Any], strategy: str = "newest") -> Dict[str, Any]:
        """Sync local bot with cloud configuration."""
        from multicord.utils.sync import MergeStrategy

        # Initialize sync manager
        sync_manager = ConfigSync(self.bots_dir)

        # Convert strategy string to enum
        strategy_map = {
            "local_first": MergeStrategy.LOCAL_FIRST,
            "cloud_first": MergeStrategy.CLOUD_FIRST,
            "newest": MergeStrategy.NEWEST,
            "manual": MergeStrategy.MANUAL
        }
        merge_strategy = strategy_map.get(strategy, MergeStrategy.NEWEST)

        # Perform sync
        return sync_manager.sync_bot(bot_name, cloud_config, merge_strategy)

    def get_venv_python(self, bot_name: str) -> Path:
        """
        Get path to bot's venv Python executable.

        Args:
            bot_name: Name of the bot

        Returns:
            Path to venv Python executable
        """
        bot_path = self.bots_dir / bot_name
        return self.venv_manager.get_venv_python(bot_path)

    def validate_bot_venv(self, bot_name: str) -> tuple[bool, str]:
        """
        Validate that a bot's virtual environment is properly set up.

        Args:
            bot_name: Name of the bot

        Returns:
            Tuple of (is_valid, message)
        """
        bot_path = self.bots_dir / bot_name
        if not bot_path.exists():
            return False, f"Bot '{bot_name}' does not exist"

        return self.venv_manager.validate_venv(bot_path)

    def get_bot_venv_info(self, bot_name: str) -> Optional[Dict]:
        """
        Get detailed information about a bot's virtual environment.

        Args:
            bot_name: Name of the bot

        Returns:
            Dictionary with venv info, or None if invalid
        """
        bot_path = self.bots_dir / bot_name
        if not bot_path.exists():
            return None

        return self.venv_manager.get_venv_info(bot_path)

    def set_bot_token(self, bot_name: str, token: str) -> bool:
        """
        Store Discord bot token securely.

        Args:
            bot_name: Name of the bot
            token: Discord bot token

        Returns:
            True if token stored successfully

        Raises:
            ValueError: If bot doesn't exist or token format is invalid
        """
        bot_path = self.bots_dir / bot_name
        if not bot_path.exists():
            raise ValueError(f"Bot '{bot_name}' does not exist")

        # Store token using TokenManager (validates format automatically)
        return self.token_manager.store_token(bot_name, token)

    def get_bot_token(self, bot_name: str) -> Optional[str]:
        """
        Retrieve Discord bot token from secure storage.

        Automatically migrates from .env file if token found there.

        Args:
            bot_name: Name of the bot

        Returns:
            Discord token if found, None otherwise
        """
        # Try secure storage first
        token = self.token_manager.get_token(bot_name)

        # If not in secure storage, check .env and auto-migrate
        if not token:
            bot_path = self.bots_dir / bot_name
            if bot_path.exists():
                if self.token_manager.migrate_from_env(bot_path, bot_name):
                    # Migration successful, retrieve the migrated token
                    token = self.token_manager.get_token(bot_name)

        return token

    def delete_bot_token(self, bot_name: str) -> bool:
        """
        Delete Discord bot token from secure storage.

        Args:
            bot_name: Name of the bot

        Returns:
            True if token deleted successfully
        """
        return self.token_manager.delete_token(bot_name)

    def migrate_bot_token(self, bot_name: str) -> tuple[bool, str]:
        """
        Manually migrate bot token from .env to secure storage.

        Args:
            bot_name: Name of the bot

        Returns:
            Tuple of (success, message)
        """
        bot_path = self.bots_dir / bot_name
        if not bot_path.exists():
            return False, f"Bot '{bot_name}' does not exist"

        # Check if already in secure storage
        if self.token_manager.get_token(bot_name):
            return False, "Token already in secure storage"

        # Attempt migration
        if self.token_manager.migrate_from_env(bot_path, bot_name):
            storage_method = self.token_manager.get_storage_method()
            return True, f"Token migrated to {storage_method}"
        else:
            return False, "No valid token found in .env file"

    def get_token_storage_method(self) -> str:
        """
        Get description of current token storage method.

        Returns:
            Human-readable description (e.g., "Windows Credential Manager")
        """
        return self.token_manager.get_storage_method()