"""
Template-Based Execution Strategy
=================================

Executes Discord.py bots using templates for convenience features.
Templates provide technical enhancements without business logic coupling.
"""

import asyncio
import sys
import subprocess
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

from .bot_execution_strategy import (
    BotExecutionStrategy, 
    BotConfiguration, 
    ProcessHandle, 
    ExecutionError
)
from ..entities.process_info import ProcessInfo, ProcessSource, HealthStatus
from ..services.template_discovery_service import TemplateDiscoveryService, TemplateMetadata


class TemplateBasedStrategy(BotExecutionStrategy):
    """
    Template-based execution strategy.
    
    Provides convenience templates with technical enhancements while
    maintaining zero business logic coupling. Templates are purely
    technical convenience features.
    """
    
    def __init__(self, 
                 template_discovery_service: TemplateDiscoveryService = None,
                 logger: logging.Logger = None):
        """
        Initialize template-based strategy.
        
        Args:
            template_discovery_service: Service for template discovery and management
            logger: Logger instance for strategy operations
        """
        self.logger = logger or logging.getLogger(__name__)
        self.template_service = template_discovery_service or TemplateDiscoveryService(logger=self.logger)
    
    @property
    def strategy_name(self) -> str:
        """Name of this execution strategy."""
        return "template"
    
    @property
    def supports_zero_modification(self) -> bool:
        """Templates provide convenience but don't require modifications."""
        return True
    
    async def validate_configuration(self, config: BotConfiguration) -> bool:
        """
        Validate configuration for template-based execution.
        
        Checks for:
        - Discord token presence
        - Template specification and availability
        - Template-specific requirements
        """
        try:
            # Check Discord token
            discord_token = config.environment_config.get("DISCORD_TOKEN")
            if not discord_token:
                self.logger.error(f"No Discord token provided for {config.client_id}")
                return False
            
            # Check template specification
            template_name = config.environment_config.get("TEMPLATE_NAME")
            if not template_name:
                self.logger.error(f"No template specified for {config.client_id}")
                return False
            
            # Use template service for validation
            if not await self.template_service.validate_template(template_name):
                self.logger.error(f"Template '{template_name}' validation failed")
                return False
            
            # Get template metadata
            template_metadata = await self.template_service.get_template(template_name)
            if not template_metadata:
                self.logger.error(f"Template '{template_name}' not found")
                return False
            
            # Check template requirements
            if not await self._validate_template_requirements(template_metadata, config):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    async def prepare_execution_environment(self, config: BotConfiguration) -> Dict[str, Any]:
        """
        Prepare execution environment for template-based bot.
        
        Sets up template environment with technical enhancements.
        """
        try:
            template_name = config.environment_config.get("TEMPLATE_NAME")
            
            # Get template metadata from service
            template_metadata = await self.template_service.get_template(template_name)
            if not template_metadata:
                raise ExecutionError(f"Template '{template_name}' not found", self.strategy_name, config)
            
            # Create bot workspace
            bot_workspace = Path(f"bots/{config.client_id}")
            bot_workspace.mkdir(parents=True, exist_ok=True)
            
            # Copy template to workspace
            await self._instantiate_template(template_metadata, bot_workspace, config)
            
            # Prepare environment variables
            env = os.environ.copy()
            env.update(config.environment_config)
            
            # Add template-specific environment variables
            env.update(template_metadata.environment)
            
            # Ensure UTF-8 encoding
            env['PYTHONIOENCODING'] = 'utf-8'
            if os.name == 'nt':  # Windows
                env['PYTHONLEGACYWINDOWSSTDIO'] = '1'
            
            # Prepare log directory
            config.log_directory.mkdir(parents=True, exist_ok=True)
            
            return {
                "environment": env,
                "working_directory": bot_workspace,
                "template_metadata": template_metadata,
                "log_directory": config.log_directory,
                "bot_file": bot_workspace / template_metadata.main_file
            }
            
        except Exception as e:
            self.logger.error(f"Failed to prepare template environment for {config.client_id}: {e}")
            raise ExecutionError(f"Template environment preparation failed: {e}", self.strategy_name, config)
    
    async def start(self, config: BotConfiguration) -> ProcessHandle:
        """
        Start a template-based Discord bot process.
        
        Instantiates template and executes with technical enhancements.
        """
        try:
            # Validate configuration first
            if not await self.validate_configuration(config):
                raise ExecutionError("Template configuration validation failed", self.strategy_name, config)
            
            # Prepare environment
            env_setup = await self.prepare_execution_environment(config)
            
            # Build command to execute bot
            bot_file = env_setup["bot_file"]
            if not bot_file.exists():
                raise ExecutionError(f"Template bot file not found: {bot_file}", self.strategy_name, config)
            
            # Use just the filename since we're setting cwd to the bot workspace
            template_metadata = env_setup["template_metadata"]
            cmd = [sys.executable, template_metadata.main_file]
            
            # Set up logging
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file_path = config.log_directory / f"template_bot_output_{timestamp}.log"
            
            # Start the process
            with open(log_file_path, 'w', encoding='utf-8', errors='replace', buffering=1) as log_file:
                process = subprocess.Popen(
                    cmd,
                    env=env_setup["environment"],
                    cwd=env_setup["working_directory"],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1
                )
            
            # Create ProcessInfo
            process_info = ProcessInfo(
                process_id=None,  # Will be set by repository
                instance_id=config.instance_id,
                client_id=config.client_id,
                pid=process.pid,
                started_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                source=ProcessSource.LAUNCHED,
                log_file_path=str(log_file_path),
                terminal_instance=f"template_{process.pid}"
            )
            
            # Create process handle
            handle = ProcessHandle(
                process_info=process_info,
                subprocess_handle=process
            )
            
            template_name = config.environment_config.get("TEMPLATE_NAME")
            self.logger.info(f"Started template bot {config.client_id} using '{template_name}' (PID: {process.pid})")
            return handle
            
        except Exception as e:
            self.logger.error(f"Failed to start template bot {config.client_id}: {e}")
            raise ExecutionError(f"Template bot startup failed: {e}", self.strategy_name, config)
    
    async def stop(self, handle: ProcessHandle) -> bool:
        """
        Stop a running template-based bot process.
        
        Uses same graceful termination as standard strategy.
        """
        try:
            if not handle.is_running:
                return True
            
            process = handle.subprocess_handle
            if process:
                # Try graceful termination first
                process.terminate()
                try:
                    process.wait(timeout=10)
                    self.logger.info(f"Gracefully stopped template bot {handle.process_info.client_id}")
                    return True
                except subprocess.TimeoutExpired:
                    # Force kill if graceful termination fails
                    process.kill()
                    process.wait()
                    self.logger.warning(f"Force killed template bot {handle.process_info.client_id}")
                    return True
            else:
                # Use psutil for process not started by us
                import psutil
                try:
                    proc = psutil.Process(handle.process_info.pid)
                    proc.terminate()
                    proc.wait(timeout=10)
                    return True
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    try:
                        proc.kill()
                        return True
                    except psutil.NoSuchProcess:
                        return True  # Already dead
                    
        except Exception as e:
            self.logger.error(f"Failed to stop template bot {handle.process_info.client_id}: {e}")
            return False
    
    async def restart(self, handle: ProcessHandle, config: BotConfiguration) -> ProcessHandle:
        """
        Restart a template-based bot process.
        
        Stops the current process and starts a new one with updated configuration.
        """
        try:
            # Stop current process
            stop_success = await self.stop(handle)
            if not stop_success:
                self.logger.warning(f"Failed to cleanly stop template bot {config.client_id}, continuing with restart")
            
            # Wait a moment for cleanup
            await asyncio.sleep(1)
            
            # Start new process
            new_handle = await self.start(config)
            
            # Update restart count
            new_handle.process_info.restart_count = handle.process_info.restart_count + 1
            new_handle.process_info.last_restart = datetime.now(timezone.utc)
            
            self.logger.info(f"Restarted template bot {config.client_id} (new PID: {new_handle.process_info.pid})")
            return new_handle
            
        except Exception as e:
            self.logger.error(f"Failed to restart template bot {config.client_id}: {e}")
            raise ExecutionError(f"Template bot restart failed: {e}", self.strategy_name, config)
    
    async def get_health_status(self, handle: ProcessHandle) -> HealthStatus:
        """Get detailed health status for the template bot process."""
        return handle.process_info.get_current_health_status()
    
    async def get_logs(self, handle: ProcessHandle, lines: int = 100) -> List[str]:
        """
        Get recent log lines from the template bot process.
        """
        try:
            log_file_path = handle.process_info.log_file_path
            if not log_file_path or not Path(log_file_path).exists():
                return ["Log file not found"]
            
            # Read last N lines from log file
            with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()
                return [line.rstrip() for line in all_lines[-lines:]]
                
        except Exception as e:
            self.logger.error(f"Failed to read template bot logs for {handle.process_info.client_id}: {e}")
            return [f"Error reading logs: {e}"]
    
    async def list_available_templates(self) -> List[Dict[str, Any]]:
        """Get list of available templates using template discovery service."""
        try:
            templates_metadata = await self.template_service.discover_templates()
            return [template.to_dict() for template in templates_metadata]
            
        except Exception as e:
            self.logger.error(f"Failed to list templates: {e}")
            return []
    
    
    async def _validate_template_requirements(self, template_metadata: TemplateMetadata, config: BotConfiguration) -> bool:
        """Validate template-specific requirements."""
        try:
            requirements = template_metadata.requirements
            
            for requirement in requirements:
                if requirement.get("type") == "environment_variable":
                    var_name = requirement.get("name")
                    if var_name not in config.environment_config:
                        if requirement.get("required", False):
                            self.logger.error(f"Required environment variable '{var_name}' not provided")
                            return False
                
                elif requirement.get("type") == "feature":
                    feature_name = requirement.get("name")
                    if feature_name not in config.technical_features:
                        if requirement.get("required", False):
                            self.logger.error(f"Required feature '{feature_name}' not enabled")
                            return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to validate template requirements: {e}")
            return False
    
    async def _instantiate_template(self, template_metadata: TemplateMetadata, workspace: Path, config: BotConfiguration) -> None:
        """Instantiate template in bot workspace with configuration substitution."""
        try:
            # Copy template files to workspace
            template_path = template_metadata.template_path
            for item in template_path.iterdir():
                if item.name == "template.json":
                    continue  # Skip template metadata
                
                if item.is_file():
                    # Copy file with potential template substitution
                    await self._copy_template_file(item, workspace / item.name, config)
                elif item.is_dir():
                    # Copy directory recursively
                    shutil.copytree(item, workspace / item.name, dirs_exist_ok=True)
            
        except Exception as e:
            self.logger.error(f"Failed to instantiate template: {e}")
            raise
    
    async def _copy_template_file(self, source: Path, destination: Path, config: BotConfiguration) -> None:
        """Copy template file with configuration substitution."""
        try:
            # Simple template variable substitution
            template_vars = {
                "CLIENT_ID": config.client_id,
                "DISCORD_TOKEN": config.environment_config.get("DISCORD_TOKEN", ""),
                **config.environment_config
            }
            
            if source.suffix in ['.py', '.txt', '.md', '.json', '.yml', '.yaml']:
                # Text file - perform substitution
                content = source.read_text(encoding='utf-8')
                for var_name, var_value in template_vars.items():
                    content = content.replace(f"{{{{{var_name}}}}}", str(var_value))
                
                destination.write_text(content, encoding='utf-8')
            else:
                # Binary file - direct copy
                shutil.copy2(source, destination)
                
        except Exception as e:
            self.logger.error(f"Failed to copy template file {source} to {destination}: {e}")
            raise