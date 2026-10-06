"""Beta: reacts to alpha's greetings."""

import sdk
from example_plugins import alpha  # type: ignore[import-not-found]


@alpha.greeted.on
def on_greeted(name: str) -> None:
    print(f"  [beta] hello {name}! (running as {sdk.plugins.require_current().name})")
