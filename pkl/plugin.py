"""Plugin class and related functionality."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .context import plugin_context
from .events import EventBase

if TYPE_CHECKING:
    from .host import PluginHost

__all__ = ["Plugin", "PluginState", "LifecycleEvent", "LifecycleEvent"]


class LifecycleEvent(EventBase):
    """A special event that runs when a plugin reaches a lifecycle point.
    
    Unlike regular events, lifecycle events only execute handlers registered
    by the plugin that owns the event, and are automatically invoked by the
    plugin system at the appropriate lifecycle point.
    """

    def __init__(self, plugin: "Plugin", name: str) -> None:
        """Initialize the lifecycle event.
        
        Args:
            plugin: The plugin that owns this event.
            name: The event name.
        """
        self.plugin = plugin
        self.name = name
        self._handlers: List[Callable[[], None]] = []

    def subscribe(self, handler: Callable[[], None]) -> None:
        """Subscribe to this lifecycle event.
        
        Args:
            handler: A callback function that takes no arguments.
            
        Raises:
            RuntimeError: If called outside of plugin context or from wrong plugin.
        """
        current = self.plugin.host.get_current_plugin()
        if current is None:
            raise RuntimeError(f"Cannot subscribe to {self.name} outside of plugin context")
        
        if current != self.plugin:
            raise RuntimeError(
                f"Cannot subscribe to {self.plugin.name}.{self.name} from {current.name}. "
                f"Lifecycle events can only be subscribed to by the owning plugin."
            )
        
        self._handlers.append(handler)

    def _invoke(self) -> None:
        """Invoke all handlers (internal use only)."""
        # Run handlers in the plugin's context
        with plugin_context(self.plugin.host, self.plugin):
            for handler in self._handlers:
                try:
                    handler()
                except Exception as e:
                    # Log but don't stop other handlers
                    import logging
                    logging.exception(
                        f"Error in {self.plugin.name}.{self.name} handler: {e}"
                    )


class PluginState(Enum):
    """Plugin state enumeration."""

    UNLOADED = "unloaded"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


class Plugin:
    """Represents a loaded plugin."""

    def __init__(
        self,
        host: "PluginHost",
        name: str,
        path: Optional[Path] = None,
        parent: Optional["Plugin"] = None,
    ) -> None:
        """Initialize the plugin.

        Args:
            host: The plugin host.
            name: The plugin name.
            path: The plugin path.
            parent: The parent plugin, if this is a child plugin.
        """
        self.host = host
        self.name = name
        self.path = path
        self.parent = parent
        self.metadata: Dict[str, Any] = {}
        self.module: Any = None
        self._state = PluginState.UNLOADED
        self._error: Optional[Exception] = None
        
        # Lifecycle events
        self.on_disable = LifecycleEvent(self, "on_disable")
        self.on_unload = LifecycleEvent(self, "on_unload")

    @property
    def state(self) -> PluginState:
        """Get the current state of the plugin."""
        return self._state

    @property
    def error(self) -> Optional[Exception]:
        """Get the error that occurred during plugin loading/enabling, if any."""
        return self._error

    def enable(self) -> None:
        """Enable the plugin.

        Raises:
            RuntimeError: If the plugin is already enabled or in an error state.
        """
        if self._state == PluginState.ENABLED:
            return

        if self._state == PluginState.ERROR:
            raise RuntimeError(f"Plugin {self.name} is in error state: {self._error}")

        if self._state == PluginState.UNLOADED:
            # Load first
            self.host._load_plugin(self)

        if self._state != PluginState.LOADED:
            raise RuntimeError(f"Plugin {self.name} cannot be enabled from state {self._state}")

        try:
            # Set state to enabled before running entrypoint
            self._state = PluginState.ENABLED

            # Call enable hooks
            for hook in self.host._enable_hooks:
                hook(self)

            # Execute plugin entrypoint if it has one
            if hasattr(self.module, "__enable__"):
                with plugin_context(self.host, self):
                    self.module.__enable__()

        except Exception as e:
            self._error = e
            self._state = PluginState.ERROR
            raise

    def disable(self) -> None:
        """Disable the plugin and clean up its resources.

        Raises:
            RuntimeError: If called from a different plugin context.
        """
        if self._state != PluginState.ENABLED:
            return

        # Check if we're being called by ourselves
        current = self.host.get_current_plugin()
        if current is not None and current != self:
            raise RuntimeError(f"Plugin {self.name} can only be disabled by itself")

        try:
            # Call disable hooks
            for hook in self.host._disable_hooks:
                hook(self)
            
            # Invoke on_disable lifecycle event
            self.on_disable._invoke()

            # Clean up resources (this will handle child plugins via ChildPluginResource)
            self.host.resource_manager.cleanup_plugin(self)

            self._state = PluginState.DISABLED

        except Exception as e:
            self._error = e
            self._state = PluginState.ERROR
            raise

    def __repr__(self) -> str:
        """Get a string representation of the plugin."""
        return f"Plugin(name={self.name!r}, state={self._state.value})"
