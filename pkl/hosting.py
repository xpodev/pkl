"""A plugin host as a resource: a plugin that owns a world of plugins of its own.

A *host* is what an application builds from the core: a ``PluginTracker`` (who is
executing) and the registries (lifetimes) that hold their resources. This module
makes that bundle a resource. A plugin creates a ``PluginHost`` - say, a plugin
that is itself a plugin framework, loading plugins of its own - and because the
host is tracked like any other resource, releasing the owning plugin releases
the whole nested world with it::

    class RuntimeResource(Tracked[AppPlugin], tracker=runtime_tracker): ...
    class Host(hosting.PluginHost[SubPlugin], RuntimeResource): ...

    # inside the owning plugin
    host = Host()
    runtime = host.registry()                 # a lifetime of the nested world
    tracker = host.tracker_for(runtime)       # attributes new resources to its plugins
    with host.plugins.executing(sub_plugin):
        Timer.with_tracker(tracker).interval(poll, 1.0)

    runtime_registry.release(owner)           # releases the owner, the host, and every sub-plugin
"""

from __future__ import annotations

import threading
from typing import Any, Generic, TypeVar

from .errors import PklError
from .plugin import Plugin
from .plugin_tracker import PluginTracker
from .registry import ResourceRegistry
from .resource import Resource
from .tracking import ResourceTracker, Tracked

__all__ = ["PluginHost", "HostedRegistry", "HostReleasedError"]

Q = TypeVar("Q", bound=Plugin)


class HostReleasedError(PklError, RuntimeError):
    """Raised when something is added to a plugin host that was already released."""


class HostedRegistry(ResourceRegistry[Q]):
    """A registry that belongs to a ``PluginHost``.

    It behaves like any registry until its host is released; after that it
    refuses new resources, because nobody would ever release them.
    """

    def __init__(self, host: PluginHost[Q]) -> None:
        super().__init__()
        self.host = host

    def register(self, plugin: Q, resource: Resource) -> None:
        if self.host.released:
            raise HostReleasedError("this registry's plugin host was released")
        super().register(plugin, resource)


class PluginHost(Tracked[Any], Generic[Q]):
    """A plugin tracker plus the lifetimes of the plugins it runs, as a resource.

    The host is owned by the plugin that created it. Releasing the host (by
    hand, or by releasing its owner's lifetime) releases every resource of every
    plugin it hosts, newest lifetime first. After that it accepts nothing new.

    Args:
        plugins: The tracker the hosted plugins execute under. A new one is made
            if omitted.
    """

    def __init__(self, plugins: PluginTracker[Q] | None = None) -> None:
        self.plugins: PluginTracker[Q] = plugins if plugins is not None else PluginTracker[Q]()
        self._lock = threading.Lock()
        self._registries: list[HostedRegistry[Q]] = []

    def registry(self) -> HostedRegistry[Q]:
        """Create a lifetime of this host.

        Raises:
            HostReleasedError: If the host was released.
        """
        with self._lock:
            if self.released:
                raise HostReleasedError("this plugin host was released")
            registry = HostedRegistry(self)
            self._registries.append(registry)
            return registry

    def tracker_for(
        self, registry: ResourceRegistry[Q], *, allow_orphans: bool = False
    ) -> ResourceTracker[Q]:
        """A ``ResourceTracker`` that attributes resources to this host's plugins.

        Args:
            registry: Where the resources go; normally one made by ``registry()``.
            allow_orphans: Whether resources may be created while none of the
                host's plugins is executing.
        """
        return ResourceTracker(self.plugins, registry, allow_orphans=allow_orphans)

    @property
    def registries(self) -> tuple[HostedRegistry[Q], ...]:
        """The lifetimes made by ``registry()``, oldest first."""
        with self._lock:
            return tuple(self._registries)

    def on_release(self) -> None:
        errors: list[BaseException] = []
        for registry in reversed(self.registries):
            try:
                registry.release_all()
            except BaseException as error:  # collected and re-raised as a group
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("failed to release a plugin host", errors)
