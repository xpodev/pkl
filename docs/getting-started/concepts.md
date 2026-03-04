# Core Concepts

Understanding PKL's architecture and design principles.

## The OS Analogy

PKL treats plugins like **processes** in an operating system:

- Each plugin runs in its own "context"
- Resources are tracked like file descriptors
- Context switches happen automatically
- Cleanup is guaranteed (like process exit)

## Architecture Overview

```
┌─────────────────────────────────────────┐
│           PluginHost                     │
│  ┌────────────────────────────────────┐ │
│  │     ResourceManager                │ │
│  │  - Tracks all resources            │ │
│  │  - Cleanup on disable              │ │
│  └────────────────────────────────────┘ │
│                                          │
│  ┌──────────┐  ┌──────────┐            │
│  │ Plugin A │  │ Plugin B │  ...       │
│  │          │  │          │            │
│  │ Resources│  │ Resources│            │
│  │ - Events │  │ - Timers │            │
│  │ - Loggers│  │ - Custom │            │
│  └──────────┘  └──────────┘            │
└─────────────────────────────────────────┘
```

## Key Components

### PluginHost

The central coordinator that manages:

- Plugin loading and lifecycle
- Context tracking (which plugin is currently executing)
- System-wide hooks
- Host-level events

```python
host = pkl.PluginHost(name="my_app")
```

### Plugin

Represents a loaded plugin with:

- **State**: UNLOADED → LOADED → ENABLED → DISABLED
- **Resources**: Everything the plugin creates
- **Module**: The loaded Python module
- **Metadata**: Name, version, dependencies, etc.

```python
plugin = host.load_plugin(path)  # State: LOADED
plugin.enable()                   # State: ENABLED
plugin.disable()                  # State: DISABLED, resources cleaned up
```

### Resources

Objects that need cleanup. Built-in resources:

- **EventSubscription** - Event handlers
- **Timer** - Scheduled callbacks (set_timeout, set_interval)
- **Logger** - Per-plugin loggers

Custom resources:

```python
from pkl import Resource

class DatabaseConnection(Resource):
    def _cleanup(self):
        self.conn.close()
```

### ResourceManager

Tracks all resources and handles cleanup:

```python
# Automatic registration for built-in resources
timer = pkl.set_timeout(my_func, 5.0)  # Auto-registered

# Manual registration for custom resources
conn = DatabaseConnection(plugin, "localhost")
plugin.host.resource_manager.register(conn)
```

## Plugin Context

The "current plugin" is tracked using context variables (thread-safe and async-safe):

```python
from pkl import get_current_plugin

def my_function():
    plugin = get_current_plugin()
    print(f"Running as: {plugin.name}")
```

### Context Switches

Context automatically switches during:

- Plugin enable/disable
- Event handler execution
- API calls with `@syscall`

```python
# Plugin A code
@syscall
def my_api():
    # Always runs as Plugin A
    print(get_current_plugin().name)  # "a"

# Plugin B code
from pkl.plugins import a

a.my_api()  # Context switches: B → A → B
```

## Event System

Events come in two flavors:

### Plugin Events

Owned by a plugin, only that plugin can invoke:

```python
# In Plugin A
@event()
def user_login(username: str):
    print(f"User logging in: {username}")
    yield  # Handlers run here
    print("Login complete")

# Other plugins can only subscribe
# Plugin B
from pkl.plugins import a

def on_login(username):
    print("Handling login...")

a.user_login += on_login  # ✅ Subscribe OK
# a.user_login("alice")    # ❌ RuntimeError: Only Plugin A can invoke
```

### Host Events

System-wide events with no owner. Defined outside plugin context:

```python
# host_events.py - defined before plugins load
import pkl

@pkl.event()
def system_started():
    """Automatically becomes a host event (no plugin context)."""
    print("System starting...")
    yield

# Any plugin can subscribe
from host_events import system_started

def on_start():
    print("Plugin sees startup!")

system_started += on_start
```

## Lifecycle

### Plugin Lifecycle States

```
UNLOADED → LOADED → ENABLED → DISABLED
                        ↓
                     ERROR
```

- **UNLOADED**: Plugin doesn't exist yet
- **LOADED**: Module loaded, ready to enable
- **ENABLED**: Running, resources active
- **DISABLED**: Stopped, all resources cleaned up
- **ERROR**: Failed to load or enable

### Lifecycle Events

Plugins can hook into their own lifecycle:

```python
from pkl import get_current_plugin

plugin = get_current_plugin()

@plugin.on_disable.on
def cleanup():
    print("Plugin is being disabled!")

# Or using += operator:
# plugin.on_disable += cleanup
plugin.on_unload += lambda: print("Plugin unloading")
```

## Resource Cleanup

When a plugin is disabled:

1. **Lifecycle events fire** - `on_disable` handlers run
2. **Resources cleaned up** - In reverse registration order
3. **Plugin disabled** - State transitions to DISABLED

All automatic - no manual cleanup needed!

```python
# Plugin code
logger = pkl.get_logger("db")
timer = pkl.set_timeout(task, 10.0)
event_sub = other_plugin.some_event += handler

# Later...
plugin.disable()
# ✓ Timer cancelled
# ✓ Event subscription removed  
# ✓ Logger disabled
# All automatic!
```

## Type Safety

PKL is fully typed with strict type checking:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pkl import Plugin

def process_plugin(plugin: Plugin) -> None:
    reveal_type(plugin.name)  # str
    reveal_type(plugin.state)  # PluginState
```

## Async Support

Context variables work across async/await:

```python
from pkl import syscall

@syscall
async def async_api():
    await asyncio.sleep(1)
    # Context still preserved!
    plugin = get_current_plugin()
    print(plugin.name)  # Correct
```

## Next Steps

- [Creating Plugins](../guide/creating-plugins.md) - Build your first plugin
- [Events](../guide/events.md) - Master the event system
- [Resources](../guide/resources.md) - Create custom resources
- [API Reference](../api/index.md) - Detailed API docs
