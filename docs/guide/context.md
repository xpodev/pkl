# Context, syscalls, async and threads

## Syscalls

A function marked with `pkl.syscall.syscall` runs as the plugin that **defined** it, whoever calls it, and the caller's
plugin is restored afterwards.

```python
syscall = partial(pkl.syscall.syscall, plugins)      # bind once per application

with plugins.executing(provider):
    @syscall
    def who_am_i() -> AppPlugin | None:
        return plugins.current

with plugins.executing(caller):
    who_am_i()                   # provider
    plugins.current              # caller again
```

The defining plugin is the one executing when the decorator is applied (so, while a plugin's module loads). Defined
outside any plugin it runs as the host. Plain and `async` functions are supported. Because the tracker is passed
explicitly there is no hidden host: `syscall` works with any number of trackers.

## Binding callbacks

`plugins.bind(func)` is the primitive behind syscalls: it captures the plugin executing *now* and returns a function
that runs as that plugin, from any thread or task. `plugins.bind_as(plugin, func)` is the same for an explicit plugin.
Everything in pkl that has to "run as someone" goes through it.

```python
with plugins.executing(alpha):
    on_message = plugins.bind(handle)          # captured at creation, no need to remember later
threading.Thread(target=on_message).start()    # runs as alpha
```

Resources have a shortcut that binds to their owner: `self.bind(func)`. And `tracker.callback(func, finalizer=...)`
makes a tracked, releasable `Callback` (inert once released).

## Async

The current plugin is in a `ContextVar`. Concurrent tasks that run as different plugins never see each other's plugin,
also across `await`s, and tasks inherit the plugin they were created under (`create_task`, `TaskGroup`).

## Threads

New threads start with an empty context, so a plain `threading.Thread` has no current plugin. Bind the entry point
(or copy the context):

```python
threading.Thread(target=plugins.bind(work)).start()
# or: loop.run_in_executor(None, plugins.bind(work))
# or: context = contextvars.copy_context(); threading.Thread(target=context.run, args=(work,))
```

Creating a tracked resource in such a thread raises `NoCurrentPluginError` instead of leaking silently.
`pkl.timing.Timer` re-enters its owner for you.
