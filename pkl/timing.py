"""Timers: delayed and repeated calls that belong to the plugin that scheduled them."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any, Self

from .tracking import Tracked

__all__ = ["Timer"]

_logger = logging.getLogger("pkl.timing")


class Timer(Tracked[Any]):
    """Calls ``callback`` after ``delay`` seconds, once or repeatedly.

    The callback runs on a background thread as the plugin that created the
    timer (as the host if it has no owner). Releasing the timer cancels it. A
    one-shot timer releases itself once it has fired, so it leaves nothing
    behind in the registry.

    An exception in the callback is logged; a repeating timer keeps going.

    Create timers with ``Timer.timeout(...)`` and ``Timer.interval(...)``.
    """

    def __init__(
        self, callback: Callable[[], object], delay: float, *, repeat: bool = False
    ) -> None:
        self.callback = callback
        self.delay = delay
        self.repeat = repeat
        self._timer_lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._schedule()

    @classmethod
    def timeout(cls, callback: Callable[[], object], delay: float = 0) -> Self:
        """Call ``callback`` once, after ``delay`` seconds."""
        return cls(callback, delay)

    @classmethod
    def interval(cls, callback: Callable[[], object], delay: float) -> Self:
        """Call ``callback`` every ``delay`` seconds."""
        return cls(callback, delay, repeat=True)

    def _schedule(self) -> None:
        with self._timer_lock:
            if self.released:
                return
            timer = threading.Timer(self.delay, self._run)
            timer.daemon = True
            self._timer = timer
            timer.start()

    def _run(self) -> None:
        if self.released:
            return
        try:
            with self.executing_as_owner():
                self.callback()
        except Exception:
            _logger.exception("error in %s callback", "interval" if self.repeat else "timeout")
        if self.repeat:
            self._schedule()
        else:
            self.release()

    def _release(self) -> None:
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
