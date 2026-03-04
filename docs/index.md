# PKL - Plugin Hosting System

<p align="center">
  <em>A Python plugin system with automatic resource management, inspired by operating system concepts.</em>
</p>

---

## Overview

**PKL** treats plugins like processes in an operating system. Each plugin has its own resources, and the system keeps track of everything. When a plugin is disabled, all of its resources are automatically cleaned up.

## Key Features

✨ **Automatic Resource Management** - All plugin resources are tracked and cleaned up automatically

🔄 **Lifecycle Events** - Register handlers for `on_disable` and `on_unload` events

🎯 **Context Preservation** - Functions maintain plugin context with `@syscall` decorator

📡 **Flexible Event System** - Plugin events and host events with automatic context detection

⚡ **Async Support** - Full async/await support with context variable propagation

🔌 **Child Plugins** - Plugins can load and manage other plugins

🎨 **Custom Resources** - Define your own resource types (routes, workers, etc.)

🔒 **Type Safety** - Full typing support with strict type checking

🪝 **System Hooks** - Monitor plugin lifecycle and context switches

## Quick Example

```python
import pkl
from pathlib import Path

# Create a host
host = pkl.PluginHost()
pkl.set_default_host(host)

# Load and enable a plugin
plugin = pkl.load_plugin(Path("./my_plugin"))
plugin.enable()

# Use the plugin's API
from pkl.plugins import my_plugin
my_plugin.do_something()

# Clean up
plugin.disable()  # All resources automatically cleaned up!
```

## What Makes PKL Different?

Unlike traditional plugin systems, PKL provides:

- **Automatic cleanup** - Never worry about leaked resources
- **Context tracking** - Always know which plugin is active
- **Event lifecycle** - Subscriptions automatically removed when plugins disable
- **Host events** - System-wide events for inter-plugin communication
- **Type-safe** - Full IDE support and type checking

## Installation

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv pip install pkl
```

Or with pip:

```bash
pip install pkl
```

## Next Steps

- [Quick Start](getting-started/quick-start.md) - Get started in 5 minutes
- [Core Concepts](getting-started/concepts.md) - Understand how PKL works
- [User Guide](guide/creating-plugins.md) - Learn to create plugins
- [Examples](examples/overview.md) - See real-world examples

## License

MIT License - see [LICENSE](https://github.com/xpodev/pkl/blob/main/LICENSE) for details.
