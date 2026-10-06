"""Tests for pkl.syscall."""

from __future__ import annotations

from functools import partial

import pytest

from pkl import Plugin, PluginTracker
from pkl.syscall import syscall


def test_runs_as_the_defining_plugin_and_restores_the_caller() -> None:
    plugins = PluginTracker[Plugin]()
    provider, caller = Plugin(), Plugin()

    bound = partial(syscall, plugins)  # the app-level decorator
    with plugins.executing(provider):

        @bound
        def whoami() -> Plugin | None:
            return plugins.current

    with plugins.executing(caller):
        assert whoami() is provider
        assert plugins.current is caller
    assert plugins.current is None


def test_defined_outside_any_plugin_runs_as_the_host() -> None:
    plugins = PluginTracker[Plugin]()

    def whoami() -> Plugin | None:
        return plugins.current

    wrapped = syscall(plugins, whoami)
    with plugins.executing(Plugin()):
        assert wrapped() is None


def test_passes_arguments_and_return_value() -> None:
    plugins = PluginTracker[Plugin]()

    def add(a: int, b: int = 0) -> int:
        return a + b

    wrapped = syscall(plugins, add)
    assert wrapped(1, b=2) == 3


def test_preserves_function_metadata() -> None:
    plugins = PluginTracker[Plugin]()

    def documented() -> None:
        """Docs."""

    wrapped = syscall(plugins, documented)
    assert wrapped.__name__ == "documented"
    assert wrapped.__doc__ == "Docs."


def test_restores_the_caller_when_the_function_raises() -> None:
    plugins = PluginTracker[Plugin]()
    provider, caller = Plugin(), Plugin()
    with plugins.executing(provider):

        def boom() -> None:
            raise RuntimeError

        wrapped = syscall(plugins, boom)

    with plugins.executing(caller):
        with pytest.raises(RuntimeError):
            wrapped()
        assert plugins.current is caller


async def test_async_function_runs_as_the_defining_plugin() -> None:
    plugins = PluginTracker[Plugin]()
    provider, caller = Plugin(), Plugin()

    with plugins.executing(provider):

        async def whoami() -> Plugin | None:
            return plugins.current

        wrapped = syscall(plugins, whoami)

    with plugins.executing(caller):
        assert await wrapped() is provider
        assert plugins.current is caller


def test_syscalls_of_different_trackers_do_not_interfere() -> None:
    one, two = PluginTracker[Plugin](), PluginTracker[Plugin]()
    a = Plugin()
    with one.executing(a):
        wrapped = syscall(one, lambda: (one.current, two.current))
    assert wrapped() == (a, None)
