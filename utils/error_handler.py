"""
Enhanced Error Handler
=====================

Professional error handling system with contextual error messages, helpful suggestions,
and integrated embed support for better user experience.
"""

import traceback
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone

import discord
from discord.ext import commands

from utils.embeds import (
    create_error_embed,
    create_warning_embed,
    create_permission_error_embed,
    EmbedBuilder,
    EmbedType
)
from utils.exceptions import (
    BotError,
    CommandError,
    ValidationError,
    PermissionError,
    ConfigurationError,
    DatabaseError,
    APIError
)


# // ========================================( Error Context )======================================== // #


class ErrorContext:
    """Context information for enhanced error reporting."""

    def __init__(
            self,
            ctx: commands.Context,
            command_name: Optional[str] = None,
            error_time: Optional[datetime] = None
    ) -> None:
        """
        Initialize error context.

        Args:
            ctx: Discord command context
            command_name: Name of the command that failed
            error_time: When the error occurred
        """
        self.ctx = ctx
        self.command_name = command_name or (ctx.command.qualified_name if ctx.command else "unknown")
        self.error_time = error_time or datetime.now(timezone.utc)

        # User information
        self.user_id = ctx.author.id
        self.user_name = str(ctx.author)
        self.user_display_name = ctx.author.display_name

        # Guild information
        self.guild_id = ctx.guild.id if ctx.guild else None
        self.guild_name = ctx.guild.name if ctx.guild else "DM"
        self.channel_id = ctx.channel.id
        self.channel_name = str(ctx.channel)

        # Command information
        self.message_content = ctx.message.content
        self.command_args = ctx.args[2:] if len(ctx.args) > 2 else []  # Skip self and ctx
        self.command_kwargs = ctx.kwargs


# // ========================================( Error Messages )======================================== // #


class ErrorMessages:
    """Centralized error messages with helpful suggestions."""

    # Command errors
    COMMAND_NOT_FOUND = {
        "title": "Command Not Found",
        "description": "That command doesn't exist.",
        "suggestion": "Use `{prefix}help` to see available commands."
    }

    MISSING_PERMISSIONS = {
        "title": "Insufficient Permissions",
        "description": "You don't have permission to use this command.",
        "suggestion": "Contact a server administrator if you believe this is an error."
    }

    BOT_MISSING_PERMISSIONS = {
        "title": "Bot Missing Permissions",
        "description": "I don't have the required permissions to execute this command.",
        "suggestion": "Ask a server administrator to grant me the necessary permissions."
    }

    COMMAND_ON_COOLDOWN = {
        "title": "Command on Cooldown",
        "description": "This command is currently on cooldown.",
        "suggestion": "Please wait before using this command again."
    }

    MISSING_REQUIRED_ARGUMENT = {
        "title": "Missing Required Argument",
        "description": "You're missing a required argument for this command.",
        "suggestion": "Use `{prefix}help {command}` to see the correct usage."
    }

    INVALID_ARGUMENT = {
        "title": "Invalid Argument",
        "description": "One or more arguments are invalid.",
        "suggestion": "Check your input and try again."
    }

    # General errors
    RATE_LIMITED = {
        "title": "Rate Limited",
        "description": "You're using commands too quickly.",
        "suggestion": "Please slow down and try again in a moment."
    }

    DATABASE_ERROR = {
        "title": "Database Error",
        "description": "There was an issue accessing the database.",
        "suggestion": "Please try again later. If the problem persists, contact support."
    }

    API_ERROR = {
        "title": "External Service Error",
        "description": "An external service is currently unavailable.",
        "suggestion": "Please try again later."
    }

    VALIDATION_ERROR = {
        "title": "Validation Error",
        "description": "The provided input is invalid.",
        "suggestion": "Please check your input and try again."
    }

    UNKNOWN_ERROR = {
        "title": "Unexpected Error",
        "description": "An unexpected error occurred.",
        "suggestion": "Please try again later. If the problem persists, contact support."
    }


# // ========================================( Enhanced Error Handler )======================================== // #


class EnhancedErrorHandler:
    """
    Enhanced error handler with contextual messages and embed support.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        Initialize the error handler.

        Args:
            bot: The bot instance
        """
        self.bot = bot
        self.logger = bot.logger if hasattr(bot, 'logger') else None
        self.error_count = 0
        self.recent_errors: Dict[int, List[datetime]] = {}  # User ID -> list of error times

    async def handle_command_error(
            self,
            ctx: commands.Context,
            error: commands.CommandError
    ) -> None:
        """
        Handle command errors with enhanced messaging.

        Args:
            ctx: Command context
            error: The error that occurred
        """
        error_ctx = ErrorContext(ctx)
        self.error_count += 1

        # Track user errors for rate limiting detection
        self._track_user_error(ctx.author.id)

        # Handle specific error types
        if isinstance(error, commands.CommandNotFound):
            # Usually we ignore these, but if enabled in config:
            if getattr(self.bot.config, 'RESPOND_TO_UNKNOWN_COMMANDS', False):
                await self._send_command_not_found_error(ctx, error_ctx)
            return

        elif isinstance(error, commands.MissingPermissions):
            await self._send_missing_permissions_error(ctx, error, error_ctx)

        elif isinstance(error, commands.BotMissingPermissions):
            await self._send_bot_missing_permissions_error(ctx, error, error_ctx)

        elif isinstance(error, commands.CommandOnCooldown):
            await self._send_cooldown_error(ctx, error, error_ctx)

        elif isinstance(error, commands.MissingRequiredArgument):
            await self._send_missing_argument_error(ctx, error, error_ctx)

        elif isinstance(error, (commands.BadArgument, commands.ArgumentParsingError)):
            await self._send_invalid_argument_error(ctx, error, error_ctx)

        elif isinstance(error, commands.NSFWChannelRequired):
            await self._send_nsfw_required_error(ctx, error_ctx)

        elif isinstance(error, commands.DisabledCommand):
            await self._send_disabled_command_error(ctx, error_ctx)

        elif isinstance(error, commands.MaxConcurrencyReached):
            await self._send_max_concurrency_error(ctx, error, error_ctx)

        # Handle custom bot errors
        elif isinstance(error, commands.CommandInvokeError):
            original_error = error.original

            if isinstance(original_error, ValidationError):
                await self._send_validation_error(ctx, original_error, error_ctx)
            elif isinstance(original_error, PermissionError):
                await self._send_permission_error(ctx, original_error, error_ctx)
            elif isinstance(original_error, DatabaseError):
                await self._send_database_error(ctx, original_error, error_ctx)
            elif isinstance(original_error, APIError):
                await self._send_api_error(ctx, original_error, error_ctx)
            else:
                await self._send_unknown_error(ctx, original_error, error_ctx)

        else:
            await self._send_unknown_error(ctx, error, error_ctx)

        # Log the error
        await self._log_error(error_ctx, error)

    def _track_user_error(self, user_id: int) -> None:
        """Track user errors for rate limiting detection."""
        now = datetime.now(timezone.utc)

        if user_id not in self.recent_errors:
            self.recent_errors[user_id] = []

        # Add current error time
        self.recent_errors[user_id].append(now)

        # Remove errors older than 5 minutes
        cutoff = now.timestamp() - 300  # 5 minutes
        self.recent_errors[user_id] = [
            error_time for error_time in self.recent_errors[user_id]
            if error_time.timestamp() > cutoff
        ]

    def _is_user_error_spamming(self, user_id: int) -> bool:
        """Check if user is spamming error commands."""
        if user_id not in self.recent_errors:
            return False

        # More than 5 errors in 5 minutes
        return len(self.recent_errors[user_id]) > 5

    # // ========================================( Specific Error Handlers )======================================== // #

    async def _send_command_not_found_error(
            self,
            ctx: commands.Context,
            error_ctx: ErrorContext
    ) -> None:
        """Send command not found error."""
        message = ErrorMessages.COMMAND_NOT_FOUND

        embed = create_error_embed(
            title=message["title"],
            description=message["description"],
            user=ctx.author
        )

        embed.add_field(
            "💡 Suggestion",
            message["suggestion"].format(prefix=ctx.prefix),
            inline=False
        )

        await ctx.send(embed=embed, delete_after=30)

    async def _send_missing_permissions_error(
            self,
            ctx: commands.Context,
            error: commands.MissingPermissions,
            error_ctx: ErrorContext
    ) -> None:
        """Send missing permissions error."""
        missing_perms = [perm.replace('_', ' ').title() for perm in error.missing_permissions]

        embed = create_error_embed(
            title="Insufficient Permissions",
            description="You don't have permission to use this command.",
            user=ctx.author
        )

        embed.add_field(
            "Required Permissions",
            ', '.join([f"`{perm}`" for perm in missing_perms]),
            inline=False
        )

        embed.add_field(
            "💡 Suggestion",
            "Contact a server administrator if you believe this is an error.",
            inline=False
        )

        await ctx.send(embed=embed)

    async def _send_bot_missing_permissions_error(
            self,
            ctx: commands.Context,
            error: commands.BotMissingPermissions,
            error_ctx: ErrorContext
    ) -> None:
        """Send bot missing permissions error."""
        missing_perms = [perm.replace('_', ' ').title() for perm in error.missing_permissions]
        embed = create_permission_error_embed(missing_perms, ctx.author)
        await ctx.send(embed=embed)

    async def _send_cooldown_error(
            self,
            ctx: commands.Context,
            error: commands.CommandOnCooldown,
            error_ctx: ErrorContext
    ) -> None:
        """Send cooldown error with time remaining."""
        message = ErrorMessages.COMMAND_ON_COOLDOWN

        embed = create_warning_embed(
            title=message["title"],
            description=message["description"],
            user=ctx.author
        )

        # Format time remaining
        time_left = round(error.retry_after)
        if time_left >= 60:
            minutes = time_left // 60
            seconds = time_left % 60
            time_str = f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
        else:
            time_str = f"{time_left}s"

        embed.add_field(
            "⏰ Time Remaining",
            time_str,
            inline=True
        )

        embed.add_field(
            "🔄 Cooldown Type",
            error.cooldown.type.name.title(),
            inline=True
        )

        await ctx.send(embed=embed, delete_after=15)

    async def _send_missing_argument_error(
            self,
            ctx: commands.Context,
            error: commands.MissingRequiredArgument,
            error_ctx: ErrorContext
    ) -> None:
        """Send missing argument error."""
        message = ErrorMessages.MISSING_REQUIRED_ARGUMENT

        embed = create_error_embed(
            title=message["title"],
            description=message["description"],
            user=ctx.author
        )

        embed.add_field(
            "Missing Argument",
            f"`{error.param.name}`",
            inline=True
        )

        # Show command usage if available
        if ctx.command and hasattr(ctx.command, 'signature'):
            usage = f"{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}"
            embed.add_field(
                "Correct Usage",
                f"`{usage}`",
                inline=False
            )

        embed.add_field(
            "💡 Suggestion",
            message["suggestion"].format(prefix=ctx.prefix, command=error_ctx.command_name),
            inline=False
        )

        await ctx.send(embed=embed)

    async def _send_invalid_argument_error(
            self,
            ctx: commands.Context,
            error: commands.CommandError,
            error_ctx: ErrorContext
    ) -> None:
        """Send invalid argument error."""
        message = ErrorMessages.INVALID_ARGUMENT

        embed = create_error_embed(
            title=message["title"],
            description=message["description"],
            user=ctx.author
        )

        embed.add_field(
            "Error Details",
            str(error),
            inline=False
        )

        if ctx.command and hasattr(ctx.command, 'signature'):
            usage = f"{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}"
            embed.add_field(
                "Correct Usage",
                f"`{usage}`",
                inline=False
            )

        await ctx.send(embed=embed)

    async def _send_nsfw_required_error(
            self,
            ctx: commands.Context,
            error_ctx: ErrorContext
    ) -> None:
        """Send NSFW channel required error."""
        embed = create_error_embed(
            title="NSFW Channel Required",
            description="This command can only be used in NSFW channels.",
            user=ctx.author
        )

        embed.add_field(
            "💡 Suggestion",
            "Move to an NSFW channel or ask an administrator to mark this channel as NSFW.",
            inline=False
        )

        await ctx.send(embed=embed)

    async def _send_disabled_command_error(
            self,
            ctx: commands.Context,
            error_ctx: ErrorContext
    ) -> None:
        """Send disabled command error."""
        embed = create_error_embed(
            title="Command Disabled",
            description="This command is currently disabled.",
            user=ctx.author
        )

        embed.add_field(
            "💡 Suggestion",
            "Contact a server administrator for more information.",
            inline=False
        )

        await ctx.send(embed=embed)

    async def _send_max_concurrency_error(
            self,
            ctx: commands.Context,
            error: commands.MaxConcurrencyReached,
            error_ctx: ErrorContext
    ) -> None:
        """Send max concurrency error."""
        embed = create_warning_embed(
            title="Command Busy",
            description="This command is already running at maximum capacity.",
            user=ctx.author
        )

        embed.add_field(
            "Limit Type",
            error.per.name.title(),
            inline=True
        )

        embed.add_field(
            "Max Concurrent",
            str(error.number),
            inline=True
        )

        embed.add_field(
            "💡 Suggestion",
            "Please wait for the current operation to complete before trying again.",
            inline=False
        )

        await ctx.send(embed=embed)

    # // ========================================( Custom Error Handlers )======================================== // #

    async def _send_validation_error(
            self,
            ctx: commands.Context,
            error: ValidationError,
            error_ctx: ErrorContext
    ) -> None:
        """Send validation error."""
        embed = create_error_embed(
            title="Validation Error",
            description="The provided input is invalid.",
            user=ctx.author
        )

        if hasattr(error, 'field_name') and error.field_name:
            embed.add_field("Field", f"`{error.field_name}`", inline=True)

        if hasattr(error, 'value') and error.value is not None:
            embed.add_field("Provided Value", f"`{error.value}`", inline=True)

        if hasattr(error, 'expected_format') and error.expected_format:
            embed.add_field("Expected Format", error.expected_format, inline=False)

        await ctx.send(embed=embed)

    async def _send_permission_error(
            self,
            ctx: commands.Context,
            error: PermissionError,
            error_ctx: ErrorContext
    ) -> None:
        """Send permission error."""
        embed = create_error_embed(
            title="Permission Denied",
            description=str(error),
            user=ctx.author
        )

        if hasattr(error, 'required_permission') and error.required_permission:
            embed.add_field(
                "Required Permission",
                f"`{error.required_permission}`",
                inline=False
            )

        await ctx.send(embed=embed)

    async def _send_database_error(
            self,
            ctx: commands.Context,
            error: DatabaseError,
            error_ctx: ErrorContext
    ) -> None:
        """Send database error."""
        message = ErrorMessages.DATABASE_ERROR

        embed = create_error_embed(
            title=message["title"],
            description=message["description"],
            user=ctx.author
        )

        embed.add_field(
            "💡 Suggestion",
            message["suggestion"],
            inline=False
        )

        await ctx.send(embed=embed)

    async def _send_api_error(
            self,
            ctx: commands.Context,
            error: APIError,
            error_ctx: ErrorContext
    ) -> None:
        """Send API error."""
        message = ErrorMessages.API_ERROR

        embed = create_error_embed(
            title=message["title"],
            description=message["description"],
            user=ctx.author
        )

        if hasattr(error, 'status_code') and error.status_code:
            embed.add_field("Status Code", str(error.status_code), inline=True)

        embed.add_field(
            "💡 Suggestion",
            message["suggestion"],
            inline=False
        )

        await ctx.send(embed=embed)

    async def _send_unknown_error(
            self,
            ctx: commands.Context,
            error: Exception,
            error_ctx: ErrorContext
    ) -> None:
        """Send unknown error with error ID for tracking."""
        error_id = f"ERR-{self.error_count:06d}"

        embed = create_error_embed(
            title="Unexpected Error",
            description="An unexpected error occurred while processing your command.",
            error_code=error_id,
            user=ctx.author
        )

        embed.add_field(
            "💡 What to do",
            "Please try again later. If the problem persists, contact support with the error code above.",
            inline=False
        )

        await ctx.send(embed=embed)

    # // ========================================( Logging )======================================== // #

    async def _log_error(
            self,
            error_ctx: ErrorContext,
            error: Exception
    ) -> None:
        """Log error with context information."""
        if not self.logger:
            return

        log_data = {
            "error_type": type(error).__name__,
            "command": error_ctx.command_name,
            "user": error_ctx.user_name,
            "user_id": error_ctx.user_id,
            "guild": error_ctx.guild_name,
            "guild_id": error_ctx.guild_id,
            "channel": error_ctx.channel_name,
            "channel_id": error_ctx.channel_id,
            "message_content": error_ctx.message_content[:200],  # Truncate long messages
            "error_count": self.error_count
        }

        # Log level based on error type
        if isinstance(error, (commands.CommandNotFound, commands.MissingPermissions)):
            log_level = "INFO"
        elif isinstance(error, (commands.CommandOnCooldown, commands.MissingRequiredArgument)):
            log_level = "WARNING"
        else:
            log_level = "ERROR"

        # Log the error
        if log_level == "INFO":
            self.logger.info(f"Command error: {error}", extra=log_data)
        elif log_level == "WARNING":
            self.logger.warning(f"Command error: {error}", extra=log_data)
        else:
            # Include full traceback for serious errors
            tb = traceback.format_exception(type(error), error, error.__traceback__)
            log_data["traceback"] = "".join(tb)
            self.logger.error(f"Command error: {error}", extra=log_data)


# // ========================================( Integration Function )======================================== // #


def setup_enhanced_error_handling(bot: commands.Bot) -> EnhancedErrorHandler:
    """
    Set up enhanced error handling for the bot.

    Args:
        bot: The bot instance

    Returns:
        The error handler instance for further customization
    """
    error_handler = EnhancedErrorHandler(bot)

    # Store the error handler on the bot instance for access in Application class
    bot.error_handler = error_handler

    # NOTE: on_command_error handling moved to Application class to avoid event override conflicts

    if hasattr(bot, 'logger'):
        bot.logger.info("Successfully initialized module")

    return error_handler
