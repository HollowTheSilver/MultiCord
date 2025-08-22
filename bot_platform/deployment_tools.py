"""
Complete ClientOnboardingTool with Template Integration
======================================================

This is the complete, clean version of ClientOnboardingTool that replaces the existing one.
Integrates template selection, FLAGS editor, and database choice directly into the class.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot_platform.client_manager import ClientManager
from bot_platform.service_manager import PlatformOrchestrator
from bot_platform.template_manager import TemplateManager


class ClientOnboardingTool:
    """Interactive tool for creating new clients with template support."""

    def __init__(self):
        self.client_manager = ClientManager()
        self.orchestrator = PlatformOrchestrator()
        self.template_manager = TemplateManager()

    def interactive_onboarding(self) -> bool:
        """Run interactive client onboarding process (original workflow)."""
        print("🚀 Multi-Client Platform - New Client Onboarding")
        print("=" * 55)

        try:
            if not self.orchestrator.initialize():
                print("❌ Platform initialization failed")
                return False

            # Collect client information
            client_id = self._get_client_id()
            if not client_id:
                return False

            display_name = self._get_display_name(client_id)
            plan = self._get_plan()

            # Additional configuration
            print(f"\n📋 Creating client '{client_id}' with plan '{plan}'...")

            success = self.client_manager.create_client(
                client_id=client_id,
                display_name=display_name,
                plan=plan
            )

            if success:
                print(f"✅ Client '{client_id}' created successfully!")
                print(f"📁 Configuration directory: clients/{client_id}/")
                print(f"⚙️  Edit clients/{client_id}/.env to add your Discord token")
                print(f"🚀 Start with: python platform_main.py --client {client_id}")
                return True
            else:
                print(f"❌ Failed to create client '{client_id}'")
                return False

        except Exception as e:
            print(f"❌ Onboarding failed: {e}")
            return False

    def template_workflow_onboarding(self) -> bool:
        """Template-based client creation workflow."""
        print("🚀 Multi-Client Platform - Template-Based Client Creation")
        print("=" * 65)
        print("✨ Template Selection + FLAGS Editor + Database Choice")
        print()

        try:
            if not self.orchestrator.initialize():
                print("❌ Platform initialization failed")
                return False

            # Step 1: Template Selection
            print("📋 Step 1: Template Selection")
            template_info = self._select_template()
            print(f"✅ Selected template: {template_info.get('name', 'Custom')}")
            print()

            # Step 2: Basic Client Information
            print("👤 Step 2: Client Information")
            client_id = self._get_client_id()
            if not client_id:
                return False
            display_name = self._get_display_name(client_id)
            print(f"✅ Client: {client_id} ({display_name})")
            print()

            # Step 3: Database Backend Selection
            print("🗄️ Step 3: Database Backend Selection")
            database_backend = self._select_database_backend(template_info)
            print(f"✅ Database: {database_backend}")
            print()

            # Step 4: FLAGS Editor
            print("⚙️ Step 4: FLAGS Configuration")
            custom_flags = self._interactive_flags_editor(template_info)
            print("✅ FLAGS configured")
            print()

            # Step 5: Optional Business Model (preserve existing system)
            print("💼 Step 5: Business Model (Optional)")
            plan = self._get_plan_optional()
            print(f"✅ Plan: {plan}")
            print()

            # Final confirmation
            print("📋 Configuration Summary:")
            print(f"  Client ID: {client_id}")
            print(f"  Display Name: {display_name}")
            print(f"  Template: {template_info.get('name', 'Custom')}")
            print(f"  Database: {database_backend}")
            print(f"  Plan: {plan}")
            print()

            confirm = input("Create client with this configuration? (y/N): ").strip().lower()
            if confirm != 'y':
                print("❌ Client creation cancelled")
                return False

            # Create client using existing ClientManager with new parameters
            print(f"🔧 Creating client '{client_id}'...")
            success = self.client_manager.create_client(
                client_id=client_id,
                display_name=display_name,
                plan=plan,
                template_info=template_info,
                flags=custom_flags,
                database_backend=database_backend
            )

            if success:
                print(f"✅ Client '{client_id}' created successfully!")
                print()
                print("📁 Next Steps:")
                print(f"  1. Edit clients/{client_id}/.env to add your Discord token")
                print(f"  2. Customize branding in clients/{client_id}/branding.py")
                print(f"  3. Review FLAGS in clients/{client_id}/flags.py")
                print(f"  4. Start with: python platform_main.py --client {client_id}")
                return True
            else:
                print(f"❌ Failed to create client '{client_id}'")
                return False

        except Exception as e:
            print(f"❌ Template workflow failed: {e}")
            return False

    def _get_client_id(self) -> str:
        """Get and validate client ID."""
        while True:
            client_id = input("Client ID (alphanumeric, underscore, hyphen): ").strip().lower()

            if not client_id:
                print("❌ Client ID is required")
                continue

            if not client_id.replace('_', '').replace('-', '').isalnum():
                print("❌ Client ID can only contain letters, numbers, underscore, and hyphen")
                continue

            # Check if already exists
            if self.orchestrator.config_manager.client_configs.get(client_id):
                print(f"❌ Client '{client_id}' already exists")
                continue

            return client_id

    def _get_display_name(self, client_id: str) -> str:
        """Get display name for the client."""
        default_name = client_id.replace('_', ' ').replace('-', ' ').title()
        display_name = input(f"Display Name [{default_name}]: ").strip()
        return display_name or default_name

    def _get_plan(self) -> str:
        """Get business plan selection."""
        print("\nBusiness Plan Selection:")
        print("  1. Basic ($200/month) - Standard features, basic support")
        print("  2. Premium ($350/month) - + Analytics, tickets, advanced features")
        print("  3. Enterprise ($500/month) - + API access, priority support, unlimited")

        while True:
            choice = input("Select plan (1-3) [1]: ").strip()

            if choice == "" or choice == "1":
                return "basic"
            elif choice == "2":
                return "premium"
            elif choice == "3":
                return "enterprise"
            else:
                print("❌ Please enter 1, 2, or 3")

    def _get_plan_optional(self) -> str:
        """Get business plan selection (optional)."""
        print("Business model (optional - preserves existing plan system):")
        print("  1) Skip business model (simple deployment)")
        print("  2) Basic ($200/month) - Standard features")
        print("  3) Premium ($350/month) - + Analytics, advanced features")
        print("  4) Enterprise ($500/month) - + API access, priority support")
        print("  5) Custom pricing")

        while True:
            choice = input("Select option (1-5) [1]: ").strip()

            if choice == "" or choice == "1":
                return "custom"  # No business model
            elif choice == "2":
                return "basic"
            elif choice == "3":
                return "premium"
            elif choice == "4":
                return "enterprise"
            elif choice == "5":
                return "custom"
            else:
                print("❌ Please enter 1-5")

    def _select_template(self) -> Dict[str, Any]:
        """Interactive template selection with discovery."""
        templates = self.template_manager.discover_templates()

        print("Available templates:")
        print("  1) Blank Template (basic setup, no cogs)")

        builtin_templates = [t for t in templates if t.get("source") == "Built-in Templates"]

        template_options = ["blank"]
        option_num = 2

        for template in builtin_templates:
            if template["name"].lower() != "blank template":
                print(f"  {option_num}) {template['name']} - {template.get('description', '')}")
                template_options.append(template["name"])
                option_num += 1

        # Community templates
        community_templates = [t for t in templates if t.get("source") != "Built-in Templates"]
        if community_templates:
            print(f"  {option_num}) Browse Community Templates...")
            template_options.append("community")
            option_num += 1

        print(f"  {option_num}) Load from Repository Source...")
        template_options.append("repository")

        while True:
            try:
                choice = input(f"Select template (1-{len(template_options) + 1}) [1]: ").strip()

                if choice == "" or choice == "1":
                    return {"name": "blank", "path": "templates/builtin/blank"}

                choice_num = int(choice) - 1
                if 0 <= choice_num < len(template_options):
                    selected = template_options[choice_num]

                    if selected == "community":
                        return self._browse_community_templates(community_templates)
                    elif selected == "repository":
                        return self._load_from_repository()
                    else:
                        # Find template by name
                        for template in templates:
                            if template["name"].lower() == selected.lower():
                                return template
                        # Fallback to built-in template
                        return {"name": selected.lower().replace(" ", "_"),
                               "path": f"templates/builtin/{selected.lower().replace(' ', '_')}"}
                else:
                    print(f"❌ Please enter 1-{len(template_options) + 1}")

            except ValueError:
                print("❌ Please enter a valid number")

    def _browse_community_templates(self, community_templates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Browse community templates."""
        if not community_templates:
            print("No community templates available.")
            return {"name": "blank", "path": "templates/builtin/blank"}

        print("\nCommunity Templates:")
        for i, template in enumerate(community_templates, 1):
            print(f"  {i}) {template['name']} - {template.get('description', '')}")
            print(f"     by {template.get('author', 'Unknown')} (v{template.get('version', '1.0.0')})")

        while True:
            try:
                choice = int(input(f"Select community template (1-{len(community_templates)}): "))
                if 1 <= choice <= len(community_templates):
                    return community_templates[choice - 1]
                else:
                    print(f"❌ Please enter 1-{len(community_templates)}")
            except ValueError:
                print("❌ Please enter a valid number")

    def _load_from_repository(self) -> Dict[str, Any]:
        """Load template from repository source."""
        print("\n🔗 Load from Repository Source")
        print("This feature allows loading templates from Git repositories.")
        print("For Phase 2, using blank template. Repository loading will be expanded in Phase 3.")

        return {"name": "blank", "path": "templates/builtin/blank"}

    def _select_database_backend(self, template_info: Dict[str, Any]) -> str:
        """Interactive database backend selection with template recommendations."""
        template_name = template_info.get("name", "")
        template_metadata = None

        if template_name != "blank":
            template_metadata = self.template_manager.get_template_by_name(template_name)

        print("Database backend selection:")

        # Show template recommendation if available
        if template_metadata:
            recommended = template_metadata.get("recommended_database", "sqlite")
            features = template_metadata.get("database_features", {})

            print(f"💡 Template '{template_metadata['name']}' recommends: {recommended}")

            if features.get("requires_real_time"):
                print("   Real-time updates beneficial for this template")
            if features.get("high_write_volume"):
                print("   High write volume expected")
            if features.get("complex_queries"):
                print("   Complex queries will be used")
            print()

        print("Available backends:")
        print("  1) SQLite (default) - Simple, local, zero-config")
        print("  2) Google Cloud Firestore - Real-time, scalable, cloud-native")
        print("  3) PostgreSQL - Professional relational database")
        print("  4) Custom configuration...")

        default_choice = "1"
        if template_metadata:
            recommended = template_metadata.get("recommended_database", "sqlite")
            if recommended == "firestore":
                default_choice = "2"
            elif recommended == "postgresql":
                default_choice = "3"

        while True:
            choice = input(f"Select database (1-4) [{default_choice}]: ").strip()

            if choice == "":
                choice = default_choice

            if choice == "1":
                return "sqlite"
            elif choice == "2":
                print("⚠️ Firestore requires additional configuration.")
                print("For Phase 2, using SQLite. Firestore implementation coming in Phase 3.")
                return "sqlite"  # Temporary fallback
            elif choice == "3":
                print("⚠️ PostgreSQL requires additional configuration.")
                print("For Phase 2, using SQLite. PostgreSQL implementation coming in Phase 3.")
                return "sqlite"  # Temporary fallback
            elif choice == "4":
                return self._custom_database_config()
            else:
                print("❌ Please enter 1-4")

    def _custom_database_config(self) -> str:
        """Custom database configuration."""
        print("\n🔧 Custom Database Configuration")
        print("This feature will be expanded in Phase 3.")
        print("Using SQLite for now.")
        return "sqlite"

    def _interactive_flags_editor(self, template_info: Dict[str, Any]) -> Dict[str, Any]:
        """Interactive FLAGS editor with template pre-population."""
        template_name = template_info.get("name", "")

        if template_name == "blank":
            print("Blank template - using minimal FLAGS configuration")
            return {}

        template_metadata = self.template_manager.get_template_by_name(template_name)

        if not template_metadata:
            print("No template metadata found - using default FLAGS")
            return {}

        # Start with template defaults
        flags = template_metadata.get("default_flags", {}).copy()
        customizable = template_metadata.get("customizable_flags", [])

        print(f"Template: {template_metadata['name']}")
        print(f"Description: {template_metadata.get('description', '')}")
        print()
        print("Pre-configured FLAGS from template:")
        self._display_flags_summary(flags)

        if not customizable:
            print("ℹ️ This template has no user-customizable flags.")
            return flags

        print(f"\nCustomizable FLAGS: {', '.join(customizable[:5])}")
        if len(customizable) > 5:
            print(f"  ... and {len(customizable) - 5} more")

        print("\nWould you like to customize FLAGS?")
        print("  1) Use template defaults (recommended)")
        print("  2) Open FLAGS editor")

        choice = input("Choice (1-2) [1]: ").strip()

        if choice == "2":
            return self._flags_editor_interface(flags, customizable, template_metadata)
        else:
            print("✅ Using template defaults")
            return flags

    def _flags_editor_interface(self, flags: Dict[str, Any], customizable: List[str],
                               template_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """FLAGS editor interface."""
        print(f"\n⚙️ FLAGS Editor - {template_metadata['name']}")
        print("=" * 50)

        while True:
            print("\nCommands:")
            print("  [v]iew current FLAGS")
            print("  [e]dit customizable flag")
            print("  [a]dd custom flag")
            print("  [r]eset to template defaults")
            print("  [s]ave and continue")

            command = input("FLAGS Editor> ").strip().lower()

            if command == 'v':
                self._display_flags_tree(flags)
            elif command == 'e':
                self._edit_customizable_flag(flags, customizable)
            elif command == 'a':
                self._add_custom_flag(flags)
            elif command == 'r':
                flags = template_metadata.get("default_flags", {}).copy()
                print("✅ Reset to template defaults")
            elif command == 's':
                break
            else:
                print("❌ Invalid command. Use v, e, a, r, or s")

        return flags

    def _display_flags_summary(self, flags: Dict[str, Any]) -> None:
        """Display FLAGS in a concise summary format."""
        enabled_features = []
        disabled_features = []

        for key, value in flags.items():
            if key in ["database_backend", "limits"]:
                continue

            if isinstance(value, bool):
                if value:
                    enabled_features.append(key)
                else:
                    disabled_features.append(key)

        if enabled_features:
            print(f"  ✅ Enabled: {', '.join(enabled_features[:4])}")
            if len(enabled_features) > 4:
                print(f"    ... and {len(enabled_features) - 4} more")

        if disabled_features:
            print(f"  ❌ Disabled: {', '.join(disabled_features[:3])}")
            if len(disabled_features) > 3:
                print(f"    ... and {len(disabled_features) - 3} more")

    def _display_flags_tree(self, flags: Dict[str, Any], indent: int = 0) -> None:
        """Display FLAGS in a tree structure."""
        for key, value in flags.items():
            prefix = "  " * indent + ("├─ " if indent > 0 else "┌─ ")

            if isinstance(value, dict):
                print(f"{prefix}{key}:")
                self._display_flags_tree(value, indent + 1)
            elif isinstance(value, bool):
                status = "✅" if value else "❌"
                print(f"{prefix}{key}: {status}")
            else:
                print(f"{prefix}{key}: {value}")

    def _edit_customizable_flag(self, flags: Dict[str, Any], customizable: List[str]) -> None:
        """Edit a customizable flag value."""
        print("\nCustomizable flags:")
        for i, flag in enumerate(customizable, 1):
            current_value = self._get_nested_flag_value(flags, flag)
            print(f"  {i}) {flag} = {current_value}")

        try:
            choice = int(input(f"Select flag to edit (1-{len(customizable)}): "))
            if 1 <= choice <= len(customizable):
                flag_path = customizable[choice - 1]
                current_value = self._get_nested_flag_value(flags, flag_path)

                print(f"\nEditing: {flag_path}")
                print(f"Current value: {current_value}")

                if isinstance(current_value, bool):
                    new_value = input("New value (true/false): ").strip().lower()
                    if new_value in ["true", "t", "1", "yes", "y"]:
                        self._set_nested_flag_value(flags, flag_path, True)
                    elif new_value in ["false", "f", "0", "no", "n"]:
                        self._set_nested_flag_value(flags, flag_path, False)
                    else:
                        print("❌ Invalid boolean value")
                        return
                elif isinstance(current_value, int):
                    try:
                        new_value = int(input("New value (integer): "))
                        self._set_nested_flag_value(flags, flag_path, new_value)
                    except ValueError:
                        print("❌ Invalid integer value")
                        return
                else:
                    new_value = input("New value: ").strip()
                    self._set_nested_flag_value(flags, flag_path, new_value)

                print(f"✅ Updated {flag_path}")
            else:
                print(f"❌ Please enter 1-{len(customizable)}")
        except ValueError:
            print("❌ Please enter a valid number")

    def _get_nested_flag_value(self, flags: Dict[str, Any], flag_path: str) -> Any:
        """Get value from nested flag path like 'limits.max_warnings'."""
        keys = flag_path.split('.')
        value = flags

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        return value

    def _set_nested_flag_value(self, flags: Dict[str, Any], flag_path: str, new_value: Any) -> None:
        """Set value for nested flag path like 'limits.max_warnings'."""
        keys = flag_path.split('.')
        current = flags

        # Navigate to the parent container
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set the final value
        current[keys[-1]] = new_value

    def _add_custom_flag(self, flags: Dict[str, Any]) -> None:
        """Add a custom user-defined flag."""
        print("\n➕ Add Custom Flag")
        flag_name = input("Flag name: ").strip()

        if not flag_name:
            print("❌ Flag name required")
            return

        if flag_name in flags:
            print("❌ Flag already exists")
            return

        print("Value type:")
        print("  1) Boolean (true/false)")
        print("  2) Integer")
        print("  3) String")

        value_type = input("Select type (1-3): ").strip()

        try:
            if value_type == "1":
                value_input = input("Value (true/false): ").strip().lower()
                if value_input in ["true", "t", "1", "yes", "y"]:
                    value = True
                elif value_input in ["false", "f", "0", "no", "n"]:
                    value = False
                else:
                    print("❌ Invalid boolean value")
                    return
            elif value_type == "2":
                value = int(input("Value (integer): "))
            elif value_type == "3":
                value = input("Value (string): ").strip()
            else:
                print("❌ Invalid type selection")
                return

            # Add to custom section
            if "custom" not in flags:
                flags["custom"] = {}

            flags["custom"][flag_name] = value
            print(f"✅ Added custom flag: {flag_name} = {value}")

        except ValueError:
            print("❌ Invalid value for selected type")
