"""Tests for pkl decorators."""

import pytest
import asyncio
import pkl
from pkl.decorators import syscall
from pkl.context import plugin_context
from pkl.plugin import Plugin


def test_syscall_decorator_sync():
    """Test @syscall decorator with synchronous functions."""
    plugin1 = Plugin(pkl.host, "plugin1", None)
    plugin2 = Plugin(pkl.host, "plugin2", None)
    
    # Define function in plugin1's context
    with plugin_context(pkl.host, plugin1):
        @syscall
        def my_func():
            return pkl.host.get_current_plugin()
    
    # Call from plugin2's context
    with plugin_context(pkl.host, plugin2):
        result = my_func()
    
    # Should return plugin1 (defining context)
    assert result == plugin1


def test_syscall_decorator_async():
    """Test @syscall decorator with async functions."""
    plugin1 = Plugin(pkl.host, "plugin1", None)
    plugin2 = Plugin(pkl.host, "plugin2", None)
    
    # Define async function in plugin1's context
    with plugin_context(pkl.host, plugin1):
        @syscall
        async def my_async_func():
            await asyncio.sleep(0.001)
            return pkl.host.get_current_plugin()
    
    # Call from plugin2's context
    async def run_test():
        with plugin_context(pkl.host, plugin2):
           result = await my_async_func()
        return result
    
    result = asyncio.run(run_test())
    
    # Should return plugin1 (defining context)
    assert result == plugin1


def test_syscall_preserves_function_metadata():
    """Test that @syscall preserves function metadata."""
    def my_function():
        """My docstring."""
        pass
    
    decorated = syscall(my_function)
    
    assert decorated.__name__ == "my_function"
    assert decorated.__doc__ == "My docstring."
