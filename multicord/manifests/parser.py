"""
Manifest parser for MultiCord v3.0 manifest system.
"""

import json
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List
import jsonschema


class ManifestType(Enum):
    """Manifest type enumeration."""
    COLLECTION = "collection"
    TEMPLATE = "template"
    COG = "cog"


class ManifestValidationError(Exception):
    """Raised when manifest validation fails."""
    pass


class ManifestParser:
    """
    Parser for MultiCord v3.0 manifests.

    Parses the 3-layer manifest system:
    - Layer 1: multicord.json (repository-level)
    - Layer 2: template.json/cog.json (item-level)
    - Layer 3: config.toml/.env (user runtime config - not parsed here)

    Example usage:
        parser = ManifestParser()

        # Parse repository manifest
        repo_manifest = parser.parse_repository_manifest(repo_path)

        # Parse template manifest
        template_manifest = parser.parse_template_manifest(template_path)

        # Parse cog manifest
        cog_manifest = parser.parse_cog_manifest(cog_path)
    """

    def __init__(self, schemas_dir: Optional[Path] = None):
        """
        Initialize manifest parser.

        Args:
            schemas_dir: Directory containing JSON schemas (defaults to package schemas/)
        """
        if schemas_dir is None:
            schemas_dir = Path(__file__).parent / "schemas"

        self.schemas_dir = Path(schemas_dir)
        self._schemas_cache: Dict[str, Dict[str, Any]] = {}

    def _load_schema(self, schema_name: str) -> Dict[str, Any]:
        """
        Load and cache JSON schema.

        Args:
            schema_name: Schema filename (e.g., "multicord.schema.json")

        Returns:
            Parsed JSON schema

        Raises:
            FileNotFoundError: If schema file doesn't exist
            json.JSONDecodeError: If schema is invalid JSON
        """
        if schema_name in self._schemas_cache:
            return self._schemas_cache[schema_name]

        schema_path = self.schemas_dir / schema_name
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {schema_path}")

        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)

        self._schemas_cache[schema_name] = schema
        return schema

    def _validate_against_schema(
        self,
        data: Dict[str, Any],
        schema_name: str
    ) -> None:
        """
        Validate data against JSON schema.

        Args:
            data: Data to validate
            schema_name: Schema filename

        Raises:
            ManifestValidationError: If validation fails
        """
        try:
            schema = self._load_schema(schema_name)
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as e:
            raise ManifestValidationError(
                f"Validation failed: {e.message}\n"
                f"Path: {' -> '.join(str(p) for p in e.path)}"
            ) from e
        except jsonschema.SchemaError as e:
            raise ManifestValidationError(
                f"Invalid schema: {e.message}"
            ) from e

    def _validate_repository_exists(self, repo_path: Path) -> None:
        """
        Validate that repository has a multicord.json manifest.

        Args:
            repo_path: Path to repository root

        Raises:
            FileNotFoundError: If multicord.json doesn't exist
        """
        multicord_json = repo_path / "multicord.json"
        if not multicord_json.exists():
            raise FileNotFoundError(
                f"No v3.0 manifest found in {repo_path}\n"
                f"Expected: multicord.json at repository root"
            )

    def parse_repository_manifest(
        self,
        repo_path: Path,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Parse v3.0 repository manifest (multicord.json).

        Args:
            repo_path: Path to repository root
            validate: Whether to validate against schema

        Returns:
            Parsed manifest data

        Raises:
            FileNotFoundError: If multicord.json doesn't exist
            ManifestValidationError: If validation fails
            json.JSONDecodeError: If file is invalid JSON
        """
        manifest_path = repo_path / "multicord.json"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Repository manifest not found: {manifest_path}")

        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if validate:
            self._validate_against_schema(data, "multicord.schema.json")

        return data

    def parse_template_manifest(
        self,
        template_path: Path,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Parse v3.0 template manifest (template.json).

        Args:
            template_path: Path to template directory
            validate: Whether to validate against schema

        Returns:
            Parsed manifest data

        Raises:
            FileNotFoundError: If template.json doesn't exist
            ManifestValidationError: If validation fails
            json.JSONDecodeError: If file is invalid JSON
        """
        manifest_path = template_path / "template.json"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Template manifest not found: {manifest_path}")

        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if validate:
            self._validate_against_schema(data, "template.schema.json")

        return data

    def parse_cog_manifest(
        self,
        cog_path: Path,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Parse v3.0 cog manifest (cog.json).

        Args:
            cog_path: Path to cog directory
            validate: Whether to validate against schema

        Returns:
            Parsed manifest data

        Raises:
            FileNotFoundError: If cog.json doesn't exist
            ManifestValidationError: If validation fails
            json.JSONDecodeError: If file is invalid JSON
        """
        manifest_path = cog_path / "cog.json"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Cog manifest not found: {manifest_path}")

        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if validate:
            self._validate_against_schema(data, "cog.schema.json")

        return data

    def get_template_info(
        self,
        repo_path: Path,
        template_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get template information from v3.0 manifest.

        Args:
            repo_path: Path to repository root
            template_id: Template identifier

        Returns:
            Template metadata dict, or None if not found
        """
        template_path = repo_path / template_id
        if not template_path.is_dir():
            return None

        try:
            return self.parse_template_manifest(template_path)
        except FileNotFoundError:
            return None

    def get_cog_info(
        self,
        repo_path: Path,
        cog_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cog information from v3.0 manifest.

        Args:
            repo_path: Path to repository root
            cog_id: Cog identifier

        Returns:
            Cog metadata dict, or None if not found
        """
        # Try both cogs/cog_id and cog_id paths
        for base_path in [repo_path / "cogs" / cog_id, repo_path / cog_id]:
            if base_path.is_dir():
                try:
                    return self.parse_cog_manifest(base_path)
                except FileNotFoundError:
                    continue
        return None

    def list_templates(self, repo_path: Path) -> List[str]:
        """
        List all templates in repository.

        Args:
            repo_path: Path to repository root

        Returns:
            List of template IDs
        """
        manifest = self.parse_repository_manifest(repo_path, validate=False)
        items = manifest.get("items", [])
        # Filter for template paths (not in cogs/)
        return [
            item.rstrip('/') for item in items
            if not item.startswith('cogs/')
        ]

    def list_cogs(self, repo_path: Path) -> List[str]:
        """
        List all cogs in repository.

        Args:
            repo_path: Path to repository root

        Returns:
            List of cog IDs
        """
        manifest = self.parse_repository_manifest(repo_path, validate=False)
        items = manifest.get("items", [])
        # Filter for cog paths (in cogs/)
        return [
            item.replace('cogs/', '').rstrip('/')
            for item in items
            if item.startswith('cogs/')
        ]
