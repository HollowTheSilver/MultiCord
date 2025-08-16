# Discord Bot Template

A production-ready Discord bot template with intelligent permission management, database persistence, professional error handling, and enhanced user experience.

## Features

### 🧠 Intelligent Permission System
The standout feature of this template. The permission system automatically analyzes your Discord server and classifies roles based on their actual purpose:

- **Authority Roles** (admins, mods, trusted members) - These get mapped to permission levels
- **Cosmetic Roles** (colors, teams, reaction roles) - Automatically filtered out
- **Bot Roles** - Detected and ignored during setup
- **Integration Roles** (Nitro boosters, etc.) - Properly categorized

Run `/permissions-setup` and watch it intelligently configure your entire server in seconds.

### 🛡️ Professional Error Handling
No more confusing users with "An error occurred" messages. Every error includes:
- Clear explanation of what went wrong
- Specific suggestions for how to fix it
- Your current permission level vs what's required
- Beautiful, consistent embed formatting

### ⚡ Database Integration
Built-in SQLite database with:
- Automatic schema management and migrations
- Permission configuration persistence
- Audit logging for permission changes
- Cleanup tasks for old data

### 🔧 Developer Experience
- Full type hints throughout the codebase
- Comprehensive logging with Discord.py compatibility
- Modular architecture that's easy to extend
- Professional error handling with detailed context

### 🎨 Beautiful Interface
Every user interaction uses professional embeds with:
- Contextual colors (green for success, red for errors, etc.)
- User attribution in footers
- Organized information with icons and fields
- Loading states for longer operations

### ⚡ Database Integration
Built-in SQLite database with:
- Automatic schema management and migrations
- Permission configuration persistence
- Audit logging for permission changes
- Cleanup tasks for old data

### 🔧 Developer Experience
- Full type hints throughout the codebase
- Comprehensive logging with Discord.py compatibility
- Modular architecture that's easy to extend
- Professional error handling with detailed context

## Quick Start

### Prerequisites
- Python 3.8 or higher
- A Discord bot token

### Setup

1. **Clone and install dependencies**
   ```bash
   git clone https://github.com/yourusername/discord-bot-template.git
   cd discord-bot-template
   pip install -r requirements.txt
   ```

2. **Configure your bot**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your Discord bot token and user ID:
   ```env
   DISCORD_TOKEN=your_bot_token_here
   OWNER_IDS=your_user_id_here
   ```

3. **Run the bot**
   ```bash
   python main.py
   ```

That's it. The bot will create its database automatically and be ready to use.

## Permission System Usage

The permission system is designed to be intuitive for server administrators:

### Automatic Setup
1. Run `/permissions-setup` in your server
2. The bot analyzes all roles and automatically configures authority roles
3. Review the results with `/permissions-list`
4. Fine-tune with `/permissions-set-role` if needed

### Manual Configuration
- `/permissions-set-role @Role LEVEL` - Set a role's permission level
- `/permissions-set-command command LEVEL` - Customize command requirements
- `/permissions-classify` - View how roles were categorized
- `/permissions-analyze` - Deep dive into the classification logic

### Permission Levels
- **EVERYONE** - Default level, no special roles needed
- **MEMBER** - Verified/trusted members, VIPs, supporters
- **MODERATOR** - Basic moderation permissions
- **LEAD_MOD** - Senior moderators with advanced tools
- **ADMIN** - Server administration permissions
- **LEAD_ADMIN** - Senior administrators with full control
- **OWNER** - Server owner permissions
- **BOT_OWNER** - Cross-server bot administration (you)

## Project Structure

```
discord-bot-template/
├── main.py                     # Main bot application
├── config/
│   └── settings.py             # Configuration management
├── utils/
│   ├── permission_models.py    # Permission system data models
│   ├── permissions.py          # Intelligent permission management
│   ├── permission_persistence.py # Database persistence layer
│   ├── database.py             # SQLite database abstraction
│   ├── embeds.py               # Beautiful embed utilities
│   ├── error_handler.py        # Professional error handling
│   ├── loguruConfig.py         # Discord-compatible logging
│   └── exceptions.py           # Custom exception classes
├── cogs/
│   ├── base_commands.py        # Enhanced basic commands
│   ├── permission_manager.py   # Permission management commands
│   └── ...                     # Your additional cogs
├── data/                       # Database files (auto-created)
├── logs/                       # Log files (auto-created)
└── .env                        # Environment configuration
```

## Configuration

The bot is configured through environment variables in your `.env` file:

### Essential Settings
```env
# Required
DISCORD_TOKEN=your_discord_bot_token
OWNER_IDS=your_user_id

# Bot behavior
BOT_NAME="YourBot"
COMMAND_PREFIX="!"
STATUS_MESSAGES="🤖 Online and ready!:custom"

# Features
ENABLE_STATUS_CYCLING="true"
ENABLE_AUTO_SYNC="false"
RESPOND_TO_UNKNOWN_COMMANDS="false"
```

### Advanced Configuration
The template supports extensive customization through environment variables. Check `.env.example` for all available options including logging levels, database settings, and feature flags.

## Adding Commands

The template makes it easy to add new commands with proper permissions and error handling:

```python
from utils.permission_models import PermissionLevel
from utils.permissions import require_level
from utils.embeds import create_success_embed

class YourCog(commands.Cog):
    @commands.hybrid_command()
    @require_level(PermissionLevel.MODERATOR)
    async def your_command(self, ctx: commands.Context):
        """Your command description."""
        embed = create_success_embed(
            title="Command Executed",
            description="Your command worked!",
            user=ctx.author
        )
        await ctx.send(embed=embed)
```

## Database Schema

The bot automatically creates and manages its database schema. Key tables include:

- `guild_configs` - Per-server permission configurations
- `role_mappings` - Role to permission level mappings
- `role_classifications` - How roles were categorized
- `command_overrides` - Custom command permission requirements
- `audit_log` - Permission change history

## Error Handling

The template includes comprehensive error handling that provides users with helpful feedback:

- **Permission Errors** - Shows required vs current permission level
- **Validation Errors** - Explains what input was expected
- **Cooldown Errors** - Shows exactly when the command can be used again
- **Command Errors** - Contextual help for fixing command usage

## Deployment

### Development
```bash
python main.py
```

### Production
The template works well with process managers like PM2:
```bash
pm2 start main.py --name "discord-bot" --interpreter python3
```

For containerized deployment, a basic Dockerfile would be:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

## Contributing

When extending this template:

1. Follow the existing code patterns and architecture
2. Use the embed system for all user-facing messages
3. Add proper type hints and docstrings
4. Include appropriate permission decorators
5. Test with the intelligent permission system

## Troubleshooting

### Common Issues

**Import Errors**: Run `python test_imports.py` to verify all dependencies are correctly installed.

**Permission Issues**: Use `/permissions-analyze` to debug role classification issues.

**Database Errors**: The bot creates its database automatically. If you're having issues, delete the `data/` folder and restart.

**Unicode Role Names**: The template handles fancy Unicode characters in role names automatically.

## License

This template is released under the Apache License 2.0. See LICENSE for details.

## Why Use This Template?

This template solves common problems that Discord bot developers face:

- Setting up permissions across different server structures is tedious - the intelligent classification handles it automatically
- Users get frustrated with generic error messages - the enhanced error handling provides clear, helpful feedback
- Configuration doesn't persist between restarts - the database integration saves your settings
- Basic templates lack the polish needed for real servers - this includes professional embeds and proper logging

It's designed as a solid foundation for Discord bots that need to work reliably in real servers with real users.