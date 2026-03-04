# Resources

Understanding and creating custom resources.

## What are Resources?

Resources are objects created by plugins that need cleanup:

- Event subscriptions
- Timers
- Loggers
- Database connections
- Network sockets
- File handles
- etc.

## Built-in Resources

### EventSubscription

Automatically created when subscribing to events:

```python
from pkl.plugins import other

def handler(data):
    print(data)

other.some_event += handler  # Creates EventSubscription resource
```

### Timer

Created by timing utilities:

```python
from pkl import set_timeout, set_interval

timer1 = set_timeout(callback, 5.0)
timer2 = set_interval(callback, 10.0)

# Both auto-cleanup on plugin disable
```

### Logger

Created when using logging:

```python
from pkl import log, get_logger

log.info("Message")  # Uses cached logger resource
logger = get_logger("db")  # Creates named logger resource
```

## Creating Custom Resources

```python
from pkl import Resource, get_current_plugin

class DatabaseConnection(Resource):
    def __init__(self, plugin, conn_string):
        super().__init__(plugin)
        self.conn = connect(conn_string)
        self.conn_string = conn_string
    
    def _cleanup(self):
        """Called when plugin is disabled."""
        self.conn.close()
        print(f"Closed connection to {self.conn_string}")

# Create and register
connection = DatabaseConnection(
    get_current_plugin(), 
    "localhost:5432"
)
get_current_plugin().host.resource_manager.register(connection)
```

## Resource Lifecycle

1. **Creation**: Resource initialized
2. **Registration**: Added to ResourceManager
3. **Usage**: Resource used during plugin operation
4. **Cleanup**: `_cleanup()` called when plugin disables

## Automatic Cleanup

When a plugin is disabled:

```python
plugin.disable()
# 1. on_disable lifecycle events fire
# 2. Resources cleaned up in reverse order
# 3. Plugin state set to DISABLED
```

## Best Practices

### ✅ DO

- Extend `Resource` for custom resources
- Implement `_cleanup()` method
- Register resources immediately after creation
- Clean up external resources (files, connections, etc.)

### ❌ DON'T

- Forget to call `super().__init__(plugin)`
- Raise exceptions in `_cleanup()` 
- Manually call `_cleanup()`
- Share resources between plugins without care

## Next Steps

- [Events](events.md)
- [Lifecycle](lifecycle.md)
- [API Reference](../api/resources.md)
