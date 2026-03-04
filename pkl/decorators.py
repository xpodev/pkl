"""Decorators for plugin system."""

from __future__ import annotations

import functools
import inspect
from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast

from .context import plugin_context

if TYPE_CHECKING:
    from .plugin import Plugin

__all__ = ["syscall"]

F = TypeVar("F", bound=Callable[..., Any])


def syscall(func: F) -> F:
    """Decorator that preserves the plugin context.

    When a function decorated with @syscall is called, the current plugin
    is set to the plugin that defined the function, not the plugin that
    called it.

    This is useful for API functions that should run in the context of
    the plugin that provides them.

    Args:
        func: The function to decorate.

    Returns:
        The decorated function.
    """
    # Import here to avoid circular dependency
    from . import host
    
    # Capture the plugin that defined the decorated function
    defining_plugin = host.get_current_plugin()

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with plugin_context(host, defining_plugin):
                return await func(*args, **kwargs)

        return cast(F, async_wrapper)
    else:

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with plugin_context(host, defining_plugin):
                return func(*args, **kwargs)

        return cast(F, sync_wrapper)
