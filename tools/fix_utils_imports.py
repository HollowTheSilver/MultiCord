import os
from pathlib import Path


def fix_cog_imports():
    """Fix imports in cog files."""
    cogs_dir = Path("core/cogs")

    for py_file in cogs_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue

        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Fix absolute utils imports to core.utils
        content = content.replace("from utils.", "from core.utils.")
        content = content.replace("import utils.", "import core.utils.")

        if content != original_content:
            with open(py_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Fixed imports in {py_file}")


if __name__ == "__main__":
    fix_cog_imports()
