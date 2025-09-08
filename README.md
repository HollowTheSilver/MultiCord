# MultiCord CLI

## Run Multiple Discord Bots with Ease

MultiCord makes it simple to manage multiple Discord bots on your local machine with automatic resource isolation, unified monitoring, and seamless cloud integration.

## ✨ Features

### Local Bot Management (Free Forever)
- **Run Multiple Bots**: Start unlimited Discord bots simultaneously
- **Automatic Isolation**: Each bot runs in its own process with dedicated resources
- **Port Management**: Automatic port assignment prevents conflicts
- **Unified Monitoring**: See all your bots' status in one place
- **Template System**: Quick bot creation from templates
- **Resource Tracking**: Monitor CPU and memory per bot
- **Graceful Shutdown**: Stop individual bots or all at once

### Cloud Integration (Premium)
- **Multi-Node Deployment**: Deploy bots across multiple servers
- **Advanced Analytics**: Detailed metrics and insights
- **Template Marketplace**: Access community templates
- **Enterprise Management**: Manage bots for multiple clients
- **Auto-Scaling**: Scale bots based on demand
- **High Availability**: Automatic failover and recovery

## 🚀 Quick Start

### Installation

```bash
# Install from PyPI
pip install multicord

# Or install from source
git clone https://github.com/HollowTheSilver/MultiCord.git
cd CLI
pip install -e .
```

### Basic Usage

```bash
# Create a new bot from template
multicord bot create my-music-bot --template music

# Configure your bot
cd ~/.multicord/bots/my-music-bot
# Edit config.toml with your Discord token

# Start the bot
multicord bot start my-music-bot

# Start multiple bots
multicord bot start trading-bot music-bot moderation-bot

# Check status of all bots
multicord bot list

# View bot logs
multicord bot logs my-music-bot

# Stop a bot
multicord bot stop my-music-bot

# Stop all bots
multicord bot stop --all
```

### Templates

```bash
# List available templates
multicord template list

# Install a template from URL
multicord template install https://github.com/user/discord-bot-template

# Create bot from custom template
multicord bot create my-bot --template custom-template
```

### Cloud Features (Optional)

```bash
# Login to MultiCord cloud
multicord auth login

# List both local and cloud bots
multicord bot list --sync

# Deploy bot to cloud
multicord bot deploy my-bot --node us-east-1

# Stream logs from cloud bot
multicord bot logs my-bot --cloud --follow
```

## 📁 Project Structure

```
~/.multicord/
├── bots/
│   ├── bot1/
│   │   ├── bot.py
│   │   ├── config.toml
│   │   └── logs/
│   └── bot2/
│       ├── bot.py
│       ├── config.toml
│       └── logs/
├── templates/
│   ├── basic/
│   ├── music/
│   └── moderation/
└── config.toml
```

## 🔧 Configuration

### Global Configuration
`~/.multicord/config.toml`
```toml
[general]
default_template = "basic"
log_level = "INFO"
max_bots = 10

[api]
url = "https://api.multicord.io"
timeout = 30
```

### Bot Configuration
`~/.multicord/bots/{bot-name}/config.toml`
```toml
[bot]
token = "YOUR_DISCORD_BOT_TOKEN"
prefix = "!"
description = "My awesome bot"

[resources]
max_memory_mb = 512
cpu_priority = "normal"

[logging]
level = "INFO"
file = "bot.log"
max_size_mb = 100
```

## 📋 Command Reference

### Authentication Commands
- `multicord auth login` - Login to cloud services
- `multicord auth logout` - Logout from cloud
- `multicord auth status` - Check authentication status

### Bot Management Commands
- `multicord bot create <name>` - Create new bot
- `multicord bot list` - List all bots
- `multicord bot start <name>` - Start bot(s)
- `multicord bot stop <name>` - Stop bot(s)
- `multicord bot restart <name>` - Restart bot(s)
- `multicord bot delete <name>` - Delete bot
- `multicord bot status <name>` - Detailed bot status
- `multicord bot logs <name>` - View bot logs

### Template Commands
- `multicord template list` - List templates
- `multicord template install <url>` - Install template
- `multicord template create <name>` - Create template
- `multicord template delete <name>` - Delete template

### System Commands
- `multicord config show` - Show configuration
- `multicord config set <key> <value>` - Set config value
- `multicord doctor` - Check system health
- `multicord version` - Show version

## 🧩 Templates

Templates provide pre-configured bot structures:

### Available Templates
- **basic** - Simple command bot
- **music** - Music streaming bot
- **moderation** - Server moderation bot
- **economy** - Economy system bot
- **tickets** - Support ticket bot

### Creating Custom Templates

1. Create your bot structure
2. Add template metadata
3. Install locally or share via URL

```bash
multicord template create my-template --from-bot my-bot
multicord template install https://github.com/user/my-template
```

## 🔒 Security

- **Token Storage**: Secure storage using system keyring
- **Process Isolation**: Each bot runs in isolated environment
- **Resource Limits**: Configurable CPU and memory limits
- **Audit Logging**: Track all bot operations
- **No Token Exposure**: Tokens never shown in logs or CLI output

## 🧪 Development

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/HollowTheSilver/MultiCord.git
cd CLI

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .
pip install -r requirements-dev.txt

# Run tests
pytest tests/
```

### Running Tests

```bash
# Unit tests
pytest tests/unit

# Integration tests
pytest tests/integration

# With coverage
pytest --cov=multicord --cov-report=html
```

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Areas for Contribution
- New bot templates
- Additional CLI commands
- Documentation improvements
- Bug fixes
- Test coverage

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Links

- **GitHub**: [https://github.com/HollowTheSilver/MultiCord](https://github.com/HollowTheSilver/MultiCord)
- **PyPI**: Coming soon

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/HollowTheSilver/MultiCord/issues)

---

**Made with ❤️ by the MultiCord Team**