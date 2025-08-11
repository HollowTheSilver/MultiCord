"""
Loguru Configuration Module
-----------------------------

A comprehensive configuration module for Loguru logger, optimized for asynchronous
applications with Discord.py compatible formatting. Provides sophisticated logging
including colored console output, file rotation, structured logging with operation
context, and proper resource management for async operations.

The Discord-compatible mode matches Discord.py's default logging format and colors
exactly for consistent logging output.
"""


# // ========================================( Modules )======================================== // #


import os
import sys
import threading
import json
from pathlib import Path
from typing import Any, Optional, Union, Set, Dict
from functools import lru_cache
from loguru import logger


# // ========================================( Exceptions )======================================== // #


class LoggingError(Exception):
    """Base exception for logging-related errors."""
    pass


class LoggerConfigError(LoggingError):
    """Raised when logger configuration is invalid."""
    pass


class ShutdownError(LoggingError):
    """Raised during logging system shutdown errors."""
    pass


# // ========================================( Constants )======================================== // #


# Discord.py compatible formats (matches discord.py exactly)
DISCORD_CONSOLE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss},{time:SSS} "
    "<level>{level: <8}</level> "
    "<cyan>{name}</cyan> "
    "{message}"
)

DISCORD_CONSOLE_FORMAT_EXTRA = (
    "{time:YYYY-MM-DD HH:mm:ss},{time:SSS} "
    "<level>{level: <8}</level> "
    "<cyan>{name}</cyan> "
    "{message} "
    "<dim>{extra}</dim>"
)

DISCORD_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss},{time:SSS} "
    "{level:<8} "
    "{name} "
    "{message}"
)

DISCORD_FILE_FORMAT_EXTRA = (
    "{time:YYYY-MM-DD HH:mm:ss},{time:SSS} "
    "{level:<8} "
    "{name} "
    "{message} "
    "{extra}"
)

VALID_LEVELS: Set[str] = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


# // ========================================( Classes )======================================== // #


class LoggerState:
    """Thread-safe singleton for tracking logger state."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.initialized = False
                cls._instance.handler_count = 0
        return cls._instance


# // ========================================( Functions )======================================== // #


def extra_filter(record: Dict[str, Any]) -> bool:
    """
    Enhanced filter for formatting extra fields in log records.
    Handles both string and dictionary extra fields.
    """
    extras = record.get("extra", {})

    # If no extras, set to empty string instead of None
    if not extras:
        record["extra"] = ""
        return True

    # Handle dictionary extras
    if isinstance(extras, dict):
        # Filter out empty values
        formatted_items = []
        for k, v in extras.items():
            if v is None or v == "" or v == {} or v == []:
                continue

            if isinstance(v, (dict, list)):
                v = json.dumps(v, sort_keys=True)
                if v in ('{}', '[]'):
                    continue

            formatted_items.append(f"{k}={v}")

        record["extra"] = f"[{', '.join(formatted_items)}]" if formatted_items else ""
        return True

    # Handle string extras
    if isinstance(extras, str):
        if not extras.strip() or extras.strip() in ['[]', '[extra={}]']:
            record["extra"] = ""
        return True

    return True


def _validate_level(level: str) -> None:
    """
    Validate the provided logging level.

    Args:
        level: The logging level to validate.

    Raises:
        ValueError: If the provided level is not valid.
    """
    if level.upper() not in VALID_LEVELS:
        raise ValueError(f"Invalid logging level. Must be one of: {', '.join(sorted(VALID_LEVELS))}")


def verify_logger_config() -> None:
    """
    Verify logger configuration consistency.

    Raises:
        RuntimeError: If logger configuration is missing or invalid.
    """
    state = LoggerState()
    if not state.initialized:
        raise RuntimeError("Logger not properly initialized")

    handlers = logger._core.handlers  # NOQA
    if not handlers:
        raise RuntimeError("Logger configuration missing - no handlers found")

    # Verify handler count matches expected
    if len(handlers) != state.handler_count:
        raise RuntimeError(f"Logger configuration mismatch - expected {state.handler_count} handlers, found {len(handlers)}")


@lru_cache(maxsize=1)
def configure_logger(
        log_dir: Optional[Union[str, Path]] = None,
        level: str = "DEBUG",
        rotation: str = "10 MB",
        retention: str = "1 week",
        compression: str = "zip",
        format_extra: bool = False,
        discord_compat: bool = True
) -> logger:
    """
    Configure Loguru logger with Discord.py compatible formatting and error handling.

    This enhanced version provides Discord.py compatible formatting that matches
    the default Discord.py logging format and colors exactly for consistent output.

    Args:
        log_dir: Directory for log files. If None, only console logging is configured.
        level: Minimum logging level. Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL.
        rotation: When to rotate log files (e.g., "10 MB" or "1 day").
        retention: How long to keep log files (e.g., "1 week").
        compression: Compression format for rotated logs ("zip", "gz", "tar").
        format_extra: Whether to use the extended format with extra context.
        discord_compat: Whether to use Discord.py compatible formatting and colors.

    Returns:
        logger: Configured Loguru logger instance.

    Raises:
        ValueError: If an invalid logging level is provided.
        OSError: If there are permission issues with the log directory.
    """
    state = LoggerState()

    with threading.Lock():
        if state.initialized:
            verify_logger_config()
            return logger

        # Validate logging level before proceeding
        _validate_level(level)

        # Remove any existing handlers and reset state
        logger.remove()
        state.handler_count = 0

        # Configure level colors to match Discord.py's default colors
        if discord_compat:
            logger.level("DEBUG", color="<dim>")              # Dim white/gray like discord.py
            logger.level("INFO", color="<blue>")              # Blue like discord.py INFO
            logger.level("WARNING", color="<yellow>")         # Yellow like discord.py WARNING
            logger.level("ERROR", color="<red>")              # Red like discord.py ERROR
            logger.level("CRITICAL", color="<red><bold>")     # Bold red like discord.py CRITICAL
        else:
            # Fallback to default colors (though discord_compat is always True in this setup)
            logger.level("DEBUG", color="<white><bold>")
            logger.level("INFO", color="<blue><bold>")
            logger.level("WARNING", color="<yellow><bold>")
            logger.level("ERROR", color="<red><bold>")
            logger.level("CRITICAL", color="<red><dim><bold>")

        # Use Discord-compatible formats (since discord_compat is always True)
        console_format = DISCORD_CONSOLE_FORMAT_EXTRA if format_extra else DISCORD_CONSOLE_FORMAT
        file_format = DISCORD_FILE_FORMAT_EXTRA if format_extra else DISCORD_FILE_FORMAT

        # Add console handler
        try:
            logger.add(
                sys.stdout,
                format=console_format,
                level=level,
                backtrace=True,
                diagnose=True,
                colorize=True,
                filter=extra_filter if format_extra else None
            )
            state.handler_count += 1
        except ValueError as e:
            raise ValueError(f"Invalid logging configuration: {str(e)}")

        # Configure file logging if directory is specified
        if log_dir:
            try:
                log_path = Path(log_dir)
                log_path.mkdir(parents=True, exist_ok=True)

                # Verify directory permissions
                if not os.access(log_path, os.W_OK):
                    raise OSError(f"Directory {log_dir} is not writable")

                file_path = log_path / "{time:YYYY-MM-DD}.log"
                logger.add(
                    str(file_path),
                    format=file_format,
                    level=level,
                    rotation=rotation,
                    retention=retention,
                    compression=compression,
                    backtrace=True,
                    diagnose=True,
                    encoding="utf-8",
                    filter=extra_filter if format_extra else None
                )
                state.handler_count += 1
            except Exception as e:
                logger.error(f"Failed to configure file logging: {str(e)}")
                logger.warning("Continuing with console logging only")

        state.initialized = True
        return logger
