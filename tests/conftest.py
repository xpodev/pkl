"""Pytest configuration."""

import sys
from pathlib import Path

import pytest

# Add pkl to path
pkl_path = Path(__file__).parent.parent
sys.path.insert(0, str(pkl_path))


@pytest.fixture(autouse=True)
def reset_host():
    """Reset the global host between tests."""
    import pkl
    from pkl.host import PluginHost
    from pkl.importer import install_plugin_importer
    
    # Create a fresh host for the test
    new_host = PluginHost(name="test")
    install_plugin_importer(new_host)
    
    # Replace the global host
    pkl.host = new_host
    
    yield new_host
    
    # Cleanup after test
    # Disable all plugins
    for plugin in list(new_host._plugins.values()):
        if plugin.state.value == "enabled":
            plugin.disable()

