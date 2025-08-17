#!/usr/bin/env python3
"""
Fix Platform Naming Conflict
============================

Renames platform/ directory and updates all import references to avoid
conflict with Python's built-in platform module.
"""

import os
import shutil
from pathlib import Path


def fix_naming_conflict():
    """Fix the platform directory naming conflict."""

    # Configuration
    OLD_NAME = "platform"
    NEW_NAME = "bot_platform"  # Change this if you prefer a different name

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
        shutil.copytree(OLD_NAME, backup_name)
        print(f"💾 Created backup: {backup_name}/")

    # Step 1: Check if source directory exists
    old_path = Path(OLD_NAME)
    new_path = Path(NEW_NAME)

    if not old_path.exists():
        print(f"❌ Source directory {OLD_NAME}/ not found!")
        return False

    if new_path.exists():
        print(f"❌ Target directory {NEW_NAME}/ already exists!")
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

    # Step 6: Update README and documentation
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
