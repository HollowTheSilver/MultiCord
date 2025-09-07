#!/usr/bin/env python3
"""
MultiCord Platform CLI - Main Entry Point
=========================================

Professional command-line interface for MultiCord Platform bot management.
Supports standard Discord.py bots with zero modifications required.

Usage:
    multicord start my_bot --token YOUR_TOKEN
    multicord stop my_bot  
    multicord list
    multicord status my_bot
    multicord info

Environment Variables:
    MULTICORD_DB_HOST     - PostgreSQL host (default: localhost)
    MULTICORD_DB_PORT     - PostgreSQL port (default: 5432)
    MULTICORD_DB_NAME     - Database name (default: multicord_platform)
    MULTICORD_DB_USER     - Database user (default: multicord_user)
    MULTICORD_DB_PASSWORD - Database password (default: multicord_secure_pass)
    MULTICORD_LOG_LEVEL   - Log level (default: INFO)
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path
from typing import List, Dict, Any

# Import our CLI controller
from .controllers.platform_controller import PlatformController, PlatformConfig


class MultiCordCLI:
    """Main CLI application for MultiCord Platform."""
    
    def __init__(self):
        """Initialize CLI application."""
        self.config = self._load_config()
        self.controller = PlatformController(self.config)
    
    def _load_config(self) -> PlatformConfig:
        """Load configuration from environment variables and defaults."""
        return PlatformConfig(
            db_host=os.getenv("MULTICORD_DB_HOST", "localhost"),
            db_port=int(os.getenv("MULTICORD_DB_PORT", "5432")),
            db_name=os.getenv("MULTICORD_DB_NAME", "multicord_platform"),
            db_user=os.getenv("MULTICORD_DB_USER", "multicord_user"),
            db_password=os.getenv("MULTICORD_DB_PASSWORD", "multicord_secure_pass"),
            log_level=os.getenv("MULTICORD_LOG_LEVEL", "INFO"),
            offline_mode=os.getenv("MULTICORD_OFFLINE", "false").lower() == "true"
        )
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create and configure argument parser."""
        parser = argparse.ArgumentParser(
            prog="multicord",
            description="MultiCord Platform - Professional Discord Bot Infrastructure",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  multicord start my_bot --token YOUR_DISCORD_TOKEN
  multicord start my_bot --token YOUR_TOKEN --bot-file ./my_bot.py
  multicord start my_bot --token YOUR_TOKEN --features monitoring_service branding_enhancement
  multicord stop my_bot
  multicord list --all
  multicord status my_bot
  multicord info

For more information, visit: https://multicord.platform
            """
        )
        
        # Global options
        parser.add_argument("--offline", action="store_true",
                          help="Run in offline mode (no database)")
        parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                          default="INFO", help="Set logging level")
        parser.add_argument("--db-host", help="PostgreSQL host")
        parser.add_argument("--db-port", type=int, help="PostgreSQL port")
        parser.add_argument("--db-user", help="Database user")
        parser.add_argument("--db-password", help="Database password")
        
        # Create subcommands
        subparsers = parser.add_subparsers(dest="command", help="Available commands")
        
        # Start command
        start_parser = subparsers.add_parser(
            "start", 
            help="Start a Discord bot instance",
            description="Start a Discord bot with zero modifications required"
        )
        start_parser.add_argument("client_id", help="Unique bot identifier")
        start_parser.add_argument("--token", "-t", help="Discord bot token")
        start_parser.add_argument("--bot-file", "-f", help="Path to bot Python file")
        start_parser.add_argument("--strategy", "-s", choices=["standard", "template", "enhanced"],
                                default="standard", help="Execution strategy")
        start_parser.add_argument("--template", help="Template name (for template strategy)")
        start_parser.add_argument("--features", nargs="*", 
                                help="Technical features to enable")
        start_parser.add_argument("--env", "-e", action="append", metavar="KEY=VALUE",
                                help="Additional environment variables")
        
        # Stop command
        stop_parser = subparsers.add_parser(
            "stop",
            help="Stop a running bot instance",
            description="Gracefully stop a running Discord bot"
        )
        stop_parser.add_argument("client_id", help="Bot identifier to stop")
        stop_parser.add_argument("--force", action="store_true",
                               help="Force kill if graceful stop fails")
        
        # List command  
        list_parser = subparsers.add_parser(
            "list",
            help="List bot instances",
            description="Show all bot instances and their status"
        )
        list_parser.add_argument("--all", "-a", action="store_true",
                               help="Show all instances including stopped ones")
        
        # Status command
        status_parser = subparsers.add_parser(
            "status",
            help="Show detailed bot status", 
            description="Display detailed information about a specific bot"
        )
        status_parser.add_argument("client_id", help="Bot identifier")
        
        # Info command
        subparsers.add_parser(
            "info",
            help="Show platform information",
            description="Display MultiCord Platform status and configuration"
        )
        
        # Templates command
        templates_parser = subparsers.add_parser(
            "templates",
            help="List available bot templates",
            description="Show available bot templates for convenience features"
        )
        templates_parser.add_argument("--details", "-d", action="store_true",
                                    help="Show detailed template information")
        
        # Logs command
        logs_parser = subparsers.add_parser(
            "logs",
            help="Show bot logs",
            description="Display recent log output from a bot"
        )
        logs_parser.add_argument("client_id", help="Bot identifier")
        logs_parser.add_argument("--lines", "-n", type=int, default=100,
                               help="Number of lines to show")
        logs_parser.add_argument("--follow", "-f", action="store_true",
                               help="Follow log output (live tail)")
        
        return parser
    
    def _parse_env_vars(self, env_args: List[str]) -> Dict[str, str]:
        """Parse environment variable arguments."""
        env_vars = {}
        if env_args:
            for env_arg in env_args:
                if "=" in env_arg:
                    key, value = env_arg.split("=", 1)
                    env_vars[key] = value
                else:
                    print(f"Warning: Invalid environment variable format: {env_arg}")
        return env_vars
    
    async def run_start_command(self, args) -> int:
        """Execute the start command."""
        if not args.token:
            print("Error: Discord token is required. Use --token or set DISCORD_TOKEN environment variable.")
            return 1
        
        # Handle template strategy
        if args.strategy == "template":
            if not args.template:
                print("Error: Template name is required when using template strategy. Use --template.")
                return 1
                
        env_vars = self._parse_env_vars(args.env or [])
        
        # Add template name to environment if using template strategy
        if args.strategy == "template" and args.template:
            env_vars["TEMPLATE_NAME"] = args.template
        
        success = await self.controller.start_bot(
            client_id=args.client_id,
            discord_token=args.token,
            execution_strategy=args.strategy,
            bot_file=args.bot_file,
            features=args.features,
            env_vars=env_vars
        )
        
        return 0 if success else 1
    
    async def run_stop_command(self, args) -> int:
        """Execute the stop command."""
        success = await self.controller.stop_bot(
            client_id=args.client_id,
            force=args.force
        )
        
        return 0 if success else 1
    
    async def run_list_command(self, args) -> int:
        """Execute the list command."""
        success = await self.controller.list_bots(show_all=args.all)
        return 0 if success else 1
    
    async def run_status_command(self, args) -> int:
        """Execute the status command."""
        success = await self.controller.show_bot_status(args.client_id)
        return 0 if success else 1
    
    async def run_info_command(self, args) -> int:
        """Execute the info command."""
        success = await self.controller.show_platform_info()
        return 0 if success else 1
    
    async def run_templates_command(self, args) -> int:
        """Execute the templates command."""
        success = await self.controller.list_templates(details=args.details)
        return 0 if success else 1
    
    async def run_logs_command(self, args) -> int:
        """Execute the logs command."""
        # This would require implementing log reading functionality
        print(f"Showing logs for {args.client_id} (last {args.lines} lines)")
        if args.follow:
            print("Following logs... (Press Ctrl+C to stop)")
            
        # For now, just show a message that this needs implementation
        print("Log viewing functionality will be implemented in the next iteration")
        return 0
    
    async def run(self, argv: List[str] = None) -> int:
        """
        Main entry point for CLI execution.
        
        Args:
            argv: Command line arguments (defaults to sys.argv[1:])
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        if argv is None:
            argv = sys.argv[1:]
        
        parser = self.create_parser()
        args = parser.parse_args(argv)
        
        # Override config with command line arguments
        if args.offline:
            self.config.offline_mode = True
        if args.log_level:
            self.config.log_level = args.log_level
        if args.db_host:
            self.config.db_host = args.db_host
        if args.db_port:
            self.config.db_port = args.db_port
        if args.db_user:
            self.config.db_user = args.db_user  
        if args.db_password:
            self.config.db_password = args.db_password
        
        # Recreate controller with updated config
        self.controller = PlatformController(self.config)
        
        try:
            # Initialize platform
            if not await self.controller.initialize():
                print("Failed to initialize MultiCord Platform")
                return 1
            
            # Execute command
            if args.command == "start":
                return await self.run_start_command(args)
            elif args.command == "stop":
                return await self.run_stop_command(args)
            elif args.command == "list":
                return await self.run_list_command(args)
            elif args.command == "status":
                return await self.run_status_command(args)
            elif args.command == "info":
                return await self.run_info_command(args)
            elif args.command == "templates":
                return await self.run_templates_command(args)
            elif args.command == "logs":
                return await self.run_logs_command(args)
            else:
                parser.print_help()
                return 1
                
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
            return 130
        except Exception as e:
            print(f"Unexpected error: {e}")
            return 1
        finally:
            # Clean up resources
            await self.controller.cleanup()


def main() -> None:
    """Main entry point for the CLI application."""
    cli = MultiCordCLI()
    try:
        exit_code = asyncio.run(cli.run())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()