"""Timing utilities for plugins."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Callable, Optional

from .context import plugin_context
from .resource import Resource

if TYPE_CHECKING:
    from .plugin import Plugin
    from .host import PluginHost

__all__ = ["set_timeout", "set_interval", "Timer"]


class Timer(Resource):
    """A timer resource that can be cancelled."""

    def __init__(
        self,
        plugin: "Plugin",
        callback: Callable[[], Any],
        delay: float,
        repeat: bool = False,
    ) -> None:
        """Initialize the timer.

        Args:
            plugin: The plugin that owns this timer.
            callback: The function to call.
            delay: The delay in seconds.
            repeat: If True, repeat the timer.
        """
        super().__init__(plugin)
        self.callback = callback
        self.delay = delay
        self.repeat = repeat
        self._timer: Optional[threading.Timer] = None
        self._cancelled = False

        # Start the timer
        self._schedule()

    def _schedule(self) -> None:
        """Schedule the timer."""
        if self._cancelled or not self._enabled:
            return

        self._timer = threading.Timer(self.delay, self._run)
        self._timer.start()

    def _run(self) -> None:
        """Run the timer callback."""
        if self._cancelled or not self._enabled:
            return

        # Run in plugin context
        with plugin_context(self.plugin.host, self.plugin):
            self.callback()

        # Reschedule if repeating
        if self.repeat and not self._cancelled:
            self._schedule()

    def cancel(self) -> None:
        """Cancel the timer."""
        self._cancelled = True
        if self._timer is not None:
            self._timer.cancel()

    def _cleanup(self) -> None:
        """Clean up the timer."""
        self.cancel()


def set_timeout(callback: Callable[[], Any], delay: float = 0) -> Timer:
    """Schedule a function to be called after a delay.

    Args:
        callback: The function to call.
        delay: The delay in seconds (default: 0).

    Returns:
        A Timer that can be cancelled.

    Raises:
        RuntimeError: If called outside a plugin context.
    """
    from . import host
    
    plugin = host.get_current_plugin()
    if plugin is None:
        raise RuntimeError("set_timeout() must be called from within a plugin context")

    timer = Timer(plugin, callback, delay, repeat=False)
    plugin.host.resource_manager.register(timer)
    return timer


def set_interval(callback: Callable[[], Any], delay: float) -> Timer:
    """Schedule a function to be called repeatedly.

    Args:
        callback: The function to call.
        delay: The delay in seconds between calls.

    Returns:
        A Timer that can be cancelled.

    Raises:
        RuntimeError: If called outside a plugin context.
    """
    from . import host
    
    plugin = host.get_current_plugin()
    if plugin is None:
        raise RuntimeError("set_interval() must be called from within a plugin context")

    timer = Timer(plugin, callback, delay, repeat=True)
    plugin.host.resource_manager.register(timer)
    return timer
