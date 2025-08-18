#!/usr/bin/env python3
"""
Client Configuration Validator & Fixer
======================================

Scans all client configurations for template substitution issues and other problems.
Provides fixes for common configuration inconsistencies.

Usage:
    python validate_clients.py                # Check all clients
    python validate_clients.py --fix          # Fix issues automatically
    python validate_clients.py --client default  # Check specific client
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any
import argparse


class ClientValidator:
    """Validates and fixes client configuration issues."""

    def __init__(self):
        self.clients_dir = Path("clients")
        self.issues = []
        self.fixes_applied = []

    def validate_all_clients(self, fix_issues: bool = False) -> bool:
        """Validate all client configurations."""
        print("🔍 Scanning client configurations...")
        print("=" * 50)

        if not self.clients_dir.exists():
            print("❌ No clients directory found")
            return False

        # Find all client directories
        client_dirs = [d for d in self.clients_dir.iterdir()
                       if d.is_dir() and not d.name.startswith("_")]

        if not client_dirs:
            print("❌ No client directories found")
            return False

        all_valid = True
        for client_dir in client_dirs:
            print(f"\n📁 Validating client: {client_dir.name}")
            if not self._validate_client(client_dir, fix_issues):
                all_valid = False

        self._print_summary()
        return all_valid

    def validate_client(self, client_id: str, fix_issues: bool = False) -> bool:
        """Validate a specific client configuration."""
        client_dir = self.clients_dir / client_id
        if not client_dir.exists():
            print(f"❌ Client directory not found: {client_dir}")
            return False

        print(f"🔍 Validating client: {client_id}")
        print("=" * 50)

        result = self._validate_client(client_dir, fix_issues)
        self._print_summary()
        return result

    def _validate_client(self, client_dir: Path, fix_issues: bool = False) -> bool:
        """Validate a single client's configuration."""
        client_id = client_dir.name
        all_valid = True

        # Check .env file
        env_valid = self._validate_env_file(client_dir, fix_issues)
        if not env_valid:
            all_valid = False

        # Check branding.py file
        branding_valid = self._validate_branding_file(client_dir, fix_issues)
        if not branding_valid:
            all_valid = False

        # Check required directories
        dirs_valid = self._validate_directories(client_dir, fix_issues)
        if not dirs_valid:
            all_valid = False

        return all_valid

    def _validate_env_file(self, client_dir: Path, fix_issues: bool = False) -> bool:
        """Validate .env file for template substitution issues."""
        env_file = client_dir / ".env"
        client_id = client_dir.name

        if not env_file.exists():
            issue = f"Missing .env file in {client_id}"
            self.issues.append(issue)
            print(f"   ❌ {issue}")
            return False

        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                content = f.read()

            issues_found = []
            fixes_needed = {}

            # Check for unsubstituted template variables
            template_vars = re.findall(r'\{([^}]+)\}', content)
            if template_vars:
                issue = f"Unsubstituted template variables in {client_id}: {template_vars}"
                issues_found.append(issue)
                print(f"   ❌ {issue}")

                if fix_issues:
                    # Apply common fixes
                    fixes_needed = self._generate_env_fixes(client_id, template_vars)

            # Check for required variables
            required_vars = ['CLIENT_ID', 'CLIENT_PATH', 'DISCORD_TOKEN', 'BOT_NAME']
            missing_vars = []

            for var in required_vars:
                pattern = f'^{var}='
                if not re.search(pattern, content, re.MULTILINE):
                    missing_vars.append(var)

            if missing_vars:
                issue = f"Missing required variables in {client_id}: {missing_vars}"
                issues_found.append(issue)
                print(f"   ❌ {issue}")

            # Check CLIENT_ID and CLIENT_PATH specifically
            client_id_match = re.search(r'^CLIENT_ID=(.*)$', content, re.MULTILINE)
            if client_id_match:
                client_id_value = client_id_match.group(1).strip('"\'')
                if client_id_value != client_id and '{' in client_id_value:
                    fixes_needed['CLIENT_ID'] = f'"{client_id}"'

            client_path_match = re.search(r'^CLIENT_PATH=(.*)$', content, re.MULTILINE)
            if client_path_match:
                client_path_value = client_path_match.group(1).strip('"\'')
                expected_path = f"clients/{client_id}"
                if client_path_value != expected_path:
                    fixes_needed['CLIENT_PATH'] = f'"{expected_path}"'

            # Apply fixes if requested
            if fix_issues and fixes_needed:
                self._apply_env_fixes(env_file, fixes_needed)
                self.fixes_applied.extend([f"Fixed {var} in {client_id}" for var in fixes_needed.keys()])

            if issues_found and not fix_issues:
                self.issues.extend(issues_found)
                return False

            if not issues_found:
                print(f"   ✅ .env file valid")

            return True

        except Exception as e:
            issue = f"Error reading .env file in {client_id}: {e}"
            self.issues.append(issue)
            print(f"   ❌ {issue}")
            return False

    def _generate_env_fixes(self, client_id: str, template_vars: List[str]) -> Dict[str, str]:
        """Generate fixes for common template variable issues."""
        fixes = {}

        for var in template_vars:
            if var == 'CLIENT_ID':
                fixes['CLIENT_ID'] = f'"{client_id}"'
            elif var == 'CLIENT_PATH':
                fixes['CLIENT_PATH'] = f'"clients/{client_id}"'
            elif var == 'CLIENT_NAME':
                # This appears in comments, fix the header
                fixes['CLIENT_NAME_COMMENT'] = client_id

        return fixes

    def _apply_env_fixes(self, env_file: Path, fixes: Dict[str, str]) -> None:
        """Apply fixes to .env file."""
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()

        for var, value in fixes.items():
            if var == 'CLIENT_NAME_COMMENT':
                # Fix the header comment
                content = re.sub(
                    r'# Generated for client: \{CLIENT_NAME\}',
                    f'# Generated for client: {value}',
                    content
                )
            else:
                # Fix environment variable
                pattern = f'^{var}=.*$'
                replacement = f'{var}={value}'
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"   🔧 Applied fixes to {env_file.name}")

    def _validate_branding_file(self, client_dir: Path, fix_issues: bool = False) -> bool:
        """Validate branding.py file."""
        branding_file = client_dir / "branding.py"
        client_id = client_dir.name

        if not branding_file.exists():
            issue = f"Missing branding.py file in {client_id}"
            print(f"   ⚠️ {issue} (optional but recommended)")

            if fix_issues:
                self._create_default_branding(branding_file, client_id)
                self.fixes_applied.append(f"Created branding.py for {client_id}")
            return True  # Not critical

        try:
            with open(branding_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for BRANDING dictionary
            if 'BRANDING' not in content:
                issue = f"Missing BRANDING dictionary in {client_id}/branding.py"
                self.issues.append(issue)
                print(f"   ❌ {issue}")
                return False

            print(f"   ✅ branding.py valid")
            return True

        except Exception as e:
            issue = f"Error reading branding.py in {client_id}: {e}"
            self.issues.append(issue)
            print(f"   ❌ {issue}")
            return False

    def _create_default_branding(self, branding_file: Path, client_id: str) -> None:
        """Create a default branding.py file."""
        bot_name = client_id.replace('_', ' ').title()

        content = f'''"""Client Branding Configuration for {bot_name}"""

BRANDING = {{
    "bot_name": "{bot_name}",
    "bot_description": "Discord bot for {bot_name}",
    "embed_colors": {{
        "default": 0x3498db,
        "success": 0x2ecc71,
        "error": 0xe74c3c,
        "warning": 0xf39c12,
    }},
    "status_messages": [("🤖 Online", "custom")],
    "footer_text": "Powered by {bot_name}",
}}
'''

        with open(branding_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"   🔧 Created default branding.py")

    def _validate_directories(self, client_dir: Path, fix_issues: bool = False) -> bool:
        """Validate required directories exist."""
        required_dirs = ['data', 'logs']
        missing_dirs = []

        for dir_name in required_dirs:
            dir_path = client_dir / dir_name
            if not dir_path.exists():
                missing_dirs.append(dir_name)

        if missing_dirs:
            issue = f"Missing directories in {client_dir.name}: {missing_dirs}"
            print(f"   ⚠️ {issue}")

            if fix_issues:
                for dir_name in missing_dirs:
                    (client_dir / dir_name).mkdir(exist_ok=True)
                    print(f"   🔧 Created directory: {dir_name}")
                self.fixes_applied.append(f"Created directories in {client_dir.name}")

        return True

    def _print_summary(self) -> None:
        """Print validation summary."""
        print("\n" + "=" * 50)
        print("📊 VALIDATION SUMMARY")
        print("=" * 50)

        if not self.issues and not self.fixes_applied:
            print("✅ All client configurations are valid!")
        else:
            if self.issues:
                print(f"❌ Issues found: {len(self.issues)}")
                for issue in self.issues:
                    print(f"   • {issue}")

            if self.fixes_applied:
                print(f"🔧 Fixes applied: {len(self.fixes_applied)}")
                for fix in self.fixes_applied:
                    print(f"   • {fix}")

        print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate client configurations")
    parser.add_argument("--client", help="Validate specific client only")
    parser.add_argument("--fix", action="store_true", help="Automatically fix issues")

    args = parser.parse_args()

    validator = ClientValidator()

    if args.client:
        success = validator.validate_client(args.client, args.fix)
    else:
        success = validator.validate_all_clients(args.fix)

    if not success:
        exit(1)


if __name__ == "__main__":
    main()
