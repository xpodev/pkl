"""Events: a plugin (or the host) announces something, others react to it.

An ``Event`` is a resource. Whoever creates it owns it - a plugin, or the host
when no plugin is executing - and only the owner may invoke it. Other plugins
subscribe; their subscriptions are resources of the *subscriber*, so releasing
a subscriber's lifetime removes its handlers.

Bind ``Event`` to an application's lifetime like any other ``Tracked``
resource::

    class Event(events.Event[Params], RuntimeResource): ...

    @Event
    def user_joined(name: str) -> None: ...

A generator function gives an event code that runs before and after its
handlers::

    @Event
    def user_joined(name: str) -> Generator[None, None, None]:
        print("before handlers")
        yield
        print("after handlers")
"""

from __future__ import annotations

import inspect
import threading
from collections.abc import Callable
from typing import Any, Generic, ParamSpec, Self

from .errors import PklError
from .plugin import Plugin
from .tracking import Tracked

__all__ = [
    "Event",
    "Subscription",
    "EventPermissionError",
    "EventReleasedError",
]

Params = ParamSpec("Params")


class EventPermissionError(PklError, RuntimeError):
    """Raised when a plugin does something to an event that only another may do."""


class EventReleasedError(PklError, RuntimeError):
    """Raised when a released event is subscribed to or invoked."""


def _describe(plugin: Plugin | None) -> str:
    return "the host" if plugin is None else repr(plugin)


class Subscription(Generic[Params]):
    """A handler's subscription to an event.

    It is a resource of the subscriber: releasing it - by hand, or by releasing
    the subscriber's lifetime - removes the handler from the event. A
    subscription made by the host (no plugin executing) belongs to nobody and
    lasts until the event or the subscription itself is released.
    """

    def __init__(
        self, event: Event[Params], handler: Callable[Params, object], subscriber: Plugin | None
    ) -> None:
        self.event = event
        self.handler = handler
        self.subscriber = subscriber
        self._active = True

    @property
    def active(self) -> bool:
        """Whether the handler is still subscribed."""
        return self._active

    def release(self) -> None:
        """Remove the handler from the event. Safe to call more than once."""
        if not self._active:
            return
        self._active = False
        self.event._remove(self)
        if self.subscriber is not None:
            self.event.tracker.registry.unregister(self.subscriber, self)


class Event(Tracked[Any], Generic[Params]):
    """An event that plugins can subscribe to and only its owner can invoke.

    Args:
        func: Defines the event's signature. If it is a generator function, the
            code before its ``yield`` runs before the handlers and the code
            after it runs after them. Returning (or ending) before the ``yield``
            cancels the invocation.
        protected: If true, only the owner may subscribe (a host-owned event
            can then only be subscribed to by the host).
    """

    def __init__(self, func: Callable[Params, Any], *, protected: bool = False) -> None:
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

        Raises:
            EventPermissionError: If the event is protected and the caller is not its owner.
            EventReleasedError: If the event was released.
        """
        subscriber = self.tracker.plugins.current
        if self.is_protected and subscriber is not self.owner:
            raise EventPermissionError(
                f"event {self.name!r} is protected and can only be subscribed to by "
                f"{_describe(self.owner)}"
            )
        subscription = Subscription(self, handler, subscriber)
        with self._lock:
            if self.released:
                raise EventReleasedError(f"event {self.name!r} was released")
            self._subscriptions.append(subscription)
        if subscriber is not None:
            self.tracker.registry.register(subscriber, subscription)
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
            EventPermissionError: If the caller is not the owner.
            EventReleasedError: If the event was released.
        """
        self._check_invoker()
        generator = self._start(args, kwargs)
        if generator is False:
            return
        for subscription in self.subscriptions:
            if not subscription.active:
                continue
            with self.tracker.plugins.executing(subscription.subscriber):
                subscription.handler(*args, **kwargs)
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
            if not subscription.active:
                continue
            with self.tracker.plugins.executing(subscription.subscriber):
                result = subscription.handler(*args, **kwargs)
                if inspect.isawaitable(result):
                    await result
        self._finish(generator)

    def _check_invoker(self) -> None:
        if self.released:
            raise EventReleasedError(f"event {self.name!r} was released")
        if self.tracker.plugins.current is not self.owner:
            raise EventPermissionError(
                f"event {self.name!r} can only be invoked by {_describe(self.owner)}"
            )

    def _start(self, args: Any, kwargs: Any) -> Any:
        """Run the code before the handlers. Returns False if the invocation is cancelled."""
        if self._generator is None:
            return None
        generator = self._generator(*args, **kwargs)
        try:
            next(generator)
        except StopIteration:
            return False
        return generator

    @staticmethod
    def _finish(generator: Any) -> None:
        """Run the code after the handlers."""
        if generator is None:
            return
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
