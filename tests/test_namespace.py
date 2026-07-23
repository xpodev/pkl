import sys
from pathlib import Path
from pkl import PluginHost

def test_custom_namespace():
    # Setup custom namespace
    custom_ns = "my_custom_plugins"
    host = PluginHost(namespace=custom_ns)
    
    # Must install the importer to have the namespace in sys.modules
    from pkl import install_plugin_importer
    install_plugin_importer(host)
    
    # Create a dummy plugin directory
    import shutil
    dummy_path = Path("tests/dummy_plugin")
    dummy_path.mkdir(exist_ok=True)
    (dummy_path / "__init__.py").write_text("loaded = True")
    (dummy_path / "plugin.py").write_text("entry = True")
    (dummy_path / "plugin.json").write_text('{"name": "dummy"}')
    
    try:
        plugin = host.load_plugin(dummy_path)
        
        # Check if loaded under custom namespace
        assert plugin.module.__name__.startswith(custom_ns)
        assert custom_ns in sys.modules
        
        # Verify we can access via sys.modules
        import importlib
        mod = importlib.import_module(f"{custom_ns}.dummy")
        assert mod.__name__ == f"{custom_ns}.dummy"
        assert mod.loaded
        
        # Verify virtual import works
        virtual_mod = getattr(sys.modules[custom_ns], "dummy")
        assert virtual_mod == mod
    finally:
        shutil.rmtree(dummy_path)
        if custom_ns in sys.modules:
            del sys.modules[custom_ns]

def test_namespace_conflict():
    from pkl.loader import ImportlibPluginLoader
    import pytest
    
    loader = ImportlibPluginLoader()
    # Should raise if both are provided
    with pytest.raises(ValueError, match="Cannot specify namespace when plugin_loader is provided"):
        PluginHost(plugin_loader=loader, namespace="custom")

if __name__ == "__main__":
    try:
        test_custom_namespace()
        print("Success: Custom namespace works!")
    except Exception as e:
        print(f"Failure: {e}")
        sys.exit(1)
