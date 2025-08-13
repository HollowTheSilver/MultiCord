"""
Discord Bot Template
=================================

A comprehensive, production-ready Discord bot template with integrated Loguru logging,
configuration management, graceful shutdown, enhanced embeds, professional error handling,
and enterprise-grade permission system.

Author: HollowTheSilver
Version: 1.2.0 (Enhanced Permission System)
"""

# // ========================================( Modules )======================================== // #

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    TYPE_CHECKING
)

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from config.settings import BotConfig
from utils.loguruConfig import configure_logger
from utils.permissions import setup_enhanced_permission_system, PermissionLevel  # Updated import
from utils.exceptions import BotError, ConfigurationError, ShutdownError
from utils.error_handler import setup_enhanced_error_handling

if TYPE_CHECKING:
    from loguru import Logger


# // ========================================( Bot Class )======================================== // #


class Application(commands.Bot):
    """
    Discord bot with comprehensive logging, configuration management,
    enhanced embeds, graceful shutdown capabilities, and enterprise permission system.
    """

    def __init__(self, config: Optional[BotConfig] = None) -> None:
        """
        Initialize Discord bot application.

        Args:
            config: Bot configuration object. If None, loads from default config.

        Raises:
            ConfigurationError: If configuration is invalid or missing.
        """
        # Load configuration
        self.config: BotConfig = config or BotConfig()

        # Initialize logger with Discord-compatible formatting
        self.logger: "Logger" = configure_logger(
            log_dir=self.config.LOG_DIR,
            level=self.config.LOG_LEVEL,
            rotation=self.config.LOG_ROTATION,
            retention=self.config.LOG_RETENTION,
            format_extra=True,
            discord_compat=True  # Always use Discord-compatible formatting
        )

        # Discord intents setup
        intents = discord.Intents.default()
        intents.members = self.config.ENABLE_MEMBER_INTENTS
        intents.message_content = self.config.ENABLE_MESSAGE_CONTENT_INTENT
        intents.presences = self.config.ENABLE_PRESENCE_INTENT

        # Initialize bot
        super().__init__(
            command_prefix=self.config.COMMAND_PREFIX,
            intents=intents,
            help_command=None,  # Custom help command in cogs
            case_insensitive=True,
            strip_after_prefix=True
        )

        # Bot state management
        self._startup_complete: bool = False
        self._activity_index: int = 0
        self._shutdown_requested: bool = False  # Simple flag for shutdown

        # Error handling (will be set up in setup_hook)
        self.error_handler = None
        # Enhanced permissions manager (will be set up in setup_hook)
        self.permission_manager = None

        # Optional integrations (to be implemented as needed)
        self.database: Optional[Any] = None
        self.cache: Optional[Any] = None
        self.external_api: Optional[Any] = None

        self.logger.info("Bot instance initialized", extra={
            "prefix": self.config.COMMAND_PREFIX,
            "intents": {
                "members": intents.members,
                "message_content": intents.message_content,
                "presences": intents.presences
            }
        })

    # // ========================================( Setup & Initialization )======================================== // #

    async def setup_hook(self) -> None:
        """
        Initial setup hook called when the bot starts.

        Raises:
            BotError: If setup fails at any stage.
        """
        try:
            self.logger.info("Starting bot initialization...")

            # Set up enhanced error handling first
            self.error_handler = setup_enhanced_error_handling(self)
            self.logger.info("Error handler configured")

            # Set up enhanced permission system
            self.permission_manager = setup_enhanced_permission_system(self)
            self.logger.info("Permission manager configured")

            # Load extensions/cogs
            await self._load_extensions()

            # Initialize external services (database, cache, etc.)
            await self._initialize_services()

            # Start background tasks
            await self._start_background_tasks()

            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()

            self.logger.info("Bot initialization completed successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize bot: {e}", extra={"error": str(e)})
            await self.close()
            raise BotError(f"Bot initialization failed: {e}") from e

    async def _load_extensions(self) -> None:
        """Load all cog extensions."""
        cogs_dir = Path("cogs")

        if not cogs_dir.exists():
            self.logger.warning("Cogs directory not found, creating it...")
            cogs_dir.mkdir(exist_ok=True)
            return

        loaded_count = 0
        failed_count = 0

        for cog_file in cogs_dir.glob("*.py"):
            if cog_file.name.startswith("_"):
                continue

            cog_name = f"cogs.{cog_file.stem}"

            try:
                await self.load_extension(cog_name)
                self.logger.info(f"Loaded cog: {cog_name}")
                loaded_count += 1

            except Exception as e:
                self.logger.error(f"Failed to load cog {cog_name}: {e}")
                failed_count += 1

        self.logger.info(f"Cog loading completed", extra={
            "loaded": loaded_count,
            "failed": failed_count,
            "total": loaded_count + failed_count
        })

    async def _initialize_services(self) -> None:
        """Initialize external services (database, cache, APIs, etc.)."""
        try:
            # Example service initializations
            if self.config.DATABASE_URL:
                self.logger.info("Initializing database connection...")
                # self.database = await init_database(self.config.DATABASE_URL)

            if self.config.REDIS_URL:
                self.logger.info("Initializing cache connection...")
                # self.cache = await init_redis(self.config.REDIS_URL)

            # Add other service initializations here

        except Exception as e:
            self.logger.error(f"Service initialization failed: {e}")
            raise

    async def _start_background_tasks(self) -> None:
        """Start all background tasks."""
        # Handle status messages
        if self.config.ENABLE_STATUS_CYCLING and self.config.STATUS_MESSAGES:
            if len(self.config.STATUS_MESSAGES) > 1:
                # Multiple statuses - start cycling task
                self.status_cycle_task.change_interval(
                    seconds=self.config.STATUS_CYCLE_INTERVAL
                )
                self.status_cycle_task.start()
                self.logger.info(f"Status cycling task started with {len(self.config.STATUS_MESSAGES)} statuses")
            else:
                # Single status - will be set in on_ready when bot is connected
                self.logger.info("Single status configured (will be set when bot connects)")

        if self.config.ENABLE_HEALTH_CHECKS:
            self.health_check_task.start()
            self.logger.info("Health check task started")

        # Start shutdown monitor
        self.shutdown_monitor.start()

    @tasks.loop(seconds=1)
    async def shutdown_monitor(self) -> None:
        """Monitor for shutdown requests and handle them properly."""
        if self._shutdown_requested:
            await self._perform_shutdown()

    @shutdown_monitor.before_loop
    async def before_shutdown_monitor(self) -> None:
        """Wait until bot is ready before starting shutdown monitoring."""
        await self.wait_until_ready()

    async def _perform_shutdown(self) -> None:
        """Perform the actual shutdown."""
        self.logger.warning("Initiating bot shutdown...")

        # Stop background tasks
        if hasattr(self, 'shutdown_monitor'):
            self.shutdown_monitor.cancel()

        if hasattr(self, 'status_cycle_task'):
            self.status_cycle_task.cancel()
            self.logger.info("Status cycle task stopped")

        if hasattr(self, 'health_check_task'):
            self.health_check_task.cancel()
            self.logger.info("Health check task stopped")

        # Close external connections
        if self.database:
            self.logger.info("Closing database connection...")
            # await self.database.close()

        if self.cache:
            self.logger.info("Closing cache connection...")
            # await self.cache.close()

        self.logger.info("Shutdown complete")

        # Force immediate exit - no async, no waiting
        import os
        os._exit(0)  # NOQA

    def request_shutdown(self) -> None:
        """Request a shutdown. Safe to call from any context."""
        self._shutdown_requested = True

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(sig: int, frame: Any) -> None:
            self.logger.warning(f"Received signal {sig}, requesting shutdown...")
            self.request_shutdown()

        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Termination request

        self.logger.info("Signal handlers registered for graceful shutdown")

    # // ========================================( Background Tasks )======================================== // #

    @tasks.loop(seconds=300)  # Will be changed in _start_background_tasks
    async def status_cycle_task(self) -> None:
        """Cycle through bot status messages."""
        if not self.config.STATUS_MESSAGES:
            return

        try:
            status_text, status_type = self.config.STATUS_MESSAGES[self._activity_index]
            activity = self._create_activity(status_text, status_type)
            await self.change_presence(activity=activity)

            # Move to next status
            self._activity_index = (self._activity_index + 1) % len(self.config.STATUS_MESSAGES)

        except Exception as e:
            self.logger.error(f"Failed to update bot status: {e}")

    @status_cycle_task.before_loop
    async def before_status_cycle(self) -> None:
        """Wait until bot is ready before starting status cycling."""
        await self.wait_until_ready()

    @tasks.loop(minutes=5)
    async def health_check_task(self) -> None:
        """Perform periodic health checks."""
        try:
            # Check database connection
            if self.database:
                # await self.database.execute("SELECT 1")
                pass

            # Check cache connection
            if self.cache:
                # await self.cache.ping()
                pass

            # Check Discord API latency
            latency = round(self.latency * 1000, 2)
            if latency > 1000:  # High latency warning
                self.logger.warning(f"High Discord API latency: {latency}ms")

            # Check permission system performance
            if self.permission_manager:
                cache_stats = self.permission_manager.get_cache_stats()
                if cache_stats['hit_rate'] < 50:  # Low hit rate warning
                    self.logger.warning(f"Low permission cache hit rate: {cache_stats['hit_rate']}%")

            self.logger.debug("Health check completed", extra={
                "latency": f"{latency}ms",
                "permission_cache_hit_rate": f"{cache_stats.get('hit_rate', 0)}%" if self.permission_manager else "N/A"
            })

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")

    @health_check_task.before_loop
    async def before_health_check(self) -> None:
        """Wait until bot is ready before starting health checks."""
        await self.wait_until_ready()

    # // ========================================( Event Handlers )======================================== // #

    async def on_ready(self) -> None:
        """Called when the bot is ready and connected to Discord."""
        if self._startup_complete:
            return  # Prevent multiple ready events

        self.logger.info(f"Bot connected as {self.user}", extra={
            "user_id": self.user.id,
            "guild_count": len(self.guilds),
            "user_count": sum(guild.member_count or 0 for guild in self.guilds)
        })

        # DEBUG: Check if auto-sync is enabled
        self.logger.info(f"ENABLE_AUTO_SYNC setting: {self.config.ENABLE_AUTO_SYNC}")

        # Sync slash commands if enabled
        if self.config.ENABLE_AUTO_SYNC:
            self.logger.info("Starting slash command sync...")
            try:
                synced = await self.tree.sync()
                self.logger.info(f"Successfully synced {len(synced)} slash commands")

                # DEBUG: Show what commands were synced
                for cmd in synced:
                    self.logger.info(f"Synced command: {cmd.name}")

            except Exception as e:
                self.logger.error(f"Failed to sync slash commands: {e}")
        else:
            self.logger.info("Auto-sync is disabled, skipping slash command sync")

        # Set single status now that bot is connected
        if (self.config.ENABLE_STATUS_CYCLING and
                self.config.STATUS_MESSAGES and
                len(self.config.STATUS_MESSAGES) == 1):
            await self._set_single_status()
            self.logger.info("Single status set (cycling disabled)")

        self._startup_complete = True

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Called when the bot joins a new guild."""
        self.logger.info(f"Joined new guild: {guild.name}", extra={
            "guild_id": guild.id,
            "member_count": guild.member_count,
            "owner": str(guild.owner)
        })

        # Auto-configure permissions for new guild
        if self.permission_manager:
            try:
                confident_mappings, uncertain_roles = await self.permission_manager.auto_configure_guild(guild)
                self.logger.info(f"Auto-configured {len(confident_mappings)} roles for new guild {guild.name}, "
                               f"{len(uncertain_roles)} roles need manual review")
            except Exception as e:
                self.logger.error(f"Failed to auto-configure permissions for new guild {guild.name}: {e}")

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Called when the bot is removed from a guild."""
        self.logger.info(f"Removed from guild: {guild.name}", extra={
            "guild_id": guild.id
        })

        # Clean up guild permission configuration
        if self.permission_manager and guild.id in self.permission_manager.guild_configs:
            del self.permission_manager.guild_configs[guild.id]
            self.permission_manager.clear_cache()
            self.logger.info(f"Cleaned up permission configuration for removed guild: {guild.name}")

    async def on_command_completion(self, ctx: commands.Context) -> None:
        """Called when a command is successfully executed."""
        command_name = ctx.command.qualified_name if ctx.command else "unknown"

        # Get user's permission level for logging
        user_level = "unknown"
        if self.permission_manager:
            try:
                level = self.permission_manager.get_user_permission_level(ctx.author, ctx.guild)
                user_level = level.name
            except Exception:
                pass

        self.logger.info(f"Command executed: {command_name}", extra={
            "user": str(ctx.author),
            "user_id": ctx.author.id,
            "user_permission_level": user_level,
            "guild": ctx.guild.name if ctx.guild else "DM",
            "guild_id": ctx.guild.id if ctx.guild else None,
            "channel": str(ctx.channel),
            "command": command_name
        })

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """
        Global command error handler - now handled by enhanced error handler.
        This method is overridden by the enhanced error handler setup.
        """
        # This will be overridden by setup_enhanced_error_handling
        pass

    async def on_error(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Global error handler for non-command events."""
        self.logger.error(f"Unhandled error in event {event}", extra={
            "event": event,
            "args": str(args)[:500],  # Limit length
            "kwargs": str(kwargs)[:500]
        })

    # // ========================================( Utility Methods )======================================== // #

    async def _set_single_status(self) -> None:
        """Set a single status without cycling."""
        if self.config.STATUS_MESSAGES:
            status_text, status_type = self.config.STATUS_MESSAGES[0]
            activity = self._create_activity(status_text, status_type)
            await self.change_presence(activity=activity)

    def _create_activity(self, status_text: str, status_type: str) -> discord.Activity:
        """Create a Discord activity based on type."""
        activity_mapping = {
            'playing': lambda text: discord.Game(name=text),
            'watching': lambda text: discord.Activity(type=discord.ActivityType.watching, name=text),
            'listening': lambda text: discord.Activity(type=discord.ActivityType.listening, name=text),
            'competing': lambda text: discord.Activity(type=discord.ActivityType.competing, name=text),
            'streaming': lambda text: discord.Streaming(name=text, url="https://twitch.tv/bot"),
            'custom': lambda text: discord.CustomActivity(name=text)
        }

        return activity_mapping.get(status_type.lower(), activity_mapping['custom'])(status_text)

    def get_uptime(self) -> Optional[float]:
        """Get bot uptime in seconds."""
        # Implementation depends on when you start tracking uptime
        # Could use self.start_time if you set it in __init__
        pass

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive bot statistics."""
        stats = {
            "guilds": len(self.guilds),
            "users": sum(guild.member_count or 0 for guild in self.guilds),
            "commands": len(self.commands),
            "cogs": len(self.cogs),
            "latency": round(self.latency * 1000, 2),
            "startup_complete": self._startup_complete
        }

        # Add permission system stats if available
        if self.permission_manager:
            permission_stats = self.permission_manager.get_cache_stats()
            stats.update({
                "permission_checks": permission_stats.get("total_checks", 0),
                "permission_cache_hit_rate": permission_stats.get("hit_rate", 0),
                "configured_guilds": permission_stats.get("guild_configs", 0)
            })

        return stats


# // ========================================( Main Function )======================================== // #


async def main() -> None:
    """Main entry point for the bot application."""
    # Load environment variables
    load_dotenv()

    # Verify Discord token
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not found in environment variables")
        sys.exit(1)

    try:
        # Create and configure bot
        config = BotConfig()
        bot = Application(config)

        # Start the bot (this will run until bot.close() is called)
        await bot.start(token)

    except KeyboardInterrupt:
        print("🛑 Keyboard interrupt received")

    except Exception as e:
        print(f"❌ Fatal error: {e}")

    finally:
        print("🔌 Bot shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Program interrupted")
    except SystemExit:
        pass  # Handle SystemExit gracefully
    finally:
        print("🔌 Program exiting")
