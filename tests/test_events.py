"""Tests for pkl.events."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from typing import Any

import pytest

from pkl import Plugin, PluginTracker, ResourceRegistry
from pkl.events import (
    Event,
    EventPermissionError,
    EventReleasedError,
    Subscription,
    event_decorator,
)
from pkl.tracking import ResourceTracker


class Env:
    def __init__(self) -> None:
        self.plugins = PluginTracker[Plugin]()
        self.registry = ResourceRegistry[Plugin]()
        self.tracker = ResourceTracker(self.plugins, self.registry, allow_orphans=True)
        self.event_type = Event[Any].with_tracker(self.tracker)

    def event(self, func: Callable[..., Any], *, protected: bool = True) -> Event[Any]:
        return self.event_type(func, protected=protected)


@pytest.fixture
def env() -> Env:
    return Env()


def appender(into: list[Any], value: Callable[[], Any]) -> Callable[..., None]:
    """A handler that records ``value()`` whenever it is called."""

    def handler(*_: Any) -> None:
        into.append(value())

    return handler


def noop(message: str = "") -> None:
    """An event signature."""


# --- ownership ---------------------------------------------------------------


def test_event_created_by_a_plugin_is_owned_and_tracked(env: Env) -> None:
    plugin = Plugin()
    with env.plugins.executing(plugin):
        event = env.event(noop)
    assert event.owner is plugin
    assert event.name == "noop"
    assert event.__doc__ == "An event signature."
    assert env.registry.resources(plugin) == (event,)


def test_event_created_by_the_host_has_no_owner(env: Env) -> None:
    event = env.event(noop)
    assert event.owner is None
    assert env.registry.plugins() == ()


# --- who may invoke ----------------------------------------------------------


def test_host_event_cannot_be_invoked_from_a_plugin(env: Env) -> None:
    event = env.event(noop)
    with env.plugins.executing(Plugin()):
        with pytest.raises(EventPermissionError, match="can only be invoked by the host"):
            event("x")


def test_host_event_can_be_invoked_by_the_host(env: Env) -> None:
    event = env.event(noop)
    received: list[str] = []
    event.subscribe(received.append)
    event("hello")
    assert received == ["hello"]


def test_plugin_event_cannot_be_invoked_by_another_plugin_or_the_host(env: Env) -> None:
    owner, other = Plugin(), Plugin()
    with env.plugins.executing(owner):
        event = env.event(noop)
    with pytest.raises(EventPermissionError):
        event("x")
    with env.plugins.executing(other):
        with pytest.raises(EventPermissionError):
            event("x")


def test_plugin_event_can_be_invoked_by_its_owner(env: Env) -> None:
    owner = Plugin()
    received: list[str] = []
    with env.plugins.executing(owner):
        event = env.event(noop)
        event.subscribe(received.append)
        event("hi")
    assert received == ["hi"]


# --- protected: who may invoke ------------------------------------------------


def test_events_are_protected_by_default(env: Env) -> None:
    owner = Plugin()
    with env.plugins.executing(owner):
        event = env.event_type(noop)
    assert event.is_protected
    with env.plugins.executing(Plugin()):
        with pytest.raises(EventPermissionError, match="protected"):
            event("x")


def test_unprotected_event_can_be_invoked_by_anyone(env: Env) -> None:
    owner, other = Plugin(), Plugin()
    received: list[str] = []
    with env.plugins.executing(owner):
        event = env.event(noop, protected=False)
        event.subscribe(received.append)
    event("from the host")
    with env.plugins.executing(other):
        event("from another plugin")
    with env.plugins.executing(owner):
        event("from the owner")
    assert received == ["from the host", "from another plugin", "from the owner"]


def test_unprotected_host_event_can_be_invoked_by_a_plugin(env: Env) -> None:
    event = env.event(noop, protected=False)
    received: list[str] = []
    event.subscribe(received.append)
    with env.plugins.executing(Plugin()):
        event("x")
    assert received == ["x"]


def test_there_is_no_subscription_control(env: Env) -> None:
    owner, other = Plugin(), Plugin()
    for protected in (True, False):
        with env.plugins.executing(owner):
            event = env.event(noop, protected=protected)
        event.subscribe(print)  # the host
        with env.plugins.executing(other):
            event.subscribe(print)  # another plugin
        with env.plugins.executing(owner):
            event.subscribe(print)  # the owner
        assert len(event.subscriptions) == 3


def test_generator_code_of_an_unprotected_event_runs_as_the_owner(env: Env) -> None:
    owner, invoker, subscriber = Plugin(), Plugin(), Plugin()
    seen: list[tuple[str, Plugin | None]] = []

    def signature(value: str) -> Generator[None, None, None]:
        seen.append(("before", env.plugins.current))
        yield
        seen.append(("after", env.plugins.current))

    with env.plugins.executing(owner):
        event = env.event(signature, protected=False)

    def handler(value: str) -> None:
        seen.append(("handler", env.plugins.current))

    with env.plugins.executing(subscriber):
        event.subscribe(handler)
    with env.plugins.executing(invoker):
        event("v")
        assert env.plugins.current is invoker
    assert seen == [("before", owner), ("handler", subscriber), ("after", owner)]


# --- the decorator -----------------------------------------------------------


def test_decorator_creates_events_owned_by_the_defining_plugin(env: Env) -> None:
    event = event_decorator(env.tracker)
    plugin = Plugin()
    with env.plugins.executing(plugin):

        @event
        def user_joined(name: str) -> None:
            """Someone joined."""

    assert isinstance(user_joined, Event)
    assert user_joined.name == "user_joined"
    assert user_joined.__doc__ == "Someone joined."
    assert user_joined.owner is plugin
    assert user_joined.is_protected
    assert env.registry.resources(plugin) == (user_joined,)


def test_decorator_accepts_options(env: Env) -> None:
    event = event_decorator(env.tracker)

    @event(protected=False)
    def open_event() -> None: ...

    @event()
    def default_event() -> None: ...

    assert not open_event.is_protected
    assert default_event.is_protected


def test_decorator_can_be_built_from_a_bound_event_class(env: Env) -> None:
    class AppEvent(Event[Any], tracker=env.tracker):
        pass

    event = event_decorator(AppEvent)

    @event
    def thing() -> None: ...

    assert isinstance(thing, AppEvent)


def test_decorator_is_a_plain_function() -> None:
    import inspect

    env = Env()
    assert inspect.isfunction(event_decorator(env.tracker))


# --- handlers ----------------------------------------------------------------


def test_handlers_run_as_their_subscriber(env: Env) -> None:
    owner, sub_a, sub_b = Plugin(), Plugin(), Plugin()
    seen: list[Plugin | None] = []
    with env.plugins.executing(owner):
        event = env.event(noop)
    with env.plugins.executing(sub_a):
        event.subscribe(appender(seen, lambda: env.plugins.current))
    with env.plugins.executing(sub_b):
        event.subscribe(appender(seen, lambda: env.plugins.current))
    event.subscribe(appender(seen, lambda: env.plugins.current))  # the host's
    with env.plugins.executing(owner):
        event("x")
        assert env.plugins.current is owner
    assert seen == [sub_a, sub_b, None]


def test_handlers_run_in_subscription_order(env: Env) -> None:
    event = env.event(noop)
    order: list[int] = []
    for number in range(3):
        event.subscribe(appender(order, lambda n=number: n))  # type: ignore[misc]
    event("x")
    assert order == [0, 1, 2]


def test_on_decorator_and_operators(env: Env) -> None:
    event = env.event(noop)
    received: list[str] = []

    @event.on
    def handler(message: str = "") -> None:
        received.append(message)

    event("a")
    event -= handler
    event("b")
    event += handler
    event("c")
    assert received == ["a", "c"]


def test_unsubscribe_is_per_subscriber(env: Env) -> None:
    owner, sub = Plugin(), Plugin()
    with env.plugins.executing(owner):
        event = env.event(noop)
    received: list[str] = []
    with env.plugins.executing(sub):
        event.subscribe(received.append)
    assert event.unsubscribe(received.append) is False  # the host did not subscribe it
    with env.plugins.executing(sub):
        assert event.unsubscribe(received.append) is True
    assert event.subscriptions == ()


def test_a_handler_released_during_invocation_is_skipped(env: Env) -> None:
    event = env.event(noop)
    calls: list[str] = []
    later: list[Subscription[Any]] = []

    def first(_: str = "") -> None:
        calls.append("first")
        later[0].release()

    event.subscribe(first)
    later.append(event.subscribe(appender(calls, lambda: "second")))
    event("x")
    assert calls == ["first"]


# --- generator events --------------------------------------------------------


def test_generator_runs_before_and_after_handlers(env: Env) -> None:
    log: list[str] = []

    def signature(value: str) -> Generator[None, None, None]:
        log.append(f"before {value}")
        yield
        log.append(f"after {value}")

    event = env.event(signature)

    def handler(value: str) -> None:
        log.append(f"handler {value}")

    event.subscribe(handler)
    event("v")
    assert log == ["before v", "handler v", "after v"]


def test_generator_ending_before_yield_cancels_the_invocation(env: Env) -> None:
    called: list[str] = []

    def signature(value: str) -> Generator[None, None, None]:
        return
        yield  # pragma: no cover

    event = env.event(signature)
    event.subscribe(called.append)
    event("v")
    assert called == []


# --- lifetime ----------------------------------------------------------------


def test_subscriptions_are_released_with_the_subscriber(env: Env) -> None:
    owner, subscriber = Plugin(), Plugin()
    with env.plugins.executing(owner):
        event = env.event(noop)
    received: list[str] = []
    with env.plugins.executing(subscriber):
        event.subscribe(received.append)
    host_received: list[str] = []
    event.subscribe(host_received.append)

    env.registry.release(subscriber)
    with env.plugins.executing(owner):
        event("x")
    assert received == []
    assert host_received == ["x"]  # the host's subscription persists


def test_manually_released_subscription_leaves_no_registry_entry(env: Env) -> None:
    owner, subscriber = Plugin(), Plugin()
    with env.plugins.executing(owner):
        event = env.event(noop)
    with env.plugins.executing(subscriber):
        subscription = event.subscribe(print)
    assert env.registry.resources(subscriber) == (subscription,)
    subscription.release()
    subscription.release()
    assert env.registry.resources(subscriber) == ()


def test_releasing_the_owner_drops_all_subscriptions(env: Env) -> None:
    owner, subscriber = Plugin(), Plugin()
    with env.plugins.executing(owner):
        event = env.event(noop)
    with env.plugins.executing(subscriber):
        subscription = event.subscribe(print)
    env.registry.release(owner)
    assert event.released
    assert not subscription.active
    assert env.registry.resources(subscriber) == ()


def test_released_event_cannot_be_subscribed_or_invoked(env: Env) -> None:
    event = env.event(noop)
    event.release()
    with pytest.raises(EventReleasedError):
        event.subscribe(print)
    with pytest.raises(EventReleasedError):
        event("x")


# --- async -------------------------------------------------------------------


async def test_emit_awaits_async_handlers_as_their_subscribers(env: Env) -> None:
    owner = Plugin()
    subscribers = [Plugin() for _ in range(3)]
    with env.plugins.executing(owner):
        event = env.event(noop)
    seen: list[tuple[Plugin, Plugin | None]] = []

    def make_handler(plugin: Plugin) -> Callable[[str], Any]:
        async def handler(message: str) -> None:
            await asyncio.sleep(0.001)
            seen.append((plugin, env.plugins.current))

        return handler

    for plugin in subscribers:
        with env.plugins.executing(plugin):
            event.subscribe(make_handler(plugin))

    with env.plugins.executing(owner):
        await event.emit("x")
        assert env.plugins.current is owner
    assert seen == [(p, p) for p in subscribers]


async def test_interleaved_emits_from_different_owners_keep_subscribers_straight(
    env: Env,
) -> None:
    owners = [Plugin(), Plugin()]
    events: list[Event[Any]] = []
    for owner in owners:
        with env.plugins.executing(owner):
            events.append(env.event(noop))
    subscriber = Plugin()
    seen: list[Plugin | None] = []

    async def handler(message: str = "") -> None:
        await asyncio.sleep(0.001)
        seen.append(env.plugins.current)

    with env.plugins.executing(subscriber):
        for event in events:
            event.subscribe(handler)

    async def run(owner: Plugin, event: Event[Any]) -> None:
        with env.plugins.executing(owner):
            await event.emit("x")
            assert env.plugins.current is owner

    await asyncio.gather(*(run(o, e) for o, e in zip(owners, events)))
    assert seen == [subscriber, subscriber]
