"""
Semantic versioning utilities for template version comparison.
Supports MAJOR.MINOR.PATCH format with comparison operators.
"""

from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class SemanticVersion:
    """Semantic version following MAJOR.MINOR.PATCH format."""
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __eq__(self, other: 'SemanticVersion') -> bool:
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __lt__(self, other: 'SemanticVersion') -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: 'SemanticVersion') -> bool:
        return self == other or self < other

    def __gt__(self, other: 'SemanticVersion') -> bool:
        return not self <= other

    def __ge__(self, other: 'SemanticVersion') -> bool:
        return not self < other

    def __ne__(self, other: 'SemanticVersion') -> bool:
        return not self == other

    @classmethod
    def parse(cls, version_string: str) -> Optional['SemanticVersion']:
        """
        Parse semantic version from string.

        Args:
            version_string: Version string in format "MAJOR.MINOR.PATCH"

        Returns:
            SemanticVersion instance or None if invalid format

        Examples:
            >>> SemanticVersion.parse("1.2.3")
            SemanticVersion(major=1, minor=2, patch=3)
            >>> SemanticVersion.parse("invalid")
            None
        """
        try:
            parts = version_string.strip().split('.')
            if len(parts) != 3:
                return None

            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            return cls(major=major, minor=minor, patch=patch)
        except (ValueError, AttributeError):
            return None

    def is_breaking_change_from(self, other: 'SemanticVersion') -> bool:
        """Check if this version is a breaking change from another version."""
        return self.major > other.major

    def is_feature_update_from(self, other: 'SemanticVersion') -> bool:
        """Check if this version adds features compared to another version."""
        return self.major == other.major and self.minor > other.minor

    def is_patch_update_from(self, other: 'SemanticVersion') -> bool:
        """Check if this version is just a patch compared to another version."""
        return self.major == other.major and self.minor == other.minor and self.patch > other.patch

    def update_type_from(self, other: 'SemanticVersion') -> str:
        """
        Determine update type from another version.

        Returns:
            "breaking", "feature", "patch", or "none"
        """
        if self == other:
            return "none"
        elif self.is_breaking_change_from(other):
            return "breaking"
        elif self.is_feature_update_from(other):
            return "feature"
        elif self.is_patch_update_from(other):
            return "patch"
        else:
            return "unknown"


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two semantic version strings.

    Args:
        v1: First version string
        v2: Second version string

    Returns:
        1 if v1 > v2
        0 if v1 == v2
        -1 if v1 < v2
        None if either version is invalid

    Examples:
        >>> compare_versions("2.0.0", "1.5.0")
        1
        >>> compare_versions("1.2.3", "1.2.3")
        0
        >>> compare_versions("1.0.0", "2.0.0")
        -1
    """
    ver1 = SemanticVersion.parse(v1)
    ver2 = SemanticVersion.parse(v2)

    if ver1 is None or ver2 is None:
        return None

    if ver1 > ver2:
        return 1
    elif ver1 == ver2:
        return 0
    else:
        return -1


def is_newer_version(current: str, latest: str) -> bool:
    """
    Check if latest version is newer than current.

    Args:
        current: Current version string
        latest: Latest version string

    Returns:
        True if latest > current, False otherwise
    """
    result = compare_versions(latest, current)
    return result == 1 if result is not None else False


def get_update_type(current: str, latest: str) -> Optional[str]:
    """
    Get update type between two versions.

    Args:
        current: Current version string
        latest: Latest version string

    Returns:
        "breaking", "feature", "patch", "none", or None if invalid
    """
    current_ver = SemanticVersion.parse(current)
    latest_ver = SemanticVersion.parse(latest)

    if current_ver is None or latest_ver is None:
        return None

    return latest_ver.update_type_from(current_ver)


def has_breaking_changes(current: str, latest: str) -> bool:
    """
    Check if update from current to latest includes breaking changes.

    Args:
        current: Current version string
        latest: Latest version string

    Returns:
        True if major version changed
    """
    current_ver = SemanticVersion.parse(current)
    latest_ver = SemanticVersion.parse(latest)

    if current_ver is None or latest_ver is None:
        return False

    return latest_ver.is_breaking_change_from(current_ver)
