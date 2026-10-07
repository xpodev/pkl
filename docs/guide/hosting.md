# Hosts as resources

A **host** is what an application builds from the core: a `PluginTracker` (who is executing?) and the registries
(lifetimes) that hold their resources. `pkl.hosting.PluginHost` makes that bundle a *resource*, so a plugin can own a
world of plugins of its own, for example a plugin that is itself a plugin framework. Because the host is tracked like
any other resource, releasing the owning plugin releases the whole nested world.

```python
from pkl.hosting import PluginHost

Host = PluginHost[SubPlugin].with_tracker(app_tracker)   # or subclass it, bound to your SDK's base

# inside the framework plugin:
host = Host()                          # owned by the plugin that created it
world = host.registry()                # a lifetime of the nested world
tracker = host.tracker_for(world)      # attributes new resources to the nested plugins

with host.plugins.executing(sub_plugin):
    Timer.with_tracker(tracker).interval(poll, 1.0)

runtime.release(framework)             # releases the framework, its host and every sub-plugin's resources
```

| | |
|---|---|
| `host.plugins` | The nested `PluginTracker`. Independent of the outer world's tracker. |
| `host.registry()` | Create a lifetime of the host. |
| `host.tracker_for(registry, allow_orphans=False)` | A `ResourceTracker` for the host's plugins and that registry. |
| `host.registries` | The lifetimes made so far, oldest first. |

Releasing the host (by hand, or through its owner) releases every lifetime, **newest lifetime first**, and keeps going
when a resource fails, raising an `ExceptionGroup`. Afterwards the host is closed: `registry()` and registering into one
of its registries raise `HostReleasedError`, because nobody would ever release what was added.

Hosts nest to any depth, and give the owner no special powers: a host is just a resource that happens to contain
registries. Like every tracked resource it needs an owner unless its tracker allows orphans.
