#!/usr/bin/env python3
"""
Platform Start Script
=====================
Cross-platform start script for the Discord Bot Platform.
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    print("🚀 Starting Multi-Client Discord Bot Platform")
    print("=" * 48)

    # Check if virtual environment exists
    venv_path = Path("venv")
    if not venv_path.exists():
        print("📦 Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "venv"])

    # Determine activation script based on platform
    if os.name == 'nt':  # Windows
        activate_script = venv_path / "Scripts" / "activate.bat"
        python_executable = venv_path / "Scripts" / "python.exe"
    else:  # Unix-like
        activate_script = venv_path / "bin" / "activate"
        python_executable = venv_path / "bin" / "python"

    # Install requirements
    print("📚 Installing requirements...")
    subprocess.run([str(python_executable), "-m", "pip", "install", "-r", "requirements.txt"])

    # Start platform
    print("🤖 Starting platform...")
    subprocess.run([str(python_executable), "platform_main.py"])

if __name__ == "__main__":
    main()
