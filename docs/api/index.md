# API Reference

Complete API documentation for PKL.

## Core Components

PKL provides a comprehensive plugin system with the following components:

- **PluginHost** - Main plugin management system
- **Plugin** - Plugin representation and control
- **Events** - Event system (Event, HostEvent, EventBase, @event decorator)
- **Resources** - Resource management with automatic cleanup
- **Context** - Plugin context tracking and awareness
- **Utilities** - Helper functions and decorators

## Quick Links

### Main Classes

- `PluginHost` - Plugin host system
- `Plugin` - Plugin instance
- `Event` - Plugin-owned event
- `HostEvent` - System-level event
- `Resource` - Base class for resources
- `EventSubscription` - Event subscription resource

### Decorators

- `@event()` - Create plugin or host events
- `@syscall` - Preserve plugin context

### Functions

- `load_plugin()` - Load a plugin
- `get_current_plugin()` - Get current plugin
- `get_default_host()` - Get default host
- `set_default_host()` - Set default host
- `get_logger()` - Get plugin logger
- `set_timeout()` - Schedule one-time callback
- `set_interval()` - Schedule repeating callback

### Constants

- `PluginState` - Plugin state enum
- `log` - Logging proxy

## Import Patterns

```python
import pkl

# Main API
host = pkl.PluginHost()
plugin = pkl.load_plugin(path)
current = pkl.get_current_plugin()

# Decorators
@pkl.event()
def my_event():
    yield

@pkl.syscall
def my_api():
    return \"Hello\"

# Utilities
pkl.log.info(\"Message\")
logger = pkl.get_logger(\"component\")
timer = pkl.set_timeout(callback, 5.0)

# Plugin imports
from pkl.plugins import other_plugin
other_plugin.do_something()
```

## Type Annotations

```python
from typing import Optional
from pkl import Plugin, PluginHost, Event, Resource

def process_plugin(plugin: Plugin) -> None:
    ...

def handle_resource(resource: Resource) -> None:
    ...
```
