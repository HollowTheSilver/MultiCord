"""
Docker integration module for MultiCord CLI.

This module provides Docker container support for running Discord bots
in isolated containers for local testing and cloud deployment preparation.

Architecture:
- docker_client.py: Low-level Docker SDK wrapper with connection management
- docker_manager.py: High-level Docker operations (Dockerfile generation, container lifecycle)
- scaler.py: Intelligent resource allocation and horizontal scaling (Phase 5.2)
"""

from .docker_client import DockerClient
from .docker_manager import DockerManager

__all__ = ['DockerClient', 'DockerManager']
