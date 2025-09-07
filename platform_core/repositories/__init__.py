"""
Data access repositories for MultiCord platform.

Contains PostgreSQL-based repository implementations for domain entities.
"""

from .process_repository import ProcessRepository

__all__ = [
    "ProcessRepository"
]