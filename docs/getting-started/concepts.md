# Core concepts

pkl tracks resources. To do that it needs to know *who is creating each resource* and *what each plugin owns*.
Four concepts, each in its own module, and nothing else in the core.

## Plugin

The identity of a plugin. Two plugins are the same if and only if they are the same object (`is`).
A `Plugin` has no name, path, metadata or state. Derive from it, compose it or wrap it to attach what your
application knows:

```python
from dataclasses import dataclass, field
from pkl import Plugin

@dataclass(eq=False)               # eq=False keeps identity semantics
class AppPlugin(Plugin):
    id: str
    name: str
    metadata: dict[str, str] = field(default_factory=dict)
```

pkl only ever reads the identity. (Registries key plugins by `id()`, so even a value-equal dataclass is safe.)

## PluginTracker

Knows which plugin is currently executing.

```python
plugins = PluginTracker[AppPlugin]()
plugins.current                    # AppPlugin | None
with plugins.executing(alpha):     # nests, restores on exit and on error
    plugins.current                # alpha
    plugins.require_current()      # alpha, or NoCurrentPluginError
with plugins.executing(None):      # run as the host
    ...

run = plugins.bind(func)           # captures the plugin executing *now*; `run()` then runs as it, from anywhere
plugins.bind_as(alpha, func)       # the same for an explicit plugin
```

The current plugin is stored in a `ContextVar`: it is per thread and per `asyncio` task. Trackers are independent;
there is no default tracker.

## Resource

A thing that can be released: any object with `release() -> None` (a `Protocol`). `release()` should be safe to call
twice.

## ResourceRegistry

Maps plugins to resources.

| Method | |
|---|---|
| `register(plugin, resource)` | Record that `resource` belongs to `plugin`. |
| `unregister(plugin, resource) -> bool` | Forget it without releasing. |
| `release(plugin)` | Release every resource of `plugin`, newest first. |
| `release_all()` | The same for every plugin, newest plugin first. |
| `resources(plugin)`, `plugins()` | Snapshots, oldest first. |

`release` keeps going when a resource raises and then raises an `ExceptionGroup` with all the errors. Resources
registered while releasing are released too. It is thread-safe and idempotent.

## Extensions

Everything else (`pkl.tracking`, `events`, `syscall`, `timing`, `files`, `modules`, `dependencies`, `hosting`) is an extension. The dependency
rule is one-way: the core never imports an extension, and extensions only import the core and `pkl.tracking`, never
each other. A test enforces it. Your own extensions follow the same rule and get the same treatment as ours.
