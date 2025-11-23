# MultiCord CLI

**Version 1.2.0** | Run Multiple Discord Bots Like a Pro

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

MultiCord transforms Discord bot management from chaos to control. Run 10 bots on your laptop or deploy 1000 to the cloud—all with simple, intuitive commands.

---

## 🎯 What is MultiCord?

MultiCord is a professional CLI tool for managing multiple Discord bots with complete process isolation, health monitoring, and cloud integration.

### The Problem
```bash
# Traditional approach (painful):
cd bot1 && python bot.py &
cd ../bot2 && python bot.py &  # Port conflict!
cd ../bot3 && python bot.py &  # Resource issues!
# Manual process management, no monitoring, dependency conflicts...
```

### The Solution
```bash
# MultiCord approach (professional):
multicord bot create my-bot --template music
multicord bot start my-bot music-bot trading-bot  # All handled automatically
multicord bot status  # Real-time monitoring with health metrics
```

---

## ✨ Key Features

### 🖥️ Local Bot Management (Free Forever)

- **Per-Bot Isolated Virtual Environments** ⭐ NEW in v1.1
  - Complete dependency isolation (different discord.py versions per bot)
  - Self-contained, portable bot directories
  - Shared pip cache for 60-80% disk savings
  - Industry-standard microservice architecture

- **Advanced Process Orchestration**
  - Automatic port assignment and conflict resolution
  - Sophisticated process isolation with resource monitoring
  - Real-time health monitoring with CPU, memory, and uptime tracking
  - Graceful shutdown handling with timeout management

- **Modular Cog System** ⭐ ENHANCED in v1.2
  - Install optional features as modular cogs
  - Enterprise-grade permissions system (9-level hierarchy)
  - Repository-based cog management
  - **NEW: Automatic cog dependency resolution**
  - **NEW: Circular dependency detection**

- **Token Management** ⭐ NEW in v1.2
  - Dedicated `multicord token` command group
  - Secure storage with Windows Credential Manager (or encrypted file fallback)
  - View API auth status alongside bot tokens
  - Masked token display for security

- **Template Update Ecosystem** ⭐ NEW in v1.1
  - Multi-repository support with priority system
  - Automatic update detection with semantic versioning
  - Three update strategies (core-only, safe-merge, full-replace)
  - Intelligent config merging preserving user values
  - Compressed backups with one-command rollback

- **Production-Ready Templates**
  - **basic**: Simple command bot with event handling
  - **moderation**: Full moderation suite (kick, ban, timeout, warnings, role management)
  - **music**: Music bot with YouTube integration and queue management
  - **business**: Professional bot with automatic cog loading

### ☁️ Cloud Integration (Premium)

- **Multi-Node Deployment**: Deploy bots to cloud infrastructure
- **Configuration Sync**: Bidirectional sync with conflict resolution
- **Offline Caching**: Transparent fallback when API unavailable
- **Advanced Analytics**: Detailed metrics and insights (future)
- **Auto-Scaling**: Scale based on demand (future)

---

## 🚀 Quick Start

### Installation

```bash
# Install from source (PyPI coming soon)
git clone https://github.com/HollowTheSilver/MultiCord.git
cd CLI
pip install -e .
```

**Requirements**: Python 3.9+ • Windows, Linux, or macOS

### Your First Bot in 3 Commands

```bash
# 1. Create bot from template (with isolated venv)
multicord bot create my-music-bot --template music

# 2. Configure your bot token
cd ~/.multicord/bots/my-music-bot
# Edit config.toml and add your Discord token

# 3. Start the bot
multicord bot start my-music-bot
```

### Managing Multiple Bots

```bash
# Create multiple bots
multicord bot create trading-bot --template basic
multicord bot create mod-bot --template moderation

# Start them all
multicord bot start my-music-bot trading-bot mod-bot

# Monitor with real-time dashboard
multicord bot health  # Live dashboard with health metrics

# Check status
multicord bot status  # Detailed status for all bots

# View logs
multicord bot logs my-music-bot --follow

# Stop all bots
multicord bot stop --all
```

---

## 📋 Complete Command Reference

MultiCord CLI provides **43 commands** across **9 command groups**.

### 🔐 Authentication (`multicord auth`) - 4 commands

Manage authentication with MultiCord API using Discord OAuth2.

- `multicord auth login` - Login with Discord (opens browser for OAuth2)
- `multicord auth logout` - Logout and clear stored tokens
- `multicord auth status` - Check authentication status and show Discord user info
- `multicord auth refresh` - Refresh access token

**Example**:
```bash
multicord auth login    # Opens Discord authorization in browser
multicord auth status   # Shows: Logged in as YourDiscordUser#1234
```

---

### 🤖 Bot Management (`multicord bot`) - 14 commands

Complete bot lifecycle management with health monitoring.

#### Bot Lifecycle
- `multicord bot create <name> --template <template>` - Create new bot from template
  - **Flags**: `--template` (required), `--repo` (custom repository)
  - **NEW in v1.2**: `--token` (prompt for Discord token after creation)
  - **Automatic**: Creates isolated venv, installs requirements.txt, auto-installs cogs

- `multicord bot delete <name>` - Delete a bot (with confirmation)

- `multicord bot start <name> [name2...]` - Start one or more bots
  - **Flags**: `--all` (start all bots), `--env KEY=VALUE` (inject environment variables)
  - **NEW in v1.2**: `--follow` (follow logs after starting, single bot only)
  - **Validation**: Checks venv exists before starting

- `multicord bot stop <name> [name2...]` - Stop one or more bots
  - **Flags**: `--all` (stop all bots), `--force` (force kill)

- `multicord bot restart <name> [name2...]` - Restart one or more bots

#### Monitoring
- `multicord bot list` - List all bots with status
  - **Flags**: `--local`, `--cloud`, `--sync` (merged view), `--status <running|stopped>`

- `multicord bot status [name]` - Detailed status with health metrics
  - Shows: PID, port, CPU, memory, uptime, health level

- `multicord bot health` - Real-time health monitoring dashboard
  - **Flags**: `--refresh <seconds>` (auto-refresh interval)
  - **Display**: Color-coded health levels, resource usage, alerts

- `multicord bot logs <name>` - View bot logs
  - **Flags**: `--follow` (tail -f style), `--lines <n>`, `--cloud`

#### Cloud Operations
- `multicord bot deploy <name>` - Deploy bot to cloud
  - **Flags**: `--node <node-name>` (target deployment node)

- `multicord bot pull <name>` - Pull cloud bot configuration to local

- `multicord bot sync <name>` - Bidirectional sync with conflict resolution
  - **Flags**: `--strategy <local_first|cloud_first|newest|manual>`

#### Template Updates ⭐ NEW in v1.1
- `multicord bot check-updates [name]` - Check for available template updates
  - **Flags**: `--all` (check all bots)
  - **Display**: Shows version changes, breaking changes, changelogs

- `multicord bot update <name>` - Apply template updates
  - **Flags**: `--strategy <core-only|safe-merge|full-replace>`, `--dry-run`, `--version <version>`
  - **Safety**: Automatic compressed backup before update

- `multicord bot rollback <name>` - Rollback to previous backup
  - **Flags**: `--list` (show available backups), `--backup <name>`

**Examples**:
```bash
# Create and start a bot
multicord bot create my-bot --template music
multicord bot start my-bot

# Monitor multiple bots
multicord bot list --status running
multicord bot health --refresh 5  # Auto-refresh every 5 seconds

# Update template
multicord bot check-updates my-bot
multicord bot update my-bot --strategy safe-merge
```

---

### 🔧 Virtual Environments (`multicord venv`) - 4 commands ⭐ NEW in v1.1

Manage per-bot isolated virtual environments.

- `multicord venv install <bot>` - Install/reinstall bot dependencies from requirements.txt
  - **Flags**: `--upgrade` (upgrade existing packages)

- `multicord venv clean <bot>` - Remove and recreate bot's venv from scratch
  - **Safety**: Confirmation prompt before deletion

- `multicord venv update <bot>` - Upgrade all packages in bot's venv to latest versions

- `multicord venv info <bot>` - Show venv information
  - **Flags**: `--all` (show summary for all bots)
  - **Display**: Python version, installed packages, disk usage, pip cache stats

**Examples**:
```bash
# View all bot venvs
multicord venv info --all

# Reinstall dependencies for a bot
multicord venv clean my-bot

# Upgrade all packages
multicord venv update my-bot
```

---

### 🔑 Token Management (`multicord token`) - 4 commands ⭐ NEW in v1.2

Securely manage Discord bot tokens and API credentials.

- `multicord token list [bot]` - View all stored credentials
  - Shows API authentication status (Discord OAuth2)
  - Lists all bot tokens with storage method
  - **Flags**: `--all` (include bots without tokens)

- `multicord token set <bot>` - Store bot token securely
  - Uses Windows Credential Manager (or encrypted file fallback)
  - **Flags**: `--token <value>` (provide directly, not recommended)

- `multicord token delete <bot>` - Remove stored token
  - **Flags**: `-y` (skip confirmation)

- `multicord token show <bot>` - Display token details
  - Masked by default for security
  - **Flags**: `--unmask` (show full token)

**Examples**:
```bash
# View all credentials
multicord token list

# Store token securely (recommended)
multicord token set my-bot  # Interactive prompt

# Show masked token
multicord token show my-bot
```

---

### 🧩 Cog Management (`multicord cog`) - 5 commands ⭐ ENHANCED in v1.2

Install and manage modular bot features (cogs) with dependency resolution.

- `multicord cog available` - List all available cogs from repository
  - **Display**: Grouped by category, shows version, author, featured cogs

- `multicord cog list <bot>` - Show installed cogs for a bot

- `multicord cog add <bot> <cog>` - Install cog to bot
  - **NEW in v1.2**: Automatic dependency resolution
  - **NEW in v1.2**: Circular dependency detection
  - **Flags**: `--no-deps` (skip dependency installation)

- `multicord cog remove <bot> <cog>` - Uninstall cog from bot
  - **Note**: Dependencies not automatically removed

- `multicord cog update <bot> [cog]` - Update cog(s) to latest version
  - **Flags**: `--all` (update all installed cogs)

**Examples**:
```bash
# Browse available cogs
multicord cog available

# Install cog with automatic dependencies
multicord cog add my-bot moderation-advanced
# → Checks dependencies, prompts if missing, installs in order

# List installed cogs
multicord cog list my-bot
```

---

### 📦 Template Management (`multicord template`) - 2 commands

Manage bot templates.

- `multicord template list` - List available templates
  - **Display**: Shows all templates from all enabled repositories

- `multicord template install <url>` - Install custom template from URL
  - **Supports**: Git repositories

**Examples**:
```bash
multicord template list
multicord template install https://github.com/user/custom-bot-template
```

---

### 🔄 Repository Management (`multicord repo`) - 8 commands ⭐ NEW in v1.1

Manage template and cog repositories with priority system.

- `multicord repo list` - Show all configured repositories
  - **Display**: Priority order, enabled/disabled status, type (official/custom)

- `multicord repo add <name> <url>` - Add custom repository
  - **Flags**: `--priority <n>` (higher = checked first)

- `multicord repo remove <name>` - Remove repository

- `multicord repo update [name]` - Update repository (git pull)
  - **Flags**: `--all` (update all repositories)

- `multicord repo info <name>` - Show repository details
  - **Display**: URL, branch, templates, cogs, last updated

- `multicord repo priority <name> <priority>` - Set repository priority
  - **Note**: Higher priority repos override lower ones for same template names

- `multicord repo enable <name>` - Enable repository

- `multicord repo disable <name>` - Disable repository

**Examples**:
```bash
# Add organization's private templates
multicord repo add my-org https://github.com/my-org/templates.git

# Update all repositories
multicord repo update --all

# Set priority (higher = checked first)
multicord repo priority my-org 100
```

---

### 💾 Cache Management (`multicord cache`) - 3 commands

Manage API response caching for offline operation.

- `multicord cache status` - Show cache statistics
  - **Display**: Size, entry count, hit rate, TTL info

- `multicord cache clear` - Clear all cached data

- `multicord cache refresh` - Refresh cache from API
  - **Fetches**: Bots, templates, user profile

**Examples**:
```bash
multicord cache status
multicord cache refresh  # Refresh from API
```

---

### ⚙️ Configuration (`multicord config`) - 2 commands

View and modify global configuration.

- `multicord config show` - Show current configuration
  - **Display**: Local settings, API settings, authentication status

- `multicord config set <key> <value>` - Set configuration value

**Examples**:
```bash
multicord config show
multicord config set api.url https://api.multicord.io
```

---

### 🏥 System Health (`multicord doctor`) - 1 command

Check system health and dependencies.

- `multicord doctor` - Run comprehensive system health check
  - **Checks**: Python version, discord.py, API connectivity, authentication
  - **Display**: Color-coded pass/fail for each check

**Example**:
```bash
multicord doctor
# Output:
# [OK] Python Version: 3.11.5
# [OK] discord.py: 2.3.2
# [OK] API Connection: Online
# [OK] Authentication: Valid
```

---

## 🏗️ Architecture

### Per-Bot Virtual Environments (v1.1+)

MultiCord uses industry-standard isolated virtual environments for each bot:

```
~/.multicord/
├── .venv/                     # CLI virtual environment (multicord only)
├── pip-cache/                 # Shared pip cache (60-80% disk savings)
└── bots/
    ├── LinkGuard/
    │   ├── .venv/             # Isolated LinkGuard dependencies
    │   ├── bot.py
    │   ├── requirements.txt
    │   ├── config.toml
    │   ├── logs/
    │   ├── data/
    │   └── cogs/
    │       └── permissions/   # Enterprise permissions system
    ├── MusicBot/
    │   ├── .venv/             # Isolated MusicBot dependencies
    │   ├── bot.py
    │   ├── requirements.txt
    │   └── config.toml
    └── ModBot/
        ├── .venv/             # Different discord.py version possible!
        ├── bot.py
        └── requirements.txt
```

**Benefits**:
- ✅ **No Dependency Conflicts**: Each bot can use different library versions
- ✅ **Complete Isolation**: One bot's issues don't affect others
- ✅ **Portable**: Move bot directories between systems easily
- ✅ **Professional**: Industry-standard microservice architecture

---

## 🎨 Available Templates

### Official Templates

- **basic** - Simple extensible bot with command handling and events
  - Discord.py 2.3+ implementation
  - Built-in logging and error handling
  - TOML configuration
  - Ready for extension

- **moderation** - Comprehensive moderation suite
  - Kick, ban, timeout, warnings system
  - Role management (add/remove roles)
  - Message cleanup and purge
  - Moderation logging
  - Configurable permissions

- **music** - Full-featured music playback
  - YouTube integration with search
  - Queue management (add, remove, skip, shuffle)
  - Playback controls (play, pause, stop, volume)
  - Now playing display
  - Playlist support

- **business** - Professional bot with cog loading
  - Automatic cog discovery and loading
  - Structured logging and monitoring
  - Enterprise-ready architecture
  - Template for production deployments

### Community Templates

Browse and contribute templates at:
**https://github.com/HollowTheSilver/MultiCord-Templates**

### Creating Custom Templates

```bash
# Add your organization's templates
multicord repo add my-org https://github.com/my-org/discord-templates.git

# Use them
multicord bot create my-bot --template internal-bot --repo my-org
```

---

## 🧩 Cog System

### What are Cogs?

Cogs are modular, optional features you can install into any bot. They're like plugins that extend your bot's functionality without modifying the core bot code.

### Available Cogs

**permissions** - Enterprise-Grade Permission System
- 9-level permission hierarchy (0-8)
- Role-based and user-based permissions
- Permission inheritance and overrides
- Channel-specific permissions
- Audit logging for all permission changes
- ~2,500 lines of production code

### Installing Cogs

```bash
# Browse available cogs
multicord cog available

# Install permissions system to your bot
multicord cog add my-bot permissions

# Cog dependencies automatically install into bot's venv
# Restart bot to load the cog
multicord bot restart my-bot
```

---

## 🔄 Template Updates

### Checking for Updates

```bash
# Check single bot
multicord bot check-updates my-bot

# Check all bots
multicord bot check-updates --all

# Example output:
# my-bot: music v1.0.0 → v1.2.0 available
#   ✨ v1.2.0: Added playlist support
#   🔧 v1.1.0: Fixed YouTube search
```

### Applying Updates

Three update strategies available:

1. **core-only** (safest): Update only bot.py and requirements.txt
2. **safe-merge** (recommended): Update core + intelligently merge configs
3. **full-replace** (aggressive): Replace all files except user data

```bash
# Safe merge (recommended)
multicord bot update my-bot --strategy safe-merge

# Dry run to preview changes
multicord bot update my-bot --strategy safe-merge --dry-run

# Update to specific version
multicord bot update my-bot --version 1.2.0
```

### Rollback

Automatic compressed backups (last 5 kept):

```bash
# List available backups
multicord bot rollback my-bot --list

# Rollback to previous version
multicord bot rollback my-bot
```

---

## 🔐 Authentication

### Discord OAuth2 (Hybrid Flow)

MultiCord uses Discord as the sole authentication provider:

- **Browser Flow**: Opens Discord authorization in your browser (desktop)
- **Device Flow**: Shows code for manual entry (SSH, Docker, servers)
- **Smart Detection**: Automatically chooses best method for your environment

```bash
# Desktop: Opens browser automatically
multicord auth login

# Server/SSH: Shows device code for manual entry
# No DISPLAY: MultiCord auth at https://multicord.io/device
# Enter code: ABC-123-DEF
```

**Why Discord-Only?**
- Every user already has Discord (managing Discord bots!)
- Zero friction onboarding
- Guild access for bot deployment
- Trusted provider with 2FA support

---

## 🔒 Security

### Token Storage
- Secure storage using system keyring library
- Tokens encrypted at rest
- Never shown in logs or CLI output
- Automatic token refresh

### Process Isolation
- Each bot runs in isolated process with dedicated resources
- Per-bot virtual environments prevent dependency conflicts
- Configurable CPU and memory limits (coming soon)

### API Communication
- All API calls use HTTPS with SSL verification
- JWT tokens with refresh token rotation
- Rate limiting enforced server-side
- Audit logging for all operations

---

## 🧪 Development

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/HollowTheSilver/MultiCord.git
cd CLI

# Create virtual environment (Windows)
python -m venv .venv
.venv\Scripts\activate

# Create virtual environment (Linux/macOS)
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .
pip install -r requirements-dev.txt

# Run tests
pytest tests/
```

### Cross-Platform Support

MultiCord fully supports:
- ✅ **Windows** (10, 11) - Primary development platform
- ✅ **Linux** (Ubuntu, Debian, Fedora, Arch)
- ✅ **macOS** (10.15+)

Platform-specific handling:
- Venv paths (Scripts vs bin)
- Process creation flags
- Path separators
- Command compatibility

---

## 🐛 Troubleshooting

### Bot Won't Start

**Error**: `Bot venv invalid`
**Solution**: Check venv with `multicord venv info <bot>`
**Fix**: `multicord venv clean <bot>` to recreate

### Dependency Conflicts

**Problem**: Different bots need different library versions
**Solution**: Per-bot venvs solve this! Each bot has isolated dependencies.
**Verify**: `multicord venv info <bot>` shows bot-specific packages

### Cloud Sync Fails

**Error**: API connection timeout
**Solution**: Check cache status with `multicord cache status`
**Offline Mode**: Local operations work without internet
**Fix**: `multicord cache refresh` when connection restored

### Template Not Found

**Error**: Template 'xyz' not found
**Solution**: Update repositories with `multicord repo update --all`
**Check**: `multicord template list` to see available templates
**Custom**: Add repository with `multicord repo add`

### Port Conflicts

**Problem**: Bot can't bind to port
**Solution**: MultiCord automatically assigns unique ports
**Check**: `multicord bot status` shows assigned ports
**Manual**: Edit config.toml if needed

### Common Issues

| Issue | Command | Description |
|-------|---------|-------------|
| Check system health | `multicord doctor` | Verifies Python, dependencies, API |
| View bot logs | `multicord bot logs <bot> --follow` | Real-time log streaming |
| Validate venv | `multicord venv info <bot>` | Check venv status and packages |
| Clear API cache | `multicord cache clear` | Reset offline cache |
| Update repos | `multicord repo update --all` | Sync template repositories |

### Getting Help

- **Documentation**: Full docs at https://multicord.io/docs (coming soon)
- **Issue Tracker**: https://github.com/HollowTheSilver/MultiCord/issues
- **Discussions**: https://github.com/HollowTheSilver/MultiCord/discussions

---

## 🤝 Contributing

We welcome contributions! Areas for contribution:

- **New Templates**: Share your bot templates
- **Cogs**: Create modular features for bots
- **CLI Features**: Enhance command functionality
- **Documentation**: Improve docs and examples
- **Bug Fixes**: Fix issues and edge cases
- **Tests**: Increase test coverage

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Code of Conduct**: Be respectful, inclusive, and professional.

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🔗 Links

- **GitHub**: https://github.com/HollowTheSilver/MultiCord
- **Templates**: https://github.com/HollowTheSilver/MultiCord-Templates
- **PyPI**: Coming soon - `pip install multicord`
- **API Status**: https://api.multicord.io/health
- **Issue Tracker**: https://github.com/HollowTheSilver/MultiCord/issues

---

**Made with ❤️ for the Discord bot community**

*MultiCord CLI v1.1.0 • November 2025*
