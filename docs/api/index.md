# API reference

## Core (`pkl`)

| Name | |
|---|---|
| `Plugin` | Identity of a plugin. |
| `PluginTracker[P]` | `current`, `require_current()`, `executing(plugin)`. |
| `Resource` | Protocol: `release() -> None`. |
| `ResourceRegistry[P]` | `register`, `unregister`, `release`, `release_all`, `resources`, `plugins`. |
| `PklError`, `NoCurrentPluginError` | Errors. |

## `pkl.tracking`

| Name | |
|---|---|
| `ResourceTracker[P](plugins, registry, allow_orphans=False)` | `current_owner()`, `track(resource)`. |
| `Tracked[P]` | Auto-registering base. Class keywords `tracker=`, `allow_tracker_override=`. `owner`, `tracker`, `released`, `release()`, `with_tracker(tracker)`, `executing_as_owner()`; implement `_release()`. |
| `UnboundResourceError`, `TrackerOverrideError` | Errors. |

## `pkl.events`

`Event[**Params](func, *, protected=False)`: `subscribe`, `unsubscribe`, `on`, `+=`, `-=`, `subscriptions`, call, `emit`.
`Subscription`, `EventPermissionError`, `EventReleasedError`.

## `pkl.syscall`

`syscall(plugins, func)`.

## `pkl.timing`

`Timer(callback, delay, *, repeat=False)`, `Timer.timeout(callback, delay)`, `Timer.interval(callback, delay)`.

## `pkl.files`

`File(path)`, `Directory(path)`, `TempFile(*, suffix, prefix, dir)`, `TempDirectory(*, suffix, prefix, dir)`.

## `pkl.modules`

`ModuleResource(name, path, *, package=False, replace=False)` with `module`, `name`, `path`; `ModuleAlreadyLoadedError`.
