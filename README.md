# MultiCord - Multi-Node Discord Management Platform

> **Enterprise-grade platform for managing multiple Discord bot clients with sophisticated business model support, complete client isolation, and professional deployment capabilities.**

[![Production Ready](https://img.shields.io/badge/Status-Foundation%20Hardening-orange)]()
[![Architecture](https://img.shields.io/badge/Architecture-Clean%20Enterprise-blue)]()
[![License](https://img.shields.io/badge/License-Proprietary-red)]()

## Overview

MultiCord is a sophisticated, production-ready platform that enables professional Discord service providers to manage multiple bot clients from a single codebase. Built with enterprise-grade clean architecture, comprehensive business model support, and complete client isolation.

**Strategic Evolution**: MultiCord has evolved into a dual-layer business architecture with an open-source CLI foundation and premium web platform for enterprise users.

### What Makes This Special

- **Clean Architecture** - ProcessManager, ConfigManager, ServiceManager separation with dependency injection
- **Business Model Ready** - Built-in Basic/Premium/Enterprise plan support with feature flags
- **Complete Client Isolation** - Separate databases, configurations, and branding per client
- **Production Operations** - Real-time monitoring, health checks, auto-restart capabilities
- **Advanced Template System** - 4 production templates with FLAGS configuration system
- **Multi-Database Support** - SQLite, Firestore, PostgreSQL with intelligent recommendations
- **Professional Management** - CLI tools, interactive management, and comprehensive debugging

## Quick Start

### Prerequisites
- Python 3.9+ 
- Discord bot tokens for your clients
- Basic understanding of Discord.py

### 1. Setup Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Your First Client
```bash
# Edit the default client configuration
cp clients/default/.env.example clients/default/.env
nano clients/default/.env  # Linux/Mac
notepad clients/default/.env  # Windows
```

**Update with your actual values:**
```env
DISCORD_TOKEN=your_actual_bot_token_here
OWNER_IDS=your_discord_user_id_here
BOT_NAME="Your Bot Name"
```

### 3. Launch Your First Client
```bash
python platform_main.py --client default
```

### 4. Create Additional Clients
```bash
# Template-based client creation with advanced features
python -m bot_platform.deployment_tools new-client --template

# Standard client creation
python -m bot_platform.deployment_tools new-client

# View all clients
python -m bot_platform.deployment_tools list-clients
```

### 5. Manage the Full Platform
```bash
# Start all enabled clients
python platform_main.py

# Interactive management console
python platform_main.py --interactive

# Platform status overview
python platform_main.py --status
```

## Platform Architecture

### Clean Architecture Components
```
bot_platform/
├── process_manager.py          # Multi-client process management with I/O redirection
├── config_manager.py           # Configuration discovery & validation
├── service_manager.py          # Business logic orchestration
├── client_manager.py           # CRUD operations with FLAGS system
├── client_runner.py            # Individual client execution with isolation
├── template_manager.py         # Multi-source template management
└── deployment_tools.py         # CLI tools with ClientOnboardingTool

core/
├── application.py              # Enhanced Discord.py bot runtime
├── utils/
│   ├── database.py             # Multi-backend DatabaseManager
│   ├── permissions.py          # Advanced permission management
│   ├── error_handler.py        # Comprehensive error handling
│   └── loguruConfig.py         # Enterprise logging system
└── cogs/                       # Modular command system

templates/
├── builtin/                    # 4 Production Templates
│   ├── blank/                  # Minimal setup
│   ├── moderation_bot/         # Auto-moderation system
│   ├── music_bot/             # Music streaming with playlists
│   └── economy_bot/           # Economy system with currency
└── community/                  # Community template framework

clients/
├── _template/                  # Sophisticated template system
├── default/                    # Production client example
└── [client_dirs]/             # Per-client complete isolation
    ├── logs/                   # Dedicated client logs
    ├── data/                   # Client-specific database
    ├── .env                    # Client configuration
    ├── branding.py             # Custom styling
    ├── features.py             # Feature flags
    └── custom_cogs/            # Client-specific commands
```

## Template System Excellence

### Production Templates (4 Complete)
- **Blank Template**: Minimal setup with SQLite database
- **Moderation Bot**: Auto-moderation with Firestore real-time features
- **Music Bot**: Music streaming with queue management and Firestore
- **Economy Bot**: Currency system with PostgreSQL for transactions

### Template-Based Development Workflow
```bash
# Production workflow - Template to Discord bot in <5 minutes
python -m bot_platform.deployment_tools new-client --template

# Flow: Template Selection → Client Info → Database Choice → FLAGS Editor → Deploy
# Result: Running Discord bot with template-specific features and customizations
```

### FLAGS Configuration System
Revolutionary hierarchical configuration system that adapts to templates:

```python
# Example FLAGS from Music Bot template
FLAGS = {
    # Core platform flags
    "base_commands": True,
    "permission_system": True,
    
    # Template-specific flags
    "music_streaming": True,
    "queue_management": True,
    "playlist_support": True,
    
    # Database configuration
    "database": {
        "backend": "firestore",
        "config": {"real_time": True}
    },
    
    # Customizable settings
    "limits": {
        "queue_limit": 50,
        "max_song_duration": 3600
    }
}
```

## Business Model Support

### Built-in Service Plans
Production-ready business model system:

| Plan | Monthly Fee | Features | Limits |
|------|-------------|----------|---------|
| **Basic** | $200 | Core commands, moderation, basic support | 10 custom commands, 5 automod rules |
| **Premium** | $350 | + Analytics, tickets, advanced features | 50 custom commands, 20 automod rules |
| **Enterprise** | $500 | + API access, priority support, custom integrations | Unlimited |

### Per-Client Customization
Complete visual and functional customization:

```python
# clients/your-client/branding.py
BRANDING = {
    "bot_name": "Custom Bot Name",
    "embed_colors": {
        "default": 0x3498db,
        "success": 0x2ecc71,
        "error": 0xe74c3c
    },
    "status_messages": [("Custom Status", "custom")],
    "footer_text": "Powered by Your Brand"
}
```

## Management & Operations

### CLI Management Commands
```bash
# Platform operations
python platform_main.py --status              # View all client status
python platform_main.py --interactive         # Interactive management
python platform_main.py --client alpha        # Run specific client

# Client management  
python -m bot_platform.deployment_tools new-client --template    # Template creation
python -m bot_platform.deployment_tools new-client              # Standard creation
python -m bot_platform.deployment_tools list-clients            # List all clients

# Development and debugging
python tools/validate_clients.py              # Validate configurations
python tools/debug_processes_v2.py --status   # Process diagnostics
```

### Interactive Management Console
```
MultiCord Interactive Platform Management
========================================
1. Show status          6. Stop all clients
2. Start client         7. Create new client
3. Stop client          8. Delete client
4. Restart client       9. View client logs
5. Start all clients    0. Exit console
```

### Production Monitoring Features
- **Dedicated Logging** - Each client has separate log files with UTF-8 support
- **Real-time Process Tracking** - Memory usage, CPU monitoring, uptime stats
- **Health Checks** - Automatic detection of crashed or unresponsive clients
- **Auto-restart** - Configurable restart policies with exponential backoff
- **Log Management** - Automatic rotation with configurable retention

## Multi-Database Architecture

### Current Database Support
- **SQLite**: Production-ready, perfect for development and small deployments
- **Firestore**: Architecture-ready, optimal for real-time features (music/moderation)
- **PostgreSQL**: Architecture-ready, ideal for transaction-heavy applications (economy)
- **Redis**: Planned for caching layer and high-performance scenarios

### Template-Database Intelligence
```python
# Intelligent database recommendations per template
Music Bot Template → Firestore (real-time queue updates)
Economy Bot Template → PostgreSQL (transaction integrity)
Moderation Bot Template → Firestore (real-time moderation events)
Blank Template → SQLite (zero-config development)
```

## Production Deployment

### System Requirements
- **Recommended**: 2GB RAM, 2 CPU cores per 5-10 clients
- **Storage**: 500MB per client (logs, database, configuration)
- **Network**: Stable internet connection for Discord API

### Production Features
- **Complete Client Isolation** - Separate processes, databases, configurations
- **Enterprise Logging** - Dedicated log files per client with proper encoding
- **Health Monitoring** - Built-in process health checks and restart capabilities
- **Security** - Input validation, template sandboxing, multi-tenant preparation
- **Scalability** - Clean architecture ready for multi-node deployment

### Current Status
- **Phase 2 Complete**: Template ecosystem with FLAGS system and multi-database support
- **Foundation Hardening**: Recent critical bug fixes for production stability
- **Architecture Status**: Clean enterprise architecture with dependency injection

## Development & Contribution

### Getting Started
```bash
# Clone and setup development environment
git clone <repository-url>
cd multicord
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Code Standards
- Clean architecture principles with separation of concerns
- Root cause solutions over patches or workarounds
- Comprehensive error handling with graceful degradation

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## Troubleshooting

### Common Issues

**Client Won't Start**
```bash
# Check client configuration and logs
python platform_main.py --status

# View specific client logs
python platform_main.py --interactive  # Option 9: View client logs

# Validate client configuration
python tools/validate_clients.py --fix
```

**Process Issues**
```bash
# Advanced process debugging
python tools/debug_processes_v2.py --status

# Clean up problematic processes
python tools/debug_processes_v2.py --cleanup
```

**Unicode/Encoding Issues (Windows)**
Fixed in current version with proper UTF-8 encoding and error handling.

## Future Roadmap

### Immediate Priorities (Next 4-6 weeks)
1. **Performance Optimization** - Sub-5-second client startup, memory optimization
2. **Security Hardening** - Input validation, template sandboxing
3. **Database Excellence** - Redis caching integration, connection pooling
4. **Community Preparation** - Professional documentation, 15+ templates

### Strategic Vision
**Layer 1**: Open Source MultiCord CLI (Free)
**Layer 2**: Premium MultiCord.io Web Platform (Subscription SaaS)

Target: "Multi-Node Discord Management at Scale" - enterprise-grade Discord service management.

## License & Support

This platform is proprietary software designed for professional Discord service providers. 

### Current Status
- **Production Ready**: Core platform stable with recent critical bug fixes
- **Enterprise Architecture**: Clean, scalable codebase suitable for business applications
- **Foundation Hardening**: Ongoing optimization and security improvements

---

**Ready for Business**: MultiCord is production-ready and designed to support professional Discord service businesses from day one.

**Get started today**: `python platform_main.py --client default`