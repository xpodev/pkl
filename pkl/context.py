"""Context management for tracking current plugin."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .host import PluginHost
    from .plugin import Plugin

__all__ = ["plugin_context"]


class _PluginContext:
    """Internal context manager for plugin execution."""

    def __init__(self, context_var: ContextVar[Optional["Plugin"]], plugin: Optional["Plugin"]) -> None:
        """Initialize the context.

        Args:
            context_var: The context variable for this host.
            plugin: The plugin to set as current.
        """
        self.context_var = context_var
        self.plugin = plugin
        self.token: Any = None

    def __enter__(self) -> "Plugin | None":
        """Enter the context."""
        self.token = self.context_var.set(self.plugin)
        return self.plugin

    def __exit__(self, *args: Any) -> None:
        """Exit the context."""
        self.context_var.reset(self.token)


def plugin_context(host: "PluginHost", plugin: Optional["Plugin"]) -> _PluginContext:
    """Create a context manager for plugin execution.

    Args:
        host: The plugin host.
        plugin: The plugin to execute in.

    Returns:
        A context manager that sets the current plugin.
    """
    return _PluginContext(host._context_var, plugin)
