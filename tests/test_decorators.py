"""Tests for pkl decorators."""

import pytest
import asyncio
from pkl.decorators import syscall
from pkl.context import plugin_context
from pkl.plugin import Plugin
from pkl.host import PluginHost
import pkl


def test_syscall_decorator_sync():
    """Test @syscall decorator with synchronous functions."""
    host = PluginHost()
    pkl.set_default_host(host)
    
    plugin1 = Plugin(host, "plugin1", None)
    plugin2 = Plugin(host, "plugin2", None)
    
    # Define function in plugin1's context
    with plugin_context(host, plugin1):
        @syscall
        def my_func():
            return host.get_current_plugin()
    
    # Call from plugin2's context
    with plugin_context(host, plugin2):
        result = my_func()
    
    # Should return plugin1 (defining context)
    assert result == plugin1


def test_syscall_decorator_async():
    """Test @syscall decorator with async functions."""
    host = PluginHost()
    pkl.set_default_host(host)
    
    plugin1 = Plugin(host, "plugin1", None)
    plugin2 = Plugin(host, "plugin2", None)
    
    # Define async function in plugin1's context
    with plugin_context(host, plugin1):
        @syscall
        async def my_async_func():
            await asyncio.sleep(0.001)
            return host.get_current_plugin()
    
    # Call from plugin2's context
    async def run_test():
        with plugin_context(host, plugin2):
           result = await my_async_func()
        return result
    
    result = asyncio.run(run_test())
    
    # Should return plugin1 (defining context)
    assert result == plugin1


def test_syscall_preserves_function_metadata():
    """Test that @syscall preserves function metadata."""
    host = PluginHost()
    pkl.set_default_host(host)
    
    def my_function():
        """My docstring."""
        pass
    
    decorated = syscall(my_function)
    
    assert decorated.__name__ == "my_function"
    assert decorated.__doc__ == "My docstring."
