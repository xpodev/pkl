"""Metadata loaders for plugins."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

__all__ = ["PluginMetadata", "MetadataLoader", "ManifestMetadataLoader"]


class PluginMetadata:
    """Plugin metadata container."""

    def __init__(self, data: Dict[str, Any]) -> None:
        """Initialize metadata from a dictionary.

        Args:
            data: The metadata dictionary.
        """
        self.data = data
        self.name: str = data.get("name", "")
        self.version: str = data.get("version", "0.0.0")
        self.entrypoint: str = data.get("entrypoint", "plugin")
        self.requires: List[str] = data.get("requires", [])
        self.optional: List[str] = data.get("optional", [])

    def __getitem__(self, key: str) -> Any:
        """Get a metadata value."""
        return self.data[key]

    def __contains__(self, key: str) -> bool:
        """Check if a metadata key exists."""
        return key in self.data

    def get(self, key: str, default: Any = None) -> Any:
        """Get a metadata value with a default."""
        return self.data.get(key, default)


class MetadataLoader(Protocol):
    """Protocol for metadata loaders."""

    def load(self, location: Path) -> PluginMetadata:
        """Load metadata from a location.

        Args:
            location: The plugin location (directory or file).

        Returns:
            The loaded metadata.

        Raises:
            FileNotFoundError: If the metadata cannot be found.
            ValueError: If the metadata is invalid.
        """
        ...


class ManifestMetadataLoader:
    """Loads metadata from manifest files (JSON, TOML, YAML)."""

    def __init__(self, filename: str = "plugin.json") -> None:
        """Initialize the loader.

        Args:
            filename: The manifest filename to look for.
        """
        self.filename = filename

    def load(self, location: Path) -> PluginMetadata:
        """Load metadata from a manifest file.

        Args:
            location: The plugin directory.

        Returns:
            The loaded metadata.

        Raises:
            FileNotFoundError: If no manifest file is found.
            ValueError: If the manifest is invalid.
        """
        if location.is_file():
            manifest_path = location
        else:
            manifest_path = location / self.filename

        if not manifest_path.exists():
            # Try alternative formats
            alternatives = [
                location / "plugin.json",
                location / "plugin.toml",
                location / "plugin.yaml",
                location / "plugin.yml",
            ]
            for alt in alternatives:
                if alt.exists():
                    manifest_path = alt
                    break
            else:
                # No manifest found, use defaults
                return PluginMetadata({"name": location.name, "entrypoint": "plugin"})

        # Load based on extension
        suffix = manifest_path.suffix.lower()
        if suffix == ".json":
            return self._load_json(manifest_path)
        elif suffix == ".toml":
            return self._load_toml(manifest_path)
        elif suffix in (".yaml", ".yml"):
            return self._load_yaml(manifest_path)
        else:
            raise ValueError(f"Unsupported manifest format: {suffix}")

    def _load_json(self, path: Path) -> PluginMetadata:
        """Load JSON manifest."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PluginMetadata(data)

    def _load_toml(self, path: Path) -> PluginMetadata:
        """Load TOML manifest."""
        if tomllib is None:
            raise RuntimeError("TOML support requires tomli package (pip install tomli)")
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return PluginMetadata(data)

    def _load_yaml(self, path: Path) -> PluginMetadata:
        """Load YAML manifest."""
        if yaml is None:
            raise RuntimeError("YAML support requires pyyaml package (pip install pyyaml)")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return PluginMetadata(data)
