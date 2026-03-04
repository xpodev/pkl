# Examples Overview

Practical examples demonstrating PKL's features.

## Running Examples

All examples are in the `examples/` directory:

```bash
# Run the main example
uv run examples/example.py

# Or with Python
python examples/example.py
```

## Available Examples

### Basic Plugin Example

Simple plugin demonstrating fundamentals (see `examples/plugins/a/`):

- Plugin structure and metadata
- Logging
- Initialization code
- Basic lifecycle

### Events & API Example

Advanced plugin showing event system and API (see `examples/plugins/a/` and `examples/plugins/b/`):

- Creating events with `@event()`
- Providing API functions with `@syscall`
- Event handlers with before/after hooks
- Cross-plugin communication

### Host Events Example

System-wide events for multi-plugin coordination (see `examples/host_events.py`):

- Defining host events
- Protected vs public host events
- Multiple plugins subscribing
- Automatic subscription cleanup

## Example Structure

```
examples/
├── example.py              # Main demo script
├── host_events.py          # Host-level event definitions
└── plugins/
    ├── a/                  # Plugin A
    │   ├── plugin.json     # Metadata
    │   ├── plugin.py       # Entrypoint
    │   └── __init__.py   # Public API
    └── b/                  # Plugin B
        ├── plugin.json
        ├── plugin.py
        └── __init__.py
```

## What the Examples Demonstrate

### Core Features

- ✅ Plugin loading and enabling
- ✅ Resource management and cleanup
- ✅ Event system (plugin and host events)
- ✅ Context preservation with `@syscall`
- ✅ Cross-plugin communication
- ✅ Lifecycle events (`on_disable`, `on_unload`)
- ✅ Automatic subscription cleanup
- ✅ Logging per plugin

### Advanced Features

- ✅ Child plugin loading
- ✅ Timing utilities (`set_timeout`, `set_interval`)
- ✅ Protected events
- ✅ Host hooks for monitoring
- ✅ Plugin dependencies

## Example Output

When you run `examples/example.py`, you'll see:

```
============================================================
PKL Plugin System Example
============================================================

Loading plugins...

🟢 Plugin enabled: a

Plugin B calling a.my_api():
my_api called, current plugin: a
2026-03-04 10:30:00,123 - INFO - [b] Plugin B is initializing...
🟢 Plugin enabled: b

Triggering host event (both plugins should receive it)...
[SYSTEM] Broadcasting: Hello from the host!
2026-03-04 10:30:00,124 - INFO - [a] Plugin A received system message: Hello from the host!
2026-03-04 10:30:00,125 - INFO - [b] Plugin B received system message: Hello from the host!
[SYSTEM] Broadcast complete

Triggering plugin A's event...
Before handlers: Alice
Plugin B received event for user: Alice
After handlers: Alice

Running for 20 seconds...
(Timers and intervals are executing in background)

... (plugin activity) ...

2026-03-04 10:30:15,126 - INFO - [b] Plugin B is disabling...
🔴 Plugin disabled: b
2026-03-04 10:30:15,127 - INFO - [b] Plugin B cleanup handler called!

============================================================
Shutting down...
============================================================

🔴 Plugin disabled: a

Example complete!
```

## Learning Path

1. **Start here**: Review the code in `examples/plugins/a/` - Learn the fundamentals
2. **Then**: Study `examples/plugins/b/` - Master inter-plugin communication
3. **Finally**: Examine `examples/host_events.py` - System-wide coordination

## Modifying Examples

Feel free to modify the examples:

```python
# Try changing event behavior
@event()
def my_event(data: str):
    print(f"Custom: {data}")
    yield
    print("Done!")

# Add new API functions
@syscall
def new_feature():
    return "Hello!"

# Create new subscriptions
def my_handler(data):
    print(f"My handler: {data}")

some_event += my_handler
```

## Next Steps

- Check out the example code in `examples/` directory
- [User Guide](../guide/creating-plugins.md) - Detailed guides
- [API Reference](../api/index.md) - Complete API documentation
