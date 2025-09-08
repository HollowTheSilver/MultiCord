"""
User-friendly error messages and handlers for MultiCord CLI.
"""

from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


class ErrorMessages:
    """Centralized error messages for better user experience."""
    
    # Network and connectivity errors
    NETWORK_OFFLINE = "📡 No internet connection detected. Local bot management is still available."
    API_UNREACHABLE = "⚠️  Cannot reach MultiCord API. Please check your internet connection or try again later."
    API_TIMEOUT = "⏱️  Request timed out. The API might be slow or unreachable."
    
    # Authentication errors
    AUTH_REQUIRED = "🔐 Authentication required. Please run 'multicord auth login' first."
    TOKEN_EXPIRED = "⏰ Your session has expired. Please login again with 'multicord auth login'."
    INVALID_CREDENTIALS = "❌ Invalid credentials. Please check your login information."
    DEVICE_CODE_EXPIRED = "⏰ Device code expired. Please start the authentication process again."
    
    # Bot management errors
    BOT_NOT_FOUND = "🤖 Bot '{name}' not found. Use 'multicord bot list' to see available bots."
    BOT_ALREADY_RUNNING = "✅ Bot '{name}' is already running."
    BOT_NOT_RUNNING = "💤 Bot '{name}' is not currently running."
    BOT_START_FAILED = "❌ Failed to start bot '{name}'. Check the logs for details."
    BOT_STOP_FAILED = "❌ Failed to stop bot '{name}'. It may have already stopped."
    
    # Configuration errors
    CONFIG_NOT_FOUND = "📋 Configuration file not found. Creating default configuration."
    INVALID_CONFIG = "⚠️  Invalid configuration detected. Please check your settings."
    TEMPLATE_NOT_FOUND = "📁 Template '{name}' not found. Available templates: basic, moderation, music."
    
    # Permission errors
    PERMISSION_DENIED = "🚫 Permission denied. Please check file permissions."
    PORT_IN_USE = "🔌 Port {port} is already in use. Trying alternative port."
    
    # General errors
    UNKNOWN_ERROR = "❓ An unexpected error occurred. Please try again or report this issue."
    COMMAND_FAILED = "❌ Command failed: {reason}"


class FriendlyError(Exception):
    """Base exception with user-friendly message."""
    
    def __init__(self, message: str, details: Optional[str] = None, suggestion: Optional[str] = None):
        self.message = message
        self.details = details
        self.suggestion = suggestion
        super().__init__(message)
    
    def display(self):
        """Display the error in a user-friendly format."""
        error_text = Text()
        error_text.append(self.message, style="bold red")
        
        if self.details:
            error_text.append("\n\n")
            error_text.append("Details: ", style="bold")
            error_text.append(self.details)
        
        if self.suggestion:
            error_text.append("\n\n")
            error_text.append("💡 Suggestion: ", style="bold yellow")
            error_text.append(self.suggestion, style="yellow")
        
        panel = Panel(
            error_text,
            title="Error",
            border_style="red",
            padding=(1, 2)
        )
        console.print(panel)


class NetworkError(FriendlyError):
    """Network-related errors."""
    
    def __init__(self, details: Optional[str] = None):
        super().__init__(
            ErrorMessages.NETWORK_OFFLINE,
            details,
            "You can still use local bot management commands. Run 'multicord bot list' to see local bots."
        )


class AuthenticationError(FriendlyError):
    """Authentication-related errors."""
    
    def __init__(self, message: str = None, details: Optional[str] = None):
        super().__init__(
            message or ErrorMessages.AUTH_REQUIRED,
            details,
            "Run 'multicord auth login' to authenticate with MultiCord cloud services."
        )


class BotError(FriendlyError):
    """Bot management errors."""
    
    def __init__(self, bot_name: str, message: str, details: Optional[str] = None):
        formatted_message = message.format(name=bot_name)
        super().__init__(
            formatted_message,
            details,
            f"Check bot status with 'multicord bot status {bot_name}' or view logs with 'multicord bot logs {bot_name}'."
        )


def handle_error(func):
    """Decorator to handle errors and display friendly messages."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FriendlyError as e:
            e.display()
            return None
        except ConnectionError:
            NetworkError().display()
            return None
        except PermissionError as e:
            FriendlyError(
                ErrorMessages.PERMISSION_DENIED,
                str(e),
                "Check file permissions or run with appropriate privileges."
            ).display()
            return None
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user.[/yellow]")
            return None
        except Exception as e:
            # Log the full error for debugging
            import traceback
            debug_info = traceback.format_exc()
            
            FriendlyError(
                ErrorMessages.UNKNOWN_ERROR,
                str(e),
                "Enable debug mode with --debug flag for more information."
            ).display()
            
            # In debug mode, show the full traceback
            import sys
            if '--debug' in sys.argv:
                console.print("\n[dim]Debug Information:[/dim]")
                console.print(debug_info, style="dim")
            
            return None
    
    return wrapper


def format_api_error(status_code: int, detail: str) -> str:
    """Format API error responses into user-friendly messages."""
    error_map = {
        400: "Invalid request. Please check your input.",
        401: "Authentication required. Please login first.",
        403: "Access denied. You don't have permission for this action.",
        404: "Resource not found. Please check if it exists.",
        429: "Too many requests. Please wait a moment before trying again.",
        500: "Server error. The API is experiencing issues.",
        502: "API gateway error. Please try again later.",
        503: "API is temporarily unavailable. Please try again later."
    }
    
    base_message = error_map.get(status_code, f"API error (status {status_code})")
    
    if detail:
        return f"{base_message}\nDetails: {detail}"
    
    return base_message