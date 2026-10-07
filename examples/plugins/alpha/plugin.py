"""Alpha: announces greetings, ticks, keeps data across restarts."""

from pathlib import Path

import sdk


@sdk.event
def greeted(name: str) -> None:
    """Announced whenever somebody is greeted."""


@sdk.syscall
def greet(name: str) -> None:
    """Greet somebody. Runs as alpha, so alpha may invoke its own event."""
    greeted(name)


def tick() -> None:
    print(f"  [alpha] tick, running as {sdk.plugins.require_current().name}")


# Created while alpha's module loads, hence alpha's: all of them go away on disable.
ticker = sdk.Timer.interval(tick, 0.05)
scratch = sdk.TempFile(suffix=".scratch")

# Persistent: survives `disable`, goes away on `uninstall`.
data = sdk.DataDirectory(Path(scratch.path).with_suffix(".data"))
data.path.mkdir(exist_ok=True)
