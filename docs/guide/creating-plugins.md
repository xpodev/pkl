# Creating Plugins

Learn how to create well-structured plugins for PKL.

## Plugin Structure

A minimal plugin:

```
my_plugin/
├── plugin.json      # Metadata (required)
└── plugin.py        # Entrypoint (default name)
```

A complete plugin:

```
my_plugin/
├── plugin.json      # Metadata
├── plugin.py        # Entrypoint
├── __init__.py      # Public API
├── internal.py      # Internal modules
└── subplugins/      # Child plugins (optional)
```

## Metadata File

Create `plugin.json`:

```json
{
  "name": "my_plugin",
  "version": "1.0.0",
  "entrypoint": "plugin",
  "requires": ["other_plugin"]
}
```

Fields:
- `name` - Plugin identifier (required)
- `version` - Semantic version (optional)
- `entrypoint` - Module name without `.py` (default: "plugin")
- `requires` - List of plugin dependencies (optional)

## Plugin Code

### Entrypoint (plugin.py)

The entrypoint runs when the plugin is enabled:

```python
from pkl import log, event, get_current_plugin

# This code runs on enable
log.info("Plugin starting up")

# Create events
@event()
def my_event(data: str):
    log.info(f"Event triggered: {data}")
    yield

# Register cleanup
@get_current_plugin().on_disable.on
def cleanup():
    log.info("Cleaning up!")
```

### Public API (__init__.py)

Export your public API:

```python
from pkl import syscall, get_current_plugin

@syscall
def my_api_function(value: str) -> bool:
    """Public API that other plugins can call."""
    plugin = get_current_plugin()
    # Your logic here
    return True

@syscall
def trigger_my_event(data: str):
    """Public way to trigger the event."""
    from . import plugin
    plugin.my_event(data)
```

## Best Practices

### ✅ DO

- Keep plugins focused on one responsibility
- Use `@syscall` for all public API
- Document your API functions
- Handle errors gracefully
- Clean up resources in `on_disable`

### ❌ DON'T

- Access other plugins' internals
- Store global state outside plugin context
- Block during initialization
- Forget to register resources

## Next Steps

- [Loading Plugins](loading-plugins.md)
- [Resources](resources.md)
- [Events](events.md)
