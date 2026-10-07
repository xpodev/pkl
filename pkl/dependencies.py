"""Plugin dependencies, modelled as resources.

If plugin ``B`` depends on plugin ``A``, then ``B`` is one of ``A``'s resources:
when ``A`` is released from a registry, ``B`` is released from it too, and so
are the plugins that depend on ``B``, and so on. Dependencies follow the
lifetime of the registry they are declared in: declare them in the "disable"
registry and disabling ``A`` disables its dependants; declare them in the
"uninstall" registry and uninstalling ``A`` uninstalls them.

pkl does not know what a dependency *is* (a manifest entry, an import, a
call): you tell it, with ``depends_on`` or, from inside the dependant,
``require``::

    runtime = ResourceRegistry[AppPlugin]()

    depends_on(runtime, dependant=beta, dependency=alpha)
    runtime.release(alpha)        # releases alpha's resources, then beta's

Dependants are released before the dependency's resources that were registered
before the dependency was declared, because registries release newest first.
Declare a dependency as soon as the dependant is loaded, and the dependant is
torn down before the dependency's own resources (apart from anything the
dependency created after that point).
"""

from __future__ import annotations

import threading
from typing import Any, Generic, TypeVar

from .plugin import Plugin
from .registry import ResourceRegistry
from .tracking import ResourceTracker

__all__ = ["Dependency", "depends_on", "require"]

P = TypeVar("P", bound=Plugin)


class _DependantEnd:
    """The dependant, as a resource of the dependency."""

    def __init__(self, link: Dependency[Any]) -> None:
        self._link = link

    def release(self) -> None:
        self._link._dependency_released()


class _DependencyEnd:
    """The link, as a resource of the dependant: when the dependant goes first, drop the link."""

    def __init__(self, link: Dependency[Any]) -> None:
        self._link = link

    def release(self) -> None:
        self._link._dependant_released()


class Dependency(Generic[P]):
    """The fact that ``dependant`` depends on ``dependency`` within ``registry``.

    Created by ``depends_on`` and ``require``. It holds one resource in each
    plugin's lifetime: the dependant is a resource of the dependency (so it is
    released with it), and the link is a resource of the dependant (so it
    disappears when the dependant is released on its own).
    """

    def __init__(self, registry: ResourceRegistry[P], dependant: P, dependency: P) -> None:
        if dependant is dependency:
            raise ValueError("a plugin cannot depend on itself")
        self.registry = registry
        self.dependant = dependant
        self.dependency = dependency
        self._lock = threading.Lock()
        self._active = True
        self._dependant_end = _DependantEnd(self)
        self._dependency_end = _DependencyEnd(self)
        registry.register(dependency, self._dependant_end)
        registry.register(dependant, self._dependency_end)

    @property
    def active(self) -> bool:
        """Whether the dependency still holds."""
        return self._active

    def unlink(self) -> bool:
        """Remove the dependency without releasing anybody.

        Returns:
            Whether it was still active.
        """
        if not self._deactivate():
            return False
        self.registry.unregister(self.dependency, self._dependant_end)
        self.registry.unregister(self.dependant, self._dependency_end)
        return True

    def _deactivate(self) -> bool:
        with self._lock:
            was_active = self._active
            self._active = False
        return was_active

    def _dependency_released(self) -> None:
        # The dependency is going away: take the dependant with it.
        if not self._deactivate():
            return
        self.registry.unregister(self.dependant, self._dependency_end)
        self.registry.release(self.dependant)

    def _dependant_released(self) -> None:
        # The dependant went first, on its own: the dependency no longer has it.
        if not self._deactivate():
            return
        self.registry.unregister(self.dependency, self._dependant_end)


def depends_on(registry: ResourceRegistry[P], dependant: P, dependency: P) -> Dependency[P]:
    """Declare that ``dependant`` depends on ``dependency`` within ``registry``.

    From now on, releasing ``dependency`` from ``registry`` releases ``dependant``
    from it as well (and so, transitively, its own dependants). Cycles are fine:
    each plugin is released at most once.

    Raises:
        ValueError: If a plugin is declared to depend on itself.
    """
    return Dependency(registry, dependant, dependency)


def require(tracker: ResourceTracker[P], dependency: P) -> Dependency[P]:
    """The plugin executing now depends on ``dependency``, within the tracker's registry.

    Raises:
        NoCurrentPluginError: If no plugin is executing.
        ValueError: If the executing plugin is ``dependency`` itself.
    """
    return depends_on(tracker.registry, tracker.plugins.require_current(), dependency)
