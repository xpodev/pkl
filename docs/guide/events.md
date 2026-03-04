# Events

Master PKL's flexible event system for plugin communication.

## Overview

PKL provides a powerful event system that automatically handles resource cleanup and context management. Events come in two types:

- **Plugin Events** - Owned by a plugin, only that plugin can invoke
- **Host Events** - System-wide, no owner, anyone can invoke (unless protected)

## Plugin Events

### Creating Events

Use the `@event()` decorator inside plugin code:

```python
from pkl import event, log

@event()
def data_changed(key: str, value: any):
    """Event with before/after hooks (generator function)."""
    log.info(f"Data changing: {key}={value}")
    yield  # Handlers run here
    log.info(f"Data changed: {key}={value}")

@event()
def simple_event(msg: str):
    """Simple event without hooks (regular function)."""
    pass  # Just calls handlers
```

### Generator vs Regular Functions

**Generator function** (with `yield`):
- Code before `yield` runs before handlers
- Code after `yield` runs after handlers
- Use for transactions, timing, logging, etc.

**Regular function**:
- Just calls all handlers
- Use for simple notifications

### Protected Events

Restrict subscriptions to the defining plugin only:

```python
@event(protected=True)
def internal_state_change():
    """Only this plugin can subscribe."""
    yield

# In same plugin
internal_state_change += my_handler  # ✅ OK

# In different plugin
from pkl.plugins import other
other.internal_state_change += handler  # ❌ RuntimeError!
```

### Owner-Only Invocation

**Important**: Only the owning plugin can invoke its events:

```python
# In Plugin A
@event()
def user_registered(user_id: int):
    print(f"User {user_id} registered")
    yield

# In Plugin A - invoke directly
user_registered(123)  # ✅ OK

# In Plugin B
from pkl.plugins import a
a.user_registered(123)  # ❌ RuntimeError: Only Plugin A can invoke!
```

### Providing Public API

Use `@syscall` to let other plugins trigger your events:

```python
from pkl import event, syscall

@event()
def user_registered(user_id: int):
    yield

@syscall
def register_user(user_id: int, name: str):
    """Public API for registering users."""
    # Runs in this plugin's context
    # Do registration logic...
    user_registered(user_id)  # Now we can invoke!
```

Other plugins call the API:

```python
from pkl.plugins import auth

auth.register_user(123, "Alice")  # ✅ Works!
```

## Host Events

### Creating Host Events

Define events **outside plugin context** (before plugins load):

```python
# host_events.py
import pkl

@pkl.event()
def system_message(text: str):
    """Automatically becomes a host event (no plugin context)."""
    print(f"[SYSTEM] {text}")
    yield

@pkl.event()
def config_reloaded(config: dict):
    """Simple host event."""
    pass
```

### Using Host Events

Import and use in plugins:

```python
# In your plugin
from host_events import system_message

def on_message(text: str):
    print(f"Plugin received: {text}")

system_message += on_message
```

### Protected Host Events

Host events can be protected - only non-plugin code can invoke:

```python
@pkl.event(protected=True)
def admin_notification(msg: str):
    """Only host code (outside plugin context) can invoke."""
    yield

# In host code
admin_notification("System starting")  # ✅ OK

# In plugin code
from host_events import admin_notification
admin_notification("test")  # ❌ RuntimeError!
```

Use protected host events for system-level events that plugins should observe but not trigger.

## Subscribing to Events

### Using the .on Decorator (Recommended)

The cleanest way to subscribe to events:

```python
from pkl.plugins import some_plugin

@some_plugin.some_event.on
def my_handler(data: str):
    print(f"Received: {data}")
```

### Using the += Operator

Alternatively, subscribe after defining the handler:

```python
def my_handler(data: str):
    print(f"Received: {data}")

some_plugin.some_event += my_handler
```

### Unsubscribing

Use the `-=` operator:

```python
some_plugin.some_event -= my_handler
```

### Automatic Cleanup

Event subscriptions are **resources** - they're automatically removed when the subscribing plugin is disabled:

```python
# Plugin B subscribes to Plugin A's event
from pkl.plugins import a

def handler(data):
    print(f"Got: {data}")

a.data_changed += handler

# Later... Plugin B is disabled
plugin_b.disable()

# Subscription automatically removed!
# handler() will not be called anymore
```

## Event Patterns

### Transaction Pattern

```python
@event()
def transaction(operation: str):
    """Wrap handlers in transaction."""
    db.begin()
    try:
        yield  # Handlers run in transaction
        db.commit()
    except Exception:
        db.rollback()
        raise
```

### Timing Pattern

```python
@event()
def slow_operation():
    """Measure handler execution time."""
    import time
    start = time.time()
    yield
    elapsed = time.time() - start
    log.info(f"Handlers took {elapsed:.2f}s")
```

### Validation Pattern

```python
@event()
def value_changing(old: int, new: int):
    """Allow handlers to cancel the change."""
    # Could implement cancellation logic here
    yield
    # Confirm change
```

### Chain Pattern

```python
@event()
def pipeline_stage(data: dict):
    """Each handler modifies and passes data."""
    yield
    # All handlers have processed data
```

## Context During Events

When an event is invoked, handler context switches to the **subscribing plugin**:

```python
# Plugin A defines event
@event()
def my_event():
    print(get_current_plugin().name)  # "a"
    yield
    print(get_current_plugin().name)  # "a" (restored)

# Plugin B subscribes
def handler():
    print(get_current_plugin().name)  # "b" (switched!)

# Plugin A invokes
my_event()
# Output:
# a
# b
# a
```

This ensures handlers run in their own plugin's context with access to their own resources.

## Type Safety

Events preserve type information:

```python
@event()
def typed_event(user_id: int, name: str) -> None:
    yield

# Handler must match signature
def handler(user_id: int, name: str) -> None:
    pass

typed_event += handler  # Type checker validates!
```

## Best Practices

### ✅ DO

- Use generators for before/after logic
- Use `@syscall` for public event triggers
- Use protected events for internal-only subscriptions
- Define host events before loading plugins
- Use descriptive event names

### ❌ DON'T

- Try to invoke events you don't own
- Subscribe to events during global code (outside plugin enable)
- Forget that subscriptions are automatically cleaned up
- Use events for tight coupling (prefer loose coupling)

## Examples

### Example: Authentication System

```python
# auth_plugin/plugin.py
from pkl import event, syscall, log

@event()
def user_logged_in(username: str, session_id: str):
    """Fired after successful login."""
    log.info(f"User {username} logged in")
    yield
    log.info(f"Login handlers complete for {username}")

@event(protected=True)
def password_changed(username: str):
    """Internal event - only auth plugin can subscribe."""
    yield

@syscall
def login(username: str, password: str) -> str:
    """Public API for login."""
    # Validate credentials...
    session_id = create_session(username)
    user_logged_in(username, session_id)
    return session_id
```

### Example: Analytics Plugin

```python
# analytics_plugin/plugin.py
from pkl.plugins import auth

@auth.user_logged_in.on
def track_login(username: str, session_id: str):
    """Track login events."""
    log.info(f"Analytics: User {username} logged in")
    # Send to analytics service...

# Will automatically unsubscribe when analytics plugin disables!
```

## Next Steps

- [Context & API](context-api.md) - Learn about `@syscall` and context
- [Resources](resources.md) - Understand resource management
- [Examples](../examples/overview.md) - See complete examples
- [API Reference](../api/index.md) - Detailed event API
