#!/usr/bin/env python3
"""
Phase 1 Migration Script
========================

Automatically applies Phase 1 enhancements to your existing platform.
Creates backups and safely integrates auto-detection and smart logging.

Usage:
    python migrate_phase1.py                    # Apply all enhancements
    python migrate_phase1.py --dry-run          # Show what would be changed
    python migrate_phase1.py --backup-only      # Only create backups
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
import argparse


class Phase1Migrator:
    """Handles Phase 1 migration with safety checks."""

    def __init__(self):
        self.project_root = Path.cwd()
        self.backup_dir = Path("backups") / f"phase1_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.changes_made = []

    def migrate(self, dry_run: bool = False, backup_only: bool = False) -> bool:
        """Perform Phase 1 migration."""
        print("🚀 Phase 1 Migration: Auto-Detection & Smart Logging")
        print("=" * 60)

        # Step 1: Create backups
        self._create_backups()

        if backup_only:
            print("✅ Backups created successfully!")
            return True

        # Step 2: Update platform configuration
        self._update_platform_config(dry_run)

        # Step 3: Enhance launcher
        self._enhance_launcher(dry_run)

        # Step 4: Enhance platform_main
        self._enhance_platform_main(dry_run)

        # Step 5: Summary
        self._print_summary(dry_run)

        return True

    def _create_backups(self) -> None:
        """Create backups of files that will be modified."""
        print("💾 Creating backups...")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        files_to_backup = [
            "bot_platform/launcher.py",
            "platform_main.py",
            "platform_config.json"
        ]

        for file_path in files_to_backup:
            src = Path(file_path)
            if src.exists():
                dst = self.backup_dir / file_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"   📄 Backed up: {file_path}")

        print(f"   💾 Backup location: {self.backup_dir}")

    def _update_platform_config(self, dry_run: bool) -> None:
        """Update platform_config.json with auto-healing settings."""
        print("\n🔧 Updating platform configuration...")

        config_file = Path("platform_config.json")

        # Default configuration
        default_config = {
            "platform": {
                "name": "Multi-Client Discord Bot Platform",
                "version": "2.0.1",
                "last_updated": datetime.now().isoformat()
            },
            "auto_healing": {
                "enabled": True,
                "sync_directory_to_database": True,
                "create_missing_directories": True,
                "fix_template_substitution": True,
                "register_orphaned_processes": True,
                "backup_before_changes": True,
                "max_auto_fixes_per_startup": 10
            },
            "logging": {
                "startup_verbosity": "INFO",
                "show_config_validation": True,
                "show_auto_healing_actions": True
            },
            "clients": []
        }

        # Load existing config if it exists
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)

                # Merge with defaults
                if "auto_healing" not in existing_config:
                    existing_config["auto_healing"] = default_config["auto_healing"]
                if "logging" not in existing_config:
                    existing_config["logging"] = default_config["logging"]

                config_to_save = existing_config
            except Exception as e:
                print(f"   ⚠️ Could not load existing config: {e}")
                config_to_save = default_config
        else:
            config_to_save = default_config

        if dry_run:
            print("   🔍 DRY RUN: Would update platform_config.json with auto-healing settings")
        else:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=2, ensure_ascii=False)
            print("   ✅ Updated platform_config.json")
            self.changes_made.append("Updated platform configuration")

    def _enhance_launcher(self, dry_run: bool) -> None:
        """Add enhanced launcher functionality."""
        print("\n🤖 Enhancing launcher with auto-detection...")

        launcher_file = Path("bot_platform/launcher.py")
        if not launcher_file.exists():
            print("   ❌ launcher.py not found!")
            return

        # Read existing launcher
        with open(launcher_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if already enhanced
        if "auto_healing_config" in content:
            print("   ℹ️ Launcher already appears to be enhanced")
            return

        if dry_run:
            print("   🔍 DRY RUN: Would enhance launcher.py with auto-detection features")
            print("       - Add auto-healing configuration")
            print("       - Add comprehensive client discovery")
            print("       - Add template substitution auto-fixing")
            print("       - Add health tracking")
            return

        # Create enhanced launcher file
        enhanced_file = Path("bot_platform/enhanced_launcher.py")

        enhanced_content = '''"""
Enhanced Platform Launcher
==========================

Auto-generated enhanced launcher with auto-detection and smart logging.
This file extends the original launcher with Phase 1 improvements.
"""

# Import the enhanced launcher implementation
from pathlib import Path
import sys

# Add the current directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the base launcher
from bot_platform.launcher import PlatformLauncher

# Enhanced launcher code will be inserted here by the migration script
# For now, create a simple enhanced version that can be manually completed

class EnhancedPlatformLauncher(PlatformLauncher):
    """Enhanced launcher - Phase 1 implementation placeholder."""

    def __init__(self, config_path: str = "platform_config.json"):
        """Initialize with enhanced features - implement based on artifacts."""
        super().__init__(config_path)
        print("🔧 Enhanced launcher initialized - complete implementation from artifacts")

        # TODO: Implement enhanced features from artifacts:
        # - _load_auto_healing_config()
        # - _comprehensive_client_discovery()
        # - _auto_heal_inconsistencies()
        # - Enhanced logging and health tracking
'''

        with open(enhanced_file, 'w', encoding='utf-8') as f:
            f.write(enhanced_content)

        print("   ✅ Created enhanced_launcher.py template")
        print("   📝 TODO: Complete implementation using provided artifacts")
        self.changes_made.append("Created enhanced launcher template")

    def _enhance_platform_main(self, dry_run: bool) -> None:
        """Enhance platform_main.py with better status display."""
        print("\n🎮 Enhancing platform_main with better status display...")

        main_file = Path("platform_main.py")
        if not main_file.exists():
            print("   ❌ platform_main.py not found!")
            return

        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if already enhanced
        if "Enhanced Multi-Client Platform Status" in content:
            print("   ℹ️ platform_main.py already appears to be enhanced")
            return

        if dry_run:
            print("   🔍 DRY RUN: Would enhance platform_main.py")
            print("       - Add enhanced status display")
            print("       - Add command-line options for auto-healing control")
            print("       - Add health information reporting")
            return

        # Add a simple marker to show enhancement is needed
        enhanced_content = content.replace(
            'print("📊 Multi-Client Platform Status")',
            '''print("📊 Enhanced Multi-Client Platform Status")
        # TODO: Implement enhanced status display from artifacts'''
        )

        # Add command-line arguments
        if "--no-auto-heal" not in content:
            # Find the argument parser section and add new arguments
            if "parser.add_argument" in content:
                enhanced_content = enhanced_content.replace(
                    'parser = argparse.ArgumentParser(',
                    '''parser = argparse.ArgumentParser('''
                )

                # Find a good place to add arguments
                if 'parser.add_argument("--interactive"' in enhanced_content:
                    enhanced_content = enhanced_content.replace(
                        'parser.add_argument("--interactive"',
                        '''parser.add_argument("--no-auto-heal", action="store_true",
                                    help="Disable auto-healing features")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    parser.add_argument("--interactive"'''
                    )

        with open(main_file, 'w', encoding='utf-8') as f:
            f.write(enhanced_content)

        print("   ✅ Enhanced platform_main.py (partial)")
        print("   📝 TODO: Complete status display enhancement from artifacts")
        self.changes_made.append("Enhanced platform_main.py")

    def _print_summary(self, dry_run: bool) -> None:
        """Print migration summary."""
        print("\n" + "=" * 60)
        print("📋 MIGRATION SUMMARY")
        print("=" * 60)

        if dry_run:
            print("🔍 DRY RUN COMPLETED - No files were modified")
            print("\nWould have made these changes:")
            print("   • Updated platform_config.json with auto-healing settings")
            print("   • Created enhanced_launcher.py template")
            print("   • Enhanced platform_main.py with better status display")
            print("   • Added command-line options for auto-healing control")
        else:
            if self.changes_made:
                print("✅ Migration completed successfully!")
                print(f"\nChanges made ({len(self.changes_made)}):")
                for change in self.changes_made:
                    print(f"   • {change}")
            else:
                print("ℹ️ No changes needed - platform already enhanced")

        print(f"\n💾 Backup location: {self.backup_dir}")

        if not dry_run:
            print("\n🎯 NEXT STEPS:")
            print("1. Complete the enhanced launcher implementation using the provided artifacts")
            print("2. Update platform_main.py status display using the provided artifacts")
            print("3. Test the enhanced platform: python platform_main.py")
            print("4. Verify auto-healing: python platform_main.py --verbose")

            print("\n📚 Implementation Guide:")
            print("   • Copy enhanced methods from 'Phase 1: Enhanced Launcher Implementation' artifact")
            print("   • Copy status display code from 'Phase 1: Step-by-Step Implementation Guide' artifact")
            print("   • Update imports to use EnhancedPlatformLauncher")


def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(description="Migrate platform to Phase 1 enhancements")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be changed without making changes")
    parser.add_argument("--backup-only", action="store_true",
                        help="Only create backups, don't make changes")

    args = parser.parse_args()

    migrator = Phase1Migrator()
    success = migrator.migrate(dry_run=args.dry_run, backup_only=args.backup_only)

    if not success:
        exit(1)


if __name__ == "__main__":
    main()
