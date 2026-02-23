# MultiCord CLI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

A command-line tool for managing multiple Discord bots with process isolation, dependency management, and deployment capabilities.

---

## Overview

MultiCord simplifies running multiple Discord.py bots locally or deploying them to cloud infrastructure. Each bot runs with isolated dependencies, automatic port assignment, and comprehensive health monitoring.

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
multicord bot create my-bot --from music
multicord bot run my-bot music-bot trading-bot  # All handled automatically
multicord bot status  # Real-time monitoring with health metrics
```

---

## Key Features

### Local Bot Management

- **Per-Bot Isolated Virtual Environments**
  - Complete dependency isolation (different discord.py versions per bot)
  - Self-contained, portable bot directories
  - Shared pip cache for 60-80% disk savings

- **Advanced Process Orchestration**
  - Automatic port assignment and conflict resolution
  - Real-time health monitoring with CPU, memory, and uptime tracking
  - Graceful shutdown handling with timeout management

- **Docker Support**
  - Run bots in isolated Docker containers
  - Auto-build images from bot directories
  - Container health metrics and log streaming

- **Modular Cog System**
  - Install optional features as modular cogs
  - Enterprise-grade permissions system (9-level hierarchy)
  - Automatic cog dependency resolution with circular detection

- **Token Management**
  - Secure storage with OS keyring (or encrypted file fallback)
  - Dedicated `multicord token` command group
  - Masked token display for security

- **Source Update Ecosystem**
  - Automatic update detection with semantic versioning
  - Three update strategies (core-only, safe-merge, full-replace)
  - Intelligent config merging preserving user values
  - Compressed backups with one-command rollback

- **Built-in Sources (Zero Setup)**
  - Built-in templates and cogs auto-fetched on first use
  - No import needed for built-ins - just reference by name
  - Templates: `basic`, `advanced`
  - Cogs: `permissions`, `moderation`, `music`

- **Cloud Integration**
  - Multi-node deployment to cloud infrastructure
  - Bidirectional configuration sync with conflict resolution
  - Offline caching with transparent API fallback

---

## Quick Start

### Installation

```bash
# Install from source (PyPI coming soon)
git clone https://github.com/HollowTheSilver/MultiCord.git
cd CLI
pip install -e .
```

**Requirements**: Python 3.9+ | Windows, Linux, or macOS

### Your First Bot in 3 Commands

```bash
# 1. Create bot from a built-in source (auto-fetched, isolated venv created)
multicord bot create my-bot --from basic

# 2. Add your Discord token
multicord token set my-bot

# 3. Start the bot
multicord bot run my-bot
```

### Managing Multiple Bots

```bash
# Create multiple bots from different sources
multicord bot create trading-bot --from basic
multicord bot create mod-bot --from advanced

# Add cogs to a bot
multicord bot cog add permissions mod-bot

# Run them (auto-detect local process or Docker)
multicord bot run my-bot trading-bot mod-bot

# Monitor with real-time dashboard
multicord bot health

# View logs
multicord bot logs my-bot --follow

# Stop all bots
multicord bot stop --all
```

---

## Command Reference

MultiCord provides **43 commands** across **8 command groups** plus 1 standalone command.

### Bot Management (`multicord bot`) - 16 commands

Complete bot lifecycle management with health monitoring.

#### Create
- `multicord bot create <name> --from <source>` - Create bot from any source
  - Built-in names: `basic`, `advanced`
  - Imported repos: custom repo names
  - Git URLs: `https://github.com/user/bot`
  - Local paths: `./my-bot` or `/absolute/path`
  - Automatic: Isolated venv, dependency install, .env creation, auto-cog install
  - **Flags**: `--token` (prompt for Discord token after creation)

#### Lifecycle
- `multicord bot run <name> [name2...]` - Run bot(s)
  - **Flags**: `--docker` (force Docker), `--local` (force local process), `--shards N`, `--follow`, `--rebuild`

- `multicord bot stop <name> [name2...]` - Stop bot(s)
  - **Flags**: `--all`, `--force`

- `multicord bot restart <name> [name2...]` - Restart bot(s)

#### Monitoring
- `multicord bot list` - List all bots with status
  - **Flags**: `--local`, `--cloud`, `--sync` (merged view), `--status <running|stopped>`

- `multicord bot status <name>` - Detailed status with health metrics

- `multicord bot health` - Real-time health monitoring dashboard
  - **Flags**: `--watch` (auto-refresh)

- `multicord bot logs <name>` - View bot logs
  - **Flags**: `--follow`, `--lines <n>`, `--cloud`

#### Token & Config
- `multicord bot set-token <name>` - Set bot token inline
- `multicord bot migrate-tokens` - Migrate tokens from .env to secure storage

#### Cloud Operations
- `multicord bot deploy <name>` - Deploy bot to cloud
- `multicord bot pull <name>` - Pull cloud config to local
- `multicord bot sync <name>` - Bidirectional sync

#### Source Updates
- `multicord bot check-updates [name]` - Check for source updates
  - **Flags**: `--all` (check all bots)

- `multicord bot update <name>` - Apply source updates
  - **Flags**: `--strategy <core-only|safe-merge|full-replace>`, `--dry-run`, `--version <ver>`

- `multicord bot rollback <name>` - Rollback to previous backup
  - **Flags**: `--list`, `--backup <name>`

**Examples**:
```bash
multicord bot create my-bot --from basic
multicord bot create my-bot --from https://github.com/user/bot
multicord bot create my-bot --from ./local-bot
multicord bot run my-bot --local
multicord bot check-updates --all
multicord bot update my-bot --strategy safe-merge --dry-run
```

---

### Bot Cog Management (`multicord bot cog`) - 5 commands

Install and manage modular features (cogs) for bots.

- `multicord bot cog available` - List all available cogs
- `multicord bot cog list <bot>` - Show installed cogs for a bot
- `multicord bot cog add <cog> <bot>` - Install cog with auto dependency resolution
  - **Flags**: `--no-deps` (skip dependencies)
- `multicord bot cog remove <cog> <bot>` - Remove cog from bot
- `multicord bot cog update [cog] <bot>` - Update cog(s) to latest version

**Examples**:
```bash
multicord bot cog available
multicord bot cog add permissions my-bot
multicord bot cog list my-bot
```

---

### Source Repository Management (`multicord repo`) - 5 commands

Manage Git-based sources. Built-in sources are always available without import.

- `multicord repo list` - Show built-in + imported sources
- `multicord repo import <git-url> --as <name>` - Import Git repository as reusable source (Git URLs only)
- `multicord repo info <name>` - Show source details
- `multicord repo update <name>` - Pull latest changes (git pull)
- `multicord repo remove <name>` - Remove imported source

Note: For local directories, use `multicord bot create --from <local-path>` instead.

**Built-in sources** (always available, no import needed):
| Name | Type | Description |
|------|------|-------------|
| `basic` | Template | Simple beginner-friendly bot |
| `advanced` | Template | Production-ready with sharding |
| `permissions` | Cog | 9-level permission hierarchy |
| `moderation` | Cog | Kick, ban, timeout, warnings |
| `music` | Cog | YouTube playback, queue management |

**Examples**:
```bash
multicord repo list
multicord repo import https://github.com/someone/cool-cog --as cool
multicord bot create my-bot --from cool
```

---

### Authentication (`multicord auth`) - 3 commands

- `multicord auth login` - Login with Discord OAuth2 (auto-detects browser/device flow)
- `multicord auth logout` - Logout and clear stored tokens
- `multicord auth status` - Check authentication status with Discord user info

---

### Token Management (`multicord token`) - 4 commands

- `multicord token list [bot]` - View all stored credentials
- `multicord token set <bot>` - Store bot token securely
- `multicord token delete <bot>` - Remove stored token
- `multicord token show <bot>` - Display token details (masked)
  - **Flags**: `--unmask`

---

### Virtual Environments (`multicord venv`) - 4 commands

- `multicord venv install <bot>` - Install/reinstall dependencies
- `multicord venv clean <bot>` - Remove and recreate venv from scratch
- `multicord venv update <bot>` - Upgrade all packages to latest
- `multicord venv info [bot]` - Show venv details (Python version, packages, disk usage)
  - **Flags**: `--all`

---

### Cache Management (`multicord cache`) - 3 commands

- `multicord cache status` - Show cache statistics
- `multicord cache clear` - Clear all cached data
- `multicord cache refresh` - Refresh cache from API

---

### Configuration (`multicord config`) - 2 commands

- `multicord config show` - Show current configuration
- `multicord config set <key> <value>` - Set configuration value

---

### System Health

- `multicord doctor` - Run comprehensive system health check

---

## Architecture

### Directory Layout

```
~/.multicord/
├── repos/                 # All sources (built-ins + user-imported)
│   ├── basic/             # Built-in (auto-fetched)
│   ├── advanced/          # Built-in (auto-fetched)
│   ├── permissions/       # Built-in (auto-fetched)
│   └── my-custom/         # User-imported
├── bots/                  # Bot instances
│   ├── my-bot/
│   │   ├── .venv/        # Isolated dependencies
│   │   ├── bot.py
│   │   ├── requirements.txt
│   │   ├── config.toml
│   │   ├── cogs/
│   │   │   └── permissions/
│   │   ├── logs/
│   │   └── data/
│   └── music-bot/
│       ├── .venv/        # Different discord.py version possible
│       ├── bot.py
│       └── requirements.txt
├── pip-cache/             # Shared pip cache (60-80% disk savings)
└── config/
    └── repos.json         # Imported repository registry
```

### Two-Stage Mental Model

```
Built-in Sources (always available, zero setup)
  basic, advanced, permissions, moderation, music
                    |
     +--------------+--------------+
     |                             |
  STAGE 1: repo (optional)     STAGE 2: bot (required)
  Import third-party Git       Create and run bots
  repos for reuse/sync
```

**Key concepts**:
- **Built-ins**: No import needed, just reference by name
- **repo import**: Import Git repositories for reuse across multiple bots (versioned, updatable)
- **bot create --from**: Accepts repo names, Git URLs, or local paths
  - Repo name: `--from basic` or `--from my-repo`
  - Git URL: `--from https://github.com/user/bot`
  - Local path: `--from ./my-bot`

### Flexible Bot Structure

MultiCord automatically detects Discord.py bots with non-standard entry points:

**Supported entry points** (checked in order):
1. `bot.py` (standard)
2. `main.py` (common alternative)
3. `run.py` (another common pattern)
4. `__main__.py` (Python module pattern)

All entry points are validated for Discord.py bot code before acceptance.

### Environment Configuration

Override default ports via environment variables:

```bash
# API connection
export MULTICORD_API_URL=http://localhost:8000

# OAuth callback (Discord login)
export MULTICORD_OAUTH_PORT=8899

# Bot port range
export MULTICORD_BOT_PORT_START=8100
export MULTICORD_BOT_PORT_END=8200
```

---

## Available Sources

### Built-in Templates

- **basic** - Simple extensible bot with command handling and events
- **advanced** - Production-ready with sharding, health checks, structured logging

### Built-in Cogs

- **permissions** - Enterprise-grade 9-level permission hierarchy (~2,500 lines)
- **moderation** - Kick, ban, timeout, warnings, auto-moderation
- **music** - YouTube integration, queue management, playback controls

### Using Third-Party Sources

```bash
# Option 1: Import repository for reuse (tracked, updatable)
multicord repo import https://github.com/someone/cool-bot --as cool
multicord bot create my-bot --from cool

# Option 2: Use Git URL directly (one-time copy)
multicord bot create my-bot --from https://github.com/someone/cool-bot

# Option 3: Use local directory (in-place reference)
multicord bot create my-bot --from ./existing-bot
```

---

## Source Updates

### Checking for Updates

```bash
multicord bot check-updates my-bot
multicord bot check-updates --all
```

### Applying Updates

Three strategies available:

1. **core-only** (safest): Update only bot.py and requirements.txt
2. **safe-merge** (recommended): Core + intelligently merge configs
3. **full-replace** (aggressive): Replace all except user data

```bash
multicord bot update my-bot --strategy safe-merge
multicord bot update my-bot --dry-run  # Preview changes first
```

### Rollback

Automatic compressed backups (last 5 kept):

```bash
multicord bot rollback my-bot --list
multicord bot rollback my-bot
```

---

## Authentication

MultiCord uses Discord as the sole authentication provider with smart environment detection:

- **Desktop**: Opens Discord authorization in your browser
- **Server/SSH**: Shows device code for manual entry
- **Auto-detect**: Chooses the best method for your environment

```bash
multicord auth login     # Auto-detect (recommended)
multicord auth status    # Shows Discord user info
```

---

## Security

- **Token Storage**: OS keyring or AES-encrypted file fallback
- **Process Isolation**: Each bot runs in its own process with dedicated venv
- **API Communication**: HTTPS with JWT tokens and refresh rotation
- **Docker Isolation**: Optional container-per-bot for full isolation

---

## Development

### Setting Up

```bash
git clone https://github.com/HollowTheSilver/MultiCord.git
cd CLI

# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/macOS
python -m venv .venv
source .venv/bin/activate

pip install -e .
```

### Cross-Platform Support

- **Windows** (10, 11) - Primary development platform
- **Linux** (Ubuntu, Debian, Fedora, Arch)
- **macOS** (10.15+)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Bot won't start | `multicord venv info <bot>` then `multicord venv clean <bot>` |
| Dependency conflicts | Per-bot venvs handle this - each bot is isolated |
| Source not found | `multicord repo list` to see available sources |
| Cloud sync fails | `multicord cache status` then `multicord cache refresh` |
| Port conflicts | MultiCord auto-assigns ports; check with `multicord bot status` |
| System health check | `multicord doctor` |

---

## Contributing

We welcome contributions:

- **Templates & Cogs**: Share your creations
- **CLI Features**: Enhance commands
- **Bug Fixes**: Fix issues and edge cases
- **Tests**: Increase coverage

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Links

- **CLI Repository**: https://github.com/HollowTheSilver/MultiCord
- **Basic Template**: https://github.com/HollowTheSilver/MultiCord-BasicTemplate
- **Advanced Template**: https://github.com/HollowTheSilver/MultiCord-AdvancedTemplate
- **Permissions Cog**: https://github.com/HollowTheSilver/MultiCord-PermissionsCog
- **Moderation Cog**: https://github.com/HollowTheSilver/MultiCord-ModerationCog
- **Music Cog**: https://github.com/HollowTheSilver/MultiCord-MusicCog
- **Issue Tracker**: https://github.com/HollowTheSilver/MultiCord/issues

---

**Made with care for the Discord bot community**
