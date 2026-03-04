"""Tests for pkl context management."""

import pytest
from pkl.context import plugin_context
from pkl.plugin import Plugin
from pkl.host import PluginHost


def test_get_current_plugin_default():
    """Test that get_current_plugin returns None by default."""
    host = PluginHost()
    assert host.get_current_plugin() is None


def test_plugin_context():
    """Test plugin context manager."""
    host = PluginHost()
    plugin = Plugin(host, "test_plugin", None)
    
    assert host.get_current_plugin() is None
    
    with plugin_context(host, plugin):
        assert host.get_current_plugin() == plugin
    
    assert host.get_current_plugin() is None


def test_plugin_context_nesting():
    """Test nested plugin contexts."""
    host = PluginHost()
    plugin1 = Plugin(host, "plugin1", None)
    plugin2 = Plugin(host, "plugin2", None)
    
    with plugin_context(host, plugin1):
        assert host.get_current_plugin() == plugin1
        
        with plugin_context(host, plugin2):
            assert host.get_current_plugin() == plugin2
        
        assert host.get_current_plugin() == plugin1
    
    assert host.get_current_plugin() is None


def test_set_current_plugin_when_empty():
    """Test that set_current_plugin works when no plugin is set."""
    host = PluginHost()
    plugin = Plugin(host, "test", None)
    
    host.set_current_plugin(plugin)
    assert host.get_current_plugin() == plugin
    
    host.set_current_plugin(None)
    assert host.get_current_plugin() is None


def test_set_current_plugin_raises_when_occupied():
    """Test that set_current_plugin raises when a plugin is already set."""
    host = PluginHost()
    plugin1 = Plugin(host, "plugin1", None)
    plugin2 = Plugin(host, "plugin2", None)
    
    with plugin_context(host, plugin1):
        with pytest.raises(RuntimeError, match="Cannot set current plugin"):
            host.set_current_plugin(plugin2)
