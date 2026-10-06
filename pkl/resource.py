"""Resources: things that can be released."""

from __future__ import annotations

from typing import Protocol

__all__ = ["Resource"]


class Resource(Protocol):
    """A thing that can be released.

    Anything with a ``release()`` method is a resource. Releasing a resource
    ends whatever it represents: stops a timer, removes a subscription, deletes
    a file. ``release()`` should be safe to call more than once.
    """

    def release(self) -> None:
        """Release the resource."""
        ...
