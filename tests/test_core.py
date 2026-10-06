"""Tests for the four core concepts."""

from __future__ import annotations

import contextvars
import threading
from dataclasses import dataclass

import pytest

from pkl import (
    NoCurrentPluginError,
    Plugin,
    PluginTracker,
    Resource,
    ResourceRegistry,
)


class Recorder:
    """A resource that records the order in which resources are released."""

    def __init__(self, log: list[str], name: str, *, fail: bool = False) -> None:
        self.log = log
        self.name = name
        self.fail = fail

    def release(self) -> None:
        self.log.append(self.name)
        if self.fail:
            raise ValueError(self.name)


# --- Plugin -----------------------------------------------------------------


def test_plugins_are_equal_only_if_identical() -> None:
    a, b = Plugin(), Plugin()
    assert a is not b
    assert a != b
    assert a == a
    assert len({a, b}) == 2


def test_plugin_can_be_derived_to_carry_data() -> None:
    @dataclass(eq=False)
    class AppPlugin(Plugin):
        id: str
        name: str

    first, second = AppPlugin("1", "same"), AppPlugin("1", "same")
    assert first != second
    assert first.name == "same"


# --- PluginTracker ----------------------------------------------------------


def test_current_is_none_by_default() -> None:
    tracker = PluginTracker[Plugin]()
    assert tracker.current is None
    with pytest.raises(NoCurrentPluginError):
        tracker.require_current()


def test_executing_sets_and_restores_current() -> None:
    tracker = PluginTracker[Plugin]()
    a, b = Plugin(), Plugin()
    with tracker.executing(a) as entered:
        assert entered is a
        assert tracker.current is a
        assert tracker.require_current() is a
        with tracker.executing(b):
            assert tracker.current is b
        assert tracker.current is a
    assert tracker.current is None


def test_executing_none_runs_as_the_host() -> None:
    tracker = PluginTracker[Plugin]()
    with tracker.executing(Plugin()):
        with tracker.executing(None):
            assert tracker.current is None


def test_executing_restores_on_error() -> None:
    tracker = PluginTracker[Plugin]()
    with pytest.raises(RuntimeError):
        with tracker.executing(Plugin()):
            raise RuntimeError
    assert tracker.current is None


def test_trackers_are_independent() -> None:
    one, two = PluginTracker[Plugin](), PluginTracker[Plugin]()
    a = Plugin()
    with one.executing(a):
        assert one.current is a
        assert two.current is None


def test_current_is_thread_local() -> None:
    tracker = PluginTracker[Plugin]()
    seen: list[Plugin | None] = []
    with tracker.executing(Plugin()):
        thread = threading.Thread(target=lambda: seen.append(tracker.current))
        thread.start()
        thread.join()
    assert seen == [None]


def test_current_follows_a_copied_context() -> None:
    tracker = PluginTracker[Plugin]()
    a = Plugin()
    seen: list[Plugin | None] = []
    with tracker.executing(a):
        context = contextvars.copy_context()
    # The copy was taken while `a` was executing.
    thread = threading.Thread(target=lambda: context.run(lambda: seen.append(tracker.current)))
    thread.start()
    thread.join()
    assert seen == [a]


# --- ResourceRegistry -------------------------------------------------------


def test_release_releases_newest_first() -> None:
    registry = ResourceRegistry[Plugin]()
    plugin, log = Plugin(), list[str]()
    for name in "abc":
        registry.register(plugin, Recorder(log, name))
    registry.release(plugin)
    assert log == ["c", "b", "a"]
    assert registry.resources(plugin) == ()


def test_release_only_touches_the_given_plugin() -> None:
    registry = ResourceRegistry[Plugin]()
    a, b, log = Plugin(), Plugin(), list[str]()
    registry.register(a, Recorder(log, "a"))
    registry.register(b, Recorder(log, "b"))
    registry.release(a)
    assert log == ["a"]
    assert registry.plugins() == (b,)


def test_release_is_idempotent() -> None:
    registry = ResourceRegistry[Plugin]()
    plugin, log = Plugin(), list[str]()
    registry.register(plugin, Recorder(log, "a"))
    registry.release(plugin)
    registry.release(plugin)
    registry.release(Plugin())
    assert log == ["a"]


def test_registries_are_independent_lifetimes() -> None:
    disable, uninstall = ResourceRegistry[Plugin](), ResourceRegistry[Plugin]()
    plugin, log = Plugin(), list[str]()
    disable.register(plugin, Recorder(log, "runtime"))
    uninstall.register(plugin, Recorder(log, "persistent"))
    disable.release(plugin)
    assert log == ["runtime"]
    uninstall.release(plugin)
    assert log == ["runtime", "persistent"]


def test_release_continues_after_errors_and_groups_them() -> None:
    registry = ResourceRegistry[Plugin]()
    plugin, log = Plugin(), list[str]()
    registry.register(plugin, Recorder(log, "a"))
    registry.register(plugin, Recorder(log, "b", fail=True))
    registry.register(plugin, Recorder(log, "c", fail=True))
    with pytest.raises(ExceptionGroup) as info:
        registry.release(plugin)
    assert log == ["c", "b", "a"]
    assert [str(error) for error in info.value.exceptions] == ["c", "b"]
    assert registry.resources(plugin) == ()


def test_resources_registered_during_release_are_released_too() -> None:
    registry = ResourceRegistry[Plugin]()
    plugin, log = Plugin(), list[str]()

    class Spawner:
        def release(self) -> None:
            log.append("spawner")
            registry.register(plugin, Recorder(log, "late"))

    registry.register(plugin, Spawner())
    registry.release(plugin)
    assert log == ["spawner", "late"]
    assert registry.plugins() == ()


def test_a_resource_may_unregister_itself_while_released() -> None:
    registry = ResourceRegistry[Plugin]()
    plugin = Plugin()
    outcomes: list[bool] = []

    class SelfRemoving:
        def release(self) -> None:
            outcomes.append(registry.unregister(plugin, self))

    registry.register(plugin, SelfRemoving())
    registry.release(plugin)
    assert outcomes == [False]  # already taken out by the release in progress


def test_unregister_forgets_without_releasing() -> None:
    registry = ResourceRegistry[Plugin]()
    plugin, log = Plugin(), list[str]()
    resource = Recorder(log, "a")
    registry.register(plugin, resource)
    assert registry.unregister(plugin, resource) is True
    assert registry.unregister(plugin, resource) is False
    registry.release(plugin)
    assert log == []


def test_resources_and_plugins_report_registration_order() -> None:
    registry = ResourceRegistry[Plugin]()
    a, b, log = Plugin(), Plugin(), list[str]()
    first, second = Recorder(log, "1"), Recorder(log, "2")
    registry.register(a, first)
    registry.register(b, Recorder(log, "x"))
    registry.register(a, second)
    assert registry.resources(a) == (first, second)
    assert registry.plugins() == (a, b)


def test_release_all_releases_newest_plugin_first() -> None:
    registry = ResourceRegistry[Plugin]()
    a, b, log = Plugin(), Plugin(), list[str]()
    registry.register(a, Recorder(log, "a1"))
    registry.register(b, Recorder(log, "b1"))
    registry.register(a, Recorder(log, "a2"))
    registry.release_all()
    assert log == ["b1", "a2", "a1"]
    assert registry.plugins() == ()


def test_release_all_groups_errors_across_plugins() -> None:
    registry = ResourceRegistry[Plugin]()
    a, b, log = Plugin(), Plugin(), list[str]()
    registry.register(a, Recorder(log, "a", fail=True))
    registry.register(b, Recorder(log, "b", fail=True))
    with pytest.raises(ExceptionGroup) as info:
        registry.release_all()
    assert log == ["b", "a"]
    assert len(info.value.exceptions) == 2


def test_plugins_are_keyed_by_identity_not_equality() -> None:
    @dataclass  # eq=True: equal by value and (deliberately) unhashable
    class ValuePlugin(Plugin):
        name: str

    registry = ResourceRegistry[ValuePlugin]()
    one, two, log = ValuePlugin("same"), ValuePlugin("same"), list[str]()
    assert one == two
    registry.register(one, Recorder(log, "one"))
    registry.register(two, Recorder(log, "two"))
    registry.release(one)
    assert log == ["one"]
    assert registry.plugins() == (two,)


def test_registry_is_thread_safe() -> None:
    registry = ResourceRegistry[Plugin]()
    plugin, log = Plugin(), list[str]()

    def register_many() -> None:
        for _ in range(500):
            registry.register(plugin, Recorder(log, "x"))

    threads = [threading.Thread(target=register_many) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(registry.resources(plugin)) == 4000
    registry.release(plugin)
    assert len(log) == 4000


def test_any_object_with_release_is_a_resource() -> None:
    resource: Resource = Recorder([], "x")
    registry = ResourceRegistry[Plugin]()
    registry.register(Plugin(), resource)
