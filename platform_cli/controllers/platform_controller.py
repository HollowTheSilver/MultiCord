"""
MultiCord Platform CLI Controller
================================

Clean command-line interface for bot management using platform use cases.
Follows clean architecture principles with proper separation of concerns.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from uuid import uuid4
import argparse
from dataclasses import dataclass

# Add platform_core to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from platform_core.infrastructure.postgresql_pool import PostgreSQLConnectionPool
from platform_core.repositories.process_repository import ProcessRepository
from platform_core.strategies import ExecutionStrategyFactory, StandardDiscordPyStrategy, TemplateBasedStrategy
from platform_core.use_cases.start_bot_use_case import StartBotUseCase, StartBotRequest, StartBotResponse


@dataclass
class PlatformConfig:
    """Platform configuration for CLI operations."""
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "multicord_platform"
    db_user: str = "multicord_user"
    db_password: str = "multicord_secure_pass"
    log_level: str = "INFO"
    offline_mode: bool = False


class PlatformController:
    """
    Main controller for MultiCord Platform CLI operations.
    
    Coordinates use cases and provides clean command-line interface
    for bot management operations.
    """
    
    def __init__(self, config: PlatformConfig):
        """Initialize platform controller with configuration."""
        self.config = config
        self.logger = self._setup_logging()
        
        # Platform components (initialized lazily)
        self.db_pool: Optional[PostgreSQLConnectionPool] = None
        self.process_repository: Optional[ProcessRepository] = None
        self.strategy_factory: Optional[ExecutionStrategyFactory] = None
        self.start_bot_use_case: Optional[StartBotUseCase] = None
        
        self._initialized = False
    
    def _setup_logging(self) -> logging.Logger:
        """Configure logging for CLI operations."""
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper()),
            format='%(levelname)s: %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        
        return logging.getLogger('MultiCord.CLI')
    
    async def initialize(self) -> bool:
        """
        Initialize platform components.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True
        
        try:
            self.logger.info("Initializing MultiCord Platform...")
            
            if not self.config.offline_mode:
                # Initialize PostgreSQL connection pool
                self.db_pool = PostgreSQLConnectionPool(
                    host=self.config.db_host,
                    port=self.config.db_port,
                    database=self.config.db_name,
                    user=self.config.db_user,
                    password=self.config.db_password
                )
                
                await self.db_pool.initialize()
                self.logger.info("PostgreSQL connection established")
                
                # Test database connectivity
                health = await self.db_pool.health_check()
                if health.get('status') != 'healthy':
                    self.logger.error("PostgreSQL health check failed")
                    return False
                
                # Initialize repositories
                self.process_repository = ProcessRepository(self.db_pool)
                self.logger.info("Process repository initialized")
            else:
                self.logger.info("Running in offline mode - database features disabled")
            
            # Initialize execution strategies
            self.strategy_factory = ExecutionStrategyFactory()
            self.strategy_factory.register_strategy(StandardDiscordPyStrategy())
            self.strategy_factory.register_strategy(TemplateBasedStrategy())
            self.logger.info("Execution strategies registered")
            
            # Initialize use cases
            if not self.config.offline_mode:
                self.start_bot_use_case = StartBotUseCase(
                    db_pool=self.db_pool,
                    process_repository=self.process_repository,
                    strategy_factory=self.strategy_factory,
                    logger=self.logger
                )
                self.logger.info("Use cases initialized")
            
            self._initialized = True
            self.logger.info("MultiCord Platform ready")
            return True
            
        except Exception as e:
            self.logger.error(f"Platform initialization failed: {e}")
            return False
    
    async def cleanup(self) -> None:
        """Clean up platform resources."""
        if self.db_pool:
            await self.db_pool.close()
            self.logger.info("Database connections closed")
    
    async def start_bot(self, 
                       client_id: str,
                       discord_token: Optional[str] = None,
                       execution_strategy: str = "standard",
                       bot_file: Optional[str] = None,
                       features: Optional[List[str]] = None,
                       env_vars: Optional[Dict[str, str]] = None) -> bool:
        """
        Start a Discord bot instance.
        
        Args:
            client_id: Unique identifier for the bot
            discord_token: Discord bot token
            execution_strategy: Execution strategy to use
            bot_file: Path to bot file (optional)
            features: Technical features to enable
            env_vars: Additional environment variables
            
        Returns:
            True if bot started successfully, False otherwise
        """
        if not self._initialized:
            self.logger.error("Platform not initialized. Call initialize() first.")
            return False
        
        if self.config.offline_mode:
            self.logger.error("Cannot start bots in offline mode")
            return False
        
        try:
            self.logger.info(f"Starting bot: {client_id}")
            
            # Prepare environment configuration
            environment_config = {}
            if discord_token:
                environment_config["DISCORD_TOKEN"] = discord_token
            if bot_file:
                environment_config["BOT_FILE"] = bot_file
            if env_vars:
                environment_config.update(env_vars)
            
            # Create start request
            request = StartBotRequest(
                client_id=client_id,
                execution_strategy=execution_strategy,
                environment_config=environment_config,
                technical_features=features or [],
                discord_token=discord_token
            )
            
            # Execute use case
            response = await self.start_bot_use_case.execute(request)
            
            if response.success:
                self.logger.info(f"{response.message}")
                if response.pid:
                    self.logger.info(f"   Process ID: {response.pid}")
                if response.log_file_path:
                    self.logger.info(f"   Logs: {response.log_file_path}")
                return True
            else:
                self.logger.error(f"Failed to start bot: {response.message}")
                if response.error_details:
                    self.logger.error(f"   Details: {response.error_details}")
                return False
                
        except Exception as e:
            self.logger.error(f"Unexpected error starting bot {client_id}: {e}")
            return False
    
    async def stop_bot(self, client_id: str, force: bool = False) -> bool:
        """
        Stop a running Discord bot instance.
        
        Args:
            client_id: Bot identifier to stop
            force: Force kill if graceful stop fails
            
        Returns:
            True if bot stopped successfully, False otherwise
        """
        if not self._initialized or self.config.offline_mode:
            self.logger.error("Cannot stop bots - platform not initialized or in offline mode")
            return False
        
        try:
            self.logger.info(f"Stopping bot: {client_id}")
            
            # Find running process
            process_info = await self.process_repository.find_by_client_id(client_id)
            if not process_info:
                self.logger.warning(f"No running process found for {client_id}")
                return False
            
            if not process_info.is_running:
                self.logger.info(f"Bot {client_id} is already stopped")
                # Clean up dead process record
                await self.process_repository.remove_process(process_info.process_id)
                return True
            
            # Get strategy and stop process
            strategy = self.strategy_factory.get_strategy("standard")  # Assume standard for stopping
            if strategy:
                # Create process handle for stopping
                from platform_core.strategies.bot_execution_strategy import ProcessHandle
                handle = ProcessHandle(process_info=process_info, subprocess_handle=None)
                
                success = await strategy.stop(handle)
                if success:
                    self.logger.info(f"✅ Bot {client_id} stopped successfully")
                    await self.process_repository.remove_process(process_info.process_id)
                    return True
                else:
                    self.logger.error(f"Failed to stop bot {client_id}")
                    return False
            else:
                self.logger.error("No strategy available for stopping bot")
                return False
                
        except Exception as e:
            self.logger.error(f"Error stopping bot {client_id}: {e}")
            return False
    
    async def list_bots(self, show_all: bool = False) -> bool:
        """
        List bot instances and their status.
        
        Args:
            show_all: Show all instances including stopped ones
            
        Returns:
            True if listing successful, False otherwise
        """
        if not self._initialized or self.config.offline_mode:
            self.logger.error("Cannot list bots - platform not initialized or in offline mode")
            return False
        
        try:
            self.logger.info("Bot Instance Status:")
            self.logger.info("=" * 60)
            
            # Get processes based on filter
            if show_all:
                processes = await self.process_repository.find_all_processes()
            else:
                processes = await self.process_repository.find_active_processes()
            
            if not processes:
                self.logger.info("No bot instances found")
                return True
            
            for process in processes:
                status = "RUNNING" if process.is_running else "STOPPED"
                self.logger.info(f"{status} {process.client_id}")
                self.logger.info(f"   PID: {process.pid}")
                self.logger.info(f"   Started: {process.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
                if process.log_file_path:
                    self.logger.info(f"   Logs: {process.log_file_path}")
                
                # Show health status for running processes
                if process.is_running:
                    health = process.get_current_health_status()
                    self.logger.info(f"   Memory: {health.memory_mb:.1f} MB")
                    self.logger.info(f"   CPU: {health.cpu_percent:.1f}%")
                
                self.logger.info("")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error listing bots: {e}")
            return False
    
    async def show_bot_status(self, client_id: str) -> bool:
        """
        Show detailed status for a specific bot.
        
        Args:
            client_id: Bot identifier
            
        Returns:
            True if status shown successfully, False otherwise
        """
        if not self._initialized or self.config.offline_mode:
            self.logger.error("Cannot show status - platform not initialized or in offline mode")
            return False
        
        try:
            process_info = await self.process_repository.find_by_client_id(client_id)
            if not process_info:
                self.logger.warning(f"Bot {client_id} not found")
                return False
            
            self.logger.info(f"Bot Status: {client_id}")
            self.logger.info("=" * 40)
            
            status = "RUNNING" if process_info.is_running else "STOPPED"
            self.logger.info(f"Status: {status}")
            self.logger.info(f"PID: {process_info.pid}")
            self.logger.info(f"Started: {process_info.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"Restarts: {process_info.restart_count}")
            
            if process_info.is_running:
                health = process_info.get_current_health_status()
                self.logger.info(f"Memory Usage: {health.memory_mb:.1f} MB")
                self.logger.info(f"CPU Usage: {health.cpu_percent:.1f}%")
                self.logger.info(f"Uptime: {health.uptime_seconds:.0f} seconds")
            
            if process_info.log_file_path:
                self.logger.info(f"Log File: {process_info.log_file_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error showing bot status: {e}")
            return False
    
    async def show_platform_info(self) -> bool:
        """
        Show platform information and status.
        
        Returns:
            True if info shown successfully, False otherwise
        """
        try:
            self.logger.info("MultiCord Platform Information")
            self.logger.info("=" * 50)
            self.logger.info("Platform: MultiCord Professional Bot Infrastructure")
            self.logger.info("Phase: 2 - Standard Bot Support & Technical Features")
            self.logger.info("")
            
            if self.config.offline_mode:
                self.logger.info("Mode: 🔌 OFFLINE")
            else:
                self.logger.info(f"Database: {self.config.db_host}:{self.config.db_port}/{self.config.db_name}")
                
                if self.db_pool:
                    health = await self.db_pool.health_check()
                    db_status = "HEALTHY" if health.get('status') == 'healthy' else "UNHEALTHY"
                    self.logger.info(f"DB Status: {db_status}")
                    
                    stats = await self.db_pool.get_pool_stats()
                    self.logger.info(f"Connections: {stats.get('size', 0)}/{stats.get('max_size', 0)}")
            
            # Show available strategies
            if self.strategy_factory:
                strategies = self.strategy_factory.list_strategies()
                self.logger.info(f"Strategies: {len(strategies)} available")
                for strategy_info in strategies:
                    support = "YES" if strategy_info.get('supports_zero_modification') else "WARN"
                    self.logger.info(f"  {support} {strategy_info['name']}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error showing platform info: {e}")
            return False
    
    async def list_templates(self, details: bool = False) -> bool:
        """List available bot templates.
        
        Args:
            details: Show detailed template information
            
        Returns:
            True if templates listed successfully, False otherwise
        """
        if not self._initialized:
            self.logger.error("Platform not initialized. Call initialize() first.")
            return False
        
        try:
            self.logger.info("Available Bot Templates:")
            self.logger.info("=" * 60)
            
            # Get template strategy to list templates
            template_strategy = self.strategy_factory.get_strategy("template")
            if not template_strategy:
                self.logger.warning("Template strategy not available")
                return False
            
            templates = await template_strategy.list_available_templates()
            
            if not templates:
                self.logger.info("No templates found")
                self.logger.info("")
                self.logger.info("Templates provide convenience features for common bot patterns")
                self.logger.info("   Create templates in the 'templates/' directory")
                return True
            
            for template in templates:
                name = template["name"]
                display_name = template.get("display_name", name)
                description = template.get("description", "No description available")
                version = template.get("version", "Unknown")
                
                self.logger.info(f"Template: {display_name} (v{version})")
                self.logger.info(f"   Name: {name}")
                self.logger.info(f"   Description: {description}")
                
                if details:
                    features = template.get("features", [])
                    requirements = template.get("requirements", [])
                    
                    if features:
                        self.logger.info(f"   Features: {', '.join(features)}")
                    
                    if requirements:
                        req_names = [req.get('name', '') for req in requirements if req.get('required')]
                        if req_names:
                            self.logger.info(f"   Required: {', '.join(req_names)}")
                
                self.logger.info("")
            
            self.logger.info(f"Found {len(templates)} template(s)")
            self.logger.info("")
            self.logger.info("Usage: multicord start my_bot --strategy template --template TEMPLATE_NAME --token YOUR_TOKEN")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error listing templates: {e}")
            return False