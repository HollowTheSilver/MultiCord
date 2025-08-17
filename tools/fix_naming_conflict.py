#!/usr/bin/env python3
"""
Fix Platform Naming Conflict
============================

Renames platform/ directory and updates all import references to avoid
conflict with Python's built-in platform module. Also migrates any
platform runtime files created during testing.
"""

import os
import shutil
from pathlib import Path


def migrate_platform_runtime_files():
    """Migrate platform runtime and data files to new location."""
    print("🔄 Migrating platform runtime files...")

    # Files and directories to migrate from old platform/ to bot_platform/
    migrations = [
        ("platform/runtime/", "bot_platform/runtime/"),
        ("platform/clients.json", "bot_platform/clients.json"),
        ("platform/logs/", "bot_platform/logs/"),
    ]

    migrated_count = 0
    for old_path, new_path in migrations:
        old_file = Path(old_path)
        if old_file.exists():
            new_file = Path(new_path)
            new_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                if old_file.is_dir():
                    shutil.copytree(old_file, new_file, dirs_exist_ok=True)
                    shutil.rmtree(old_file)
                    print(f"   Moved directory: {old_path} → {new_path}")
                else:
                    shutil.move(str(old_file), str(new_file))
                    print(f"   Moved file: {old_path} → {new_path}")
                migrated_count += 1
            except Exception as e:
                print(f"   ⚠️ Could not migrate {old_path}: {e}")

    if migrated_count == 0:
        print("   No runtime files found to migrate")
    else:
        print(f"   Migrated {migrated_count} platform runtime items")


def fix_naming_conflict():
    """Fix the platform directory naming conflict."""

    # Configuration
    OLD_NAME = "platform"
    NEW_NAME = "bot_platform"

    print(f"🔧 Fixing naming conflict: {OLD_NAME}/ → {NEW_NAME}/")

    # Create backup first
    backup_name = f"{OLD_NAME}_backup"
    if Path(backup_name).exists():
        print(f"⚠️  Backup directory {backup_name}/ already exists!")
        response = input("Continue anyway? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Operation cancelled")
            return False
    else:
        if Path(OLD_NAME).exists():
            shutil.copytree(OLD_NAME, backup_name)
            print(f"💾 Created backup: {backup_name}/")

    # Step 1: Check if source directory exists
    old_path = Path(OLD_NAME)
    new_path = Path(NEW_NAME)

    if not old_path.exists():
        print(f"❌ Source directory {OLD_NAME}/ not found!")
        # Still try to migrate runtime files if they exist
        migrate_platform_runtime_files()
        return False

    if new_path.exists():
        print(f"❌ Target directory {NEW_NAME}/ already exists!")
        # Still try to migrate runtime files if they exist
        migrate_platform_runtime_files()
        return False

    # Step 2: Define what will be changed
    files_to_update = [
        "platform_main.py",
        f"{NEW_NAME}/__init__.py",
        f"{NEW_NAME}/launcher.py",
        f"{NEW_NAME}/client_runner.py",
        f"{NEW_NAME}/client_manager.py",
        f"{NEW_NAME}/deployment_tools.py"
    ]

    import_replacements = [
        (f"from {OLD_NAME}.", f"from {NEW_NAME}."),
        (f"import {OLD_NAME}.", f"import {NEW_NAME}."),
        (f'"-m", "{OLD_NAME}.', f'"-m", "{NEW_NAME}.'),
        (f"python -m {OLD_NAME}.", f"python -m {NEW_NAME}."),
    ]

    # Step 3: Preview what will be changed
    print(f"\n📋 Will update these files:")
    for file_path in files_to_update:
        if Path(file_path).exists():
            print(f"   ✓ {file_path}")
        else:
            print(f"   ⚪ {file_path} (not found, skipping)")

    print(f"\n🔍 Will make these replacements:")
    for old, new in import_replacements:
        print(f"   '{old}' → '{new}'")

    response = input(f"\nProceed with changes? (y/N): ").strip().lower()
    if response != 'y':
        print("❌ Operation cancelled")
        # Clean up backup if it exists
        if Path(backup_name).exists():
            shutil.rmtree(backup_name)
        return False

    # Step 4: Rename the directory
    shutil.move(str(old_path), str(new_path))
    print(f"✅ Renamed {OLD_NAME}/ → {NEW_NAME}/")

    # Update the files_to_update list now that directory is renamed
    files_to_update = [
        "platform_main.py",
        f"{NEW_NAME}/__init__.py",
        f"{NEW_NAME}/launcher.py",
        f"{NEW_NAME}/client_runner.py",
        f"{NEW_NAME}/client_manager.py",
        f"{NEW_NAME}/deployment_tools.py"
    ]

    # Step 5: Update import statements in files
    updated_files = []

    for file_path in files_to_update:
        if Path(file_path).exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                original_content = content

                # Apply replacements
                for old_import, new_import in import_replacements:
                    content = content.replace(old_import, new_import)

                # Write back if changed
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    updated_files.append(file_path)

            except Exception as e:
                print(f"⚠️  Error updating {file_path}: {e}")

    if updated_files:
        print(f"✅ Updated imports in: {', '.join(updated_files)}")
    else:
        print("ℹ️  No import statements needed updating")

    # Step 6: Migrate runtime files that may have been created during testing
    migrate_platform_runtime_files()

    # Step 7: Update README and documentation
    readme_files = ["README.md", "CONTRIBUTING.md"]

    for readme_file in readme_files:
        if Path(readme_file).exists():
            try:
                with open(readme_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                original_content = content

                # Update command examples in documentation
                for old_import, new_import in import_replacements:
                    content = content.replace(old_import, new_import)

                if content != original_content:
                    with open(readme_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"✅ Updated documentation in {readme_file}")

            except Exception as e:
                print(f"⚠️  Error updating {readme_file}: {e}")

    print(f"\n🎉 Naming conflict fixed!")
    print(f"💾 Backup available at: {backup_name}/")
    print(f"📋 Updated commands:")
    print(f"   python platform_main.py --client default")
    print(f"   python -m {NEW_NAME}.deployment_tools new-client")
    print(f"   python -m {NEW_NAME}.deployment_tools list-clients")
    print(f"\n🗂️  To restore backup if needed: rm -rf {NEW_NAME}/ && mv {backup_name}/ {OLD_NAME}/")

    return True


if __name__ == "__main__":
    fix_naming_conflict()
