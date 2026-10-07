"""Automatic tracking: resources that register with the plugin that created them.

This is the extension every other pkl extension builds on. The core only knows
how to *record* and *release* resources; this module adds the step in between:
at creation time, find out which plugin is executing and record the new
resource under it.

An application picks its lifetimes by binding resource bases to registries::

    plugins = PluginTracker[AppPlugin]()
    runtime = ResourceRegistry[AppPlugin]()

    class RuntimeResource(Tracked[AppPlugin], tracker=ResourceTracker(plugins, runtime)): ...

Every subclass of ``RuntimeResource`` is then recorded in ``runtime`` under
whichever plugin created it, and ``runtime.release(plugin)`` releases them.
"""

from __future__ import annotations

import threading
from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, ParamSpec, Self, TypeVar, cast

from .errors import NoCurrentPluginError, PklError
from .plugin import Plugin
from .plugin_tracker import PluginTracker
from .registry import ResourceRegistry
from .resource import Resource

__all__ = [
    "ResourceTracker",
    "Tracked",
    "TrackedMeta",
    "Callback",
    "CallbackReleasedError",
    "UnboundResourceError",
    "TrackerOverrideError",
]

P = TypeVar("P", bound=Plugin)
R = TypeVar("R", bound=Resource)
Params = ParamSpec("Params")
T = TypeVar("T")


class UnboundResourceError(PklError, TypeError):
    """Raised when a ``Tracked`` class that is not bound to a tracker is instantiated."""


class TrackerOverrideError(PklError, TypeError):
    """Raised when a tracker override is attempted on a class that forbids it."""


class CallbackReleasedError(PklError, RuntimeError):
    """Raised when a released ``Callback`` is called."""


@dataclass(frozen=True)
class ResourceTracker(Generic[P]):
    """Attributes new resources to the executing plugin and records them.

    A ``ResourceTracker`` pairs a ``PluginTracker`` (who is executing?) with a
    ``ResourceRegistry`` (where do their resources go?). The registry is the
    passive map that can release a plugin's resources; the tracker is the
    active step that looks up the current plugin and records a new resource.

    Args:
        plugins: Tells which plugin is executing.
        registry: Where new resources are recorded.
        allow_orphans: What to do when a resource is created while no plugin is
            executing. By default that is an error (``NoCurrentPluginError``),
            because an owner-less resource can never be released. With
            ``allow_orphans=True`` such resources are host-owned: they are not
            recorded anywhere and live until their creator releases them.
    """

    plugins: PluginTracker[P]
    registry: ResourceRegistry[P]
    allow_orphans: bool = False

    def current_owner(self) -> P | None:
        """The plugin a resource created right now would belong to.

        Raises:
            NoCurrentPluginError: If no plugin is executing and orphans are not allowed.
        """
        owner = self.plugins.current
        if owner is None and not self.allow_orphans:
            raise NoCurrentPluginError(
                "a resource was created while no plugin is executing "
                "(create it from a plugin, or use ResourceTracker(..., allow_orphans=True))"
            )
        return owner

    def track(self, resource: R) -> R:
        """Record ``resource`` under the current plugin and return it.

        This is the explicit form of what ``Tracked`` does automatically.

        Raises:
            NoCurrentPluginError: If no plugin is executing and orphans are not allowed.
        """
        owner = self.current_owner()
        if owner is not None:
            self.registry.register(owner, resource)
        return resource

    def callback(
        self, func: Callable[Params, T], *, finalizer: Callable[[], object] | None = None
    ) -> Callback[Params, T]:
        """Make ``func`` a tracked callback of the plugin executing now.

        The callback runs as that plugin, is recorded in this tracker's
        registry, and stops working when released; ``finalizer`` (if any) runs
        on release. It is the shortest way to create a one-off resource::

            tracker.callback(lambda: None, finalizer=connection.close)
        """
        variant: Any = Callback._variant(self)
        return cast("Callback[Params, T]", variant(func, finalizer=finalizer))


class TrackedMeta(ABCMeta):
    """Metaclass that records a ``Tracked`` instance once it is fully constructed."""

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        instance = super().__call__(*args, **kwargs)
        # Registering only after __init__ succeeded means a half-built resource
        # is never recorded (and so never released).
        owner = instance.owner
        if owner is not None:
            instance.tracker.registry.register(owner, instance)
        return instance


_variants_lock = threading.Lock()


class Tracked(Generic[P], metaclass=TrackedMeta):
    """Base class for resources that are recorded automatically when created.

    Bind a base to a ``ResourceTracker`` with the ``tracker`` class keyword;
    the binding is inherited by every subclass::

        class RuntimeResource(Tracked[AppPlugin], tracker=ResourceTracker(plugins, runtime)): ...

        class Timer(RuntimeResource):
            def on_release(self) -> None: ...

    Creating a ``Timer`` then attributes it to ``plugins.current`` and records
    it in ``runtime``. The owner is known from the start of ``__init__``.

    Subclasses implement ``on_release``. ``release()`` is idempotent, calls
    ``on_release`` once, and then forgets the resource, so releasing a resource
    by hand leaves no stale entry in the registry.

    A single process can serve several trackers from one class with
    ``Timer.with_tracker(other)(...)``, unless the class is bound with
    ``allow_tracker_override=False``: an SDK that wants to stay single-host
    sets that, and plugin code then cannot pick a different tracker.
    """

    _pkl_tracker: ClassVar[ResourceTracker[Any] | None] = None
    _pkl_allow_override: ClassVar[bool] = True

    _pkl_resource_tracker: ResourceTracker[Any]
    _pkl_owner: P | None
    _pkl_released: bool
    _pkl_lock: threading.Lock

    def __init_subclass__(
        cls,
        *,
        tracker: ResourceTracker[Any] | None = None,
        allow_tracker_override: bool | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init_subclass__(**kwargs)
        if tracker is not None:
            cls._pkl_tracker = tracker
        if allow_tracker_override is not None:
            cls._pkl_allow_override = allow_tracker_override

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        tracker = cls._pkl_tracker
        if tracker is None:
            raise UnboundResourceError(
                f"{cls.__qualname__} is not bound to a ResourceTracker; derive from a class "
                "declared with `tracker=...` or use `with_tracker(...)`"
            )
        self = super().__new__(cls)
        self._pkl_resource_tracker = tracker
        self._pkl_owner = tracker.current_owner()
        self._pkl_released = False
        self._pkl_lock = threading.Lock()
        return self

    @classmethod
    def with_tracker(cls, tracker: ResourceTracker[Any]) -> type[Self]:
        """The same class, bound to ``tracker`` instead.

        Meant for processes that run several trackers. The result is cached per
        tracker and fully typed: ``Timer.with_tracker(t)(callback, 1.0)``.

        Raises:
            TrackerOverrideError: If the class was bound with ``allow_tracker_override=False``.
        """
        if not cls._pkl_allow_override:
            raise TrackerOverrideError(
                f"{cls.__qualname__} does not allow overriding its tracker"
            )
        return cls._variant(tracker)

    @classmethod
    def _variant(cls, tracker: ResourceTracker[Any]) -> type[Self]:
        """``with_tracker`` without the override check, for pkl's own use."""
        with _variants_lock:
            variants: dict[ResourceTracker[Any], type[Self]] | None = cls.__dict__.get(
                "_pkl_variants"
            )
            if variants is None:
                variants = {}
                cls._pkl_variants = variants  # type: ignore[attr-defined]
            variant = variants.get(tracker)
            if variant is None:
                namespace = {
                    "__module__": cls.__module__,
                    "__qualname__": cls.__qualname__,
                    "__doc__": cls.__doc__,
                }
                metaclass: Any = type(cls)
                variant = cast(
                    "type[Self]",
                    metaclass(cls.__name__, (cls,), namespace, tracker=tracker),
                )
                variants[tracker] = variant
            return variant

    @property
    def owner(self) -> P | None:
        """The plugin that created this resource, or ``None`` for a host-owned one."""
        return self._pkl_owner

    @property
    def tracker(self) -> ResourceTracker[Any]:
        """The tracker this resource was created under."""
        return self._pkl_resource_tracker

    @property
    def released(self) -> bool:
        """Whether ``release()`` has been called."""
        return self._pkl_released

    def bind(self, func: Callable[Params, T]) -> Callable[Params, T]:
        """Bind ``func`` to this resource's owner (the host if it has none).

        The result runs as the owner whoever calls it, e.g. from a thread or
        event loop that pkl does not control::

            threading.Thread(target=self.bind(self.serve)).start()
        """
        return self._pkl_resource_tracker.plugins.bind_as(self._pkl_owner, func)

    def release(self) -> None:
        """Release the resource. Only the first call has an effect."""
        with self._pkl_lock:
            if self._pkl_released:
                return
            self._pkl_released = True
        try:
            self.on_release()
        finally:
            owner = self._pkl_owner
            if owner is not None:
                self._pkl_resource_tracker.registry.unregister(owner, self)

    @abstractmethod
    def on_release(self) -> None:
        """Do the actual releasing. Called at most once."""


class Callback(Tracked[Any], Generic[Params, T]):
    """A callable bound to the plugin that created it, as a resource.

    Calling it runs the function as that plugin (``async`` functions stay
    ``async``). Once released it is inert: calling it raises
    ``CallbackReleasedError``. An optional ``finalizer`` runs on release.

    Create one with ``ResourceTracker.callback``.
    """

    def __init__(
        self, func: Callable[Params, T], *, finalizer: Callable[[], object] | None = None
    ) -> None:
        self.func = func
        self._finalizer = finalizer
        self._bound = self.bind(func)

    @property
    def active(self) -> bool:
        """Whether the callback can still be called."""
        return not self.released

    def __call__(self, *args: Params.args, **kwargs: Params.kwargs) -> T:
        if self.released:
            raise CallbackReleasedError("callback was released")
        return self._bound(*args, **kwargs)

    def on_release(self) -> None:
        if self._finalizer is not None:
            self._finalizer()
