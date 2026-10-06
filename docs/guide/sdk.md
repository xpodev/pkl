# Building an SDK

The intended use: your application owns an SDK module, plugins import only that, and tracking is fully automatic and
invisible. The SDK is where the application decides its plugin type, its lifetimes and its vocabulary.

```python
# myapp/sdk.py
@dataclass(eq=False)
class AppPlugin(Plugin):
    id: str
    name: str
    metadata: Mapping[str, Any]

plugins = PluginTracker[AppPlugin]()
runtime = ResourceRegistry[AppPlugin]()
persistent = ResourceRegistry[AppPlugin]()

class RuntimeResource(Tracked[AppPlugin], tracker=ResourceTracker(plugins, runtime),
                      allow_tracker_override=False): ...
class PersistentResource(Tracked[AppPlugin], tracker=ResourceTracker(plugins, persistent),
                         allow_tracker_override=False): ...

class Event(events.Event[Params], RuntimeResource): ...
class Timer(timing.Timer, RuntimeResource): ...
class DataDirectory(files.Directory, PersistentResource): ...
syscall = partial(pkl.syscall.syscall, plugins)

def disable(plugin: AppPlugin) -> None:
    runtime.release(plugin)

def uninstall(plugin: AppPlugin) -> None:
    disable(plugin)
    persistent.release(plugin)
```

A plugin then just uses the SDK:

```python
import sdk

@sdk.Event
def greeted(name: str) -> None: ...

ticker = sdk.Timer.interval(tick, 1.0)
```

Nothing global was modified, nothing was passed around, and a plugin cannot pick another lifetime or host. The complete,
runnable version is `examples/sdk.py` with `examples/main.py`. For several hosts in one process see `examples/zones.py`.

Metadata, dependencies, manifests, parent/child plugins and logging are deliberately not part of pkl: they are your
`AppPlugin` and your own extensions (a child plugin, for example, is just a resource whose `release()` calls
`registry.release(child)`).
