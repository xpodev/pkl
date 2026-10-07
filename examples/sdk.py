"""The example application's plugin SDK.

Plugins import *this*, never ``pkl``. Everything a plugin creates through the
SDK is tracked automatically: the SDK decides which lifetime each resource kind
has, and who calls ``release`` when.

pkl never learns what a plugin is. ``AppPlugin`` is this application's idea of
one: pkl only sees its identity, the rest (id, name, metadata) is ours.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import partial
from typing import Any

from pkl import Plugin, PluginTracker, ResourceRegistry
from pkl import events, files, modules, timing
from pkl.syscall import syscall as _syscall
from pkl.tracking import ResourceTracker, Tracked


@dataclass(eq=False)  # eq=False: two plugins are the same only if they are the same object
class AppPlugin(Plugin):
    id: str
    name: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


# One host. Two registries, i.e. two lifetimes: what dies on `disable`, and what
# dies on `uninstall`. pkl does not know either word.
plugins = PluginTracker[AppPlugin]()
runtime = ResourceRegistry[AppPlugin]()
persistent = ResourceRegistry[AppPlugin]()


# Resources the host itself creates (host-defined events) belong to no plugin.
runtime_tracker = ResourceTracker(plugins, runtime, allow_orphans=True)


class RuntimeResource(
    Tracked[AppPlugin],
    tracker=runtime_tracker,
    # A plugin cannot pick another tracker: this SDK is single-host.
    allow_tracker_override=False,
): ...


class PersistentResource(
    Tracked[AppPlugin],
    tracker=ResourceTracker(plugins, persistent),
    allow_tracker_override=False,
): ...


# --- what plugins get to use ---------------------------------------------------


# `@event` and `@event(protected=False)`: a function, not a class.
event = events.event_decorator(runtime_tracker)


class Timer(timing.Timer, RuntimeResource): ...


class TempFile(files.TempFile, RuntimeResource): ...


class DataDirectory(files.Directory, PersistentResource): ...


class Module(modules.ModuleResource, RuntimeResource): ...


syscall = partial(_syscall, plugins)


# --- the host's side -------------------------------------------------------------


def load(plugin: AppPlugin, path: Any) -> Module:
    """Load a plugin's package; whatever its top-level code creates is the plugin's."""
    with plugins.executing(plugin):
        return Module(f"example_plugins.{plugin.name}", path, package=True)


def disable(plugin: AppPlugin) -> None:
    runtime.release(plugin)


def uninstall(plugin: AppPlugin) -> None:
    disable(plugin)
    persistent.release(plugin)
