"""
Local bot process management with advanced orchestration.
"""

import json
import toml
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from .process_orchestrator import ProcessOrchestrator, ProcessStatus
from .health_monitor import HealthMonitor
from multicord.utils.sync import ConfigSync
from multicord.utils.template_repository import TemplateRepository


class BotManager:
    """Manages local Discord bot processes with health monitoring."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".multicord"
        self.bots_dir = self.config_dir / "bots"
        self.templates_dir = self.config_dir / "templates"

        # Ensure directories exist
        self.bots_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Initialize orchestrator and health monitor
        self.orchestrator = ProcessOrchestrator(bots_dir=self.bots_dir)
        self.health_monitor = HealthMonitor(self.orchestrator)

        # Initialize template repository manager
        self.template_repo = TemplateRepository()
    
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
                    
                    # Check if template metadata exists
                    template = "unknown"
                    meta_file = bot_dir / ".multicord_meta.json"
                    if meta_file.exists():
                        try:
                            with open(meta_file, encoding='utf-8') as f:
                                meta = json.load(f)
                                template = meta.get("template", "unknown")
                        except:
                            pass
                    
                    if status is None or status == "all" or status == bot_status:
                        bots.append({
                            "name": bot_name,
                            "status": bot_status,
                            "template": template,
                            "pid": pid,
                            "port": port,
                            "memory_mb": memory_mb,
                            "cpu_percent": cpu_percent
                        })
        return bots
    
    def create_bot(self, name: str, template: str, repo: Optional[str] = None) -> Path:
        """
        Create a new bot from template repository.

        Args:
            name: Bot name to create
            template: Template name to use
            repo: Specific repository to use, or None to auto-detect by priority

        Returns:
            Path to created bot directory
        """
        bot_path = self.bots_dir / name
        if bot_path.exists():
            raise ValueError(f"Bot '{name}' already exists")

        # Find template using priority system if repo not specified
        if repo is None:
            template_match = self.template_repo.find_template(template)
            if not template_match:
                raise ValueError(
                    f"Template '{template}' not found in any enabled repository. "
                    f"Run 'multicord template list' to see available templates or "
                    f"'multicord repo update --all' to refresh repositories."
                )
            repo, template_info = template_match
        else:
            # Use specific repository
            template_info = self.template_repo.get_template_info(template, repo)
            if not template_info:
                raise ValueError(f"Template '{template}' not found in repository '{repo}'")

        # Install template from repository
        try:
            self.template_repo.install_template(template, bot_path, repo)

            # Create metadata file with version tracking
            meta_file = bot_path / ".multicord_meta.json"
            meta_data = {
                "template": template,
                "repository": repo,
                "template_version": template_info.get("version", "unknown"),
                "created_at": datetime.now().isoformat(),
                "multicord_version": "1.0.0"
            }
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(meta_data, f, indent=2)

            # Create logs directory
            (bot_path / "logs").mkdir(exist_ok=True)

            # Create data directory for bot data
            (bot_path / "data").mkdir(exist_ok=True)

            return bot_path

        except Exception as e:
            # Clean up on failure
            if bot_path.exists():
                import shutil
                shutil.rmtree(bot_path)
            raise RuntimeError(f"Failed to create bot from template: {e}")
    
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
    
    def list_templates(self) -> List[Dict[str, str]]:
        """List available templates."""
        templates = []
        
        # Check builtin templates directory
        templates_dir = Path(__file__).parent.parent.parent / "templates"
        if templates_dir.exists():
            for template_dir in templates_dir.iterdir():
                if template_dir.is_dir():
                    # Try to read template description from config
                    description = "Custom template"
                    config_file = template_dir / "config.toml"
                    if config_file.exists():
                        try:
                            import toml
                            with open(config_file, encoding='utf-8') as f:
                                config = toml.load(f)
                                description = config.get("bot", {}).get("description", description)
                        except:
                            pass
                    
                    templates.append({
                        "name": template_dir.name,
                        "description": description,
                        "type": "builtin"
                    })
        
        # Check user templates in templates directory
        user_templates_dir = self.templates_dir
        if user_templates_dir.exists():
            for template_dir in user_templates_dir.iterdir():
                if template_dir.is_dir():
                    templates.append({
                        "name": template_dir.name,
                        "description": "User template",
                        "type": "user"
                    })
        
        # If no templates found, return defaults
        if not templates:
            templates = [
                {"name": "basic", "description": "Basic Discord bot", "type": "builtin"},
                {"name": "music", "description": "Music bot template", "type": "builtin"},
                {"name": "moderation", "description": "Moderation bot template", "type": "builtin"}
            ]
        
        return templates
    
    def install_template(self, url: str, name: Optional[str] = None) -> str:
        """Install a template from URL."""
        # TODO: Implement template installation
        return name or "custom"

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

        # Get template info from metadata
        template = "custom"
        meta_file = bot_path / ".multicord_meta.json"
        if meta_file.exists():
            try:
                with open(meta_file, encoding='utf-8') as f:
                    meta = json.load(f)
                    template = meta.get("template", "custom")
            except:
                pass

        # Build deployment package
        deploy_package = {
            "name": bot_name,
            "template": template,
            "config": config,
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
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