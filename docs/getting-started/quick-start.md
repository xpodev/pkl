# Quick Start

Get up and running with PKL in minutes!

## Your First Plugin

Let's create a simple plugin that logs messages.

### 1. Create Plugin Structure

```bash
mkdir my_plugin
cd my_plugin
```

### 2. Create Metadata File

Create `plugin.json`:

```json
{
  "name": "my_plugin",
  "version": "1.0.0",
  "entrypoint": "plugin"
}
```

### 3. Create Plugin Code

Create `plugin.py`:

```python
from pkl import log, event

# Plugin initialization code runs when enabled
log.info("My plugin is starting!")

# Create an event
@event()
def on_message(text: str):
    """Event fired when a message is received."""
    log.info(f"Before handlers: {text}")
    yield  # Handlers run here
    log.info(f"After handlers: {text}")
```

### 4. Create Plugin API

Create `__init__.py`:

```python
from pkl import syscall, get_current_plugin

@syscall
def send_message(text: str):
    """Public API to send a message."""
    # This runs in my_plugin's context
    from . import plugin
    plugin.on_message(text)

@syscall
def get_plugin_name() -> str:
    """Get the name of this plugin."""
    return get_current_plugin().name
```

### 5. Load and Use the Plugin

Create `main.py` in the parent directory:

```python
import pkl
from pathlib import Path

# Create a plugin host
host = pkl.PluginHost()
pkl.set_default_host(host)

# Load and enable your plugin
plugin = pkl.load_plugin(Path("./my_plugin"))
plugin.enable()

# Use the plugin's API
from pkl.plugins import my_plugin

# Call the API
name = my_plugin.get_plugin_name()
print(f"Plugin name: {name}")

# Subscribe to the event
@plugin.module.on_message.on
def on_msg(text: str):
    print(f"Handler received: {text}")

# Trigger the event via API
my_plugin.send_message("Hello, PKL!")

# Clean up
plugin.disable()
print("Plugin disabled - all resources cleaned up!")
```

### 6. Run It!

```bash
uv run main.py
```

You should see output like:

```
2026-03-04 10:30:00,123 - INFO - [my_plugin] My plugin is starting!
Plugin name: my_plugin
2026-03-04 10:30:00,124 - INFO - [my_plugin] Before handlers: Hello, PKL!
Handler received: Hello, PKL!
2026-03-04 10:30:00,125 - INFO - [my_plugin] After handlers: Hello, PKL!
Plugin disabled - all resources cleaned up!
```

## What Just Happened?

1. **Plugin created** - With metadata, code, and API
2. **Host initialized** - The plugin management system
3. **Plugin loaded** - Code was loaded and prepared
4. **Plugin enabled** - Initialization code ran
5. **API called** - Function ran in plugin's context
6. **Event subscribed** - Handler automatically registered as resource
7. **Event triggered** - Via the public API (enforces owner-only invocation)
8. **Plugin disabled** - All resources (handler, logger) automatically cleaned up

## Key Concepts Demonstrated

- **`@event()`** - Creates events with before/after hooks
- **`@syscall`** - Preserves plugin context across calls
- **`log`** - Per-plugin logging with automatic cleanup
- **Resource management** - Automatic tracking and cleanup

## Next Steps

- [Core Concepts](concepts.md) - Understand the architecture
- [Creating Plugins](../guide/creating-plugins.md) - Learn plugin best practices
- [Events](../guide/events.md) - Master the event system
- [Examples](../examples/overview.md) - See more complex examples
