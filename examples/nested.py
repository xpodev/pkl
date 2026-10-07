"""A plugin that owns a plugin host. Run with ``python examples/nested.py``.

``framework`` is a plugin of the application, and it is also a framework: it runs
plugins of its own in a host that it owns. The host is a resource of
``framework``, so releasing ``framework`` releases its whole world.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from pkl import Plugin, PluginTracker, ResourceRegistry
from pkl.hosting import PluginHost
from pkl.timing import Timer
from pkl.tracking import ResourceTracker


@dataclass(eq=False)
class AppPlugin(Plugin):
    name: str


# The application's world.
plugins = PluginTracker[AppPlugin]()
runtime = ResourceRegistry[AppPlugin]()
app_tracker = ResourceTracker(plugins, runtime)
Host = PluginHost[AppPlugin].with_tracker(app_tracker)


def main() -> None:
    framework = AppPlugin("framework")

    with plugins.executing(framework):
        host = Host()  # owned by `framework`, recorded in `runtime`

    # framework's own world: its plugins, and a lifetime for them
    sub_plugins = [AppPlugin("greeter"), AppPlugin("counter")]
    world = host.registry()
    world_tracker = host.tracker_for(world)
    for sub in sub_plugins:
        with host.plugins.executing(sub):
            Timer.with_tracker(world_tracker).interval(
                lambda sub=sub: print(f"  [{sub.name}] tick"), 0.05  # type: ignore[misc]
            )

    print(f"framework owns {len(runtime.resources(framework))} resource (the host)")
    print(f"the host runs {len(world.plugins())} plugins, "
          f"{sum(len(world.resources(p)) for p in sub_plugins)} timers")
    time.sleep(0.12)

    print("release framework:")
    runtime.release(framework)
    print(f"  host released: {host.released}")
    print(f"  timers left: {sum(len(world.resources(p)) for p in sub_plugins)}")
    time.sleep(0.12)  # nothing ticks any more


if __name__ == "__main__":
    main()
