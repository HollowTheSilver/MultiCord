"""
Standard Discord.py Execution Strategy
=====================================

Executes vanilla Discord.py bots with ZERO modifications required.
This strategy supports any standard Discord.py bot without framework coupling.
"""

import asyncio
import sys
import subprocess
import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone
import logging

from .bot_execution_strategy import (
    BotExecutionStrategy, 
    BotConfiguration, 
    ProcessHandle, 
    ExecutionError
)
from ..entities.process_info import ProcessInfo, ProcessSource, HealthStatus


class StandardDiscordPyStrategy(BotExecutionStrategy):
    """
    Standard Discord.py execution strategy.
    
    Executes vanilla Discord.py bots with zero modifications required.
    Supports any bot.py file or package-based Discord bot.
    """
    
    def __init__(self, logger: logging.Logger = None):
        """Initialize standard strategy."""
        self.logger = logger or logging.getLogger(__name__)
    
    @property
    def strategy_name(self) -> str:
        """Name of this execution strategy."""
        return "standard"
    
    @property
    def supports_zero_modification(self) -> bool:
        """This strategy supports zero-modification execution."""
        return True
    
    async def validate_configuration(self, config: BotConfiguration) -> bool:
        """
        Validate configuration for standard Discord.py execution.
        
        Checks for:
        - Discord token presence
        - Bot file existence
        - Python environment accessibility
        """
        try:
            # Check Discord token
            discord_token = config.environment_config.get("DISCORD_TOKEN")
            if not discord_token:
                self.logger.error(f"No Discord token provided for {config.client_id}")
                return False
            
            # Check for bot file
            bot_file = self._find_bot_file(config)
            if not bot_file:
                self.logger.error(f"No bot file found for {config.client_id}")
                return False
            
            # Verify Python accessibility
            try:
                result = subprocess.run([sys.executable, "--version"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    self.logger.error(f"Python not accessible: {result.stderr}")
                    return False
            except (subprocess.SubprocessError, subprocess.TimeoutExpired):
                self.logger.error("Failed to verify Python environment")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    async def prepare_execution_environment(self, config: BotConfiguration) -> Dict[str, Any]:
        """
        Prepare execution environment for standard Discord.py bot.
        
        Sets up environment variables and working directory without
        modifying the bot's code or structure.
        """
        try:
            # Start with system environment
            env = os.environ.copy()
            
            # Add bot-specific environment variables
            env.update(config.environment_config)
            
            # Ensure UTF-8 encoding
            env['PYTHONIOENCODING'] = 'utf-8'
            if os.name == 'nt':  # Windows
                env['PYTHONLEGACYWINDOWSSTDIO'] = '1'
            
            # Set working directory to bot location
            bot_file = self._find_bot_file(config)
            if bot_file:
                working_dir = bot_file.parent
            else:
                working_dir = Path(f"bots/{config.client_id}")
                working_dir.mkdir(parents=True, exist_ok=True)
            
            # Prepare log directory
            config.log_directory.mkdir(parents=True, exist_ok=True)
            
            return {
                "environment": env,
                "working_directory": working_dir,
                "bot_file": bot_file,
                "log_directory": config.log_directory
            }
            
        except Exception as e:
            self.logger.error(f"Failed to prepare environment for {config.client_id}: {e}")
            raise ExecutionError(f"Environment preparation failed: {e}", self.strategy_name, config)
    
    async def start(self, config: BotConfiguration) -> ProcessHandle:
        """
        Start a standard Discord.py bot process.
        
        Executes the bot using Python subprocess without any modifications
        to the bot's code or structure.
        """
        try:
            # Validate configuration first
            if not await self.validate_configuration(config):
                raise ExecutionError("Configuration validation failed", self.strategy_name, config)
            
            # Prepare environment
            env_setup = await self.prepare_execution_environment(config)
            
            # Build command to execute bot
            bot_file = env_setup["bot_file"]
            if not bot_file or not bot_file.exists():
                raise ExecutionError(f"Bot file not found: {bot_file}", self.strategy_name, config)
            
            # Use just the filename since we're setting cwd
            cmd = [sys.executable, bot_file.name]
            
            # Set up logging
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file_path = config.log_directory / f"bot_output_{timestamp}.log"
            
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
                terminal_instance=f"standard_{process.pid}"
            )
            
            # Create process handle
            handle = ProcessHandle(
                process_info=process_info,
                subprocess_handle=process
            )
            
            self.logger.info(f"Started standard Discord.py bot {config.client_id} (PID: {process.pid})")
            return handle
            
        except Exception as e:
            self.logger.error(f"Failed to start bot {config.client_id}: {e}")
            raise ExecutionError(f"Bot startup failed: {e}", self.strategy_name, config)
    
    async def stop(self, handle: ProcessHandle) -> bool:
        """
        Stop a running Discord.py bot process.
        
        Gracefully terminates the bot process with fallback to force kill.
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
                    self.logger.info(f"Gracefully stopped bot {handle.process_info.client_id}")
                    return True
                except subprocess.TimeoutExpired:
                    # Force kill if graceful termination fails
                    process.kill()
                    process.wait()
                    self.logger.warning(f"Force killed bot {handle.process_info.client_id}")
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
            self.logger.error(f"Failed to stop bot {handle.process_info.client_id}: {e}")
            return False
    
    async def restart(self, handle: ProcessHandle, config: BotConfiguration) -> ProcessHandle:
        """
        Restart a Discord.py bot process.
        
        Stops the current process and starts a new one with updated configuration.
        """
        try:
            # Stop current process
            stop_success = await self.stop(handle)
            if not stop_success:
                self.logger.warning(f"Failed to cleanly stop bot {config.client_id}, continuing with restart")
            
            # Wait a moment for cleanup
            await asyncio.sleep(1)
            
            # Start new process
            new_handle = await self.start(config)
            
            # Update restart count
            new_handle.process_info.restart_count = handle.process_info.restart_count + 1
            new_handle.process_info.last_restart = datetime.now(timezone.utc)
            
            self.logger.info(f"Restarted bot {config.client_id} (new PID: {new_handle.process_info.pid})")
            return new_handle
            
        except Exception as e:
            self.logger.error(f"Failed to restart bot {config.client_id}: {e}")
            raise ExecutionError(f"Bot restart failed: {e}", self.strategy_name, config)
    
    async def get_health_status(self, handle: ProcessHandle) -> HealthStatus:
        """Get detailed health status for the bot process."""
        return handle.process_info.get_current_health_status()
    
    async def get_logs(self, handle: ProcessHandle, lines: int = 100) -> List[str]:
        """
        Get recent log lines from the bot process.
        
        Reads from the log file created during bot startup.
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
            self.logger.error(f"Failed to read logs for {handle.process_info.client_id}: {e}")
            return [f"Error reading logs: {e}"]
    
    def _find_bot_file(self, config: BotConfiguration) -> Path:
        """
        Find the main bot file for execution.
        
        Looks for common bot file patterns:
        - bot.py
        - main.py  
        - __main__.py
        - {client_id}.py
        """
        # Check if bot file is specified in config
        bot_file_config = config.environment_config.get("BOT_FILE")
        if bot_file_config:
            bot_file = Path(bot_file_config)
            if bot_file.exists():
                return bot_file
        
        # Look in standard locations
        bot_directory = Path(f"bots/{config.client_id}")
        if bot_directory.exists():
            # Common bot file names
            candidates = [
                "bot.py",
                "main.py",
                "__main__.py",
                f"{config.client_id}.py",
                "run.py",
                "start.py"
            ]
            
            for candidate in candidates:
                bot_file = bot_directory / candidate
                if bot_file.exists():
                    return bot_file
        
        # Check current directory patterns
        current_dir = Path.cwd()
        for candidate in ["bot.py", "main.py"]:
            bot_file = current_dir / candidate
            if bot_file.exists():
                return bot_file
        
        return None