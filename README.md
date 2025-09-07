# MultiCord Platform
**Professional Discord Bot Infrastructure**

MultiCord is a production-ready platform for managing Discord bots with enterprise-grade features. Run any Discord.py bot with zero modifications while optionally adding professional monitoring, logging, and management capabilities.

## ✨ Key Features

- **Zero Learning Curve**: Run existing Discord.py bots without any code changes
- **Professional Management**: Start, stop, monitor, and scale bots from a single CLI
- **PostgreSQL Integration**: Enterprise-grade data persistence and multi-server coordination
- **Template System**: Optional convenience templates for common bot patterns
- **Production Ready**: Health monitoring, structured logging, and process management

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Discord bot token
- MultiCord account *(Coming Soon - Phase 4)*

**Optional for self-hosting:**
- Docker Desktop (for local PostgreSQL)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/MultiCord.git
   cd MultiCord
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Authenticate with MultiCord** *(Coming Soon - Phase 4)*
   ```bash
   # Connect to our hosted backend (no setup required)
   multicord auth login
   # Opens browser to authenticate with your MultiCord account
   ```

4. **Start your first bot**
   ```bash
   # Run any existing Discord.py bot (connects to our SaaS backend)
   python -m platform_cli start my_bot --token YOUR_DISCORD_TOKEN

   # Or use a template for convenience features
   python -m platform_cli start my_bot --strategy template --template basic_business_bot --token YOUR_DISCORD_TOKEN
   ```

## 🏠 Self-Hosting (Advanced)

For enterprise deployments or privacy requirements, you can run your own PostgreSQL backend:

<details>
<summary>Click to expand self-hosting instructions</summary>

### PostgreSQL Setup
```bash
# Start PostgreSQL container
docker run --name multicord-postgres \
  -e POSTGRES_PASSWORD=multicord_secure_pass \
  -e POSTGRES_DB=multicord_platform \
  -e POSTGRES_USER=multicord_user \
  -p 5432:5432 \
  -d postgres:15

# Run database migrations
docker exec multicord-postgres psql -U multicord_user -d multicord_platform -f migrations/001_initial_platform_schema.sql
docker exec multicord-postgres psql -U multicord_user -d multicord_platform -f migrations/002_api_security_infrastructure.sql
```

### Configure Self-Hosted Mode
```bash
# Point CLI to your local database
python -m platform_cli start my_bot --backend self-hosted --db-host localhost --token YOUR_DISCORD_TOKEN
```

**Note**: Self-hosted deployments require manual setup and don't include web dashboard access. For web dashboard integration, use our hosted SaaS backend.

</details>

## 📋 Common Commands

```bash
# List running bots
python -m platform_cli list

# Check bot status
python -m platform_cli status my_bot

# Stop a bot
python -m platform_cli stop my_bot

# View available templates
python -m platform_cli templates

# Platform information
python -m platform_cli info
```

## 🎯 Use Cases

### Individual Developers
- **Zero Setup**: Run your Discord.py bots immediately without changes
- **Professional Monitoring**: Get insights into bot performance and health
- **Easy Management**: Start/stop multiple bots from one interface

### Small Teams
- **Centralized Management**: Coordinate multiple bots from a single platform
- **Template Sharing**: Share common bot patterns across team members
- **PostgreSQL Backend**: Reliable data persistence and coordination

### Enterprise Operations
- **Multi-Server Support**: Coordinate bots across multiple server nodes
- **Audit Logging**: Comprehensive activity tracking for compliance
- **API Integration**: REST endpoints for web dashboard integration

## 🛠️ Bot Execution Strategies

MultiCord supports multiple approaches as equal first-class citizens:

### Standard Strategy (Default)
Perfect for existing Discord.py projects:
```bash
python -m platform_cli start my_bot --token TOKEN
```
- No code modifications required
- Full Discord.py compatibility
- Professional process management

### Template Strategy
Convenience features for common patterns:
```bash
python -m platform_cli start my_bot --strategy template --template basic_business_bot --token TOKEN
```
- Pre-built professional bot templates
- Built-in monitoring and error handling
- Customizable through environment variables

## 📁 Directory Structure

```
MultiCord/
├── platform_cli/           # Command-line interface
├── platform_core/          # Core infrastructure
├── templates/               # Bot templates
├── migrations/              # Database schema
├── tests/                   # Test suite
└── tools/                   # Development utilities
```

## 🔧 Development

### Running Tests
```bash
# All tests
python -m pytest tests/

# Specific test categories
python -m pytest tests/unit/
python -m pytest tests/integration/
```

### Database Management
```bash
# Reset development database
python tools/setup_postgres_test.py

# Health check
python tools/quick_test.py
```

## 📚 Documentation

- **CLAUDE.md** - Architecture principles and development standards
- **PROJECT_STRUCTURE.md** - Detailed project organization
- **TODO.md** - Active development roadmap and tasks

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Read `CLAUDE.md` for coding standards and architecture principles
4. Run tests to ensure everything works
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Issues**: Report bugs or request features via GitHub Issues
- **Documentation**: Check our comprehensive documentation files
- **Discord**: Join our Discord server for community support

---

**MultiCord Platform** - Professional Discord bot infrastructure that grows with your needs, from individual projects to enterprise deployments.