# Plugin A - API definitions

from pkl import syscall, get_current_plugin, set_timeout, load_plugin, event

# Export the User class for other plugins
class User:
    """Example user class."""
    def __init__(self, name: str) -> None:
        self.name = name

# Export the event for other plugins to subscribe
@event()  # protected=False is the default
def my_event(user: User):
    """Example event with before/after handlers."""
    # code here runs before handlers
    print(f"Before handlers: {user.name}")
    yield
    # code here runs after handlers
    print(f"After handlers: {user.name}")

# Simple event without before/after behavior
@event()
def simple_event(message: str):
    """Simple event that just calls handlers."""
    pass  # No before/after code, just invokes handlers

@syscall
def trigger_my_event(user: User):
    """API to trigger my_event.
    
    Since only the owning plugin can invoke events, this API function
    allows other plugins to trigger the event. It uses @syscall to ensure
    it runs in plugin A's context.
    """
    my_event(user)

@syscall
def my_api():
    """API that preserves plugin context."""
    print(f"my_api called, current plugin: {get_current_plugin().name}")  # type: ignore
    # should always be 'a' since this is a context preserved API

def my_other_api():
    """API that uses caller's context."""
    current = get_current_plugin()
    if current:
        print(f"my_other_api called from plugin: {current.name}")
    else:
        print("my_other_api called from no plugin context")

def delayed_entry():
    """Delayed initialization that loads child plugins."""
    this = get_current_plugin()
    if this is None or this.path is None:
        return
    
    print(f"Plugin {this.name} delayed entry running")
    
    # Load child plugin using the new API
    subplugins_path = this.path / "subplugins"
    if subplugins_path.exists():
        sp1_path = subplugins_path / "sp1"
        if sp1_path.exists():
            child = load_plugin(sp1_path)
            child.enable()  # Child plugin, disabled when parent is disabled
            print(f"Loaded child plugin: {child.name}")

# Schedule delayed entry
set_timeout(delayed_entry, 1)
