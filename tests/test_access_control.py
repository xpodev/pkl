"""Tests for access control and security boundaries."""

import pytest
import pkl
from pkl import Event, HostEvent
from pkl.context import plugin_context
from pkl.plugin import Plugin, PluginState


def test_host_event_invocation_from_plugin_blocked():
    """Test that plugins cannot invoke host events."""
    # Create a host event
    host_evt = HostEvent(pkl.host, "admin_action", protected=False)
    
    # Create a plugin
    plugin = Plugin(pkl.host, "bad_plugin", None)
    
    # Try to invoke from plugin context - should fail
    with plugin_context(pkl.host, plugin):
        with pytest.raises(RuntimeError, match="can only be invoked by the host"):
            host_evt()


def test_host_event_invocation_from_host_allowed():
    """Test that host can invoke host events."""
    # Create a host event
    host_evt = HostEvent(pkl.host, "system_action", protected=False)
    
    called = []
    
    def handler():
        called.append(True)
    
    # Subscribe from plugin context
    plugin = Plugin(pkl.host, "test_plugin", None)
    with plugin_context(pkl.host, plugin):
        host_evt.subscribe(handler)
    
    # Invoke from host context (no plugin context) - should work
    host_evt()
    
    assert len(called) == 1


def test_protected_host_event_subscription_from_plugin_blocked():
    """Test that plugins cannot subscribe to protected host events."""
    # Create a protected host event
    host_evt = HostEvent(pkl.host, "admin_only", protected=True)
    
    plugin = Plugin(pkl.host, "test_plugin", None)
    
    def handler():
        pass
    
    # Try to subscribe from plugin context - should fail
    with plugin_context(pkl.host, plugin):
        with pytest.raises(RuntimeError, match="protected and can only be subscribed to by the host"):
            host_evt.subscribe(handler)


def test_protected_host_event_subscription_from_host_allowed():
    """Test that host can subscribe to protected host events."""
    # Create a protected host event
    host_evt = HostEvent(pkl.host, "admin_only", protected=True)
    
    called = []
    
    def handler():
        called.append(True)
    
    # Subscribe from host context (no plugin context) - should work
    host_evt.subscribe(handler)
    
    # Invoke it
    host_evt()
    
    assert len(called) == 1


def test_plugin_event_invocation_from_wrong_plugin_blocked():
    """Test that plugins cannot invoke other plugins' events."""
    plugin_a = Plugin(pkl.host, "plugin_a", None)
    plugin_b = Plugin(pkl.host, "plugin_b", None)
    
    # Create event owned by plugin_a
    with plugin_context(pkl.host, plugin_a):
        event_a = Event(plugin_a, "my_event", protected=False)
        pkl.host.resource_manager.register(event_a)
    
    # Try to invoke from plugin_b - should fail
    with plugin_context(pkl.host, plugin_b):
        with pytest.raises(RuntimeError, match="can only be invoked by plugin_a"):
            event_a()


def test_plugin_event_invocation_from_host_blocked():
    """Test that host cannot invoke plugin events."""
    plugin = Plugin(pkl.host, "test_plugin", None)
    
    # Create event owned by plugin
    with plugin_context(pkl.host, plugin):
        event = Event(plugin, "my_event", protected=False)
        pkl.host.resource_manager.register(event)
    
    # Try to invoke from host context - should fail
    with pytest.raises(RuntimeError, match="can only be invoked by test_plugin"):
        event()


def test_plugin_event_invocation_from_owner_allowed():
    """Test that plugin can invoke its own events."""
    plugin = Plugin(pkl.host, "test_plugin", None)
    
    called = []
    
    def handler():
        called.append(True)
    
    # Create event and subscribe
    with plugin_context(pkl.host, plugin):
        event = Event(plugin, "my_event", protected=False)
        pkl.host.resource_manager.register(event)
        event.subscribe(handler)
        
        # Invoke from owner - should work
        event()
    
    assert len(called) == 1


def test_protected_plugin_event_subscription_from_wrong_plugin_blocked():
    """Test that other plugins cannot subscribe to protected plugin events."""
    plugin_a = Plugin(pkl.host, "plugin_a", None)
    plugin_b = Plugin(pkl.host, "plugin_b", None)
    
    # Create protected event owned by plugin_a
    with plugin_context(pkl.host, plugin_a):
        event_a = Event(plugin_a, "private_event", protected=True)
        pkl.host.resource_manager.register(event_a)
    
    def handler():
        pass
    
    # Try to subscribe from plugin_b - should fail
    with plugin_context(pkl.host, plugin_b):
        with pytest.raises(RuntimeError, match="protected and can only be subscribed to by plugin_a"):
            event_a.subscribe(handler)


def test_protected_plugin_event_subscription_from_owner_allowed():
    """Test that plugin can subscribe to its own protected events."""
    plugin = Plugin(pkl.host, "test_plugin", None)
    
    called = []
    
    def handler():
        called.append(True)
    
    # Create protected event and subscribe from owner
    with plugin_context(pkl.host, plugin):
        event = Event(plugin, "private_event", protected=True)
        pkl.host.resource_manager.register(event)
        event.subscribe(handler)
        
        # Invoke it
        event()
    
    assert len(called) == 1


def test_non_protected_plugin_event_subscription_from_other_plugin_allowed():
    """Test that other plugins can subscribe to non-protected plugin events."""
    plugin_a = Plugin(pkl.host, "plugin_a", None)
    plugin_b = Plugin(pkl.host, "plugin_b", None)
    
    called = []
    
    def handler():
        called.append(True)
    
    # Create non-protected event owned by plugin_a
    with plugin_context(pkl.host, plugin_a):
        event_a = Event(plugin_a, "public_event", protected=False)
        pkl.host.resource_manager.register(event_a)
    
    # Subscribe from plugin_b - should work
    with plugin_context(pkl.host, plugin_b):
        event_a.subscribe(handler)
    
    # Invoke from plugin_a
    with plugin_context(pkl.host, plugin_a):
        event_a()
    
    assert len(called) == 1


def test_non_protected_host_event_subscription_from_host_allowed():
    """Test that host can subscribe to non-protected host events."""
    # Create a non-protected host event
    host_evt = HostEvent(pkl.host, "system_event", protected=False)
    
    called = []
    
    def handler():
        called.append(True)
    
    # Subscribe from host context - should work
    host_evt.subscribe(handler)
    
    # Invoke it
    host_evt()
    
    assert len(called) == 1


def test_plugin_disable_from_wrong_context():
    """Test that plugins cannot disable other plugins."""
    plugin_a = Plugin(pkl.host, "plugin_a", None)
    plugin_b = Plugin(pkl.host, "plugin_b", None)
    
    # Enable plugin_a
    plugin_a._state = PluginState.ENABLED
    
    # Try to disable plugin_a from plugin_b context - should fail
    with plugin_context(pkl.host, plugin_b):
        with pytest.raises(RuntimeError, match="can only be disabled by itself"):
            plugin_a.disable()


def test_plugin_can_disable_itself():
    """Test that a plugin can successfully disable itself."""
    plugin = Plugin(pkl.host, "test_plugin", None)
    
    # Enable plugin
    plugin._state = PluginState.ENABLED
    
    # Plugin should be able to disable itself
    with plugin_context(pkl.host, plugin):
        plugin.disable()
    
    assert plugin.state == PluginState.DISABLED


def test_host_can_disable_any_plugin():
    """Test that the host can disable any plugin."""
    plugin_a = Plugin(pkl.host, "plugin_a", None)
    plugin_b = Plugin(pkl.host, "plugin_b", None)
    
    # Enable both plugins
    plugin_a._state = PluginState.ENABLED
    plugin_b._state = PluginState.ENABLED
    
    # Host should be able to disable any plugin
    plugin_a.disable()
    assert plugin_a.state == PluginState.DISABLED
    
    plugin_b.disable()
    assert plugin_b.state == PluginState.DISABLED


def test_syscall_preserves_invocation_context():
    """Test that @syscall prevents plugins from bypassing invocation restrictions."""
    from pkl.decorators import syscall
    
    plugin_a = Plugin(pkl.host, "plugin_a", None)
    plugin_b = Plugin(pkl.host, "plugin_b", None)
    
    # Create event owned by plugin_a
    with plugin_context(pkl.host, plugin_a):
        event_a = Event(plugin_a, "my_event", protected=False)
        pkl.host.resource_manager.register(event_a)
        
        # Create a syscall that tries to invoke the event
        @syscall
        def try_invoke():
            event_a()  # This will be invoked in plugin_a's context
    
    # Call from plugin_b - the syscall runs in plugin_a's context
    # so the invocation should succeed
    with plugin_context(pkl.host, plugin_b):
        try_invoke()  # Should work because syscall restores plugin_a context


def test_event_subscription_cleanup_on_plugin_disable():
    """Test that event subscriptions are cleaned up when plugin is disabled."""
    plugin = Plugin(pkl.host, "test_plugin", None)
    
    called = []
    
    def handler():
        called.append(True)
    
    # Create event and subscribe
    with plugin_context(pkl.host, plugin):
        event = Event(plugin, "my_event", protected=False)
        pkl.host.resource_manager.register(event)
        event.subscribe(handler)
    
    # Invoke - should work
    with plugin_context(pkl.host, plugin):
        event()
    assert len(called) == 1
    
    # Disable plugin
    plugin._state = PluginState.ENABLED
    plugin.disable()
    
    # Invoke again - handler should not be called (subscription cleaned up)
    with plugin_context(pkl.host, plugin):
        event()
    assert len(called) == 1  # Still 1, not 2


def test_host_event_subscription_cleanup_on_plugin_disable():
    """Test that host event subscriptions are cleaned up when subscriber plugin is disabled."""
    host_evt = HostEvent(pkl.host, "system_event", protected=False)
    plugin = Plugin(pkl.host, "test_plugin", None)
    
    called = []
    
    def handler():
        called.append(True)
    
    # Subscribe from plugin
    with plugin_context(pkl.host, plugin):
        host_evt.subscribe(handler)
    
    # Invoke - should work
    host_evt()
    assert len(called) == 1
    
    # Disable plugin
    plugin._state = PluginState.ENABLED
    plugin.disable()
    
    # Invoke again - handler should not be called (subscription cleaned up)
    host_evt()
    assert len(called) == 1  # Still 1, not 2


def test_protected_host_event_subscription_persists():
    """Test that protected host event subscriptions (from host) persist without cleanup."""
    host_evt = HostEvent(pkl.host, "admin_event", protected=True)
    
    called = []
    
    def handler():
        called.append(True)
    
    # Subscribe from host context
    host_evt.subscribe(handler)
    
    # Invoke multiple times - should work every time
    host_evt()
    host_evt()
    host_evt()
    
    assert len(called) == 3
