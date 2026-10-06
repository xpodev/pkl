# pkl

Attribute resources to plugins, and release them whenever you decide a lifetime ends.

A plugin system has to answer two questions: **who is running right now?** and **who owns what?**
That is the whole core of pkl. It never decides what "enable", "disable" or "uninstall" mean:
a *registry is a lifetime*, and you call `release(plugin)` whenever you want.

```python
from pkl import Plugin, PluginTracker, ResourceRegistry

plugins = PluginTracker[Plugin]()
disable = ResourceRegistry[Plugin]()      # a lifetime

class Connection:                         # anything with release() is a resource
    def release(self) -> None:
        print("closed")

alpha = Plugin()
with plugins.executing(alpha):
    disable.register(plugins.require_current(), Connection())

disable.release(alpha)                    # prints "closed"
```

- [Core concepts](getting-started/concepts.md): `Plugin`, `PluginTracker`, `Resource`, `ResourceRegistry`.
- [Quick start](getting-started/quick-start.md): from nothing to automatic tracking.
- [Lifetimes](guide/lifetimes.md): disable, uninstall, or any lifetime of your own.
- [Building an SDK](guide/sdk.md): the intended way to use pkl in an application.
