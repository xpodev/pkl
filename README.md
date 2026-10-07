# pkl

Attribute resources to plugins, and release them whenever you decide a lifetime ends.

📚 **[Documentation](https://xpodev.github.io/pkl/)** · [The idea](#the-idea) · [Quick start](#quick-start) · [Extensions](#extensions) · [Examples](#examples)

## The idea

A plugin system has to answer two questions:

1. **Who is running right now?** So that whatever gets created can be attributed to someone.
2. **Who owns what?** So that it can all be cleaned up when the plugin goes away.

That is the whole core of `pkl`, in four small concepts:

| Concept | What it is |
|---|---|
| `Plugin` | An identity. Two plugins are the same iff they are the same object. Nothing else: derive, compose or wrap it to attach your own data. |
| `PluginTracker` | Knows which plugin is currently executing (per thread / `asyncio` task). |
| `Resource` | A thing that can be released: anything with a `release()` method. |
| `ResourceRegistry` | A map from plugin to resources. `release(plugin)` releases them all, newest first. |

`pkl` never decides what "enable", "disable" or "uninstall" mean. **A registry is a lifetime**: you create as many as you
like and call `release(plugin)` whenever *you* want. Call it on disable and it is a disable lifetime; call it on uninstall
and it is an uninstall lifetime. There is no global state: a process can have any number of trackers and registries.

Everything else is an **extension**: it depends on the core, and the core never imports it.

## Installation

Python 3.11+, no dependencies.

```bash
uv add plugins-kernel      # or: pip install plugins-kernel
```

## Quick start

```python
from dataclasses import dataclass
from pkl import Plugin, PluginTracker, ResourceRegistry


@dataclass(eq=False)                 # eq=False keeps "same iff `is`"
class AppPlugin(Plugin):             # pkl only sees the identity; the rest is yours
    name: str


plugins = PluginTracker[AppPlugin]()
disable = ResourceRegistry[AppPlugin]()   # a lifetime


class Connection:                    # any object with release() is a resource
    def release(self) -> None:
        print("closed")


alpha = AppPlugin("alpha")
with plugins.executing(alpha):       # alpha is running...
    owner = plugins.require_current()
    disable.register(owner, Connection())

disable.release(alpha)               # ...and now its lifetime ends: prints "closed"
```

Registering by hand gets tedious, which is what `pkl.tracking` is for.

## Extensions

Extensions are plain modules in the package. They depend on the core (and on `tracking`), never on each other.

| Module | Provides |
|---|---|
| `pkl.tracking` | `ResourceTracker`, `Tracked` (resources that register themselves under the plugin that created them) and `Callback` (a function bound to its creating plugin, as a resource). |
| `pkl.events` | `event_decorator` builds the `@event` decorator: events are invocable only by their owner (`protected=False` opts out), anyone subscribes, subscriptions die with the subscriber. Generator events run code before/after handlers. `emit()` awaits async handlers. |
| `pkl.syscall` | `syscall`: a function that runs as the plugin that defined it, whoever calls it. Sync and async. |
| `pkl.timing` | `Timer.timeout(...)` / `Timer.interval(...)`: cancelled on release, callbacks run as their owner. |
| `pkl.files` | `File`, `Directory`, `TempFile`, `TempDirectory`: deleted on release. |
| `pkl.modules` | `ModuleResource`: load a file or package under a dotted name, unload it on release. |
| `pkl.dependencies` | `depends_on` / `require`: a dependant is a resource of its dependency, so releasing a plugin releases everything that depends on it. |
| `pkl.hosting` | `PluginHost`: a host (plugin tracker + lifetimes) as a resource, so a plugin can own a whole nested world that is released with it. |

Bring your own: subclass `Tracked`, implement `on_release`, and your resource gets the same automatic tracking.

### Automatic tracking

Bind a base class to a lifetime once; every subclass is then recorded under the plugin that creates it:

```python
from pkl.tracking import ResourceTracker, Tracked
from pkl.timing import Timer

runtime = ResourceRegistry[AppPlugin]()


class RuntimeResource(Tracked[AppPlugin], tracker=ResourceTracker(plugins, runtime)): ...


class AppTimer(Timer, RuntimeResource): ...


with plugins.executing(alpha):
    AppTimer.interval(lambda: print("tick"), 1.0)   # attributed to alpha, recorded in `runtime`

runtime.release(alpha)                               # the timer is cancelled
```

Creating a tracked resource while no plugin is executing raises `NoCurrentPluginError`, because it could never be
released. Pass `ResourceTracker(..., allow_orphans=True)` for resources that legitimately belong to the host.

One class can also serve several trackers (e.g. one per game zone) without subclassing:
`Timer.with_tracker(zone.tracker).interval(...)`. An SDK that must stay single-host forbids that with
`allow_tracker_override=False`.

### An SDK for your plugins

If plugin authors only ever import *your* SDK, tracking is 100% automatic and they never see `pkl`. See
[`examples/sdk.py`](examples/sdk.py): it defines a derived `AppPlugin` (id, name, metadata), a runtime and a persistent
lifetime, the resource classes plugins use, and `disable()` / `uninstall()`.

## Async and threads

The current plugin lives in a `ContextVar`, so concurrent `asyncio` tasks that run as different plugins never see each
other's plugin, and tasks inherit the plugin they were created under. New threads start with an empty context: bind
their entry point with `plugins.bind(fn)` (it captures the plugin executing now), or `self.bind(fn)` inside a resource.
`Timer` does this for you.

## Examples

```bash
python examples/main.py    # two plugins, one host, disable vs uninstall lifetimes
python examples/zones.py   # several independent hosts in one process
python examples/dependencies.py   # releasing a plugin releases its dependants
python examples/nested.py  # a plugin that owns a plugin host
```

## Development

```bash
uv sync
uv run pytest
uv run mypy --strict pkl tests
```

## License

MIT
