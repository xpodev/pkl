# Tracking

`pkl.tracking` turns "create a resource" into "create a resource and record it under whoever is running".

## ResourceTracker

A `PluginTracker` (who is running?) paired with a `ResourceRegistry` (where do their resources go?).
The registry is the passive map; the tracker is the active step.

```python
tracker = ResourceTracker(plugins, runtime)
tracker.track(resource)            # explicit form: registers under plugins.current
```

If no plugin is executing, `track` raises `NoCurrentPluginError`: an owner-less resource could never be released.
`ResourceTracker(..., allow_orphans=True)` instead lets such resources be host-owned (not recorded anywhere).

## Tracked

An abstract base class whose instances register themselves. Bind it with the `tracker` class keyword; subclasses inherit
the binding:

```python
class RuntimeResource(Tracked[AppPlugin], tracker=ResourceTracker(plugins, runtime)): ...
class PersistentResource(Tracked[AppPlugin], tracker=ResourceTracker(plugins, persistent)): ...
```

Subclasses implement `on_release()`. Properties: `owner` (typed as your plugin), `tracker`, `released`. Lifetime is
therefore not a library type: two bases bound to two registries are two lifetimes.

Instantiating a class that is not bound to a tracker raises `UnboundResourceError`.

### Several trackers from one class

```python
zone_timer = Timer.with_tracker(ResourceTracker(zone.plugins, zone.registry))
zone_timer.interval(callback, 1.0)
```

`with_tracker` returns the same class bound to another tracker (cached per tracker, fully typed). Seal a base with
`allow_tracker_override=False` and it raises `TrackerOverrideError` instead; use that in an SDK that is single-host by
design.

### Callbacks

For a one-off resource, or a function that must run as its creator, no class is needed:

```python
tracker.callback(on_message, finalizer=connection.close)   # tracked; runs as its creator; inert once released
```

### Your own resources

```python
class Socket(RuntimeResource):
    def __init__(self, address: str) -> None:
        self.connection = connect(address)       # self.owner is already available here
        # work on threads pkl does not control: bind it to the owner
        threading.Thread(target=self.bind(self.serve), daemon=True).start()
    def on_release(self) -> None:
        self.connection.close()
```
