# Timers, files and modules

All of these are `Tracked` resources: bind them to a lifetime by deriving from your own base, as in
[Tracking](tracking.md).

```python
class Timer(timing.Timer, RuntimeResource): ...
class TempFile(files.TempFile, RuntimeResource): ...
class DataDirectory(files.Directory, PersistentResource): ...
class Module(modules.ModuleResource, RuntimeResource): ...
```

## Timers (`pkl.timing`)

`Timer.timeout(callback, delay)` and `Timer.interval(callback, delay)`. Callbacks run on a background thread as the
plugin that created the timer. Release cancels it; a one-shot timer releases itself after firing. Exceptions in the
callback are logged to the `pkl.timing` logger and a repeating timer keeps going.

## Files (`pkl.files`)

`File(path)` and `Directory(path)` are deleted on release (already gone is fine). `TempFile(...)` and
`TempDirectory(...)` create a temporary one first. Bound to a runtime registry they vanish on disable; bound to a
persistent one, on uninstall.

## Modules (`pkl.modules`)

`ModuleResource(name, path, *, package=False, replace=False)` loads a `.py` file, or a package directory containing
`__init__.py`, under the dotted name you choose.

- A package is real: `__path__` points at its directory, so `from .plugin import x`, `from . import helpers` and
  `importlib.import_module(f"{name}.plugin")` work, and nothing is executed twice.
- The module's top-level code runs as whichever plugin is executing, so what it creates is that plugin's.
- Missing parent packages (`myapp.plugins`) are stubbed and removed again with their last child.
- Release removes the module and everything nested under it from `sys.modules`; a failed load leaves nothing behind.
- A taken name raises `ModuleAlreadyLoadedError` unless `replace=True`.

`sys.modules` is process-global: keep names unique (`f"myapp.plugins.{plugin.name}"`). Other plugins can then import a
plugin's package by that name, e.g. `from myapp.plugins import alpha`.
