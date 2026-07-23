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

__version__ = "0.1.1"

__all__ = [
    # Core
    "host",
    "get_default_host",
    "set_default_host",
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


def get_default_host() -> PluginHost:
    """Get the default (process-global) plugin host.

    Returns:
        The current default `PluginHost` instance.
    """
    return host


def set_default_host(new_host: PluginHost) -> None:
    """Replace the default plugin host used by module-level convenience functions.

    Every module-level function in `pkl` (`load_plugin`, `get_current_plugin`,
    `set_timeout`, `set_interval`, the `pkl.plugins` virtual-import machinery, etc.)
    operates on the default host. Call this to point them at a different
    `PluginHost` instance, e.g. to give each `PluginHost` owner (or each test) an
    independent host instead of sharing the single process-global one.

    Note: `@syscall` captures the default host at decoration time, so a function
    decorated before this call keeps running against the *old* host. Swap hosts
    once at startup, before any `@syscall`-decorated function is defined.

    Args:
        new_host: The `PluginHost` instance to install as the default.
    """
    global host
    host = new_host
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
