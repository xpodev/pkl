"""Plugins loaded as modules calling each other's APIs, passing callbacks.

The rule under test: an API that is *not* a syscall runs as its caller. So a
callback created inside such an API is created as the caller, and when it is
finally invoked - by anyone, from anywhere - it runs as that caller.
"""

from __future__ import annotations

import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from pkl import Plugin, PluginTracker, ResourceRegistry
from pkl.events import EventPermissionError, event_decorator
from pkl.modules import ModuleResource
from pkl.syscall import syscall
from pkl.tracking import ResourceTracker

PROVIDER = '''
import SDK

@SDK.event
def ready(name):
    """The provider announces something."""

@SDK.event(protected=False)
def open_ready(name):
    """Anybody may invoke this one."""

callbacks = []
seen = []

def register(callback):
    """NOT a syscall: runs as whoever calls it."""
    seen.append(("register ran as", SDK.plugins.current))
    callbacks.append(SDK.tracker.callback(callback))

def run_callbacks(value):
    """NOT a syscall: runs as its caller, and invokes the callbacks it was given."""
    return [callback(value) for callback in callbacks]

def announce_unprotected(name):
    """NOT a syscall: tries to invoke the provider's own event as the caller."""
    ready(name)

@SDK.syscall
def announce(name):
    """A syscall: runs as the provider, so it may invoke the provider's event."""
    seen.append(("announce ran as", SDK.plugins.current))
    ready(name)
'''

CONSUMER = '''
import SDK
import PROVIDER_MODULE as provider

seen = []

def on_value(value):
    seen.append(("callback ran as", SDK.plugins.current))
    return value * 2

provider.register(on_value)

@provider.ready.on
def on_ready(name):
    seen.append(("event handler ran as", SDK.plugins.current, name))

@provider.open_ready.on
def on_open_ready(name):
    seen.append(("open handler ran as", SDK.plugins.current, name))

def poke_open_event():
    """The consumer invokes the provider's unprotected event itself."""
    provider.open_ready("poked")
'''


class World:
    """One application: a tracker, a runtime lifetime, and the SDK plugins import."""

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.plugins = PluginTracker[Plugin]()
        self.runtime = ResourceRegistry[Plugin]()
        self.tracker = ResourceTracker(self.plugins, self.runtime)
        self.sdk = ModuleType(f"{prefix}_SDK")
        self.sdk.plugins = self.plugins  # type: ignore[attr-defined]
        self.sdk.tracker = self.tracker  # type: ignore[attr-defined]
        self.sdk.event = event_decorator(self.tracker)  # type: ignore[attr-defined]
        self.sdk.syscall = lambda func: syscall(self.plugins, func)  # type: ignore[attr-defined]
        self.module_type = ModuleResource.with_tracker(self.tracker)
        sys.modules[self.sdk.__name__] = self.sdk

    def load(self, plugin: Plugin, name: str, files: dict[str, str], root: Path) -> ModuleResource:
        package = root / name
        package.mkdir(parents=True)
        for filename, source in files.items():
            source = source.replace("PROVIDER_MODULE", f"{self.prefix}.provider")
            source = source.replace("import SDK", f"import {self.sdk.__name__} as SDK")
            (package / filename).write_text(source, encoding="utf-8")
        with self.plugins.executing(plugin):
            return self.module_type(f"{self.prefix}.{name}", package, package=True)


@pytest.fixture
def world() -> Iterator[World]:
    prefix = f"pkltest_{uuid.uuid4().hex}"
    instance = World(prefix)
    yield instance
    for key in [k for k in sys.modules if k.startswith(prefix)]:
        del sys.modules[key]


@pytest.fixture
def loaded(world: World, tmp_path: Path) -> tuple[World, Plugin, Plugin, ModuleType, ModuleType]:
    provider, consumer = Plugin(), Plugin()
    provider_module = world.load(provider, "provider", {"__init__.py": PROVIDER}, tmp_path)
    consumer_module = world.load(consumer, "consumer", {"__init__.py": CONSUMER}, tmp_path)
    return world, provider, consumer, provider_module.module, consumer_module.module


def test_a_non_syscall_api_runs_as_its_caller(
    loaded: tuple[World, Plugin, Plugin, ModuleType, ModuleType],
) -> None:
    _, provider, consumer, provider_module, _ = loaded
    # The consumer called provider.register while its own module loaded.
    assert provider_module.seen == [("register ran as", consumer)]


def test_a_callback_created_inside_the_api_belongs_to_the_caller(
    loaded: tuple[World, Plugin, Plugin, ModuleType, ModuleType],
) -> None:
    world, provider, consumer, provider_module, _ = loaded
    (callback,) = provider_module.callbacks
    assert callback.owner is consumer
    assert callback in world.runtime.resources(consumer)
    assert world.runtime.resources(provider)  # the provider's own event, not the callback
    assert callback not in world.runtime.resources(provider)


def test_the_callback_runs_as_its_owner_whoever_invokes_it(
    loaded: tuple[World, Plugin, Plugin, ModuleType, ModuleType],
) -> None:
    world, provider, consumer, provider_module, consumer_module = loaded

    with world.plugins.executing(provider):
        assert provider_module.run_callbacks(21) == [42]
        assert world.plugins.current is provider  # restored afterwards
    assert world.plugins.current is None
    assert consumer_module.seen == [("callback ran as", consumer)]

    consumer_module.seen.clear()
    assert provider_module.run_callbacks(1) == [2]  # invoked by the host
    assert consumer_module.seen == [("callback ran as", consumer)]


def test_a_syscall_runs_as_the_provider_while_a_plain_api_does_not(
    loaded: tuple[World, Plugin, Plugin, ModuleType, ModuleType],
) -> None:
    world, provider, consumer, provider_module, consumer_module = loaded

    with world.plugins.executing(consumer):
        provider_module.announce("hello")  # syscall: runs as the provider, may invoke its event
        with pytest.raises(EventPermissionError):
            provider_module.announce_unprotected("hello")  # plain: runs as the consumer

    assert ("announce ran as", provider) in provider_module.seen
    # The consumer's handler ran as the consumer, not as whoever invoked the event.
    assert consumer_module.seen[-1] == ("event handler ran as", consumer, "hello")


def test_an_unprotected_event_can_be_invoked_by_another_plugin(
    loaded: tuple[World, Plugin, Plugin, ModuleType, ModuleType],
) -> None:
    world, provider, consumer, _, consumer_module = loaded
    with world.plugins.executing(consumer):
        consumer_module.poke_open_event()
    # Invoked by the consumer, handled by the consumer's own subscription - as the consumer.
    assert consumer_module.seen[-1] == ("open handler ran as", consumer, "poked")


def test_releasing_the_consumer_silences_its_callbacks_and_handlers(
    loaded: tuple[World, Plugin, Plugin, ModuleType, ModuleType],
) -> None:
    world, provider, consumer, provider_module, consumer_module = loaded
    world.runtime.release(consumer)

    assert [callback.active for callback in provider_module.callbacks] == [False]
    with world.plugins.executing(provider):
        provider_module.announce("after")
    assert consumer_module.seen == []  # nothing the consumer registered can run any more
    assert f"{world.prefix}.consumer" not in sys.modules
    assert f"{world.prefix}.provider" in sys.modules  # the provider is unaffected
    assert world.runtime.resources(provider)


def test_releasing_the_provider_unloads_it_and_drops_its_event(
    loaded: tuple[World, Plugin, Plugin, ModuleType, ModuleType],
) -> None:
    world, provider, consumer, provider_module, consumer_module = loaded
    event = provider_module.ready
    world.runtime.release(provider)

    assert event.released
    assert event.subscriptions == ()
    assert f"{world.prefix}.provider" not in sys.modules
    # The consumer still owns what it registered; releasing it afterwards is clean.
    world.runtime.release(consumer)
    assert world.runtime.plugins() == ()
