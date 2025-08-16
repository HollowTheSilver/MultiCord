"""
Bot Exceptions Module
====================

Custom exception classes for the Discord bot with comprehensive error handling
and logging integration.
"""

from typing import Optional, Any, Dict
import discord
from discord.ext import commands


# // ========================================( Base Exceptions )======================================== // #


class BotError(Exception):
    """Base exception class for all bot-related errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the bot error.

        Args:
            message: Human-readable error message
            error_code: Optional error code for categorization
            context: Additional context information
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}

    def __str__(self) -> str:
        """String representation of the error."""
        base = self.message
        if self.error_code:
            base = f"[{self.error_code}] {base}"
        return base

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context
        }


# // ========================================( Configuration Exceptions )======================================== // #


class ConfigurationError(BotError):
    """Raised when there's an issue with bot configuration."""

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs) -> None:
        super().__init__(message, error_code="CONFIG_ERROR", **kwargs)
        self.config_key = config_key


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""

    def __init__(self, config_key: str, **kwargs) -> None:
        message = f"Required configuration '{config_key}' is missing"
        super().__init__(message, config_key=config_key, **kwargs)


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid."""

    def __init__(self, config_key: str, value: Any, expected: str, **kwargs) -> None:
        message = f"Invalid value for '{config_key}': {value}. Expected: {expected}"
        super().__init__(message, config_key=config_key, **kwargs)
        self.value = value
        self.expected = expected


# // ========================================( Database Exceptions )======================================== // #


class DatabaseError(BotError):
    """Base class for database-related errors."""

    def __init__(self, message: str, operation: Optional[str] = None, **kwargs) -> None:
        super().__init__(message, error_code="DB_ERROR", **kwargs)
        self.operation = operation


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""

    def __init__(self, message: str = "Failed to connect to database", **kwargs) -> None:
        super().__init__(message, operation="connect", **kwargs)


class DatabaseQueryError(DatabaseError):
    """Raised when a database query fails."""

    def __init__(self, query: str, error: Exception, **kwargs) -> None:
        message = f"Database query failed: {error}"
        super().__init__(message, operation="query", **kwargs)
        self.query = query
        self.original_error = error


# // ========================================( API Exceptions )======================================== // #


class APIError(BotError):
    """Base class for external API-related errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        endpoint: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(message, error_code="API_ERROR", **kwargs)
        self.status_code = status_code
        self.endpoint = endpoint


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""

    def __init__(
        self,
        retry_after: Optional[float] = None,
        endpoint: Optional[str] = None,
        **kwargs
    ) -> None:
        message = f"Rate limit exceeded"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message, status_code=429, endpoint=endpoint, **kwargs)
        self.retry_after = retry_after


class APITimeoutError(APIError):
    """Raised when API request times out."""

    def __init__(self, timeout: float, endpoint: Optional[str] = None, **kwargs) -> None:
        message = f"API request timed out after {timeout} seconds"
        super().__init__(message, status_code=408, endpoint=endpoint, **kwargs)
        self.timeout = timeout


# // ========================================( Permission Exceptions )======================================== // #


class PermissionError(BotError):
    """Base class for permission-related errors."""

    def __init__(
        self,
        message: str,
        required_permission: Optional[str] = None,
        user_id: Optional[int] = None,
        **kwargs
    ) -> None:
        super().__init__(message, error_code="PERMISSION_ERROR", **kwargs)
        self.required_permission = required_permission
        self.user_id = user_id


class InsufficientPermissionsError(PermissionError):
    """Raised when user lacks required permissions."""

    def __init__(
        self,
        required_permission: str,
        user_id: int,
        **kwargs
    ) -> None:
        message = f"User {user_id} lacks required permission: {required_permission}"
        super().__init__(
            message,
            required_permission=required_permission,
            user_id=user_id,
            **kwargs
        )


class BotPermissionError(PermissionError):
    """Raised when bot lacks required permissions."""

    def __init__(self, required_permission: str, guild_id: Optional[int] = None, **kwargs) -> None:
        message = f"Bot lacks required permission: {required_permission}"
        if guild_id:
            message += f" in guild {guild_id}"
        super().__init__(message, required_permission=required_permission, **kwargs)
        self.guild_id = guild_id


# // ========================================( Command Exceptions )======================================== // #


class CommandError(BotError):
    """Base class for command-related errors."""

    def __init__(
        self,
        message: str,
        command_name: Optional[str] = None,
        user_id: Optional[int] = None,
        **kwargs
    ) -> None:
        super().__init__(message, error_code="COMMAND_ERROR", **kwargs)
        self.command_name = command_name
        self.user_id = user_id


class CommandCooldownError(CommandError):
    """Raised when command is on cooldown."""

    def __init__(
        self,
        command_name: str,
        retry_after: float,
        user_id: int,
        **kwargs
    ) -> None:
        message = f"Command '{command_name}' is on cooldown. Retry after {retry_after:.1f} seconds"
        super().__init__(message, command_name=command_name, user_id=user_id, **kwargs)
        self.retry_after = retry_after


class CommandValidationError(CommandError):
    """Raised when command arguments fail validation."""

    def __init__(
        self,
        command_name: str,
        validation_error: str,
        **kwargs
    ) -> None:
        message = f"Validation failed for command '{command_name}': {validation_error}"
        super().__init__(message, command_name=command_name, **kwargs)
        self.validation_error = validation_error


# // ========================================( Service Exceptions )======================================== // #


class ServiceError(BotError):
    """Base class for service-related errors."""

    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(message, error_code="SERVICE_ERROR", **kwargs)
        self.service_name = service_name


class ServiceUnavailableError(ServiceError):
    """Raised when a service is unavailable."""

    def __init__(self, service_name: str, **kwargs) -> None:
        message = f"Service '{service_name}' is unavailable"
        super().__init__(message, service_name=service_name, **kwargs)


class ServiceTimeoutError(ServiceError):
    """Raised when a service operation times out."""

    def __init__(self, service_name: str, timeout: float, **kwargs) -> None:
        message = f"Service '{service_name}' timed out after {timeout} seconds"
        super().__init__(message, service_name=service_name, **kwargs)
        self.timeout = timeout


# // ========================================( Shutdown Exceptions )======================================== // #


class ShutdownError(BotError):
    """Raised during bot shutdown process."""

    def __init__(self, message: str = "Error during bot shutdown", **kwargs) -> None:
        super().__init__(message, error_code="SHUTDOWN_ERROR", **kwargs)


class BotShutdownRequest(Exception):
    """
    Special exception to request bot shutdown.

    This exception is designed to bubble up through the Discord.py event system
    and terminate the bot.run() loop cleanly. When raised, it causes the bot
    to stop running and allows the program to exit gracefully.
    """
    pass


class GracefulShutdownError(ShutdownError):
    """Raised when graceful shutdown fails."""

    def __init__(self, component: str, original_error: Exception, **kwargs) -> None:
        message = f"Failed to gracefully shutdown {component}: {original_error}"
        super().__init__(message, **kwargs)
        self.component = component
        self.original_error = original_error


# // ========================================( Validation Exceptions )======================================== // #


class ValidationError(BotError):
    """Base class for validation-related errors."""

    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ) -> None:
        super().__init__(message, error_code="VALIDATION_ERROR", **kwargs)
        self.field_name = field_name
        self.value = value


class InvalidInputError(ValidationError):
    """Raised when user input is invalid."""

    def __init__(
        self,
        field_name: str,
        value: Any,
        expected_format: str,
        **kwargs
    ) -> None:
        message = f"Invalid input for '{field_name}': {value}. Expected format: {expected_format}"
        super().__init__(message, field_name=field_name, value=value, **kwargs)
        self.expected_format = expected_format


class ValueOutOfRangeError(ValidationError):
    """Raised when a value is outside acceptable range."""

    def __init__(
        self,
        field_name: str,
        value: Any,
        min_value: Optional[Any] = None,
        max_value: Optional[Any] = None,
        **kwargs
    ) -> None:
        range_str = ""
        if min_value is not None and max_value is not None:
            range_str = f" (allowed range: {min_value} - {max_value})"
        elif min_value is not None:
            range_str = f" (minimum: {min_value})"
        elif max_value is not None:
            range_str = f" (maximum: {max_value})"

        message = f"Value for '{field_name}' is out of range: {value}{range_str}"
        super().__init__(message, field_name=field_name, value=value, **kwargs)
        self.min_value = min_value
        self.max_value = max_value


# // ========================================( Utility Functions )======================================== // #


def handle_discord_exception(error: discord.DiscordException, context: Dict[str, Any]) -> BotError:
    """
    Convert Discord.py exceptions to bot exceptions.

    Args:
        error: The Discord exception to convert
        context: Additional context for the error

    Returns:
        BotError: Converted bot exception
    """
    if isinstance(error, discord.Forbidden):
        return BotPermissionError(
            required_permission="unknown",
            context={**context, "discord_error": str(error)}
        )
    elif isinstance(error, discord.NotFound):
        return BotError(
            message="Discord resource not found",
            error_code="DISCORD_NOT_FOUND",
            context={**context, "discord_error": str(error)}
        )
    elif isinstance(error, discord.HTTPException):
        return APIError(
            message=f"Discord API error: {error}",
            status_code=getattr(error, 'status', None),
            context={**context, "discord_error": str(error)}
        )
    else:
        return BotError(
            message=f"Discord error: {error}",
            error_code="DISCORD_ERROR",
            context={**context, "discord_error": str(error)}
        )


def handle_command_exception(error: commands.CommandError, context: commands.Context) -> BotError:
    """
    Convert command exceptions to bot exceptions.

    Args:
        error: The command exception to convert
        context: The command context

    Returns:
        BotError: Converted bot exception
    """
    ctx_data = {
        "command": context.command.qualified_name if context.command else "unknown",
        "user_id": context.author.id,
        "guild_id": context.guild.id if context.guild else None,
        "channel_id": context.channel.id
    }

    if isinstance(error, commands.CommandOnCooldown):
        return CommandCooldownError(
            command_name=ctx_data["command"],
            retry_after=error.retry_after,
            user_id=ctx_data["user_id"],
            context=ctx_data
        )
    elif isinstance(error, commands.MissingPermissions):
        return InsufficientPermissionsError(
            required_permission=", ".join(error.missing_permissions),
            user_id=ctx_data["user_id"],
            context=ctx_data
        )
    elif isinstance(error, commands.BotMissingPermissions):
        return BotPermissionError(
            required_permission=", ".join(error.missing_permissions),
            guild_id=ctx_data["guild_id"],
            context=ctx_data
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        return CommandValidationError(
            command_name=ctx_data["command"],
            validation_error=f"Missing required argument: {error.param.name}",
            context=ctx_data
        )
    else:
        return CommandError(
            message=f"Command error: {error}",
            command_name=ctx_data["command"],
            user_id=ctx_data["user_id"],
            context=ctx_data
        )
