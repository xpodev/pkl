"""Tests for pkl context management."""

import pytest
import pkl
from pkl.context import plugin_context
from pkl.plugin import Plugin


def test_get_current_plugin_default():
    """Test that get_current_plugin returns None by default."""
    assert pkl.host.get_current_plugin() is None


def test_plugin_context():
    """Test plugin context manager."""
    plugin = Plugin(pkl.host, "test_plugin", None)
    
    assert pkl.host.get_current_plugin() is None
    
    with plugin_context(pkl.host, plugin):
        assert pkl.host.get_current_plugin() == plugin
    
    assert pkl.host.get_current_plugin() is None


def test_plugin_context_nesting():
    """Test nested plugin contexts."""
    plugin1 = Plugin(pkl.host, "plugin1", None)
    plugin2 = Plugin(pkl.host, "plugin2", None)
    
    with plugin_context(pkl.host, plugin1):
        assert pkl.host.get_current_plugin() == plugin1
        
        with plugin_context(pkl.host, plugin2):
            assert pkl.host.get_current_plugin() == plugin2
        
        assert pkl.host.get_current_plugin() == plugin1
    
    assert pkl.host.get_current_plugin() is None


def test_set_current_plugin_when_empty():
    """Test that set_current_plugin works when no plugin is set."""
    plugin = Plugin(pkl.host, "test", None)
    
    pkl.host.set_current_plugin(plugin)
    assert pkl.host.get_current_plugin() == plugin
    
    pkl.host.set_current_plugin(None)
    assert pkl.host.get_current_plugin() is None


def test_set_current_plugin_raises_when_occupied():
    """Test that set_current_plugin raises when a plugin is already set."""
    plugin1 = Plugin(pkl.host, "plugin1", None)
    plugin2 = Plugin(pkl.host, "plugin2", None)
    
    with plugin_context(pkl.host, plugin1):
        with pytest.raises(RuntimeError, match="Cannot set current plugin"):
            pkl.host.set_current_plugin(plugin2)
