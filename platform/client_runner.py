"""
Client Runner System
===================

Individual client bot runner that loads client-specific configuration
and starts a bot instance with custom branding and features.
"""

import asyncio
import os
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, Any
import importlib.util

# Add core modules to path
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from dotenv import load_dotenv
from core.application import Application
from config.settings import BotConfig


class ClientRunner:
    """
    Runner for individual client bot instances with custom configuration.
    """

    def __init__(self, client_id: str):
        """Initialize client runner."""
        self.client_id = client_id
        self.client_path = Path("clients") / client_id
        self.core_path = Path("core")

        # Validate client directory
        if not self.client_path.exists():
            raise FileNotFoundError(f"Client directory not found: {self.client_path}")

        # Load client environment
        client_env = self.client_path / ".env"
        if client_env.exists():
            load_dotenv(client_env)
        else:
            raise FileNotFoundError(f"Client .env file not found: {client_env}")

        # Set client-specific paths
        os.environ["CLIENT_ID"] = client_id
        os.environ["CLIENT_PATH"] = str(self.client_path)

        # Load client configuration
        self.client_config = self._load_client_config()
        self.bot_config = self._create_bot_config()
        self.branding = self._load_client_branding()
        self.features = self._load_client_features()

    def _load_client_config(self) -> Dict[str, Any]:
        """Load client-specific configuration."""
        try:
            config_file = self.client_path / "config.py"
            if config_file.exists():
                spec = importlib.util.spec_from_file_location("client_config", config_file)
                config_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(config_module)

                if hasattr(config_module, 'CLIENT_CONFIG'):
                    return config_module.CLIENT_CONFIG

        except Exception as e:
            print(f"Warning: Failed to load client config: {e}")

        return {}

    def _create_bot_config(self) -> BotConfig:
        """Create bot configuration with client-specific overrides."""
        # Start with base configuration
        config = BotConfig()

        # Apply client-specific overrides
        client_overrides = self.client_config.get('bot_config', {})

        for key, value in client_overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)

        # Set client-specific paths
        config.LOG_DIR = str(self.client_path / "logs")
        config.DATABASE_URL = str(self.client_path / "data" / "permissions.db")

        # Ensure directories exist
        Path(config.LOG_DIR).mkdir(parents=True, exist_ok=True)
        Path(config.DATABASE_URL).parent.mkdir(parents=True, exist_ok=True)

        return config

    def _load_client_branding(self) -> Dict[str, Any]:
        """Load client-specific branding configuration."""
        try:
            branding_file = self.client_path / "branding.py"
            if branding_file.exists():
                spec = importlib.util.spec_from_file_location("client_branding", branding_file)
                branding_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(branding_module)

                if hasattr(branding_module, 'BRANDING'):
                    return branding_module.BRANDING

        except Exception as e:
            print(f"Warning: Failed to load client branding: {e}")

        return {}

    def _load_client_features(self) -> Dict[str, Any]:
        """Load client-specific feature configuration."""
        try:
            features_file = self.client_path / "features.py"
            if features_file.exists():
                spec = importlib.util.spec_from_file_location("client_features", features_file)
                features_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(features_module)

                if hasattr(features_module, 'FEATURES'):
                    return features_module.FEATURES

        except Exception as e:
            print(f"Warning: Failed to load client features: {e}")

        return {}

    async def _load_custom_cogs(self, bot: Application) -> None:
        """Load client-specific cogs."""
        custom_cogs_dir = self.client_path / "custom_cogs"

        if not custom_cogs_dir.exists():
            return

        # Add client cogs to path
        sys.path.insert(0, str(custom_cogs_dir))

        loaded_count = 0
        for cog_file in custom_cogs_dir.glob("*.py"):
            if cog_file.name.startswith("_"):
                continue

            cog_name = f"custom_cogs.{cog_file.stem}"

            try:
                await bot.load_extension(cog_name)
                loaded_count += 1
                bot.logger.info(f"Loaded custom cog: {cog_name}")

            except Exception as e:
                bot.logger.error(f"Failed to load custom cog {cog_name}: {e}")

        if loaded_count > 0:
            bot.logger.info(f"Loaded {loaded_count} custom cogs for client {self.client_id}")

    def _apply_branding(self, bot: Application) -> None:
        """Apply client-specific branding to the bot."""
        if not self.branding:
            return

        # Store branding in bot for use by embeds
        bot.client_branding = self.branding
        bot.client_id = self.client_id

        # Apply any direct configuration overrides
        if 'status_messages' in self.branding:
            bot.config.STATUS_MESSAGES = self.branding['status_messages']

    async def run(self) -> None:
        """Run the client bot instance."""
        # Get Discord token
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise ValueError(f"DISCORD_TOKEN not found for client {self.client_id}")

        try:
            # Create bot application with client config
            bot = ClientApplication(
                config=self.bot_config,
                client_id=self.client_id,
                client_branding=self.branding,
                client_features=self.features
            )

            # Apply branding
            self._apply_branding(bot)

            # Load custom cogs after setup
            async def after_setup():
                await self._load_custom_cogs(bot)

            # Add setup hook
            original_setup_hook = bot.setup_hook
            async def enhanced_setup_hook():
                await original_setup_hook()
                await after_setup()

            bot.setup_hook = enhanced_setup_hook

            # Start the bot
            bot.logger.info(f"Starting client bot: {self.client_id}")
            await bot.start(token)

        except Exception as e:
            print(f"Failed to start client {self.client_id}: {e}")
            raise


class ClientApplication(Application):
    """
    Enhanced Application class with client-specific functionality.
    """

    def __init__(self, config: Optional[BotConfig] = None, client_id: str = None,
                 client_branding: Dict[str, Any] = None, client_features: Dict[str, Any] = None):
        """Initialize client application with custom configuration."""
        super().__init__(config)

        self.client_id = client_id
        self.client_branding = client_branding or {}
        self.client_features = client_features or {}

        # Add client info to logger context
        if self.logger and client_id:
            self.logger = self.logger.bind(client_id=client_id)

    def get_branded_embed_color(self, embed_type: str = "default") -> int:
        """Get client-specific embed color."""
        if not self.client_branding:
            return 0x3498db  # Default blue

        colors = self.client_branding.get('embed_colors', {})
        return colors.get(embed_type, colors.get('default', 0x3498db))

    def get_branded_bot_name(self) -> str:
        """Get client-specific bot name."""
        if self.client_branding and 'bot_name' in self.client_branding:
            return self.client_branding['bot_name']
        return self.config.BOT_NAME

    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a specific feature is enabled for this client."""
        if not self.client_features:
            return True  # Default to enabled if no feature config

        return self.client_features.get(feature, True)

    async def on_ready(self) -> None:
        """Enhanced on_ready with client-specific initialization."""
        await super().on_ready()

        # Log client-specific startup
        if self.client_id:
            self.logger.info(f"Client {self.client_id} is ready!", extra={
                "client_id": self.client_id,
                "branded_name": self.get_branded_bot_name(),
                "features": list(self.client_features.keys()) if self.client_features else []
            })

    def get_stats(self) -> Dict[str, Any]:
        """Get enhanced stats with client information."""
        stats = super().get_stats()

        # Add client-specific stats
        stats.update({
            "client_id": self.client_id,
            "branded_name": self.get_branded_bot_name(),
            "enabled_features": list(self.client_features.keys()) if self.client_features else [],
            "custom_cogs": len([name for name in self.cogs.keys() if "custom_cogs" in name])
        })

        return stats


def main():
    """Main entry point for client runner."""
    parser = argparse.ArgumentParser(description="Run a specific Discord bot client")
    parser.add_argument("--client-id", required=True, help="Client ID to run")

    args = parser.parse_args()

    try:
        runner = ClientRunner(args.client_id)
        asyncio.run(runner.run())

    except KeyboardInterrupt:
        print(f"Client {args.client_id} stopped by user")
    except Exception as e:
        print(f"Client {args.client_id} failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
