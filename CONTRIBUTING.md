# Contributing Guidelines

## Git Commit Standards

### Commit Message Format
```
<Type>: <Summary>

<Optional detailed description>
- Bullet points for specific changes
- Technical details and context
- Breaking changes or migration notes
```

### Commit Types
- **Fix:** Bug fixes, error corrections, patches
- **Implement:** New features, functionality, or components  
- **Enhance:** Improvements to existing features or performance
- **Refactor:** Code restructuring without changing functionality
- **Remove:** Deletion of features, dependencies, or code
- **Update:** Dependencies, documentation, or configuration changes
- **Add:** New files, assets, or simple additions
- **Change:** Modifications that don't fit other categories

### Examples
```
Fix: Unicode normalization breaking age pattern matching

- Fixed regex patterns to preserve + and - characters
- Updated demographic role detection for 40+, 30-39 patterns
- Resolved word boundary issues with special characters
```

```
Implement: Enhanced permission system with role classification

- Added RoleType enum with AUTHORITY, BOT, COSMETIC, etc.
- Implemented intelligent role classifier with confidence scoring
- Added Unicode text normalization for fancy Discord role names
- Created management commands for setup and debugging
```

```
Enhance: Role classification system with permissions-first logic

- Removed REACTION role type to simplify classification
- Implemented permissions-first classification logic over name patterns
- Fixed member role detection for authority roles with channel overrides
```

### Guidelines
- Keep summary under 72 characters
- Use present tense ("Fix" not "Fixed")
- Be specific about what changed
- Include context for complex changes
- Group related changes in single commits when logical

## Code Standards
- Use type hints for all functions
- Include docstrings for public methods
- Follow existing naming conventions
- Add logging for important operations
- Handle errors gracefully with user-friendly messages