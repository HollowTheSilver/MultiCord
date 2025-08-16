# Contributing to Multi-Client Discord Bot Platform

Thank you for your interest in contributing to this project! This document provides guidelines and information for contributors.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Process](#pull-request-process)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Issue Reporting](#issue-reporting)
- [Multi-Client Platform Guidelines](#multi-client-platform-guidelines)

## 🤝 Code of Conduct

This project follows a professional code of conduct. Please be respectful, inclusive, and constructive in all interactions.

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Git
- Discord bot token for testing
- Basic understanding of Discord.py and async Python

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/discord-bot-platform.git
   cd discord-bot-platform
   ```

2. **Set up development environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure test environment**
   ```bash
   cp clients/default/.env.example clients/default/.env
   # Edit clients/default/.env with your test bot token
   ```

4. **Run initial tests**
   ```bash
   python platform_main.py --client default
   ```

## 🔄 Development Workflow

### Branch Naming

Use descriptive branch names with prefixes:
- `feature/add-new-client-branding`
- `fix/env-template-missing-variables`
- `docs/update-deployment-guide`
- `refactor/simplify-client-manager`
- `update/dependencies`

### Development Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow code standards
   - Add tests for new functionality
   - Update documentation as needed

3. **Test thoroughly**
   ```bash
   # Test single client
   python platform_main.py --client default
   
   # Test platform management
   python platform_main.py --status
   python platform_main.py --interactive
   
   # Test client creation
   python -m platform.deployment_tools new-client
   ```

4. **Commit with clear format**
   ```bash
   git add .
   git commit -m "implement: add advanced client branding system"
   ```

5. **Push and create pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

## 📝 Commit Message Guidelines

We use a clear and descriptive commit message format:

### Format
```
<type>: <description>

[optional body]

[optional footer(s)]
```

### Types (lowercase)
- **fix**: Bug fixes, error corrections, patches
- **implement**: New features, functionality, or components
- **enhance**: Improvements to existing features or performance
- **refactor**: Code restructuring without changing functionality
- **remove**: Deletion of features, dependencies, or code
- **update**: Dependencies, documentation, or configuration changes
- **add**: New files, assets, or simple additions
- **change**: Modifications that don't fit other categories

### Examples

```bash
# Good commits
implement: add health monitoring for client processes
fix: resolve branding color inheritance issue
update: add deployment guide for production
refactor: simplify permission checking logic
update: discord.py to v2.3.0
enhance: improve client startup performance
add: comprehensive .env template system
remove: deprecated legacy configuration options

# Bad commits (avoid these)
Fix bug in client manager
Added new feature
Update stuff
WIP
```

### Commit Message Details

- **Subject line**: 72 characters or less, lowercase, no period
- **Body**: Wrap at 72 characters, explain what and why vs. how
- **Footer**: Reference issues and breaking changes

Example with body:
```
implement: add automatic client restart on failure

Implements health monitoring that detects when client processes
crash or become unresponsive. Automatically restarts failed
clients up to a configurable limit with exponential backoff.

Closes #123
```

## 🔍 Pull Request Process

### Before Submitting

- [ ] Branch is up to date with main
- [ ] All tests pass
- [ ] Code follows style guidelines
- [ ] Documentation is updated
- [ ] Commit messages follow project format

### Pull Request Template

```markdown
## Description
Brief description of changes and why they're needed.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Tested single client startup
- [ ] Tested multi-client platform
- [ ] Tested client creation/management
- [ ] All existing tests pass

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Breaking changes documented
```

## 🎨 Code Standards

### Python Style
- Follow PEP 8
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use docstrings for all public functions and classes

### Example Function
```python
async def create_client_embed(
    bot: Application,
    title: str = "Information",
    description: Optional[str] = None,
    user: Optional[Union[discord.User, discord.Member]] = None
) -> discord.Embed:
    """
    Create a client-branded embed with consistent styling.
    
    Args:
        bot: Bot application instance with client branding
        title: Embed title
        description: Optional embed description
        user: User to include in footer
        
    Returns:
        Configured Discord embed with client branding
    """
    # Implementation here
```

### File Organization
- Group imports: standard library, third-party, local
- Use absolute imports for clarity
- Organize code into logical sections with comments

### Error Handling
- Use specific exception types
- Provide helpful error messages
- Log errors with context
- Fail gracefully where possible

## 🧪 Testing

### Test Requirements
- Test new features thoroughly
- Ensure existing functionality isn't broken
- Test both single-client and multi-client scenarios
- Test error conditions and edge cases

### Manual Testing Checklist
```bash
# Platform functionality
python platform_main.py --status
python platform_main.py --interactive
python platform_main.py --client default

# Client management
python -m platform.deployment_tools new-client
python -m platform.deployment_tools list-clients

# Core bot functionality
# Test commands in Discord
# Verify permission system
# Check logging and error handling
```

### Automated Testing
- Write unit tests for utility functions
- Test configuration loading and validation
- Verify client isolation

## 📚 Documentation

### Documentation Standards
- Update README.md for significant changes
- Document new configuration options
- Include examples for complex features
- Keep docstrings current

### Documentation Types
- **Code comments**: Explain complex logic
- **Docstrings**: Public API documentation
- **README**: Setup and usage instructions
- **Guides**: Step-by-step tutorials

## 🐛 Issue Reporting

### Bug Reports
Include:
- Python version and OS
- Discord.py version
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs/screenshots
- Configuration details (sanitized)

### Feature Requests
Include:
- Clear description of the feature
- Use case and benefits
- Possible implementation approach
- Impact on existing functionality

### Issue Labels
- `bug`: Something isn't working
- `enhancement`: New feature or request
- `documentation`: Documentation improvements
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention needed
- `platform`: Platform-specific issues
- `client`: Client-specific issues
- `core`: Core bot functionality
- `config`: Configuration related

## 🏗️ Multi-Client Platform Guidelines

### Platform-Specific Considerations

1. **Client Isolation**
   - Ensure complete data isolation between clients
   - Test configuration independence
   - Verify process separation

2. **Backward Compatibility**
   - Don't break existing client configurations
   - Provide migration paths for changes
   - Test with multiple client types

3. **Resource Management**
   - Monitor memory usage across clients
   - Test restart and recovery scenarios
   - Verify health monitoring

4. **Configuration Management**
   - Test template generation
   - Verify variable substitution
   - Check plan-based feature flags

### Testing Multi-Client Features

```bash
# Create test clients
python -m platform.deployment_tools new-client
# Configure with different plans/features

# Test concurrent operation
python platform_main.py
# Verify multiple clients run simultaneously

# Test management operations
python platform_main.py --interactive
# Test start/stop/restart operations
```

## 🤝 Getting Help

- **Discord**: Join our development Discord server
- **Discussions**: Use GitHub Discussions for questions
- **Issues**: Create an issue for bugs and feature requests
- **Email**: Contact maintainers for security issues

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to making this platform better! 🚀