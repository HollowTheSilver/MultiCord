"""
Display utilities for CLI output.
"""

from rich.console import Console
from rich.theme import Theme


# Custom theme for MultiCord
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green"
})


class Display:
    """Handles formatted console output."""
    
    def __init__(self):
        self.console = Console(theme=custom_theme)
    
    def info(self, message: str) -> None:
        """Display info message."""
        self.console.print(f"[info]ℹ {message}[/info]")
    
    def success(self, message: str) -> None:
        """Display success message."""
        self.console.print(f"[success]✓ {message}[/success]")
    
    def warning(self, message: str) -> None:
        """Display warning message."""
        self.console.print(f"[warning]⚠ {message}[/warning]")
    
    def error(self, message: str) -> None:
        """Display error message."""
        self.console.print(f"[error]✗ {message}[/error]")