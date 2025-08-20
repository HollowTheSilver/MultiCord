#!/usr/bin/env python3
"""Platform Setup Script"""

import subprocess
import sys
from pathlib import Path


def main():
    print("🔧 Setting up Multi-Client Discord Bot Platform")
    print("=" * 48)

    # Install requirements
    print("📚 Installing Python requirements...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    subprocess.run([sys.executable, "-m", "pip", "install", "psutil"])

    # Create necessary directories
    dirs = ["bot_platform/logs", "backups", "data"]
    for directory in dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"   Created directory: {directory}")

    print("✅ Setup complete!")
    print("🚀 Next steps:")
    print("1. Copy platform code from artifacts into platform/ files")
    print("2. Update clients/default/.env with your Discord token")
    print("3. Run 'python platform_main.py --client default' to test")


if __name__ == "__main__":
    main()
