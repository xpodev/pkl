"""Tests for pkl.timing."""

from __future__ import annotations

import logging
import threading
import time

import pytest

from pkl import NoCurrentPluginError, Plugin, PluginTracker, ResourceRegistry
from pkl.timing import Timer
from pkl.tracking import ResourceTracker

WAIT = 2.0


class Env:
    def __init__(self, *, allow_orphans: bool = False) -> None:
        self.plugins = PluginTracker[Plugin]()
        self.registry = ResourceRegistry[Plugin]()
        self.tracker = ResourceTracker(self.plugins, self.registry, allow_orphans=allow_orphans)
        self.timer_type = Timer.with_tracker(self.tracker)


def test_timeout_fires_once_as_its_owner() -> None:
    env, plugin = Env(), Plugin()
    fired = threading.Event()
    seen: list[Plugin | None] = []

    def callback() -> None:
        seen.append(env.plugins.current)
        fired.set()

    with env.plugins.executing(plugin):
        timer = env.timer_type.timeout(callback, 0.01)
    assert fired.wait(WAIT)
    assert seen == [plugin]
    assert timer.owner is plugin


def test_one_shot_timer_releases_itself_after_firing() -> None:
    env, plugin = Env(), Plugin()
    fired = threading.Event()
    with env.plugins.executing(plugin):
        timer = env.timer_type.timeout(fired.set, 0.01)
        assert env.registry.resources(plugin) == (timer,)
    assert fired.wait(WAIT)
    deadline = time.monotonic() + WAIT
    while env.registry.resources(plugin) and time.monotonic() < deadline:
        time.sleep(0.005)
    assert env.registry.resources(plugin) == ()
    assert timer.released


def test_interval_repeats_until_released() -> None:
    env, plugin = Env(), Plugin()
    ticks = 0
    three = threading.Event()

    def callback() -> None:
        nonlocal ticks
        ticks += 1
        if ticks >= 3:
            three.set()

    with env.plugins.executing(plugin):
        timer = env.timer_type.interval(callback, 0.01)
    assert three.wait(WAIT)
    env.registry.release(plugin)
    assert timer.released
    settled = ticks
    time.sleep(0.1)
    assert ticks <= settled + 1  # at most one tick that was already in flight


def test_release_before_firing_cancels() -> None:
    env, plugin = Env(), Plugin()
    fired = threading.Event()
    with env.plugins.executing(plugin):
        timer = env.timer_type.timeout(fired.set, 0.05)
    timer.release()
    assert not fired.wait(0.2)


def test_releasing_one_plugin_leaves_other_plugins_timers() -> None:
    env, a, b = Env(), Plugin(), Plugin()
    a_fired, b_fired = threading.Event(), threading.Event()
    with env.plugins.executing(a):
        env.timer_type.timeout(a_fired.set, 0.1)
    with env.plugins.executing(b):
        env.timer_type.timeout(b_fired.set, 0.1)
    env.registry.release(a)
    assert b_fired.wait(WAIT)
    assert not a_fired.is_set()


def test_callback_error_is_logged_and_interval_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    env, plugin = Env(), Plugin()
    calls = 0
    twice = threading.Event()

    def callback() -> None:
        nonlocal calls
        calls += 1
        if calls >= 2:
            twice.set()
        raise ValueError("boom")

    with caplog.at_level(logging.ERROR, logger="pkl.timing"):
        with env.plugins.executing(plugin):
            env.timer_type.interval(callback, 0.01)
        assert twice.wait(WAIT)
        env.registry.release(plugin)
    assert any("boom" in (record.exc_text or "") or record.exc_info for record in caplog.records)


def test_timer_needs_a_plugin_unless_orphans_are_allowed() -> None:
    with pytest.raises(NoCurrentPluginError):
        Env().timer_type.timeout(lambda: None, 1)

    env = Env(allow_orphans=True)
    fired = threading.Event()
    seen: list[Plugin | None] = []

    def callback() -> None:
        seen.append(env.plugins.current)
        fired.set()

    timer = env.timer_type.timeout(callback, 0.01)
    assert timer.owner is None
    assert fired.wait(WAIT)
    assert seen == [None]
