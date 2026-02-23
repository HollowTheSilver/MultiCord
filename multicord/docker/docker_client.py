"""
Low-level Docker SDK wrapper with connection management.

This module provides a thin abstraction layer over the Docker Python SDK,
handling connection management, platform detection, and MultiCord-specific
Docker conventions.
"""

import os
import platform
import logging
from typing import Optional, List, Dict
from pathlib import Path

import docker
from docker.errors import DockerException, APIError, ImageNotFound
from docker.models.networks import Network
from docker.models.containers import Container
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

logger = logging.getLogger('multicord.docker.client')
console = Console()


class DockerConnectionError(Exception):
    """Raised when Docker daemon connection fails."""
    pass


class DockerClient:
    """
    Thin wrapper around Docker SDK with MultiCord conventions.

    Provides connection management, platform detection, and MultiCord-specific
    Docker operations like network setup and container filtering.

    Uses singleton pattern to ensure only one Docker client instance exists.
    """

    _instance: Optional['DockerClient'] = None
    _client: Optional[docker.DockerClient] = None

    def __new__(cls):
        """Singleton pattern - only one Docker client instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize Docker client with connection validation."""
        if self._client is None:
            self._initialize_client()

    def _initialize_client(self):
        """Initialize Docker SDK client with platform detection."""
        try:
            # Attempt to connect to Docker daemon
            self._client = docker.from_env()

            # Validate connection by pinging Docker daemon
            self._client.ping()

            logger.info("Successfully connected to Docker daemon")
            self._log_docker_info()

        except DockerException as e:
            raise DockerConnectionError(
                f"Failed to connect to Docker daemon. Is Docker running?\n"
                f"Error: {e}\n\n"
                f"Troubleshooting:\n"
                f"  - Windows: Start Docker Desktop\n"
                f"  - Linux: sudo systemctl start docker\n"
                f"  - macOS: Start Docker Desktop from Applications"
            )

    def _log_docker_info(self):
        """Log Docker daemon information for debugging."""
        try:
            info = self._client.info()
            version = self._client.version()

            logger.info(f"Docker version: {version.get('Version', 'unknown')}")
            logger.info(f"Docker API version: {version.get('ApiVersion', 'unknown')}")
            logger.info(f"Platform: {info.get('OSType', 'unknown')}/{info.get('Architecture', 'unknown')}")
            logger.info(f"Containers running: {info.get('ContainersRunning', 0)}")

        except Exception as e:
            logger.warning(f"Could not retrieve Docker info: {e}")

    @property
    def client(self) -> docker.DockerClient:
        """Get the underlying Docker SDK client."""
        if self._client is None:
            self._initialize_client()
        return self._client

    def ensure_network(self, network_name: str = "multicord-network") -> Network:
        """
        Create MultiCord Docker network if it doesn't exist.

        Args:
            network_name: Name of the Docker network (default: multicord-network)

        Returns:
            Docker Network object

        Raises:
            DockerException: If network creation fails
        """
        try:
            # Check if network already exists
            networks = self.client.networks.list(names=[network_name])
            if networks:
                logger.debug(f"Network '{network_name}' already exists")
                return networks[0]

            # Create network with bridge driver
            logger.info(f"Creating Docker network: {network_name}")
            network = self.client.networks.create(
                network_name,
                driver="bridge",
                check_duplicate=True,
                labels={"managed-by": "multicord"}
            )

            logger.info(f"✓ Created network: {network_name}")
            return network

        except APIError as e:
            logger.error(f"Failed to create Docker network: {e}")
            raise

    def list_containers(
        self,
        filter_prefix: str = "multicord_",
        all_containers: bool = False
    ) -> List[Container]:
        """
        List all MultiCord-managed containers.

        Args:
            filter_prefix: Container name prefix to filter by (default: multicord_)
            all_containers: If True, include stopped containers (default: False)

        Returns:
            List of Docker Container objects
        """
        try:
            # Get all containers (running or all)
            containers = self.client.containers.list(all=all_containers)

            # Filter by name prefix using the reliable .name attribute
            # (attrs['Names'] can be empty even for valid containers)
            multicord_containers = [
                c for c in containers
                if c.name.startswith(filter_prefix)
            ]

            logger.debug(f"Found {len(multicord_containers)} MultiCord containers")
            return multicord_containers

        except APIError as e:
            logger.error(f"Failed to list containers: {e}")
            return []

    def inspect_container(self, container_id: str) -> Optional[Dict]:
        """
        Get detailed container information.

        Args:
            container_id: Container ID or name

        Returns:
            Container inspection dictionary or None if not found
        """
        try:
            container = self.client.containers.get(container_id)
            return container.attrs

        except docker.errors.NotFound:
            logger.warning(f"Container not found: {container_id}")
            return None
        except APIError as e:
            logger.error(f"Failed to inspect container: {e}")
            return None

    def pull_base_image(
        self,
        image: str = "python:3.11-slim",
        show_progress: bool = True
    ) -> bool:
        """
        Pull Python base image with progress display.

        Args:
            image: Docker image name with tag (default: python:3.11-slim)
            show_progress: Show progress bar (default: True)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if image already exists
            try:
                self.client.images.get(image)
                logger.debug(f"Image '{image}' already exists locally")
                return True
            except ImageNotFound:
                pass

            logger.info(f"Pulling Docker image: {image}")

            if show_progress:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console
                ) as progress:
                    task = progress.add_task(f"Pulling {image}...", total=None)

                    # Pull image with low-level API for progress
                    for line in self.client.api.pull(image, stream=True, decode=True):
                        status = line.get('status', '')
                        if 'progress' in line:
                            progress.update(task, description=f"{status}: {line['progress']}")
                        else:
                            progress.update(task, description=status)
            else:
                self.client.images.pull(image)

            logger.info(f"✓ Pulled image: {image}")
            return True

        except APIError as e:
            logger.error(f"Failed to pull image '{image}': {e}")
            console.print(f"[red]✗ Failed to pull image: {e}[/red]")
            return False

    def get_platform_info(self) -> Dict[str, str]:
        """
        Get platform-specific Docker information.

        Returns:
            Dictionary with platform, docker_type, socket_path
        """
        system = platform.system()

        if system == "Windows":
            return {
                "platform": "Windows",
                "docker_type": "Docker Desktop",
                "socket_path": "npipe:////./pipe/docker_engine"
            }
        elif system == "Darwin":  # macOS
            return {
                "platform": "macOS",
                "docker_type": "Docker Desktop",
                "socket_path": "unix:///var/run/docker.sock"
            }
        else:  # Linux
            return {
                "platform": "Linux",
                "docker_type": "Docker Engine",
                "socket_path": "unix:///var/run/docker.sock"
            }

    def validate_docker_version(self, min_version: str = "20.0.0") -> bool:
        """
        Validate Docker daemon version meets minimum requirements.

        Args:
            min_version: Minimum required Docker version

        Returns:
            True if version is compatible, False otherwise
        """
        try:
            version = self.client.version()
            docker_version = version.get('Version', '0.0.0')

            # Simple version comparison (major.minor.patch)
            current_parts = [int(x) for x in docker_version.split('.')[:3]]
            min_parts = [int(x) for x in min_version.split('.')[:3]]

            is_compatible = current_parts >= min_parts

            if not is_compatible:
                logger.warning(
                    f"Docker version {docker_version} is below minimum {min_version}"
                )

            return is_compatible

        except Exception as e:
            logger.error(f"Failed to validate Docker version: {e}")
            return False

    def cleanup_orphaned_containers(self, bot_name: Optional[str] = None):
        """
        Remove stopped MultiCord containers.

        Args:
            bot_name: If specified, only clean up containers for this bot
        """
        try:
            # Get all stopped containers
            stopped_containers = self.list_containers(all_containers=True)
            stopped_containers = [c for c in stopped_containers if c.status != 'running']

            # Filter by bot name if specified
            if bot_name:
                stopped_containers = [
                    c for c in stopped_containers
                    if any(bot_name in name for name in c.attrs.get('Names', []))
                ]

            if not stopped_containers:
                logger.debug("No stopped containers to clean up")
                return

            logger.info(f"Cleaning up {len(stopped_containers)} stopped container(s)")

            for container in stopped_containers:
                try:
                    container.remove()
                    logger.debug(f"Removed container: {container.name}")
                except APIError as e:
                    logger.warning(f"Failed to remove container {container.name}: {e}")

        except Exception as e:
            logger.error(f"Failed to cleanup containers: {e}")

    def close(self):
        """Close Docker client connection."""
        if self._client:
            try:
                self._client.close()
                logger.info("Docker client connection closed")
            except Exception as e:
                logger.warning(f"Error closing Docker client: {e}")
            finally:
                self._client = None
                DockerClient._instance = None
