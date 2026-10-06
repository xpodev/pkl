# Quick start

## By hand

```python
from pkl import Plugin, PluginTracker, ResourceRegistry

plugins = PluginTracker[Plugin]()
registry = ResourceRegistry[Plugin]()

class Worker:
    def release(self) -> None:
        print("worker stopped")

alpha = Plugin()
with plugins.executing(alpha):
    registry.register(plugins.require_current(), Worker())

registry.release(alpha)
```

## Automatically

Registering by hand is what `pkl.tracking` removes. Bind a base class to a tracker once:

```python
from pkl.tracking import ResourceTracker, Tracked

class RuntimeResource(Tracked[Plugin], tracker=ResourceTracker(plugins, registry)): ...

class Worker(RuntimeResource):
    def _release(self) -> None:
        print("worker stopped")

with plugins.executing(alpha):
    Worker()                      # attributed to alpha, recorded in `registry`

registry.release(alpha)           # prints "worker stopped"
```

`Tracked` handles the rest: the owner is known from the start of `__init__`, the resource is registered only once
`__init__` succeeded, `release()` is idempotent, and releasing by hand also forgets the resource.

Next: [Lifetimes](../guide/lifetimes.md), [Tracking](../guide/tracking.md).
