"""
MultiCord Basic Business Bot Template
====================================

Professional Discord bot with technical convenience features.
Generated from template: basic_business_bot v1.0.0

This template provides common business bot functionality without
business logic coupling. All features are technical enhancements.
"""

import discord
from discord.ext import commands
import logging
import os
import sys
from datetime import datetime, timezone
import asyncio


class MultiCordBot(commands.Bot):
    """
    Professional Discord bot with MultiCord platform integration.
    
    Provides technical convenience features while maintaining clean
    separation from business logic.
    """
    
    def __init__(self):
        # Bot configuration from environment
        command_prefix = os.getenv("COMMAND_PREFIX", "!")
        bot_name = os.getenv("BOT_NAME", "MultiCord Bot")
        
        # Initialize bot with intents
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix=command_prefix,
            description=f"{bot_name} - Powered by MultiCord Platform",
            intents=intents,
            help_command=commands.DefaultHelpCommand()
        )
        
        # Bot configuration
        self.bot_name = bot_name
        self.start_time = datetime.now(timezone.utc)
        self.client_id = "{{CLIENT_ID}}"
        
        # Embed colors (technical branding feature)
        self.colors = {
            "primary": 0x3498db,
            "success": 0x2ecc71,
            "warning": 0xf39c12,
            "error": 0xe74c3c
        }
        
        # Setup logging
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup structured logging for the bot."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(f'MultiCord.Bot.{self.client_id}')
        
    async def setup_hook(self):
        """Called when the bot is starting up."""
        self.logger.info(f"🤖 {self.bot_name} is initializing...")
        self.logger.info(f"Template: basic_business_bot v1.0.0")
        self.logger.info(f"Prefix: {self.command_prefix}")
        
        # Load extensions (if any)
        await self.load_extensions()
        
    async def load_extensions(self):
        """Load bot extensions and cogs."""
        # This is where additional functionality would be loaded
        # For now, we keep it simple with built-in commands
        pass
        
    async def on_ready(self):
        """Called when the bot successfully connects to Discord."""
        self.logger.info(f"✅ {self.bot_name} is online!")
        self.logger.info(f"Connected as: {self.user} (ID: {self.user.id})")
        self.logger.info(f"Guilds: {len(self.guilds)}")
        
        # Set bot activity status
        activity_text = os.getenv("ACTIVITY_TEXT", f"for commands | {self.command_prefix}help")
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=activity_text.replace("{{COMMAND_PREFIX}}", str(self.command_prefix))
        )
        await self.change_presence(activity=activity)
        
    async def on_command_error(self, ctx, error):
        """Handle command errors professionally."""
        if isinstance(error, commands.CommandNotFound):
            embed = discord.Embed(
                title="❓ Command Not Found",
                description=f"The command `{ctx.invoked_with}` was not found.\nUse `{ctx.prefix}help` to see available commands.",
                color=self.colors["warning"]
            )
            await ctx.send(embed=embed)
            
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="⚠️ Missing Argument",
                description=f"Missing required argument: `{error.param.name}`\nUse `{ctx.prefix}help {ctx.command}` for more info.",
                color=self.colors["error"]
            )
            await ctx.send(embed=embed)
            
        else:
            # Log unexpected errors
            self.logger.error(f"Command error in {ctx.command}: {error}")
            embed = discord.Embed(
                title="❌ Command Error",
                description="An unexpected error occurred. Please try again later.",
                color=self.colors["error"]
            )
            await ctx.send(embed=embed)
    
    async def on_message(self, message):
        """Process messages and commands."""
        # Ignore bot messages
        if message.author.bot:
            return
            
        # Log command usage (technical monitoring feature)
        if message.content.startswith(self.command_prefix):
            self.logger.info(f"Command used: {message.content} by {message.author} in {message.guild}")
        
        # Process commands
        await self.process_commands(message)


# Bot Commands
@commands.command(name="ping")
async def ping_command(ctx):
    """Check bot responsiveness and latency."""
    latency = round(ctx.bot.latency * 1000, 2)
    
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot latency: {latency}ms",
        color=ctx.bot.colors["success"]
    )
    embed.set_footer(text=f"Powered by MultiCord Platform")
    
    await ctx.send(embed=embed)


@commands.command(name="info")
async def info_command(ctx):
    """Display bot and server information."""
    bot = ctx.bot
    guild = ctx.guild
    
    embed = discord.Embed(
        title=f"📊 {bot.bot_name} Information",
        color=bot.colors["primary"]
    )
    
    embed.add_field(
        name="🤖 Bot Stats",
        value=f"**Uptime:** {_get_uptime(bot.start_time)}\n"
              f"**Guilds:** {len(bot.guilds)}\n"
              f"**Latency:** {round(bot.latency * 1000, 2)}ms",
        inline=True
    )
    
    if guild:
        embed.add_field(
            name="🏠 Server Stats",
            value=f"**Name:** {guild.name}\n"
                  f"**Members:** {guild.member_count}\n"
                  f"**Created:** {guild.created_at.strftime('%Y-%m-%d')}",
            inline=True
        )
    
    embed.add_field(
        name="⚙️ Technical",
        value=f"**Template:** basic_business_bot v1.0.0\n"
              f"**Platform:** MultiCord\n"
              f"**Python:** {sys.version.split()[0]}",
        inline=False
    )
    
    embed.set_footer(text=f"Bot ID: {bot.client_id} | Powered by MultiCord Platform")
    embed.timestamp = datetime.now(timezone.utc)
    
    await ctx.send(embed=embed)


@commands.command(name="status")
async def status_command(ctx):
    """Display bot health and status information."""
    bot = ctx.bot
    
    embed = discord.Embed(
        title="📈 Bot Status",
        color=bot.colors["success"]
    )
    
    embed.add_field(
        name="🟢 System Status",
        value="All systems operational",
        inline=True
    )
    
    embed.add_field(
        name="⏱️ Uptime",
        value=_get_uptime(bot.start_time),
        inline=True
    )
    
    embed.add_field(
        name="🔗 Connection",
        value=f"Latency: {round(bot.latency * 1000, 2)}ms",
        inline=True
    )
    
    # Technical features status
    embed.add_field(
        name="🛠️ Features",
        value="✅ Monitoring\n✅ Logging\n✅ Error Handling\n✅ Health Checks",
        inline=False
    )
    
    embed.set_footer(text="MultiCord Platform - Professional Bot Infrastructure")
    embed.timestamp = datetime.now(timezone.utc)
    
    await ctx.send(embed=embed)


def _get_uptime(start_time: datetime) -> str:
    """Calculate and format bot uptime."""
    uptime = datetime.now(timezone.utc) - start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def main():
    """Main bot entry point."""
    # Get Discord token
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ ERROR: DISCORD_TOKEN environment variable not set!")
        print("Please provide your Discord bot token.")
        sys.exit(1)
    
    # Create and run bot
    bot = MultiCordBot()
    
    # Add commands to bot
    bot.add_command(ping_command)
    bot.add_command(info_command)
    bot.add_command(status_command)
    
    try:
        print(f"🚀 Starting {bot.bot_name}...")
        bot.run(token, log_handler=None)  # We handle logging ourselves
    except discord.LoginFailure:
        print("❌ ERROR: Invalid Discord token!")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"👋 {bot.bot_name} shutting down...")
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()