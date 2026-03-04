"""Tests for pkl plugin functionality."""

import pytest
from pathlib import Path
from pkl.plugin import Plugin, PluginState
from pkl.host import PluginHost


def test_plugin_creation():
    """Test plugin creation with basic properties."""
    host = PluginHost()
    plugin = Plugin(host, "test_plugin", Path("/test/path"))
    
    assert plugin.name == "test_plugin"
    assert plugin.path == Path("/test/path")
    assert plugin.state == PluginState.UNLOADED
    assert plugin.error is None


def test_plugin_state_transitions():
    """Test plugin state management."""
    host = PluginHost()
    plugin = Plugin(host, "test", None)
    
    assert plugin.state == PluginState.UNLOADED
    
    plugin._state = PluginState.LOADED
    assert plugin.state == PluginState.LOADED
    
    plugin._state = PluginState.ENABLED
    assert plugin.state == PluginState.ENABLED


def test_plugin_repr():
    """Test plugin string representation."""
    host = PluginHost()
    plugin = Plugin(host, "test", None)
    
    repr_str = repr(plugin)
    assert "test" in repr_str
    assert "unloaded" in repr_str.lower()
