"""Tests for pkl.hosting: a plugin host as a resource."""

from __future__ import annotations

import threading

import pytest

from pkl import NoCurrentPluginError, Plugin, PluginTracker, ResourceRegistry
from pkl.hosting import HostedRegistry, HostReleasedError, PluginHost
from pkl.timing import Timer
from pkl.tracking import Callback, ResourceTracker


class Outer:
    """The application's own world: where a plugin that owns a host lives."""

    def __init__(self) -> None:
        self.plugins = PluginTracker[Plugin]()
        self.registry = ResourceRegistry[Plugin]()
        self.tracker = ResourceTracker(self.plugins, self.registry)
        self.host_type = PluginHost[Plugin].with_tracker(self.tracker)


class Recorder:
    def __init__(self, log: list[str], name: str, *, fail: bool = False) -> None:
        self.log, self.name, self.fail = log, name, fail

    def release(self) -> None:
        self.log.append(self.name)
        if self.fail:
            raise ValueError(self.name)


def test_a_host_is_a_resource_of_the_plugin_that_creates_it() -> None:
    outer, owner = Outer(), Plugin()
    with outer.plugins.executing(owner):
        host = outer.host_type()
    assert host.owner is owner
    assert outer.registry.resources(owner) == (host,)
    assert isinstance(host.plugins, PluginTracker)


def test_releasing_the_owner_releases_every_hosted_plugins_resources() -> None:
    outer, owner = Outer(), Plugin()
    log: list[str] = []
    s1, s2 = Plugin(), Plugin()
    with outer.plugins.executing(owner):
        host = outer.host_type()
    runtime, persistent = host.registry(), host.registry()
    runtime.register(s1, Recorder(log, "s1 runtime"))
    runtime.register(s2, Recorder(log, "s2 runtime"))
    persistent.register(s1, Recorder(log, "s1 persistent"))

    outer.registry.release(owner)

    # Newest lifetime first, and within a lifetime newest plugin first.
    assert log == ["s1 persistent", "s2 runtime", "s1 runtime"]
    assert host.released
    assert runtime.plugins() == () and persistent.plugins() == ()
    assert outer.registry.plugins() == ()


def test_releasing_the_owner_cancels_timers_of_hosted_plugins() -> None:
    outer, owner, sub = Outer(), Plugin(), Plugin()
    fired = threading.Event()
    with outer.plugins.executing(owner):
        host = outer.host_type()
    registry = host.registry()
    tracker = host.tracker_for(registry)
    with host.plugins.executing(sub):
        timer = Timer.with_tracker(tracker).timeout(fired.set, 0.1)
    assert registry.resources(sub) == (timer,)
    outer.registry.release(owner)
    assert timer.released
    assert not fired.wait(0.3)


def test_the_hosts_plugins_are_independent_of_the_outer_world() -> None:
    outer, owner, sub = Outer(), Plugin(), Plugin()
    with outer.plugins.executing(owner):
        host = outer.host_type()
        with host.plugins.executing(sub):
            assert host.plugins.current is sub
            assert outer.plugins.current is owner  # the owner is still the outer current plugin
    assert host.plugins.current is None


def test_a_host_can_be_given_an_existing_tracker() -> None:
    outer, owner = Outer(), Plugin()
    inner = PluginTracker[Plugin]()
    with outer.plugins.executing(owner):
        host = outer.host_type(inner)
    assert host.plugins is inner


def test_manual_release_is_idempotent_and_unregisters_from_the_owner() -> None:
    outer, owner = Outer(), Plugin()
    log: list[str] = []
    with outer.plugins.executing(owner):
        host = outer.host_type()
    host.registry().register(Plugin(), Recorder(log, "x"))
    host.release()
    host.release()
    assert log == ["x"]
    assert outer.registry.resources(owner) == ()


def test_a_released_host_accepts_nothing_new() -> None:
    outer, owner = Outer(), Plugin()
    with outer.plugins.executing(owner):
        host = outer.host_type()
    registry = host.registry()
    host.release()
    with pytest.raises(HostReleasedError):
        host.registry()
    with pytest.raises(HostReleasedError):
        registry.register(Plugin(), Recorder([], "late"))
    assert isinstance(registry, HostedRegistry)


def test_errors_are_collected_and_every_lifetime_is_still_released() -> None:
    outer, owner = Outer(), Plugin()
    log: list[str] = []
    with outer.plugins.executing(owner):
        host = outer.host_type()
    first, second = host.registry(), host.registry()
    first.register(Plugin(), Recorder(log, "first", fail=True))
    second.register(Plugin(), Recorder(log, "second", fail=True))
    with pytest.raises(ExceptionGroup):
        outer.registry.release(owner)
    assert log == ["second", "first"]
    assert host.released


def test_hosts_nest() -> None:
    outer, owner = Outer(), Plugin()
    log: list[str] = []
    with outer.plugins.executing(owner):
        middle = outer.host_type()
    middle_registry = middle.registry()
    middle_plugin = Plugin()  # a plugin of the middle host that has a host of its own
    middle_tracker = middle.tracker_for(middle_registry)
    with middle.plugins.executing(middle_plugin):
        inner = PluginHost[Plugin].with_tracker(middle_tracker)()
    inner_registry = inner.registry()
    inner_registry.register(Plugin(), Recorder(log, "innermost"))
    middle_registry.register(middle_plugin, Recorder(log, "middle plugin's own"))

    outer.registry.release(owner)

    assert sorted(log) == ["innermost", "middle plugin's own"]
    assert middle.released and inner.released


def test_a_host_needs_an_owner_unless_orphans_are_allowed() -> None:
    plugins = PluginTracker[Plugin]()
    registry = ResourceRegistry[Plugin]()
    strict = PluginHost[Plugin].with_tracker(ResourceTracker(plugins, registry))
    with pytest.raises(NoCurrentPluginError):
        strict()
    lenient = PluginHost[Plugin].with_tracker(ResourceTracker(plugins, registry, allow_orphans=True))
    host = lenient()
    assert host.owner is None
    host.registry().register(Plugin(), Recorder([], "x"))
    host.release()


def test_hosted_callbacks_stop_working_with_the_host() -> None:
    outer, owner, sub = Outer(), Plugin(), Plugin()
    with outer.plugins.executing(owner):
        host = outer.host_type()
    tracker = host.tracker_for(host.registry())
    with host.plugins.executing(sub):
        callback: Callback[[], str] = tracker.callback(lambda: "alive")
    assert callback() == "alive"
    outer.registry.release(owner)
    assert not callback.active
