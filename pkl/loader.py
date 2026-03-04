"""Plugin loaders."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from .plugin import Plugin

__all__ = ["PluginLoader", "ImportlibPluginLoader"]


class PluginLoader(Protocol):
    """Protocol for plugin loaders."""

    def load(self, plugin: "Plugin") -> Any:
        """Load a plugin and return its module.

        Args:
            plugin: The plugin to load.

        Returns:
            The loaded module.

        Raises:
            ImportError: If the plugin cannot be loaded.
        """
        ...


class ImportlibPluginLoader:
    """Default plugin loader using importlib."""

    def load(self, plugin: "Plugin") -> Any:
        """Load a plugin using importlib.

        Args:
            plugin: The plugin to load.

        Returns:
            The loaded module.

        Raises:
            ImportError: If the plugin cannot be loaded.
        """
        if plugin.path is None:
            raise ImportError(f"Plugin {plugin.name} has no path")

        # Get entrypoint from metadata
        entrypoint = plugin.metadata.get("entrypoint", "plugin")

        # Build the module path
        module_path = plugin.path / f"{entrypoint}.py"
        if not module_path.exists():
            raise ImportError(f"Plugin entrypoint not found: {module_path}")

        # Create a unique module name
        module_name = f"pkl.plugins.{plugin.name}"

        # Load the module
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {module_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        # Also check for __init__.py and load that too
        init_path = plugin.path / "__init__.py"
        if init_path.exists():
            init_module_name = f"pkl.plugins.{plugin.name}.__init__"
            init_spec = importlib.util.spec_from_file_location(init_module_name, init_path)
            if init_spec is not None and init_spec.loader is not None:
                init_module = importlib.util.module_from_spec(init_spec)
                sys.modules[init_module_name] = init_module
                # Make the package accessible
                sys.modules[f"pkl.plugins.{plugin.name}"] = init_module
                init_spec.loader.exec_module(init_module)

        # Execute the entrypoint module
        spec.loader.exec_module(module)

        return module
