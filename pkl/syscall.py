"""System calls: functions that run as the plugin that defined them."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

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

    This is ``plugins.bind(func)``: works for plain and ``async`` functions, and
    the caller's plugin is restored afterwards.

    Bind the tracker once per application with ``functools.partial``::

        syscall = partial(pkl.syscall.syscall, plugins)
    """
    return plugins.bind(func)
