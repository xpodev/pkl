"""Tests for pkl resource management."""

import pytest
import pkl
from pkl.resource import Resource, ResourceManager
from pkl.plugin import Plugin


class DummyResource(Resource):
    """Test resource implementation."""
    
    def __init__(self, plugin):
        super().__init__(plugin)
        self.cleaned_up = False
    
    def _cleanup(self):
        self.cleaned_up = True


def test_resource_creation():
    """Test resource creation."""
    plugin = Plugin(pkl.host, "test", None, None)
    resource = DummyResource(plugin)
    
    assert resource.plugin == plugin
    assert resource.enabled
    assert not resource.cleaned_up


def test_resource_cleanup():
    """Test resource cleanup."""
    plugin = Plugin(pkl.host, "test", None, None)
    resource = DummyResource(plugin)
    
    resource.disable()
    
    assert resource.cleaned_up
    assert not resource.enabled


def test_resource_manager_register():
    """Test resource registration."""
    manager = ResourceManager()
    plugin = Plugin(pkl.host, "test", None, None)
    resource = DummyResource(plugin)
    
    manager.register(resource)
    
    resources = manager.get_resources(plugin)
    assert resource in resources


def test_resource_manager_cleanup_plugin():
    """Test cleanup of all plugin resources."""
    manager = ResourceManager()
    plugin = Plugin(pkl.host, "test", None, None)
    
    # Create and register multiple resources
    resources = [DummyResource(plugin) for _ in range(3)]
    for res in resources:
        manager.register(res)
    
    # Clean up plugin
    manager.cleanup_plugin(plugin)
    
    # All resources should be cleaned up
    for res in resources:
        assert res.cleaned_up
        assert not res.enabled
    
    # No resources should remain
    assert len(manager.get_resources(plugin)) == 0


def test_resource_manager_hooks():
    """Test resource manager hooks."""
    manager = ResourceManager()
    plugin = Plugin(pkl.host, "test", None, None)
    
    registered = []
    cleaned = []
    
    manager.add_register_hook(lambda r: registered.append(r))
    manager.add_cleanup_hook(lambda r: cleaned.append(r))
    
    resource = DummyResource(plugin)
    manager.register(resource)
    
    assert resource in registered
    assert resource not in cleaned
    
    manager.cleanup_plugin(plugin)
    
    assert resource in cleaned
