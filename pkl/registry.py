"""Registries: plugin -> resources, releasable per plugin."""

from __future__ import annotations

import threading
from typing import Generic, TypeVar

from .plugin import Plugin
from .resource import Resource

__all__ = ["ResourceRegistry"]

P = TypeVar("P", bound=Plugin)


class ResourceRegistry(Generic[P]):
    """Maps plugins to their resources and releases them on demand.

    A registry *is* a lifetime. Whoever calls ``release(plugin)`` decides when
    that lifetime ends: on disable, on uninstall, on a timer, or never. Use as
    many registries as you have lifetimes.

    Plugins are keyed by identity (``is``), whatever their ``__eq__`` and
    ``__hash__`` say. The registry is thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # id(plugin) -> (plugin, resources in registration order). Holding the
        # plugin keeps its id from being reused while it has resources.
        self._entries: dict[int, tuple[P, list[Resource]]] = {}

    def register(self, plugin: P, resource: Resource) -> None:
        """Record that ``resource`` belongs to ``plugin``."""
        with self._lock:
            entry = self._entries.get(id(plugin))
            if entry is None:
                self._entries[id(plugin)] = (plugin, [resource])
            else:
                entry[1].append(resource)

    def unregister(self, plugin: P, resource: Resource) -> bool:
        """Forget ``resource`` without releasing it.

        Returns:
            Whether the resource was registered under ``plugin``.
        """
        with self._lock:
            entry = self._entries.get(id(plugin))
            if entry is None:
                return False
            resources = entry[1]
            for index in range(len(resources) - 1, -1, -1):
                if resources[index] is resource:
                    del resources[index]
                    if not resources:
                        del self._entries[id(plugin)]
                    return True
            return False

    def resources(self, plugin: P) -> tuple[Resource, ...]:
        """The resources currently registered under ``plugin``, oldest first."""
        with self._lock:
            entry = self._entries.get(id(plugin))
            return tuple(entry[1]) if entry is not None else ()

    def plugins(self) -> tuple[P, ...]:
        """The plugins that currently have resources, oldest first."""
        with self._lock:
            return tuple(plugin for plugin, _ in self._entries.values())

    def release(self, plugin: P) -> None:
        """Release every resource of ``plugin``, newest first.

        Every resource is released even if some of them raise; the errors are
        then raised together as an exception group. Resources registered while
        releasing are released too. Releasing a plugin without resources does
        nothing, so calling this twice is harmless.

        Raises:
            ExceptionGroup: If one or more resources failed to release.
        """
        errors = self._release(plugin)
        if errors:
            raise BaseExceptionGroup(f"failed to release resources of {plugin!r}", errors)

    def release_all(self) -> None:
        """Release the resources of every plugin, the newest plugin first.

        Raises:
            ExceptionGroup: If one or more resources failed to release.
        """
        errors: list[BaseException] = []
        for plugin in reversed(self.plugins()):
            errors.extend(self._release(plugin))
        if errors:
            raise BaseExceptionGroup("failed to release resources", errors)

    def _release(self, plugin: P) -> list[BaseException]:
        errors: list[BaseException] = []
        while True:
            # Take the resources out first and release outside the lock, so a
            # resource may call back into the registry (e.g. unregister itself).
            with self._lock:
                entry = self._entries.pop(id(plugin), None)
            if entry is None:
                return errors
            for resource in reversed(entry[1]):
                try:
                    resource.release()
                except BaseException as error:  # collected and re-raised as a group
                    errors.append(error)
