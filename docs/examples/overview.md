# Examples

The repository ships runnable examples in `examples/`.

## `examples/main.py`: two plugins, one host

Uses `examples/sdk.py` (an SDK with a derived `AppPlugin`, a runtime and a persistent lifetime) and two plugins in
`examples/plugins/`. `alpha` defines an event, a syscall, a timer, a temp file and a data directory; `beta` subscribes
to alpha's event through `from example_plugins import alpha`. The script then disables `beta` (its subscription
disappears), disables `alpha` (timer and temp file go, the data directory stays) and finally uninstalls it.

```bash
python examples/main.py
```

## `examples/zones.py`: several hosts in one process

Each zone owns its own `PluginTracker` and `ResourceRegistry`; one `Timer` class serves all of them through
`Timer.with_tracker(...)`. Releasing a plugin in one zone leaves the other zones untouched.

```bash
python examples/zones.py
```
