# Plugin B - Example plugin that uses plugin A's API

from pkl import set_interval, get_current_plugin, log

# Import plugin A using the custom importer
from pkl.plugins import a

# Call the context-preserving API
print("Plugin B calling a.my_api():")
a.my_api()

# Set up an interval to call the other API
def periodic_call():
    """Called periodically."""
    a.my_other_api()

set_interval(periodic_call, 10)

# Subscribe to plugin A's event
@a.my_event.on
def on_my_event(user):
    """Handler for my_event."""
    print(f"Plugin B received event for user: {user.name}")

# Subscribe to host-level system_message event
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from host_events import system_message

@system_message.on
def on_system_message(message: str):
    """Handler for system messages."""
    logger.info(f"Plugin B received system message: {message}")

# Test logging
logger = log
logger.info("Plugin B is initializing...")

# Register a cleanup handler using lifecycle event with .on decorator
@get_current_plugin().on_disable.on
def cleanup():
    """Called when plugin is being disabled."""
    logger.info("Plugin B cleanup handler called!")

# Schedule self-disable
def disable_self():
    """Disable this plugin after a delay."""
    logger.info("Plugin B is disabling...")
    get_current_plugin().disable()  # type: ignore
    logger.info("Plugin B is disabled!")  # should not show since plugin is disabled

from pkl import set_timeout
set_timeout(disable_self, 15)
