"""Type definitions for pkl."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Protocol, TypeVar

if TYPE_CHECKING:
    from .plugin import Plugin
    from .resource import Resource

__all__ = [
    "ResourceFactory",
    "EventHandler",
    "PluginEntrypoint",
    "T",
    "P",
]

T = TypeVar("T")
P = TypeVar("P", bound="Plugin")

ResourceFactory = Callable[..., "Resource"]
EventHandler = Callable[..., Any]
PluginEntrypoint = Callable[[], None]


class SupportsDisable(Protocol):
    """Protocol for objects that can be disabled."""

    def disable(self) -> None:
        """Disable this object."""
        ...
