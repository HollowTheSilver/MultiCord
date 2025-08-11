# Discord Bot Template V2

A production-ready Discord bot template with integrated Loguru logging, configuration management, **beautiful embeds**, **professional error handling**, and reliable shutdown handling.

## ✨ Features

- **🎨 Beautiful Embed System**: Consistent, professional embeds with smart utilities and type-safe builders
- **🛡️ Enhanced Error Handling**: Contextual error messages with helpful suggestions instead of generic responses
- **⏱️ Smart Cooldowns**: Built-in rate limiting to prevent spam and abuse
- **🔧 Input Validation**: Comprehensive validation with user-friendly feedback
- **🔧 Discord.py Compatible Logging**: Loguru logging that matches Discord.py's format and colors exactly
- **⚙️ Environment-Based Configuration**: Centralized configuration with validation and type safety
- **🔄 Reliable Shutdown**: Working shutdown system that actually terminates properly
- **📊 Smart Background Tasks**: Status cycling with automatic single/multiple detection
- **🎯 Type Safety**: Full type hints for better development experience
- **🚀 Production Ready**: Battle-tested patterns used by major Discord bots

## 📁 Project Structure

```
discord-bot-template/
├── main.py                 # Main bot file with Application class
├── config/
│   └── settings.py         # Configuration management
├── utils/
│   ├── loguruConfig.py     # Discord-compatible Loguru logging
│   ├── embeds.py           # Beautiful embed system and utilities
│   ├── error_handler.py    # Enhanced error handling with context
│   └── exceptions.py       # Custom exception classes
├── cogs/
│   ├── basic_commands.py   # Enhanced commands with embeds and cooldowns
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

## 🎨 V2 Improvements - What's New

### **Beautiful Embed System**
Transform boring text responses into professional, consistent embeds:

**Before (V1):**
```
🏓 Pong! API Latency: 45ms, Message Latency: 120ms
```

**After (V2):**
- 🎨 Beautiful color-coded embeds (green/yellow/red based on performance)
- ⏳ Loading states during operations
- 📊 Organized information with icons and fields
- 👤 User attribution in footers
- 🔗 Interactive elements and links

### **Enhanced Error Handling**
Stop confusing users with generic error messages:

**Before (V1):**
```
❌ An error occurred. Please try again later.
```

**After (V2):**
- 🎯 **Contextual errors** with specific problem identification
- 💡 **Helpful suggestions** for how to fix the issue
- 🔢 **Error codes** for tracking and support
- ⏰ **Cooldown timers** showing exactly when to retry
- 🛡️ **Permission helpers** explaining what's needed

### **Smart Features**
- **Command Cooldowns**: Prevents spam with user-friendly rate limiting
- **Input Validation**: Sanitizes and validates all user input
- **Loading States**: Shows progress for longer operations
- **Enhanced Logging**: More detailed logging with user context

## 🎨 Embed System Usage

### Quick Embeds
```python
from utils.embeds import create_success_embed, create_error_embed

# Success message
embed = create_success_embed(
    title="Task Completed",
    description="Your request was processed successfully!",
    user=ctx.author
)

# Error message with suggestions
embed = create_error_embed(
    title="Invalid Input", 
    description="The provided value is not valid.",
    error_code="VALIDATION_001",
    user=ctx.author
)
```

### Advanced Embed Builder
```python
from utils.embeds import EmbedBuilder, EmbedType

embed = EmbedBuilder(EmbedType.INFO, "User Profile") \
    .add_field("Username", user.name, inline=True) \
    .add_field("Joined", f"<t:{int(user.created_at.timestamp())}:R>", inline=True) \
    .set_thumbnail(user.avatar.url) \
    .set_footer(f"ID: {user.id}") \
    .build()
```

### Embed Types
- **EmbedType.SUCCESS** - ✅ Green embeds for successful operations
- **EmbedType.ERROR** - ❌ Red embeds for errors and failures  
- **EmbedType.WARNING** - ⚠️ Yellow embeds for warnings
- **EmbedType.INFO** - ℹ️ Blue embeds for information
- **EmbedType.LOADING** - ⏳ Purple embeds for ongoing operations

## 🛡️ Enhanced Error Handling

The V2 error system provides contextual, helpful error messages:

```python
# Automatic handling in your commands
@commands.hybrid_command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def my_command(self, ctx, value: int):
    if value < 0:
        raise ValidationError(
            field_name="value",
            value=value, 
            expected_format="positive integer"
        )
    # Command logic here
```

**Users see beautiful embeds with:**
- Clear problem description
- Specific field that caused the error
- Expected format or range
- Helpful suggestions for fixing the issue

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

### Enhanced Features
- `RESPOND_TO_UNKNOWN_COMMANDS`: Whether to respond to unknown commands (default: false)
- `ENABLE_STATUS_CYCLING`: Enable automatic status cycling
- `ENABLE_HEALTH_CHECKS`: Enable periodic health checks

### Logging
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOG_DIR`: Directory for log files
- `LOG_ROTATION`: When to rotate logs (e.g., "10 MB", "1 day")
- `LOG_RETENTION`: How long to keep logs (e.g., "1 week")

## 🎯 Key Components

### Enhanced Bot Class (`main.py`)

The `Application` class extends `commands.Bot` with:
- Integrated Discord-compatible Loguru logging
- Professional error handling system
- Beautiful embed integration
- Configuration management  
- Background task management
- Reliable shutdown handling

### Embed System (`utils/embeds.py`)

Comprehensive embed utilities:
- **EmbedBuilder**: Fluent API for complex embeds
- **Quick Functions**: One-line embed creation
- **Type Safety**: Predefined embed types with consistent styling
- **Auto-truncation**: Prevents Discord limits issues
- **Pagination**: Built-in support for large data sets

### Error Handler (`utils/error_handler.py`)

Professional error handling:
- **Contextual Messages**: Specific, helpful error responses
- **Error Tracking**: User error rate monitoring
- **Beautiful Embeds**: Consistent error presentation
- **Comprehensive Coverage**: Handles all Discord.py errors

### Configuration (`config/settings.py`)

The `BotConfig` class provides:
- Environment variable loading with defaults
- Configuration validation
- Type-safe configuration access

## 📝 Creating Enhanced Cogs

Example V2 cog structure with embeds and error handling:

```python
import discord
from discord.ext import commands
from utils.loguruConfig import configure_logger
from utils.embeds import create_success_embed, EmbedBuilder, EmbedType
from utils.exceptions import ValidationError

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
    @commands.cooldown(2, 10, commands.BucketType.user)
    async def your_command(self, ctx: commands.Context, value: str) -> None:
        """Enhanced command with validation and beautiful embeds."""
        
        # Input validation
        if len(value) > 100:
            raise ValidationError(
                field_name="value",
                value=f"{len(value)} characters",
                expected_format="maximum 100 characters"
            )
        
        # Create beautiful response
        embed = create_success_embed(
            title="Command Executed",
            description=f"Successfully processed: {value}",
            user=ctx.author
        )
        
        await ctx.send(embed=embed)
        
        # Enhanced logging
        self.logger.info("Command executed successfully", extra={
            "user": str(ctx.author),
            "value_length": len(value),
            "guild": ctx.guild.name if ctx.guild else "DM"
        })

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(YourCog(bot))
```

## 🔄 Reliable Shutdown System

The bot uses a **proven shutdown pattern** that actually works:

### Commands:
- `!shutdown` - Owner-only command for remote shutdown
- `Ctrl+C` - Signal-based shutdown for local development

### Why This Works:
- ✅ **No Deadlocks**: Avoids Discord.py's event loop conflicts
- ✅ **Clean Resource Cleanup**: Proper task and connection management
- ✅ **Guaranteed Termination**: Uses OS-level exit for reliability
- ✅ **Production Pattern**: Same approach used by major Discord bots

## 🔒 Security Best Practices

1. **Never commit your `.env` file** - Add it to `.gitignore`
2. **Use environment variables** for all sensitive data
3. **Validate user input** in all commands (automatic with V2 system)
4. **Implement proper permission checks**
5. **Rate limit commands** with cooldowns (built into V2)
6. **Log security events** for monitoring

## 📊 Monitoring and Logging

The template includes comprehensive logging that matches Discord.py exactly:
- **Console output**: Discord.py compatible colored logs for development
- **File logging**: Structured logs with rotation and compression
- **Error tracking**: Detailed error logs with user context
- **Performance monitoring**: Latency and health check logging
- **User action tracking**: Command usage with context

## 🚨 Error Handling Examples

### V2 Error Messages Users See:

**Permission Error:**
```
❌ Missing Permissions

You don't have permission to use this command.

Required Permissions: Manage Messages, Kick Members

💡 Suggestion
Contact a server administrator if you believe this is an error.
```

**Validation Error:**
```
❌ Validation Error

The provided input is invalid.

Field: username
Provided Value: user123!@#$%
Expected Format: alphanumeric characters only

💡 Suggestion
Remove special characters and try again.
```

**Rate Limit Error:**
```
⚠️ Command on Cooldown

This command is currently on cooldown.

⏰ Time Remaining: 2m 15s
🔄 Cooldown Type: User

Please wait before using this command again.
```

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

1. Follow the existing V2 patterns
2. Use the embed system for all user-facing messages
3. Add proper type hints and validation
4. Include comprehensive logging with context
5. Handle errors using the enhanced error system
6. Add appropriate cooldowns to prevent abuse
7. Write docstrings for all functions
8. Update configuration if needed

## 📄 License

This template is provided under the Apache License 2.0. See LICENSE file for details.

## 🆘 Support

- Check the logs in `logs/` directory for error details
- Ensure all required environment variables are set
- Verify Discord bot permissions and intents
- Check Discord.py documentation for API-specific issues
- V2 error messages now include helpful suggestions automatically

## 🔗 Useful Links

- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Discord Developer Portal](https://discord.com/developers/applications)
- [Loguru Documentation](https://loguru.readthedocs.io/)
- [Discord Bot Best Practices](https://discord.com/developers/docs/topics/community-resources)

---

**Ready to build amazing Discord bots?** This V2 template eliminates setup friction and provides professional-grade UX so you can focus on creating great features! 🚀

## 🎉 What's Next?

Consider these future enhancements:
- Custom help system with embed categories
- Plugin/module system for easy extensibility  
- Advanced caching strategies
- Performance monitoring and metrics
- Database integration examples
- Webhook integrations for external services