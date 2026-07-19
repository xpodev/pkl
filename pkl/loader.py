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

        package_name = f"pkl.plugins.{plugin.name}"

        # Purge any stale sys.modules entries left behind by a previous load of
        # a same-named plugin (possibly against a different host), so this load
        # always starts from a clean slate instead of picking up cached submodules.
        for key in [
            k for k in sys.modules if k == package_name or k.startswith(package_name + ".")
        ]:
            del sys.modules[key]

        init_path = plugin.path / "__init__.py"
        if init_path.exists():
            # Load __init__.py as the real package module, with a __path__
            # pointing at the plugin's own directory, so relative imports
            # (both inside __init__.py and inside the entrypoint) resolve
            # against the plugin's own files like an ordinary Python package.
            init_spec = importlib.util.spec_from_file_location(
                package_name, init_path, submodule_search_locations=[str(plugin.path)]
            )
            if init_spec is None or init_spec.loader is None:
                raise ImportError(f"Cannot create module spec for {init_path}")

            init_module = importlib.util.module_from_spec(init_spec)
            sys.modules[package_name] = init_module
            init_spec.loader.exec_module(init_module)

            # __init__.py's own relative imports (e.g. `from .plugin import X`)
            # may already have triggered normal import machinery to load and
            # register the entrypoint as a submodule. Reuse that module instead
            # of loading and executing the entrypoint a second time under a
            # second, distinct module object.
            entrypoint_name = f"{package_name}.{entrypoint}"
            module = sys.modules.get(entrypoint_name)
            if module is None:
                spec = importlib.util.spec_from_file_location(entrypoint_name, module_path)
                if spec is None or spec.loader is None:
                    raise ImportError(f"Cannot create module spec for {module_path}")

                module = importlib.util.module_from_spec(spec)
                sys.modules[entrypoint_name] = module
                spec.loader.exec_module(module)

            # Make the entrypoint accessible as an attribute of the package,
            # matching normal Python submodule-import behavior.
            setattr(init_module, entrypoint, module)

            return module

        # No __init__.py: load the entrypoint as a plain module, unchanged
        # from prior behavior.
        spec = importlib.util.spec_from_file_location(package_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {module_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[package_name] = module
        spec.loader.exec_module(module)

        return module
