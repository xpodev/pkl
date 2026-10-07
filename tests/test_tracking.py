"""Tests for pkl.tracking."""

from __future__ import annotations

import pytest

from pkl import NoCurrentPluginError, Plugin, PluginTracker, ResourceRegistry
from pkl.tracking import (
    ResourceTracker,
    Tracked,
    TrackerOverrideError,
    UnboundResourceError,
)


class Env:
    """One application's tracking setup."""

    def __init__(self, *, allow_orphans: bool = False) -> None:
        self.plugins = PluginTracker[Plugin]()
        self.registry = ResourceRegistry[Plugin]()
        self.tracker = ResourceTracker(self.plugins, self.registry, allow_orphans=allow_orphans)


class Probe(Tracked[Plugin]):
    """A resource that records what happens to it."""

    def __init__(self, *, fail: bool = False) -> None:
        self.owner_during_init = self.owner
        self.releases = 0
        if fail:
            raise ValueError("init failed")

    def on_release(self) -> None:
        self.releases += 1


def make_base(env: Env) -> type[Probe]:
    return Probe.with_tracker(env.tracker)


def test_resource_is_recorded_under_the_creating_plugin() -> None:
    env, plugin = Env(), Plugin()
    probe_type = make_base(env)
    with env.plugins.executing(plugin):
        probe = probe_type()
    assert probe.owner is plugin
    assert probe.tracker is env.tracker
    assert env.registry.resources(plugin) == (probe,)


def test_owner_is_available_during_init() -> None:
    env, plugin = Env(), Plugin()
    with env.plugins.executing(plugin):
        probe = make_base(env)()
    assert probe.owner_during_init is plugin


def test_registry_release_releases_the_resource() -> None:
    env, plugin = Env(), Plugin()
    with env.plugins.executing(plugin):
        probe = make_base(env)()
    env.registry.release(plugin)
    assert probe.released
    assert probe.releases == 1


def test_manual_release_is_idempotent_and_unregisters() -> None:
    env, plugin = Env(), Plugin()
    with env.plugins.executing(plugin):
        probe = make_base(env)()
    probe.release()
    probe.release()
    assert probe.releases == 1
    assert env.registry.resources(plugin) == ()
    env.registry.release(plugin)
    assert probe.releases == 1


def test_failed_init_is_not_recorded() -> None:
    env, plugin = Env(), Plugin()
    with env.plugins.executing(plugin):
        with pytest.raises(ValueError):
            make_base(env)(fail=True)
    assert env.registry.resources(plugin) == ()


def test_creation_without_a_plugin_raises_by_default() -> None:
    env = Env()
    with pytest.raises(NoCurrentPluginError):
        make_base(env)()


def test_orphans_are_host_owned_and_untracked_when_allowed() -> None:
    env = Env(allow_orphans=True)
    probe = make_base(env)()
    assert probe.owner is None
    assert env.registry.plugins() == ()
    probe.release()
    assert probe.releases == 1


def test_unbound_class_cannot_be_instantiated() -> None:
    with pytest.raises(UnboundResourceError):
        Probe()


def test_binding_by_class_keyword_is_inherited() -> None:
    env, plugin = Env(), Plugin()

    class Base(Tracked[Plugin], tracker=env.tracker):
        def on_release(self) -> None: ...

    class Child(Base): ...

    class Grandchild(Child): ...

    with env.plugins.executing(plugin):
        child, grandchild = Child(), Grandchild()
    assert env.registry.resources(plugin) == (child, grandchild)


def test_two_bindings_coexist_with_independent_lifetimes() -> None:
    plugins = PluginTracker[Plugin]()
    runtime, persistent = ResourceRegistry[Plugin](), ResourceRegistry[Plugin]()

    class RuntimeResource(Tracked[Plugin], tracker=ResourceTracker(plugins, runtime)):
        def on_release(self) -> None: ...

    class PersistentResource(Tracked[Plugin], tracker=ResourceTracker(plugins, persistent)):
        def on_release(self) -> None: ...

    plugin = Plugin()
    with plugins.executing(plugin):
        timer, record = RuntimeResource(), PersistentResource()
    assert runtime.resources(plugin) == (timer,)
    assert persistent.resources(plugin) == (record,)
    runtime.release(plugin)
    assert timer.released and not record.released


def test_with_tracker_rebinds_one_class_to_several_trackers() -> None:
    one, two, plugin = Env(), Env(), Plugin()
    with one.plugins.executing(plugin), two.plugins.executing(plugin):
        first = Probe.with_tracker(one.tracker)()
        second = Probe.with_tracker(two.tracker)()
    assert one.registry.resources(plugin) == (first,)
    assert two.registry.resources(plugin) == (second,)
    assert isinstance(first, Probe) and isinstance(second, Probe)


def test_with_tracker_is_cached_per_tracker() -> None:
    env = Env()
    assert Probe.with_tracker(env.tracker) is Probe.with_tracker(env.tracker)
    assert Probe.with_tracker(env.tracker) is not Probe.with_tracker(Env().tracker)


def test_with_tracker_can_be_forbidden() -> None:
    env = Env()

    class Sealed(Tracked[Plugin], tracker=env.tracker, allow_tracker_override=False):
        def on_release(self) -> None: ...

    class Derived(Sealed): ...

    for cls in (Sealed, Derived):
        with pytest.raises(TrackerOverrideError):
            cls.with_tracker(Env().tracker)


def test_explicit_track_records_under_the_current_plugin() -> None:
    env, plugin = Env(), Plugin()

    class Plain:
        def release(self) -> None: ...

    resource = Plain()
    with env.plugins.executing(plugin):
        assert env.tracker.track(resource) is resource
    assert env.registry.resources(plugin) == (resource,)
    with pytest.raises(NoCurrentPluginError):
        env.tracker.track(Plain())


def test_executing_as_owner_runs_as_the_owner() -> None:
    env, plugin = Env(), Plugin()
    with env.plugins.executing(plugin):
        probe = make_base(env)()
    assert env.plugins.current is None
    with probe.executing_as_owner():
        assert env.plugins.current is plugin
    assert env.plugins.current is None


def test_release_error_still_unregisters() -> None:
    env, plugin = Env(), Plugin()

    class Failing(Tracked[Plugin], tracker=env.tracker):
        def on_release(self) -> None:
            raise OSError("nope")

    with env.plugins.executing(plugin):
        resource = Failing()
    with pytest.raises(ExceptionGroup):
        env.registry.release(plugin)
    assert env.registry.resources(plugin) == ()
    assert resource.released
