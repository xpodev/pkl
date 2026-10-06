"""Several independent hosts in one process. Run with ``python examples/zones.py``.

Unlike ``sdk.py`` (one global host), a game server might want one host per zone.
Nothing in pkl is global, so each zone simply owns its trackers.
"""

from __future__ import annotations

from pkl import Plugin, PluginTracker, ResourceRegistry
from pkl.timing import Timer
from pkl.tracking import ResourceTracker


class Zone:
    def __init__(self, name: str) -> None:
        self.name = name
        self.plugins = PluginTracker[Plugin]()
        self.registry = ResourceRegistry[Plugin]()
        # One Timer class, rebound to this zone's tracker.
        self.timer = Timer.with_tracker(ResourceTracker(self.plugins, self.registry))


def main() -> None:
    forest, desert = Zone("forest"), Zone("desert")
    weather = Plugin()  # the same plugin identity can run in both zones

    for zone in (forest, desert):
        with zone.plugins.executing(weather):
            zone.timer.interval(lambda: None, 60)

    print(f"forest tracks {len(forest.registry.resources(weather))} resource(s)")
    print(f"desert tracks {len(desert.registry.resources(weather))} resource(s)")

    forest.registry.release(weather)
    print(f"after releasing forest: forest={len(forest.registry.resources(weather))}, "
          f"desert={len(desert.registry.resources(weather))}")
    desert.registry.release_all()


if __name__ == "__main__":
    main()
