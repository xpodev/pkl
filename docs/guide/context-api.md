# Context & API

Understanding plugin context and creating cross-plugin APIs.

## Plugin Context

The "current plugin" is the plugin whose code is currently executing. PKL tracks this using context variables (thread-safe and async-safe).

### Getting Current Plugin

```python
from pkl import get_current_plugin

def my_function():
    plugin = get_current_plugin()
    print(f"Running as: {plugin.name}")
    print(f"Plugin path: {plugin.path}")
    print(f"Plugin state: {plugin.state}")
```

### Context Switches

Context automatically switches when:

1. **Plugin enable/disable** - Context set to the plugin
2. **Event handlers** - Context switches to subscribing plugin
3. **API calls** with `@syscall` - Context switches to defining plugin

```python
# Plugin A
def normal_function():
    print(get_current_plugin().name)  # Could be any plugin!

# Plugin B calls it
from pkl.plugins import a
a.normal_function()  # Prints "b" (caller's context)
```

## The @syscall Decorator

`@syscall` preserves the defining plugin's context across calls.

### Basic Usage

```python
from pkl import syscall, get_current_plugin

@syscall
def my_api():
    """Always runs as the plugin that defined it."""
    plugin = get_current_plugin()
    print(f"Running as: {plugin.name}")  # Always this plugin
    return plugin.name
```

When another plugin calls this function, context switches:

```python
# Plugin A defines the API
@syscall
def get_plugin_info():
    return {
        "name": get_current_plugin().name,  # "a"
        "state": get_current_plugin().state
    }

# Plugin B calls it
from pkl.plugins import a

info = a.get_plugin_info()
print(info["name"])  # "a" (not "b"!)
```

### Why Use @syscall?

**Problem**: Without `@syscall`, functions run in the caller's context:

```python
# Plugin A
def broken_api():
    # Intended to return Plugin A's name
    return get_current_plugin().name

# Plugin B
from pkl.plugins import a
name = a.broken_api()  # Returns "b", not "a"!
```

**Solution**: Use `@syscall` to preserve plugin context:

```python
# Plugin A
@syscall
def fixed_api():
    return get_current_plugin().name

# Plugin B
from pkl.plugins import a
name = a.fixed_api()  # Returns "a" ✓
```

### Common Use Cases

#### 1. Resource Access

```python
@syscall
def get_database():
    """Access this plugin's database connection."""
    return get_current_plugin().db_connection
```

#### 2. Event Invocation

```python
from pkl import event, syscall

@event()
def data_changed():
    yield

@syscall
def update_data(value):
    """Public API that triggers internal event."""
    # Do the update...
    data_changed()  # Can only invoke in our context!
```

#### 3. State Management

```python
@syscall
def get_config(key: str):
    """Get configuration from this plugin's state."""
    plugin = get_current_plugin()
    return plugin.config.get(key)
```

#### 4. Logging

```python
@syscall
def log_action(message: str):
    """Log to this plugin's logger."""
    from pkl import log
    log.info(message)  # Logs with this plugin's name
```

## Creating Plugin APIs

### Structure

Typical plugin structure:

```
my_plugin/
  ├── plugin.json          # Metadata
  ├── plugin.py            # Entrypoint (initialization)
  ├── __init__.py          # Public API
  └── internal.py          # Internal modules
```

### __init__.py Pattern

Export your public API from `__init__.py`:

```python
# my_plugin/__init__.py
"""Public API for my_plugin."""

from pkl import syscall, get_current_plugin

@syscall
def do_something(value: str) -> bool:
    """Public API function."""
    plugin = get_current_plugin()
    # Access plugin resources...
    return True

@syscall
def get_status() -> dict:
    """Get plugin status."""
    plugin = get_current_plugin()
    return {
        "name": plugin.name,
        "enabled": plugin.state == pkl.PluginState.ENABLED,
        "resources": len(plugin.host.resource_manager._resources.get(plugin, []))
    }
```

### Importing Plugin APIs

Other plugins import via `pkl.plugins`:

```python
# In another plugin
from pkl.plugins import my_plugin

result = my_plugin.do_something("test")
status = my_plugin.get_status()
```

## Advanced Context Patterns

### Temporary Context Switch

Manually switch context (rarely needed):

```python
from pkl import get_default_host
from pkl.context import plugin_context

host = get_default_host()
other_plugin = host.get_plugin("other")

with plugin_context(host, other_plugin):
    # Code here runs as other_plugin
    print(get_current_plugin().name)  # "other"
```

### Async Context Preservation

Context is preserved across `await`:

```python
@syscall
async def async_api():
    plugin = get_current_plugin()
    print(f"Before await: {plugin.name}")
    
    await asyncio.sleep(1)
    
    # Context preserved!
    plugin = get_current_plugin()
    print(f"After await: {plugin.name}")  # Same plugin
```

### Detached Context

Run code without plugin context:

```python
from pkl.context import plugin_context

with plugin_context(host, None):
    # No current plugin
    plugin = get_current_plugin()  # None
```

## Multi-Plugin Communication

### Direct API Calls

Simplest way to interact:

```python
# Plugin A provides API
@syscall
def get_data():
    return {"value": 42}

# Plugin B uses it
from pkl.plugins import a
data = a.get_data()
```

### Event-Based Communication

Loose coupling via events:

```python
# Plugin A defines event
@event()
def task_completed(task_id: int):
    yield

# Plugin B subscribes
from pkl.plugins import a

def on_task_done(task_id: int):
    print(f"Task {task_id} is done!")

a.task_completed += on_task_done

# Plugin A triggers via API
@syscall
def complete_task(task_id: int):
    # Do work...
    task_completed(task_id)
```

### Host Events for Broadcast

System-wide notifications:

```python
# host_events.py
@pkl.event()
def configuration_changed():
    yield

# Multiple plugins can react
# Plugin A
from host_events import configuration_changed
configuration_changed += reload_config_a

# Plugin B
from host_events import configuration_changed
configuration_changed += reload_config_b

# Host triggers
from host_events import configuration_changed
configuration_changed()  # All plugins notified
```

## Type Safety

### Typed APIs

Use type hints for better IDE support:

```python
from typing import Optional, Dict, List
from pkl import syscall

@syscall
def find_user(user_id: int) -> Optional[Dict[str, any]]:
    """Find a user by ID."""
    ...

@syscall
def list_users(limit: int = 10) -> List[Dict[str, any]]:
    """List users."""
    ...
```

### TYPE_CHECKING

Use for type checking without circular imports:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pkl import Plugin

@syscall
def process(plugin: "Plugin") -> str:
    """Type hints work with forward references."""
    return plugin.name
```

## Best Practices

### ✅ DO

- Use `@syscall` for all public API functions
- Document API functions clearly
- Keep APIs focused and minimal
- Use type hints
- Version your APIs

### ❌ DON'T

- Access internal plugin state directly
- Call private functions from other plugins
- Assume context without checking
- Mix sync/async without care
- Break encapsulation

## Examples

### Example: Database Plugin API

```python
# database_plugin/__init__.py
from typing import Optional, List, Dict
from pkl import syscall, get_current_plugin

@syscall
def execute_query(sql: str) -> List[Dict]:
    """Execute a SQL query."""
    plugin = get_current_plugin()
    conn = plugin.connection
    return conn.execute(sql).fetchall()

@syscall
def get_connection_info() -> Dict[str, str]:
    """Get database connection information."""
    plugin = get_current_plugin()
    return {
        "host": plugin.db_host,
        "database": plugin.db_name,
        "status": "connected"
    }
```

### Example: Using the Database API

```python
# In another plugin
from pkl.plugins import database

# Execute query (runs in database plugin's context)
results = database.execute_query("SELECT * FROM users")

# Get info
info = database.get_connection_info()
print(f"Connected to: {info['database']}")
```

## Next Steps

- [Resources](resources.md) - Manage plugin resources
- [Lifecycle](lifecycle.md) - Plugin lifecycle management
- [Events](events.md) - Event system deep dive
- [Examples](../examples/overview.md) - Complete examples
