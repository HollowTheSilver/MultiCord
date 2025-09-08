"""
Local bot process management.
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Any


class BotManager:
    """Manages local Discord bot processes."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".multicord"
        self.bots_dir = self.config_dir / "bots"
        self.templates_dir = self.config_dir / "templates"
        self.running_bots: Dict[str, subprocess.Popen] = {}
        
        # Ensure directories exist
        self.bots_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
    
    def list_bots(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all local bots."""
        bots = []
        if self.bots_dir.exists():
            for bot_dir in self.bots_dir.iterdir():
                if bot_dir.is_dir():
                    bot_status = "stopped"
                    if bot_dir.name in self.running_bots:
                        bot_status = "running"
                    
                    if status is None or status == "all" or status == bot_status:
                        bots.append({
                            "name": bot_dir.name,
                            "status": bot_status,
                            "template": "unknown"
                        })
        return bots
    
    def create_bot(self, name: str, template: str) -> Path:
        """Create a new bot from template."""
        bot_path = self.bots_dir / name
        if bot_path.exists():
            raise ValueError(f"Bot '{name}' already exists")
        
        bot_path.mkdir(parents=True)
        
        # Create basic bot file
        bot_file = bot_path / "bot.py"
        bot_file.write_text("""#!/usr/bin/env python3
# Discord bot implementation
print(f"Bot {__name__} starting...")
""")
        
        # Create config file
        config_file = bot_path / "config.toml"
        config_file.write_text("""[bot]
token = "YOUR_BOT_TOKEN_HERE"
prefix = "!"

[logging]
level = "INFO"
""")
        
        return bot_path
    
    def start_bot(self, name: str) -> int:
        """Start a bot process."""
        bot_path = self.bots_dir / name
        if not bot_path.exists():
            raise ValueError(f"Bot '{name}' does not exist")
        
        if name in self.running_bots:
            raise ValueError(f"Bot '{name}' is already running")
        
        bot_file = bot_path / "bot.py"
        if not bot_file.exists():
            raise ValueError(f"Bot file not found: {bot_file}")
        
        # Start bot process
        process = subprocess.Popen(
            ["python", str(bot_file)],
            cwd=str(bot_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        self.running_bots[name] = process
        return process.pid
    
    def stop_bot(self, name: str) -> None:
        """Stop a bot process."""
        if name not in self.running_bots:
            raise ValueError(f"Bot '{name}' is not running")
        
        process = self.running_bots[name]
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        
        del self.running_bots[name]
    
    def get_bot_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a bot."""
        bot_path = self.bots_dir / name
        if not bot_path.exists():
            return None
        
        status = {
            "name": name,
            "path": str(bot_path),
            "status": "running" if name in self.running_bots else "stopped"
        }
        
        if name in self.running_bots:
            status["pid"] = self.running_bots[name].pid
        
        return status
    
    def get_logs(self, name: str, lines: int = 50) -> List[str]:
        """Get bot logs."""
        log_file = self.bots_dir / name / "logs" / "bot.log"
        if not log_file.exists():
            return ["No logs available"]
        
        with open(log_file, "r") as f:
            all_lines = f.readlines()
            return all_lines[-lines:]
    
    def follow_logs(self, name: str) -> None:
        """Follow bot logs in real-time."""
        # TODO: Implement log following
        print(f"Following logs for {name}...")
    
    def list_templates(self) -> List[Dict[str, str]]:
        """List available templates."""
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