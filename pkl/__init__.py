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
    "PluginHost",
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
    "set_default_host",
    "get_default_host",
    # Types
    "EventHandler",
    "PluginEntrypoint",
    "ResourceFactory",
]

# Default host instance
_default_host: Optional[PluginHost] = None


def set_default_host(host: PluginHost) -> None:
    """Set the default plugin host.

    Args:
        host: The host to set as default.
    """
    global _default_host
    _default_host = host
    # Install the plugin importer
    install_plugin_importer(host)


def get_default_host() -> PluginHost:
    """Get the default plugin host.

    Returns:
        The default host.
    """
    global _default_host
    if _default_host is None:
        # Auto-create a default host
        host = PluginHost(name="default")
        set_default_host(host)
    assert _default_host is not None  # Type guard for mypy
    return _default_host


def get_current_plugin(host: Optional[PluginHost] = None) -> Optional[Plugin]:
    """Get the currently executing plugin.

    Args:
        host: The plugin host to use (defaults to the default host).

    Returns:
        The current plugin, or None if no plugin is executing.
    """
    if host is None:
        host = get_default_host()
    return host.get_current_plugin()


def load_plugin(source: Union[str, Path], detached: bool = False, host: Optional[PluginHost] = None) -> Plugin:
    """Load a plugin from the current context.

    If called from within a plugin context, the loaded plugin becomes a child
    of the current plugin. If called outside a plugin context (root level),
    the plugin is loaded as a root plugin.

    Args:
        source: The plugin source (path or name).
        detached: If True and loading as a child, the child plugin becomes
                  independent of its parent.
        host: The plugin host to use (defaults to the default host).

    Returns:
        The loaded plugin.
    """
    return _load_plugin_impl(source, detached, host)


# Convenience log proxy instance
log = LogProxy()
