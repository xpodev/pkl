# Loading Plugins

How to load and manage plugins in your application.

## Basic Loading

```python
import pkl
from pathlib import Path

# Create a host
host = pkl.PluginHost()
pkl.set_default_host(host)

# Load a plugin
plugin = pkl.load_plugin(Path("./my_plugin"))

# Enable it
plugin.enable()

# Use it
from pkl.plugins import my_plugin
my_plugin.do_something()

# Disable when done
plugin.disable()
```

## Plugin States

Plugins transition through states:

```
UNLOADED → LOADED → ENABLED → DISABLED
              ↓
           ERROR
```

- **UNLOADED**: Not yet loaded
- **LOADED**: Code loaded, not running
- **ENABLED**: Active and running
- **DISABLED**: Stopped, resources cleaned up
- **ERROR**: Failed to load/enable

## Loading from Different Sources

### From Path

```python
plugin = pkl.load_plugin(Path("/path/to/plugin"))
```

### From String Path

```python
plugin = pkl.load_plugin("./plugins/my_plugin")
```

## Plugin Dependencies

Plugins can depend on other plugins:

```json
{
  "name": "my_plugin",
  "requires": ["auth", "database"]
}
```

Dependencies must be loaded and enabled first:

```python
auth = pkl.load_plugin("./auth")
auth.enable()

db = pkl.load_plugin("./database")  
db.enable()

# Now can load dependent plugin
my_plugin = pkl.load_plugin("./my_plugin")
my_plugin.enable()
```

## Error Handling

```python
try:
    plugin = pkl.load_plugin(path)
    plugin.enable()
except ImportError as e:
    print(f"Failed to load: {e}")
except Exception as e:
    print(f"Failed to enable: {e}")
    print(f"Plugin state: {plugin.state}")
```

## Next Steps

- [Resources](resources.md)
- [Lifecycle](lifecycle.md)
