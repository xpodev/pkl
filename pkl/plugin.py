"""The identity of a plugin."""

from __future__ import annotations

__all__ = ["Plugin"]


class Plugin:
    """The identity of a plugin, and nothing else.

    Two plugins are the same if and only if they are the same object (``is``).
    A plugin carries no name, path, metadata or state: derive from it, compose
    it or wrap it to attach whatever your application knows about its plugins.
    pkl never reads anything from a plugin other than its identity.

    If you derive with ``@dataclass``, pass ``eq=False`` so that the identity
    semantics (and hashability) are preserved.
    """
