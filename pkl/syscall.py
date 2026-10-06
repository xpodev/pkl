"""System calls: functions that run as the plugin that defined them."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar, cast

from .plugin_tracker import PluginTracker

__all__ = ["syscall"]

Params = ParamSpec("Params")
T = TypeVar("T")


def syscall(plugins: PluginTracker[Any], func: Callable[Params, T]) -> Callable[Params, T]:
    """Make ``func`` run as the plugin that defined it, whoever calls it.

    The defining plugin is the one executing when ``syscall`` is applied, i.e.
    while the plugin's code is being loaded. Resources the function creates are
    then attributed to the defining plugin, not to the caller. If no plugin is
    executing at definition time the function runs as the host.

    Works for plain and ``async`` functions; the caller's plugin is restored
    afterwards. Generators are not wrapped beyond their creation.

    Bind the tracker once per application with ``functools.partial``::

        syscall = partial(pkl.syscall.syscall, plugins)
    """
    owner = plugins.current

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with plugins.executing(owner):
                return await func(*args, **kwargs)

        return cast("Callable[Params, T]", async_wrapper)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with plugins.executing(owner):
            return func(*args, **kwargs)

    return cast("Callable[Params, T]", wrapper)
