"""Host-level events for the example."""

import sys
from pathlib import Path

# Add pkl to path (for development)
sys.path.insert(0, str(Path(__file__).parent.parent))

import pkl


# Define host events here so they can be imported by both
# the main example and the plugins

@pkl.event()
def system_message(message: str):
    """System-wide message broadcast.
    
    This is a host-level event that any plugin can subscribe to.
    """
    print(f"[SYSTEM] Broadcasting: {message}")
    yield
    print(f"[SYSTEM] Broadcast complete")
