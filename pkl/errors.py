"""Errors raised by the pkl core."""

from __future__ import annotations

__all__ = ["PklError", "NoCurrentPluginError"]


class PklError(Exception):
    """Base class for errors raised by pkl."""


class NoCurrentPluginError(PklError, RuntimeError):
    """Raised when a plugin is required but none is currently executing."""
