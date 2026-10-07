"""Tests for pkl.dependencies."""

from __future__ import annotations

import pytest

from pkl import NoCurrentPluginError, Plugin, PluginTracker, ResourceRegistry
from pkl.dependencies import depends_on, require
from pkl.tracking import ResourceTracker


class Recorder:
    """A resource that records the order in which things are released."""

    def __init__(self, log: list[str], name: str, *, fail: bool = False) -> None:
        self.log, self.name, self.fail = log, name, fail

    def release(self) -> None:
        self.log.append(self.name)
        if self.fail:
            raise ValueError(self.name)


class Named(Plugin):
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"<{self.name}>"


def world() -> tuple[ResourceRegistry[Named], list[str]]:
    return ResourceRegistry[Named](), []


def give(registry: ResourceRegistry[Named], log: list[str], plugin: Named) -> None:
    """Give a plugin one resource of its own, named after it."""
    registry.register(plugin, Recorder(log, f"{plugin.name}'s resource"))


def test_releasing_the_dependency_releases_its_dependants() -> None:
    registry, log = world()
    a, b = Named("a"), Named("b")
    give(registry, log, a)
    give(registry, log, b)
    depends_on(registry, dependant=b, dependency=a)
    registry.release(a)
    assert sorted(log) == ["a's resource", "b's resource"]
    assert registry.plugins() == ()


def test_dependants_go_before_the_dependencys_earlier_resources() -> None:
    registry, log = world()
    a, b = Named("a"), Named("b")
    give(registry, log, a)  # the dependency's own, created before the dependant is declared
    give(registry, log, b)
    depends_on(registry, dependant=b, dependency=a)
    registry.release(a)
    assert log == ["b's resource", "a's resource"]


def test_releasing_the_dependant_does_not_release_the_dependency() -> None:
    registry, log = world()
    a, b = Named("a"), Named("b")
    give(registry, log, a)
    give(registry, log, b)
    depends_on(registry, dependant=b, dependency=a)
    registry.release(b)
    assert log == ["b's resource"]
    assert registry.plugins() == (a,)


def test_a_released_dependant_leaves_no_trace_in_the_dependency() -> None:
    registry, log = world()
    a, b = Named("a"), Named("b")
    give(registry, log, a)
    link = depends_on(registry, dependant=b, dependency=a)
    assert len(registry.resources(a)) == 2  # its own + the dependant
    registry.release(b)
    assert not link.active
    assert len(registry.resources(a)) == 1
    registry.release(a)
    assert log == ["a's resource"]  # b is not released a second time


def test_dependencies_are_transitive() -> None:
    registry, log = world()
    a, b, c = Named("a"), Named("b"), Named("c")
    for plugin in (a, b, c):
        give(registry, log, plugin)
    depends_on(registry, dependant=b, dependency=a)
    depends_on(registry, dependant=c, dependency=b)
    registry.release(a)
    assert sorted(log) == ["a's resource", "b's resource", "c's resource"]
    assert log.index("c's resource") < log.index("b's resource") < log.index("a's resource")
    assert registry.plugins() == ()


def test_several_dependants_and_a_diamond() -> None:
    registry, log = world()
    a, b, c, d = Named("a"), Named("b"), Named("c"), Named("d")
    for plugin in (a, b, c, d):
        give(registry, log, plugin)
    depends_on(registry, dependant=b, dependency=a)
    depends_on(registry, dependant=c, dependency=a)
    depends_on(registry, dependant=d, dependency=b)  # d needs both b and c
    depends_on(registry, dependant=d, dependency=c)
    registry.release(a)
    assert sorted(log) == ["a's resource", "b's resource", "c's resource", "d's resource"]
    assert log.count("d's resource") == 1
    assert registry.plugins() == ()


def test_releasing_a_middle_plugin_leaves_the_dependency_alone() -> None:
    registry, log = world()
    a, b, c = Named("a"), Named("b"), Named("c")
    for plugin in (a, b, c):
        give(registry, log, plugin)
    depends_on(registry, dependant=b, dependency=a)
    depends_on(registry, dependant=c, dependency=b)
    registry.release(b)
    assert sorted(log) == ["b's resource", "c's resource"]
    assert registry.plugins() == (a,)


def test_cycles_terminate_and_release_each_plugin_once() -> None:
    registry, log = world()
    a, b = Named("a"), Named("b")
    give(registry, log, a)
    give(registry, log, b)
    depends_on(registry, dependant=b, dependency=a)
    depends_on(registry, dependant=a, dependency=b)
    registry.release(a)
    assert sorted(log) == ["a's resource", "b's resource"]
    assert registry.plugins() == ()


def test_a_plugin_cannot_depend_on_itself() -> None:
    registry, _ = world()
    a = Named("a")
    with pytest.raises(ValueError, match="itself"):
        depends_on(registry, dependant=a, dependency=a)
    assert registry.plugins() == ()


def test_dependencies_follow_the_lifetime_they_are_declared_in() -> None:
    disable, uninstall = ResourceRegistry[Named](), ResourceRegistry[Named]()
    log: list[str] = []
    a, b = Named("a"), Named("b")
    for registry in (disable, uninstall):
        give(registry, log, a)
        give(registry, log, b)
    depends_on(disable, dependant=b, dependency=a)  # only while enabled
    disable.release(a)
    assert sorted(log) == ["a's resource", "b's resource"]  # both disabled...
    assert len(uninstall.resources(b)) == 1  # ...but b is not uninstalled
    assert len(uninstall.resources(a)) == 1


def test_unlink_removes_the_dependency_without_releasing_anyone() -> None:
    registry, log = world()
    a, b = Named("a"), Named("b")
    give(registry, log, a)
    give(registry, log, b)
    link = depends_on(registry, dependant=b, dependency=a)
    assert link.unlink() is True
    assert link.unlink() is False
    assert len(registry.resources(a)) == 1 and len(registry.resources(b)) == 1
    registry.release(a)
    assert log == ["a's resource"]  # b is no longer a dependant


def test_errors_in_a_dependant_are_reported_and_the_rest_still_released() -> None:
    registry, log = world()
    a, b = Named("a"), Named("b")
    give(registry, log, a)
    registry.register(b, Recorder(log, "b's resource", fail=True))
    depends_on(registry, dependant=b, dependency=a)
    with pytest.raises(ExceptionGroup) as info:
        registry.release(a)
    assert sorted(log) == ["a's resource", "b's resource"]
    (nested,) = info.value.exceptions
    assert isinstance(nested, ExceptionGroup)
    assert registry.plugins() == ()


def test_require_declares_a_dependency_from_the_executing_plugin() -> None:
    plugins = PluginTracker[Named]()
    registry = ResourceRegistry[Named]()
    tracker = ResourceTracker(plugins, registry)
    log: list[str] = []
    a, b = Named("a"), Named("b")
    give(registry, log, a)
    give(registry, log, b)
    with pytest.raises(NoCurrentPluginError):
        require(tracker, a)
    with plugins.executing(b):
        link = require(tracker, a)
    assert (link.dependant, link.dependency) == (b, a)
    registry.release(a)
    assert sorted(log) == ["a's resource", "b's resource"]
