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

## Async

The current plugin is in a `ContextVar`. Concurrent tasks that run as different plugins never see each other's plugin,
also across `await`s, and tasks inherit the plugin they were created under (`create_task`, `TaskGroup`).

## Threads

New threads start with an empty context, so a plain `threading.Thread` has no current plugin. Hand the context over:

```python
context = contextvars.copy_context()
threading.Thread(target=context.run, args=(work,)).start()
# or: loop.run_in_executor(None, context.run, work)
```

Creating a tracked resource in such a thread raises `NoCurrentPluginError` instead of leaking silently.
`pkl.timing.Timer` re-enters its owner for you.
