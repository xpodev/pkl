"""Static typing checks, verified by ``mypy --strict`` (never executed by pytest).

Every ``# type: ignore[...]`` below must be *needed*: with ``warn_unused_ignores``
(part of ``--strict``) mypy fails if the line stops being an error.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import assert_type

from pkl import Plugin, PluginTracker, ResourceRegistry
from pkl.events import Event, event_decorator
from pkl.syscall import syscall
from pkl.tracking import ResourceTracker, Tracked


class AppPlugin(Plugin):
    name: str


def plugin_tracker_is_typed_by_the_derived_plugin() -> None:
    tracker = PluginTracker[AppPlugin]()
    assert_type(tracker.current, AppPlugin | None)
    assert_type(tracker.require_current(), AppPlugin)
    registry = ResourceRegistry[AppPlugin]()
    registry.register(AppPlugin(), Timer())
    registry.register(Plugin(), Timer())  # type: ignore[arg-type]


class Timer:
    def release(self) -> None: ...


def tracked_owner_is_typed() -> None:
    class Resource(Tracked[AppPlugin]):
        def on_release(self) -> None: ...

    resource = Resource()
    assert_type(resource.owner, AppPlugin | None)


def events_are_typed_by_their_signature() -> None:
    def user_joined(name: str, level: int) -> None: ...

    event = Event(user_joined)

    def good(name: str, level: int) -> None: ...

    def bad(name: int) -> None: ...

    event.subscribe(good)
    event.subscribe(bad)  # type: ignore[arg-type]
    event("a", 1)
    event("a", "b")  # type: ignore[arg-type]
    event("a")  # type: ignore[call-arg]


def generator_events_keep_their_signature() -> None:
    def signature(value: int) -> Generator[None, None, None]:
        yield

    generator_event = Event(signature)
    generator_event(1)
    generator_event("x")  # type: ignore[arg-type]


def syscall_preserves_signatures() -> None:
    plugins = PluginTracker[Plugin]()

    def add(a: int, b: int) -> int:
        return a + b

    wrapped = syscall(plugins, add)
    assert_type(wrapped(1, 2), int)
    wrapped("1", 2)  # type: ignore[arg-type]


def resource_tracker_is_generic_over_the_plugin() -> None:
    tracker = ResourceTracker(PluginTracker[AppPlugin](), ResourceRegistry[AppPlugin]())
    assert_type(tracker.current_owner(), AppPlugin | None)


def bind_and_callback_preserve_signatures() -> None:
    plugins = PluginTracker[Plugin]()

    def add(a: int, b: int) -> int:
        return a + b

    bound = plugins.bind(add)
    assert_type(bound(1, 2), int)
    bound("1", 2)  # type: ignore[arg-type]

    tracker = ResourceTracker(plugins, ResourceRegistry[Plugin](), allow_orphans=True)
    callback = tracker.callback(add)
    assert_type(callback(1, 2), int)
    callback("1", 2)  # type: ignore[arg-type]


def the_event_decorator_keeps_signatures() -> None:
    plugins = PluginTracker[Plugin]()
    tracker = ResourceTracker(plugins, ResourceRegistry[Plugin](), allow_orphans=True)
    event = event_decorator(tracker)

    @event
    def joined(name: str) -> None: ...

    @event(protected=False)
    def left(name: str, reason: int) -> None: ...

    joined("a")
    joined(1)  # type: ignore[arg-type]
    left("a", 1)
    left("a")  # type: ignore[call-arg]
    joined.subscribe(lambda name: None)
    assert isinstance(joined, Event)


def hosts_and_dependencies_are_typed() -> None:
    from pkl.dependencies import Dependency, depends_on, require
    from pkl.hosting import PluginHost

    outer = ResourceTracker(PluginTracker[Plugin](), ResourceRegistry[Plugin](), allow_orphans=True)
    host = PluginHost[AppPlugin].with_tracker(outer)()
    assert_type(host.plugins, PluginTracker[AppPlugin])
    assert_type(host.plugins.current, AppPlugin | None)
    registry = host.registry()
    assert_type(registry.plugins(), tuple[AppPlugin, ...])
    assert_type(host.tracker_for(registry), ResourceTracker[AppPlugin])
    registry.register(Plugin(), Timer())  # type: ignore[arg-type]

    link = depends_on(registry, AppPlugin(), AppPlugin())
    assert_type(link, Dependency[AppPlugin])
    depends_on(registry, Plugin(), AppPlugin())  # type: ignore[misc]
    assert_type(require(host.tracker_for(registry), AppPlugin()), Dependency[AppPlugin])
