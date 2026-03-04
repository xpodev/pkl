# Plugin Lifecycle

Understanding plugin states and lifecycle events.

## Plugin States

```
UNLOADED → LOADED → ENABLED → DISABLED
              ↓
           ERROR
```

### UNLOADED

Plugin hasn't been loaded yet.

### LOADED

Plugin module loaded, ready to enable:

```python
plugin = pkl.load_plugin(path)  # State: LOADED
```

### ENABLED

Plugin is active and running:

```python
plugin.enable()  # State: ENABLED
# - Entrypoint code runs
# - Resources can be created
# - Plugin is fully operational
```

### DISABLED

Plugin stopped, all resources cleaned up:

```python
plugin.disable()  # State: DISABLED
# - on_disable events fire
# - Resources cleaned up
# - Plugin no longer operational
```

### ERROR

Plugin failed to load or enable:

```python
try:
    plugin.enable()
except Exception as e:
    print(plugin.state)  # ERROR
    print(plugin._error)  # The exception
```

## Lifecycle Events

Plugins can react to their own lifecycle:

### on_disable

Called when plugin is being disabled:

```python
from pkl import get_current_plugin

@get_current_plugin().on_disable.on
def cleanup():
    print("Plugin is being disabled!")
    # Save state, close connections, etc.
```

Or using += operator:

```python
def cleanup():
    print("Plugin is being disabled!")

get_current_plugin().on_disable += cleanup
```

### on_unload

Called when plugin is being unloaded:

```python
def final_cleanup():
    print("Plugin is being unloaded!")

get_current_plugin().on_unload += final_cleanup
```

## Lifecycle Hooks

Host-level hooks for monitoring:

```python
host = pkl.PluginHost()

def on_enable(plugin):
    print(f"Plugin enabled: {plugin.name}")

def on_disable(plugin):
    print(f"Plugin disabled: {plugin.name}")

host.add_enable_hook(on_enable)
host.add_disable_hook(on_disable)
```

## Cleanup Order

When `plugin.disable()` is called:

1. `on_disable` lifecycle event fires
2. Resources cleaned up (reverse registration order)
3. Plugin state set to DISABLED
4. Host disable hooks called

```python
# During plugin enable:
timer1 = set_timeout(func1, 1.0)  # Registered first
timer2 = set_timeout(func2, 2.0)  # Registered second

# During plugin disable:
# timer2 cleaned up first
# timer1 cleaned up second
```

## Best Practices

### ✅ DO

- Use `on_disable` for cleanup logic
- Save state in `on_disable`
- Handle errors gracefully
- Clean up external resources

### ❌ DON'T

- Assume resources live after disable
- Access disabled plugin's resources
- Call `disable()` from the same plugin
- Raise exceptions in lifecycle handlers

## Next Steps

- [Resources](resources.md)
- [Events](events.md)
- [API Reference](../api/index.md)
