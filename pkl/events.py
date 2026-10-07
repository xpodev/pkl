"""Events: a plugin (or the host) announces something, others react to it.

An ``Event`` is a resource. Whoever creates it owns it - a plugin, or the host
when no plugin is executing. By default only the owner may invoke it
(``protected``); anybody may subscribe. Subscriptions are resources of the
*subscriber*, so releasing a subscriber's lifetime removes its handlers. There
is no subscription control: an event that must not be subscribed to should not
be part of the plugin's public API.

Create events with the decorator that ``event_decorator`` builds for your
application's lifetime (once, in the SDK)::

    event = events.event_decorator(runtime_tracker)

    @event
    def user_joined(name: str) -> None: ...

    @event(protected=False)          # anyone may invoke this one
    def ping() -> None: ...

A generator function gives an event code that runs before and after its
handlers, as the owner::

    @event
    def user_joined(name: str) -> Generator[None, None, None]:
        print("before handlers")
        yield
        print("after handlers")
"""

from __future__ import annotations

import dataclasses
import inspect
import threading
from collections.abc import Callable
from typing import Any, Generic, ParamSpec, Protocol, Self, cast, overload

from .errors import PklError
from .plugin import Plugin
from .tracking import Callback, CallbackReleasedError, ResourceTracker, Tracked

__all__ = [
    "Event",
    "EventDecorator",
    "Subscription",
    "EventPermissionError",
    "EventReleasedError",
    "event_decorator",
]

Params = ParamSpec("Params")


class EventPermissionError(PklError, RuntimeError):
    """Raised when a plugin does something to an event that only another may do."""


class EventReleasedError(PklError, RuntimeError):
    """Raised when a released event is subscribed to or invoked."""


def _describe(plugin: Plugin | None) -> str:
    return "the host" if plugin is None else repr(plugin)


class Subscription(Callback[Params, object]):
    """A handler's subscription to an event.

    A subscription is a ``Callback`` created by whoever subscribed: it runs the
    handler as the subscriber, wherever and by whomever the event is invoked,
    and it is a resource of the subscriber. Releasing it - by hand, or by
    releasing the subscriber's lifetime - removes the handler from the event. A
    subscription made by the host (no plugin executing) belongs to nobody and
    lasts until the event or the subscription itself is released.
    """

    def __init__(self, event: Event[Params], handler: Callable[Params, object]) -> None:
        super().__init__(handler)
        self.event = event

    @property
    def handler(self) -> Callable[Params, object]:
        """The subscribed handler."""
        return self.func

    @property
    def subscriber(self) -> Plugin | None:
        """The plugin that subscribed, or ``None`` for the host."""
        return self.owner

    def on_release(self) -> None:
        self.event._remove(self)
        super().on_release()


class Event(Tracked[Any], Generic[Params]):
    """An event that anybody can subscribe to.

    Prefer the decorator from ``event_decorator`` over calling this directly.

    Args:
        func: Defines the event's signature. If it is a generator function, the
            code before its ``yield`` runs before the handlers and the code
            after it runs after them, both as the owner. Returning (or ending)
            before the ``yield`` cancels the invocation.
        protected: If true (the default), only the owner may invoke the event.
            With ``protected=False`` anybody may.
    """

    def __init__(self, func: Callable[Params, Any], *, protected: bool = True) -> None:
        self.name: str = getattr(func, "__name__", repr(func))
        self.__doc__ = func.__doc__
        self.is_protected = protected
        self._generator = func if inspect.isgeneratorfunction(func) else None
        self._subscriptions: list[Subscription[Params]] = []
        self._lock = threading.Lock()

    # -- subscribing ---------------------------------------------------------

    def subscribe(self, handler: Callable[Params, object]) -> Subscription[Params]:
        """Subscribe ``handler`` on behalf of the plugin that is executing.

        The handler will run as that plugin (as the host if none is executing).
        Anybody may subscribe.

        Raises:
            EventReleasedError: If the event was released.
        """
        # The subscription is a callback created *as the subscriber* (this code
        # runs as whoever called subscribe, even if it is the event owner's
        # non-syscall API), so it runs the handler as the subscriber later.
        # Host subscribers are always fine, whatever the tracker says about orphans.
        variant: Any = Subscription._variant(dataclasses.replace(self.tracker, allow_orphans=True))
        subscription: Subscription[Params] = variant(self, handler)
        with self._lock:
            accepted = not self.released
            if accepted:
                self._subscriptions.append(subscription)
        if not accepted:
            subscription.release()  # outside the lock: releasing takes it
            raise EventReleasedError(f"event {self.name!r} was released")
        return subscription

    def unsubscribe(self, handler: Callable[Params, object]) -> bool:
        """Remove the handler the executing plugin subscribed.

        Returns:
            Whether a subscription was found and removed.
        """
        subscriber = self.tracker.plugins.current
        with self._lock:
            found = next(
                (
                    s
                    for s in self._subscriptions
                    if s.subscriber is subscriber and s.handler == handler
                ),
                None,
            )
        if found is None:
            return False
        found.release()
        return True

    def on(self, handler: Callable[Params, object]) -> Callable[Params, object]:
        """Decorator form of ``subscribe``; returns the handler unchanged."""
        self.subscribe(handler)
        return handler

    def __iadd__(self, handler: Callable[Params, object]) -> Self:
        self.subscribe(handler)
        return self

    def __isub__(self, handler: Callable[Params, object]) -> Self:
        self.unsubscribe(handler)
        return self

    @property
    def subscriptions(self) -> tuple[Subscription[Params], ...]:
        """The active subscriptions, oldest first."""
        with self._lock:
            return tuple(self._subscriptions)

    # -- invoking ------------------------------------------------------------

    def __call__(self, *args: Params.args, **kwargs: Params.kwargs) -> None:
        """Invoke the event, running every handler as its subscriber.

        Raises:
            EventPermissionError: If the event is protected and the caller is not the owner.
            EventReleasedError: If the event was released.
        """
        self._check_invoker()
        generator = self._start(args, kwargs)
        if generator is False:
            return
        for subscription in self.subscriptions:
            try:
                subscription(*args, **kwargs)  # runs as the subscriber
            except CallbackReleasedError:
                continue  # unsubscribed while this invocation was in progress
        self._finish(generator)

    async def emit(self, *args: Params.args, **kwargs: Params.kwargs) -> None:
        """Invoke the event, awaiting handlers that return awaitables.

        Handlers run one after the other, each as its subscriber, also across
        awaits.
        """
        self._check_invoker()
        generator = self._start(args, kwargs)
        if generator is False:
            return
        for subscription in self.subscriptions:
            try:
                result = subscription(*args, **kwargs)  # runs as the subscriber
            except CallbackReleasedError:
                continue
            if inspect.isawaitable(result):
                await result
        self._finish(generator)

    def _check_invoker(self) -> None:
        if self.released:
            raise EventReleasedError(f"event {self.name!r} was released")
        if self.is_protected and self.tracker.plugins.current is not self.owner:
            raise EventPermissionError(
                f"event {self.name!r} is protected and can only be invoked by "
                f"{_describe(self.owner)}"
            )

    def _start(self, args: Any, kwargs: Any) -> Any:
        """Run the code before the handlers. Returns False if the invocation is cancelled."""
        if self._generator is None:
            return None
        # The event's own code is the owner's code, whoever invokes the event.
        with self.tracker.plugins.executing(self.owner):
            generator = self._generator(*args, **kwargs)
            try:
                next(generator)
            except StopIteration:
                return False
        return generator

    def _finish(self, generator: Any) -> None:
        """Run the code after the handlers."""
        if generator is None:
            return
        with self.tracker.plugins.executing(self.owner):
            try:
                next(generator)
            except StopIteration:
                pass

    # -- lifetime ------------------------------------------------------------

    def _remove(self, subscription: Subscription[Params]) -> None:
        with self._lock:
            try:
                self._subscriptions.remove(subscription)
            except ValueError:
                pass

    def on_release(self) -> None:
        with self._lock:
            subscriptions = list(self._subscriptions)
        for subscription in subscriptions:
            subscription.release()


class EventDecorator(Protocol):
    """What ``event_decorator`` builds: usable as ``@event`` and ``@event(protected=...)``."""

    @overload
    def __call__(self, func: Callable[Params, Any], /) -> Event[Params]: ...

    @overload
    def __call__(
        self, *, protected: bool = True
    ) -> Callable[[Callable[Params, Any]], Event[Params]]: ...


def event_decorator(source: ResourceTracker[Any] | type[Event[Any]]) -> EventDecorator:
    """Build the ``event`` decorator for an application's lifetime.

    Call this once, in the SDK, with the tracker the events belong to (or with
    an ``Event`` subclass already bound to one)::

        event = events.event_decorator(runtime_tracker)

        @event
        def user_joined(name: str) -> None: ...

        @event(protected=False)       # anybody may invoke it
        def ping() -> None: ...

    The decorated function defines the event's signature; the name becomes the
    event, owned by the plugin that is executing when it is defined (the host
    if none is).
    """
    event_type: Any = (
        Event._variant(source) if isinstance(source, ResourceTracker) else source
    )

    def decorator(func: Any = None, /, *, protected: bool = True) -> Any:
        def create(function: Callable[..., Any]) -> Event[Any]:
            return cast("Event[Any]", event_type(function, protected=protected))

        return create if func is None else create(func)

    return cast("EventDecorator", decorator)
