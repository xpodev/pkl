# Plugin A - Example plugin with API and events

from pkl import event, log

class User:
    """Example user class."""
    def __init__(self, name: str) -> None:
        self.name = name

@event()  # protected=False is the default
def my_event(user: User):
    """Example event with before/after handlers."""
    # code here runs before handlers
    print(f"Before handlers: {user.name}")
    yield
    # code here runs after handlers
    print(f"After handlers: {user.name}")

# Subscribe to host-level system_message event
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from host_events import system_message

@system_message.on
def on_system_message(message: str):
    """Handler for system messages."""
    log.info(f"Plugin A received system message: {message}")
