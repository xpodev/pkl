# Logging

Per-plugin logging with automatic cleanup.

## Basic Usage

```python
from pkl import log

log.info("Plugin starting")
log.warning("Something might be wrong")
log.error("An error occurred")
log.debug("Debug information")
```

Output includes plugin name:

```
2026-03-04 10:30:00,123 - INFO - [my_plugin] Plugin starting
2026-03-04 10:30:00,124 - WARNING - [my_plugin] Something might be wrong
```

## Named Loggers

Create loggers for different components:

```python
from pkl import get_logger

db_logger = get_logger("database")
api_logger = get_logger("api")

db_logger.info("Connected to database")
api_logger.info("API endpoint called")
```

Output:

```
2026-03-04 10:30:00,125 - INFO - [my_plugin.database] Connected to database
2026-03-04 10:30:00,126 - INFO - [my_plugin.api] API endpoint called
```

## Logger Lifecycle

Loggers are resources - they're automatically disabled:

```python
log.info("Before disable")

plugin.disable()

log.info("After disable")  # Won't log anything!
```

## Configuration

Set up logging in your application:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Or with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
```

## Best Practices

### ✅ DO

- Use appropriate log levels
- Create named loggers for components
- Log important events and errors
- Use structured logging when needed

### ❌ DON'T

- Log sensitive information
- Over-log in production
- Assume logs work after disable
- Use print() instead of logging

## Next Steps

- [Resources](resources.md)
- [Lifecycle](lifecycle.md)
