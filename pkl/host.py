"""Main plugin host implementation."""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from .context import plugin_context
from .loader import ImportlibPluginLoader, PluginLoader
from .metadata import ManifestMetadataLoader, MetadataLoader, PluginMetadata
from .plugin import Plugin, PluginState
from .resource import ResourceManager

__all__ = ["PluginHost"]


PluginHook = Callable[[Plugin], None]

_host_counter = 0


class PluginHost:
    """The main plugin host system."""

    def __init__(
        self,
        name: Optional[str] = None,
        metadata_loader: Optional[MetadataLoader] = None,
        plugin_loader: Optional[PluginLoader] = None,
    ) -> None:
        """Initialize the plugin host.

        Args:
            name: The host name (auto-generated if not provided).
            metadata_loader: The metadata loader to use.
            plugin_loader: The plugin loader to use.
        """
        global _host_counter
        if name is None:
            name = f"PluginHost<{id(self)}>"
        self.name = name
        
        self.metadata_loader: MetadataLoader = metadata_loader or ManifestMetadataLoader()
        self.plugin_loader: PluginLoader = plugin_loader or ImportlibPluginLoader()
        self.resource_manager = ResourceManager()

        # Per-host context variable
        self._context_var: ContextVar[Optional[Plugin]] = ContextVar(
            f"{self.name}.current_plugin", default=None
        )

        # Plugin registry
        self._plugins: Dict[str, Plugin] = {}

        # Host events
        self._events: Dict[str, Any] = {}  # Will store HostEvent instances

        # Hooks
        self._context_switch_hooks: List[Callable[[Optional[Plugin], Optional[Plugin]], None]] = []
        self._enable_hooks: List[PluginHook] = []
        self._disable_hooks: List[PluginHook] = []

    def load_plugin(
        self,
        source: Union[str, Path],
        parent: Optional["Plugin"] = None,
    ) -> Plugin:
        """Load a plugin from a source.

        The source is passed to registered loaders in order until one succeeds.

        Args:
            source: The plugin source (path or name).
            parent: Optional parent plugin for child plugins.

        Returns:
            The loaded plugin.

        Raises:
            ValueError: If the source is invalid.
            ImportError: If the plugin cannot be loaded.
        """
        # Convert to Path if it's a string that looks like a path
        if isinstance(source, str) and ("/" in source or "\\" in source or Path(source).exists()):
            source = Path(source)
        
        if isinstance(source, Path):
            source = source.resolve()

        # Load metadata
        try:
            metadata = self.metadata_loader.load(source if isinstance(source, Path) else Path(source))
        except (FileNotFoundError, ValueError):
            # If metadata loading fails, use source as name
            if isinstance(source, Path):
                name = source.name
                path = source
            else:
                name = source
                path = None
            metadata = PluginMetadata({"name": name})
        else:
            name = metadata.name
            path = source if isinstance(source, Path) else None

        # Check if already loaded
        if name in self._plugins:
            existing = self._plugins[name]
            # Update parent if provided and not already set
            if parent is not None and existing.parent is None:
                existing.parent = parent
            return existing

        # Create the plugin
        plugin = Plugin(host=self, name=name, path=path, parent=parent)
        plugin.metadata = metadata.data

        # Register it
        self._plugins[name] = plugin

        # Load the plugin module
        self._load_plugin(plugin)

        return plugin

    def _load_plugin(self, plugin: Plugin) -> None:
        """Load a plugin's module.

        Args:
            plugin: The plugin to load.
        """
        if plugin.state != PluginState.UNLOADED:
            return

        try:
            # Check dependencies
            metadata = PluginMetadata(plugin.metadata)
            for dep in metadata.requires:
                if dep not in self._plugins:
                    raise ImportError(f"Plugin {plugin.name} requires {dep} which is not loaded")
                dep_plugin = self._plugins[dep]
                if dep_plugin.state != PluginState.ENABLED:
                    raise ImportError(
                        f"Plugin {plugin.name} requires {dep} which is not enabled "
                        f"(state: {dep_plugin.state.value})"
                    )

            # Load the module
            with plugin_context(self, plugin):
                plugin.module = self.plugin_loader.load(plugin)

            plugin._state = PluginState.LOADED

        except Exception as e:
            plugin._error = e
            plugin._state = PluginState.ERROR
            raise

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name.

        Args:
            name: The plugin name.

        Returns:
            The plugin, or None if not found.
        """
        return self._plugins.get(name)

    def add_context_switch_hook(
        self, hook: Callable[[Optional[Plugin], Optional[Plugin]], None]
    ) -> None:
        """Add a hook for context switches.

        Args:
            hook: A function called with (old_plugin, new_plugin).
        """
        self._context_switch_hooks.append(hook)

    def add_enable_hook(self, hook: PluginHook) -> None:
        """Add a hook called when a plugin is enabled.

        Args:
            hook: The hook function.
        """
        self._enable_hooks.append(hook)

    def add_disable_hook(self, hook: PluginHook) -> None:
        """Add a hook called when a plugin is disabled.

        Args:
            hook: The hook function.
        """
        self._disable_hooks.append(hook)

    def get_current_plugin(self) -> Optional[Plugin]:
        """Get the currently executing plugin for this host.

        Returns:
            The current plugin, or None if no plugin is executing.
        """
        return self._context_var.get()
    
    def set_current_plugin(self, plugin: Optional[Plugin]) -> None:
        """Set the current plugin for this host.

        This can only be called when the current plugin is None.

        Args:
            plugin: The plugin to set as current, or None to clear.

        Raises:
            RuntimeError: If trying to set a plugin when one is already set.
        """
        current = self._context_var.get()
        if current is not None and plugin is not None:
            raise RuntimeError(
                f"Cannot set current plugin to {plugin.name} while {current.name} is executing"
            )
        self._context_var.set(plugin)
