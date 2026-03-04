"""PKL - Plugin hosting system with resource management."""

from __future__ import annotations

from typing import Optional, Union
from pathlib import Path

from .child_plugin import ChildPluginResource, load_plugin as _load_plugin_impl
from .context import plugin_context
from .decorators import syscall
from .events import Event, event, HostEvent
from .host import PluginHost
from .importer import install_plugin_importer
from .loader import ImportlibPluginLoader, PluginLoader
from .logging import PluginLogger, get_logger, LogProxy
from .metadata import ManifestMetadataLoader, MetadataLoader, PluginMetadata
from .plugin import Plugin, PluginState, LifecycleEvent
from .resource import Resource, ResourceManager
from .timing import Timer, set_interval, set_timeout
from .types import EventHandler, PluginEntrypoint, ResourceFactory

__version__ = "0.1.0"

__all__ = [
    # Core
    "host",
    "Plugin",
    "PluginState",
    "LifecycleEvent",
    # Context
    "get_current_plugin",
    "plugin_context",
    # Resources
    "Resource",
    "ResourceManager",
    "ChildPluginResource",
    # Loaders
    "MetadataLoader",
    "ManifestMetadataLoader",
    "PluginLoader",
    "ImportlibPluginLoader",
    "PluginMetadata",
    # Decorators
    "syscall",
    # Events
    "Event",
    "event",
    "HostEvent",
    # Logging
    "PluginLogger",
    "get_logger",
    "log",
    # Timing
    "Timer",
    "set_timeout",
    "set_interval",
    # Utilities
    "load_plugin",
    # Types
    "EventHandler",
    "PluginEntrypoint",
    "ResourceFactory",
]

# Global plugin host - automatically created on import
host = PluginHost(name="default")
install_plugin_importer(host)


def get_current_plugin() -> Optional[Plugin]:
    """Get the currently executing plugin.

    Returns:
        The current plugin, or None if no plugin is executing.
    """
    return host.get_current_plugin()


def load_plugin(source: Union[str, Path], detached: bool = False) -> Plugin:
    """Load a plugin from the current context.

    If called from within a plugin context, the loaded plugin becomes a child
    of the current plugin. If called outside a plugin context (root level),
    the plugin is loaded as a root plugin.

    Args:
        source: The plugin source (path or name).
        detached: If True and loading as a child, the child plugin becomes
                  independent of its parent.

    Returns:
        The loaded plugin.
    """
    return _load_plugin_impl(source, detached)


# Convenience log proxy instance
log = LogProxy()
