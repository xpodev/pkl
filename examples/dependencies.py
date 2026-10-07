"""Plugin dependencies as resources. Run with ``python examples/dependencies.py``.

``api`` depends on ``database`` and ``dashboard`` depends on ``api``. Releasing a
plugin from a lifetime releases everything that depends on it, dependants first.
"""

from __future__ import annotations

from dataclasses import dataclass

from pkl import Plugin, PluginTracker, ResourceRegistry
from pkl.dependencies import depends_on, require
from pkl.tracking import ResourceTracker


@dataclass(eq=False)
class AppPlugin(Plugin):
    name: str


plugins = PluginTracker[AppPlugin]()
disabled = ResourceRegistry[AppPlugin]()  # the "disable" lifetime
tracker = ResourceTracker(plugins, disabled)


def load(name: str) -> AppPlugin:
    plugin = AppPlugin(name)
    with plugins.executing(plugin):
        # Something the plugin owns, e.g. a connection: it announces when it is released.
        tracker.callback(lambda: None, finalizer=lambda: print(f"  {name}: released"))
    return plugin


def main() -> None:
    database, api, dashboard, reports = (load(n) for n in ("database", "api", "dashboard", "reports"))

    depends_on(disabled, dependant=api, dependency=database)  # declared by the host...
    depends_on(disabled, dependant=dashboard, dependency=api)
    with plugins.executing(reports):
        require(tracker, database)  # ...or by the dependant itself

    print("disable api (dashboard depends on it, database does not):")
    disabled.release(api)

    print("disable database (reports depends on it; api and dashboard are already gone):")
    disabled.release(database)


if __name__ == "__main__":
    main()
