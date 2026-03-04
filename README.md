# PKL - Plugin Hosting System

A Python package that implements a plugin hosting capability with comprehensive resource management, inspired by operating system concepts.

📚 **[View Full Documentation](https://xpodev.github.io/pkl/)** | [Quick Start](#quick-start) | [Examples](#examples)

## Overview

`pkl` treats plugins like processes in an operating system. Each plugin has its own resources, and the system keeps track of everything. When a plugin is disabled, all of its resources are automatically cleaned up.

### Key Features

- **Resource Management**: Automatic tracking and cleanup of plugin resources
- **Lifecycle Events**: Plugins can register handlers for `on_disable` and `on_unload` events
- **Context Preservation**: Functions can maintain plugin context across calls using `@syscall`
- **Event System**: Plugin events and host events with automatic context detection
  - Protected and public events with before/after hooks
  - Host events for system-wide notifications
  - Automatic subscription cleanup when plugins disable
- **Async Support**: Full async/await support with context variable propagation  
- **Child Plugins**: Plugins can load and manage child plugins
- **Custom Resources**: Define your own resource types (routes, workers, etc.)
- **Type Safety**: Full typing support with strict type checking
- **Hooks**: System-wide hooks for monitoring plugin lifecycle and context switches

## Installation

This project uses [uv](https://docs.astral.sh/uv/) for fast and reliable Python package management.

```bash
# Install uv first (if not already installed)
pip install uv

# Install pkl
uv pip install pkl
```

For development:
```bash
git clone https://github.com/xpodev/pkl.git
cd pkl
uv pip install -e .
```

## Quick Start

### Creating a Plugin

**plugin.json** (metadata):
```json
{
  "name": "my_plugin",
  "version": "1.0.0",
  "entrypoint": "plugin",
  "requires": []
}
```

**plugin.py** (entrypoint):
```python
from pkl import event, log

@event()
def user_login(username: str):
    log.info(f"User {username} logging in")
    yield  # Handlers run here
    log.info(f"User {username} logged in")
```

**__init__.py** (optional, for API):
```python
from pkl import syscall, get_current_plugin

@syscall
def get_user_count() -> int:
    """This runs in the plugin's context, not the caller's."""
    plugin = get_current_plugin()
    print(f"Called from plugin: {plugin.name}")
    return 42
```

### Loading and Running Plugins

```python
import pkl
from pathlib import Path

# Create a host
host = pkl.PluginHost()
pkl.set_default_host(host)

# Load and enable a plugin
plugin = pkl.load_plugin(path=Path("./my_plugin"))
plugin.enable()

# Use the plugin's API
from pkl.plugins import my_plugin
count = my_plugin.get_user_count()

# Trigger events
plugin.module.user_login("alice")

# Disable when done
plugin.disable()
```

## Core Concepts

### Resources

Resources are objects created by plugins that need cleanup. The system tracks:
- Event handlers
- Timers (set_timeout, set_interval)
- Loggers
- Custom resources you define

All resources are automatically cleaned up when their plugin is disabled.

```python
from pkl import Resource, get_current_plugin

class DatabaseConnection(Resource):
    def __init__(self, plugin, connection_string):
        super().__init__(plugin)
        self.conn = connect(connection_string)
    
    def _cleanup(self):
        self.conn.close()

# Register it
conn = DatabaseConnection(get_current_plugin(), "localhost:5432")
get_current_plugin().host.resource_manager.register(conn)
```

### Context Preservation

The `@syscall` decorator makes functions run in their defining plugin's context:

```python
from pkl import syscall, get_current_plugin

@syscall
def my_api():
    # Always runs as the plugin that defined this function
    print(get_current_plugin().name)  # Always this plugin

def normal_function():
    # Runs as whichever plugin called it
    print(get_current_plugin().name)  # Could be any plugin
```

### Events

Events provide a way for plugins to notify subscribers about actions. Event handlers are automatically cleaned up when the subscribing plugin is disabled.

The `@event` decorator automatically detects context:
- **Inside plugin code**: Creates a plugin event (owned by that plugin)
- **Outside plugin context**: Creates a host event (system-wide, no owner)

**Important**: Only the plugin that owns an event can invoke it. For host events with `protected=True`, only code running outside plugin context can invoke them.

#### Plugin Events

```python
from pkl import event, syscall

# Event with before/after behavior (generator function)
@event()
def user_login(username: str):
    print(f"User {username} logging in")
    yield  # Handlers run here
    print(f"User {username} logged in")

# Simple event (regular function) - just calls handlers
@event()
def config_changed():
    pass  # No before/after code

# Protected event - only this plugin can subscribe
@event(protected=True)
def internal_event():
    print("Internal plugin event")
    yield

# API to allow other plugins to trigger events
@syscall
def login_user(username: str):
    """Public API to trigger the login event."""
    user_login(username)  # Must use @syscall to run in this plugin's context
```

#### Host Events

Host events are system-wide events defined outside plugin context. Any plugin can subscribe to them.

**host_events.py**:
```python
import pkl

# Define host events before plugins load
# (outside plugin context, so these become host events)

@pkl.event()
def system_message(message: str):
    """System-wide message broadcast."""
    print(f"[SYSTEM] {message}")
    yield

@pkl.event(protected=True)
def admin_notification(data: str):
    """Protected - only host code can invoke."""
    print(f"[ADMIN] {data}")
    yield
```

**Using host events in plugins**:
```python
# In your plugin code
from host_events import system_message

@system_message.on
def on_message(msg: str):
    print(f"Plugin received: {msg}")

# Host code can invoke
system_message("Server starting...")  # OK

# Plugin code CANNOT invoke protected host events
# admin_notification("test")  # RuntimeError!
```

#### Subscribing to Events

```python
# Other plugins subscribe to events
from pkl.plugins import auth

@auth.user_login.on
def on_login(username: str):
    print(f"Handling login for {username}")

# Or using += operator
# auth.user_login += on_login

# To trigger the event, call the API function
auth.login_user("alice")
```

### Plugin Lifecycle

1. **Unloaded**: Not yet loaded
2. **Loaded**: Module loaded, not yet enabled
3. **Enabled**: Running and active
4. **Disabled**: Stopped and cleaned up
5. **Error**: Failed to load/enable

```python
plugin = pkl.load_plugin(path=plugin_path)  # -> LOADED
plugin.enable()                              # -> ENABLED
plugin.disable()                             # -> DISABLED
```

### Lifecycle Events

Plugins can register handlers for their own lifecycle events:

```python
from pkl import get_current_plugin

# Register cleanup handler using .on decorator
@get_current_plugin().on_disable.on
def cleanup():
    print("Cleaning up plugin!")

# Or using += operator
# get_current_plugin().on_disable += cleanup

# on_unload is also available (called when plugin is unloaded)
@get_current_plugin().on_unload.on
def unload_handler():
    print("Unloading!")
```

**Important**: Lifecycle events can only be subscribed to by the plugin itself. This ensures that cleanup handlers are always associated with the correct plugin and run at the appropriate time.

### Child Plugins

Plugins can load other plugins as children:

```python
from pkl import load_plugin, get_current_plugin

this = get_current_plugin()
child = load_plugin(path=this.path / "subplugins" / "child")
child.enable()  # Disabled when parent is disabled

# Or detach it
child.enable(detach=True)  # Independent of parent
```

### Timing Utilities

```python
from pkl import set_timeout, set_interval

# One-time delay
def delayed():
    print("Called after 5 seconds")

timer = set_timeout(delayed, 5.0)
timer.cancel()  # Cancel if needed

# Repeating
def periodic():
    print("Called every 10 seconds")

interval = set_interval(periodic, 10.0)
interval.cancel()  # Stop it
```

### Logging

```python
from pkl import log, get_logger

# Use the convenience proxy
log.info("Starting up")  # Automatically includes plugin name

# Or create a named logger
logger = get_logger("database")
logger.error("Connection failed")
```

## Advanced Usage

### Custom Plugin Loaders

```python
from pkl import PluginLoader, Plugin

class CustomLoader:
    def load(self, plugin: Plugin):
        # Your custom loading logic
        return loaded_module

host = PluginHost(plugin_loader=CustomLoader())
```

### Custom Metadata Loaders

```python
from pkl import MetadataLoader, PluginMetadata
from pathlib import Path

class CustomMetadataLoader:
    def load(self, location: Path) -> PluginMetadata:
        # Your custom metadata loading
        return PluginMetadata({"name": "...", "version": "..."})

host = PluginHost(metadata_loader=CustomMetadataLoader())
```

### Hooks

```python
host = pkl.PluginHost()

# Context switch hook
def on_context_switch(old_plugin, new_plugin):
    print(f"Switching from {old_plugin} to {new_plugin}")

host.add_context_switch_hook(on_context_switch)

# Lifecycle hooks
host.add_enable_hook(lambda p: print(f"Enabled: {p.name}"))
host.add_disable_hook(lambda p: print(f"Disabled: {p.name}"))

# Resource hooks
host.resource_manager.add_register_hook(lambda r: print(f"Resource created: {r}"))
host.resource_manager.add_cleanup_hook(lambda r: print(f"Resource cleaned: {r}"))
```

### Async Support

The system uses context variables for async compatibility:

```python
from pkl import syscall, get_current_plugin

@syscall
async def async_api():
    # Context preserved across async boundaries
    await asyncio.sleep(1)
    print(get_current_plugin().name)  # Still correct

async def main():
    await async_api()
```

## Examples

See the `examples/` directory for complete working examples:

- `examples/plugins/a/` - Plugin with events and API
- `examples/plugins/b/` - Plugin that uses plugin A
- `examples/host_events.py` - Host-level event definitions
- `examples/example.py` - Full demonstration script

Run the example:
```bash
uv run examples/example.py
```

## Architecture

### Components

- **PluginHost**: Main system coordinator
- **Plugin**: Represents a loaded plugin
- **ResourceManager**: Tracks and manages resources
- **MetadataLoader**: Loads plugin metadata from manifests
- **PluginLoader**: Loads plugin code (default uses importlib)
- **Context System**: Tracks current plugin using context variables
- **Event System**: Protected/public events with generators
- **Plugin Importer**: Virtual `pkl.plugins` module for imports

### Design Principles

1. **Automatic Cleanup**: Everything is tracked and cleaned up
2. **Context Awareness**: Always know which plugin is running
3. **Type Safety**: Full typing support throughout
4. **Extensibility**: Custom loaders, resources, and hooks
5. **Isolation**: Plugins can't interfere with each other (unless explicitly shared)
6. **Flexibility**: Works with sync and async code

## Development

### Running Tests

```bash
uv pip install -e ".[dev]"
pytest tests/
```

### Type Checking

```bash
mypy pkl/
```

### Code Formatting

```bash
black pkl/
```

## Requirements

- Python 3.9+
- No required dependencies (uses stdlib only)
- Optional: `tomli` for TOML support (Python <3.11)
- Optional: `pyyaml` for YAML manifest support

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure mypy and tests pass
5. Submit a pull request

## Roadmap

- [ ] Plugin discovery by name (registry)
- [ ] Version constraint checking
- [ ] Resource quotas and limits
- [ ] Plugin sandboxing for security
- [ ] Hot reloading support
- [ ] Plugin dependency graph visualization
- [ ] Performance profiling hooks
- [ ] Web UI for plugin management

## Credits

Created by xpodev
Inspired by operating system process management concepts
