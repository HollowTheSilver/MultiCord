# Discord Bot Template

A production-ready Discord bot template with integrated Loguru logging, configuration management, and reliable shutdown handling.

## ✨ Features

- **🔧 Discord.py Compatible Logging**: Loguru logging that matches Discord.py's format and colors exactly
- **⚙️ Environment-Based Configuration**: Centralized configuration with validation and type safety
- **🔄 Reliable Shutdown**: Working shutdown system that actually terminates properly
- **📊 Smart Background Tasks**: Status cycling with automatic single/multiple detection
- **🛡️ Professional Error Handling**: Comprehensive exception hierarchy and user-friendly error messages
- **🎯 Type Safety**: Full type hints for better development experience
- **🚀 Production Ready**: Battle-tested patterns used by major Discord bots

## 📁 Project Structure

```
discord-bot-template/
├── main.py                 # Main bot file with ProfessionalBot class
├── config/
│   └── settings.py         # Configuration management
├── utils/
│   ├── loguruConfig.py     # Discord-compatible Loguru logging
│   └── exceptions.py       # Custom exception classes
├── cogs/
│   ├── basic_commands.py   # Sample cog with essential commands
│   └── ...                 # Your additional cogs
├── logs/                   # Log files (auto-created)
├── .env                    # Environment variables (copy from .env.example)
├── .env.example            # Environment template
└── requirements.txt        # Python dependencies
```

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/discord-bot-template.git
cd discord-bot-template

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy the environment template
cp .env.example .env

# Edit .env with your bot token
nano .env
```

**Minimum required configuration:**
```env
DISCORD_TOKEN=your_discord_bot_token_here
OWNER_IDS=your_user_id_here
```

### 3. Create Your Bot Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section
4. Create a bot and copy the token
5. Enable necessary intents (Message Content Intent, Server Members Intent)

### 4. Run the Bot

```bash
python main.py
```

## 📋 Requirements

```txt
discord.py>=2.3.0
python-dotenv>=1.0.0
loguru>=0.7.0
```

**Python Version:** 3.8+

## 🎨 Discord.py Compatible Logging

The template automatically configures Loguru to match Discord.py's logging format and colors exactly:

```
2024-01-15 10:30:45,123 INFO     discord.gateway Shard ID None has connected to Gateway
2024-01-15 10:30:45,456 DEBUG    your.module Your custom log message
2024-01-15 10:30:45,789 WARNING  commands.basic_commands Command executed: ping
```

**Key Benefits:**
- **Perfect Format Matching**: Identical timestamp format with milliseconds
- **Matching Colors**: DEBUG (dim), INFO (blue), WARNING (yellow), ERROR (red), CRITICAL (bold red)
- **Side-by-side Compatibility**: No confusion between different logging styles
- **File Rotation**: Automatic log rotation, compression, and cleanup

## 🔧 Configuration Options

### Core Settings
- `DISCORD_TOKEN`: Your bot token (required)
- `COMMAND_PREFIX`: Command prefix (default: "!")
- `OWNER_IDS`: Comma-separated list of owner user IDs

### Status Messages
- `STATUS_MESSAGES`: Bot status configuration
  - **Single**: `"🤖 Always online!:custom"` (sets once, efficient)
  - **Multiple**: `"Playing:playing,Watching:watching,Listening:listening"` (cycles)
  - **Types**: `playing`, `watching`, `listening`, `streaming`, `competing`, `custom`

### Logging
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOG_DIR`: Directory for log files
- `LOG_ROTATION`: When to rotate logs (e.g., "10 MB", "1 day")
- `LOG_RETENTION`: How long to keep logs (e.g., "1 week")

### Features
- `ENABLE_STATUS_CYCLING`: Enable automatic status cycling
- `ENABLE_HEALTH_CHECKS`: Enable periodic health checks
- `ENABLE_SLASH_COMMANDS`: Enable application commands

### Performance
- `MAX_WORKERS`: Maximum worker threads
- `MAX_QUEUE_SIZE`: Maximum queue size for background tasks

## 🎯 Key Components

### Main Bot Class (`main.py`)

The `ProfessionalBot` class extends `commands.Bot` with:
- Integrated Discord-compatible Loguru logging
- Configuration management
- Background task management
- Reliable shutdown handling
- Comprehensive error handling

### Configuration (`config/settings.py`)

The `BotConfig` class provides:
- Environment variable loading with defaults
- Configuration validation
- Type-safe configuration access

### Logging (`utils/loguruConfig.py`)

Discord-compatible logging features:
- Matches Discord.py format exactly
- Same colors as Discord.py
- File rotation and compression
- Structured logging with context

### Error Handling (`utils/exceptions.py`)

Custom exception hierarchy:
- `BotError`: Base exception class
- `ConfigurationError`: Configuration-related errors
- `DatabaseError`: Database operation errors
- `APIError`: External API errors
- `PermissionError`: Permission-related errors

## 📝 Creating Cogs

Example cog structure:

```python
import discord
from discord.ext import commands
from utils.loguruConfig import configure_logger

class YourCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = configure_logger(
            log_dir=bot.config.LOG_DIR,
            level=bot.config.LOG_LEVEL,
            format_extra=True,
            discord_compat=True
        )
    
    @commands.hybrid_command()
    async def your_command(self, ctx: commands.Context) -> None:
        """Your command description."""
        # Your command logic here
        self.logger.info("Command executed", extra={
            "user": str(ctx.author),
            "guild": ctx.guild.name if ctx.guild else "DM"
        })

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(YourCog(bot))
```

## 🔄 Reliable Shutdown System

The bot uses a **proven shutdown pattern** that actually works:

### How It Works:
```python
# 1. Request shutdown (safe from any context)
bot.request_shutdown()

# 2. Background monitor detects request
@tasks.loop(seconds=1)
async def shutdown_monitor(self):
    if self._shutdown_requested:
        await self._perform_shutdown()

# 3. Clean shutdown process
async def _perform_shutdown(self):
    # Stop tasks, close connections, flush logs
    os._exit(0)  # Reliable termination
```

### Why This Works:
- ✅ **No Deadlocks**: Avoids Discord.py's event loop conflicts
- ✅ **Clean Resource Cleanup**: Proper task and connection management
- ✅ **Guaranteed Termination**: Uses OS-level exit for reliability
- ✅ **Production Pattern**: Same approach used by major Discord bots

### Commands:
- `!shutdown` - Owner-only command for remote shutdown
- `Ctrl+C` - Signal-based shutdown for local development

## 🛠️ Advanced Usage

### Custom Background Tasks

```python
from discord.ext import tasks

@tasks.loop(minutes=30)
async def my_background_task(self) -> None:
    """Your background task."""
    # Task logic here
    pass

@my_background_task.before_loop
async def before_my_task(self) -> None:
    await self.bot.wait_until_ready()
```

### Database Integration

Add database initialization in `_initialize_services()`:

```python
async def _initialize_services(self) -> None:
    if self.config.DATABASE_URL:
        self.database = await init_database(self.config.DATABASE_URL)
        self.logger.info("Database connected")
```

### Custom Error Handling

```python
from utils.exceptions import ValidationError

async def my_command(self, ctx, value: int):
    if value < 0:
        raise ValidationError(
            field_name="value", 
            value=value, 
            expected_format="positive integer"
        )
```

## 🔒 Security Best Practices

1. **Never commit your `.env` file** - Add it to `.gitignore`
2. **Use environment variables** for all sensitive data
3. **Validate user input** in commands
4. **Implement proper permission checks**
5. **Rate limit commands** where appropriate
6. **Log security events** for monitoring

## 📊 Monitoring and Logging

The template includes comprehensive logging that matches Discord.py exactly:
- **Console output**: Discord.py compatible colored logs for development
- **File logging**: Structured logs with rotation and compression
- **Error tracking**: Detailed error logs with context
- **Performance monitoring**: Latency and health check logging

Log files are automatically rotated and compressed. Check the `logs/` directory for historical data.

## 🚨 Error Handling

The bot includes robust error handling:
- **Command errors**: User-friendly error messages
- **Permission errors**: Clear permission requirements
- **Rate limiting**: Automatic cooldown handling
- **Validation errors**: Input validation with helpful messages
- **System errors**: Graceful degradation and logging

## 🔄 Deployment

### Development
```bash
python main.py
```

### Production (with PM2)
```bash
pm2 start main.py --name "discord-bot" --interpreter python3
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

## 🤝 Contributing

When extending this template:

1. Follow the existing code structure
2. Add proper type hints
3. Include comprehensive logging
4. Write docstrings for all functions
5. Handle errors appropriately
6. Update configuration if needed

## 📄 License

This template is provided under the MIT License. See LICENSE file for details.

## 🆘 Support

- Check the logs in `logs/` directory for error details
- Ensure all required environment variables are set
- Verify Discord bot permissions and intents
- Check Discord.py documentation for API-specific issues

## 🔗 Useful Links

- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Discord Developer Portal](https://discord.com/developers/applications)
- [Loguru Documentation](https://loguru.readthedocs.io/)
- [Discord Bot Best Practices](https://discord.com/developers/docs/topics/community-resources)

---

**Ready to build amazing Discord bots?** This template eliminates setup friction so you can focus on creating great features! 🚀