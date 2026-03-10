"""
Setup configuration for MultiCord CLI.
Public package for local Discord bot management.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="multicord",
    version="1.0.0",
    author="HollowTheSilver",
    author_email="",
    description="Run multiple Discord bots with ease - local orchestration and cloud management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HollowTheSilver/MultiCord",
    project_urls={
        "Bug Tracker": "https://github.com/HollowTheSilver/MultiCord/issues",
        "Source": "https://github.com/HollowTheSilver/MultiCord",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Communications :: Chat :: Discord",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    packages=find_packages(where="."),
    python_requires=">=3.9",
    install_requires=[
        "click>=8.1.0",
        "httpx>=0.26.0",
        "pydantic>=2.5.0",
        "keyring>=24.0.0",
        "rich>=13.0.0",  # For beautiful CLI output
        "python-dotenv>=1.0.0",
        "psutil>=5.9.0",  # For process management
        "aiofiles>=23.0.0",  # For async file operations
        "toml>=0.10.0",  # For config files
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=7.0.0",
            "mypy>=1.8.0",
            "types-toml",
        ],
    },
    entry_points={
        "console_scripts": [
            "multicord=multicord.cli:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "multicord": [
            "templates/**/*",
            "templates/**/.*",  # Include hidden files in templates
        ],
    },
    zip_safe=False,
)