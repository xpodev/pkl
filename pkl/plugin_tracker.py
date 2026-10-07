"""Keeping track of the plugin that is currently executing."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generic, ParamSpec, TypeVar, cast

from .errors import NoCurrentPluginError
from .plugin import Plugin

__all__ = ["PluginTracker"]

P = TypeVar("P", bound=Plugin)
Params = ParamSpec("Params")
T = TypeVar("T")


class PluginTracker(Generic[P]):
    """Knows which plugin is currently executing.

    The current plugin is what resources get attributed to. It is scoped to
    the current context (thread / ``asyncio`` task), so concurrent tasks that
    run as different plugins never see each other's plugin.

    Trackers are independent of one another: a process may have as many as it
    likes. There is no default tracker.

    Note:
        New threads start with an empty context. Code that hands work to a
        plain ``threading.Thread`` must run it under ``executing()`` (or inside
        ``contextvars.copy_context().run``) to keep the plugin.
    """

    def __init__(self) -> None:
        # One ContextVar per tracker keeps trackers independent.
        self._current: ContextVar[P | None] = ContextVar(
            f"pkl.PluginTracker@{id(self):x}", default=None
        )

    @property
    def current(self) -> P | None:
        """The plugin currently executing, or ``None`` when the host is."""
        return self._current.get()

    def require_current(self) -> P:
        """Return the current plugin.

        Raises:
            NoCurrentPluginError: If no plugin is executing.
        """
        plugin = self._current.get()
        if plugin is None:
            raise NoCurrentPluginError("no plugin is currently executing")
        return plugin

    @contextmanager
    def executing(self, plugin: P | None) -> Iterator[P | None]:
        """Run the enclosed block as ``plugin``.

        Nests: the previous plugin is restored on exit, also on error.
        ``None`` means "run as the host", i.e. as no plugin at all.
        """
        token = self._current.set(plugin)
        try:
            yield plugin
        finally:
            self._current.reset(token)

    def bind(self, func: Callable[Params, T]) -> Callable[Params, T]:
        """Bind ``func`` to the plugin executing *now*.

        The returned function runs as that plugin (as the host if none is
        executing), whoever calls it and from whichever thread or task, and
        restores the caller's plugin afterwards. This is the one place that
        turns "who created this" into "who runs this": use it for callbacks
        and thread entry points instead of re-entering the plugin by hand.

        ``async`` functions stay ``async`` and run as the plugin across their
        awaits. A plain function that merely *returns* an awaitable only runs
        as the plugin while it is being called, not while that is awaited.
        """
        return self.bind_as(self._current.get(), func)

    def bind_as(self, plugin: P | None, func: Callable[Params, T]) -> Callable[Params, T]:
        """Like ``bind``, for an explicit plugin (``None`` runs as the host)."""
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_bound(*args: Any, **kwargs: Any) -> Any:
                with self.executing(plugin):
                    return await func(*args, **kwargs)

            return cast("Callable[Params, T]", async_bound)

        @functools.wraps(func)
        def bound(*args: Any, **kwargs: Any) -> Any:
            with self.executing(plugin):
                return func(*args, **kwargs)

        return cast("Callable[Params, T]", bound)
