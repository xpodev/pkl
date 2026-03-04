"""Custom importer for pkl.plugins virtual module."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .host import PluginHost

__all__ = ["install_plugin_importer"]


class PluginsModule(ModuleType):
    """Virtual module that provides access to plugins."""

    def __init__(self, host: "PluginHost") -> None:
        """Initialize the plugins module.

        Args:
            host: The plugin host.
        """
        super().__init__("pkl.plugins")
        self._host = host
        self.__path__ = []  # type: ignore
        self.__package__ = "pkl.plugins"

    def __getattr__(self, name: str) -> Any:
        """Get a plugin by name.

        Args:
            name: The plugin name.

        Returns:
            The plugin's module.

        Raises:
            AttributeError: If the plugin is not found or doesn't have __init__.py.
        """
        plugin = self._host.get_plugin(name)
        if plugin is None:
            raise AttributeError(f"Plugin {name} not found")

        # Check if the plugin has __init__.py (is a package)
        if plugin.path is None:
            raise AttributeError(f"Plugin {name} has no path")

        init_path = plugin.path / "__init__.py"
        if not init_path.exists():
            raise AttributeError(f"Plugin {name} does not have __init__.py")

        # Return the module
        module_name = f"pkl.plugins.{name}"
        if module_name in sys.modules:
            return sys.modules[module_name]

        raise AttributeError(f"Plugin {name} module not loaded")

    def __dir__(self) -> list[str]:
        """List available plugins."""
        return [
            name
            for name, plugin in self._host._plugins.items()
            if plugin.path and (plugin.path / "__init__.py").exists()
        ]


def install_plugin_importer(host: "PluginHost") -> None:
    """Install the custom importer for pkl.plugins.

    Args:
        host: The plugin host to use for plugin lookup.
    """
    # Create the virtual pkl.plugins module
    plugins_module = PluginsModule(host)
    sys.modules["pkl.plugins"] = plugins_module
