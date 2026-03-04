#!/usr/bin/env python3
"""Example demonstrating the pkl plugin system."""

import logging
import sys
import time
from pathlib import Path

# Add pkl to path (for development)
sys.path.insert(0, str(Path(__file__).parent.parent))

import pkl

def main():
    """Run the example."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    print("=" * 60)
    print("PKL Plugin System Example")
    print("=" * 60)
    print()

    # Create a plugin host
    host = pkl.PluginHost()
    pkl.set_default_host(host)

    # Import host-level events (must be after host is created)
    from host_events import system_message

    # Add some hooks for demonstration
    def on_enable(plugin):
        print(f"🟢 Plugin enabled: {plugin.name}")

    def on_disable(plugin):
        print(f"🔴 Plugin disabled: {plugin.name}")

    host.add_enable_hook(on_enable)
    host.add_disable_hook(on_disable)

    # Get plugin paths
    examples_dir = Path(__file__).parent
    plugins_dir = examples_dir / "plugins"

    print("Loading plugins...")
    print()

    # Load plugin A
    plugin_a = pkl.load_plugin(plugins_dir / "a")
    plugin_a.enable()
    print()

    # Load plugin B (depends on A)
    plugin_b = pkl.load_plugin(plugins_dir / "b")
    plugin_b.enable()
    print()

    # Trigger the host event
    print("Triggering host event (both plugins should receive it)...")
    system_message("Hello from the host!")
    print()

    # Trigger plugin A's event
    print("Triggering plugin A's event...")
    # Import plugin A to access its API
    from pkl.plugins import a
    user = a.User("Alice")
    a.trigger_my_event(user)
    print()

    # Let the system run for a bit
    print("Running for 20 seconds...")
    print("(Timers and intervals are executing in background)")
    print()

    try:
        time.sleep(20)
    except KeyboardInterrupt:
        print("\nInterrupted by user")

    print()
    print("Triggering plugin A's event again (after B is disabled)...")
    user2 = a.User("Bob")
    a.trigger_my_event(user2)
    print()

    print("Triggering host event (only plugin A should receive it now)...")
    system_message("Plugin B is disabled!")
    print()

    print()
    print("=" * 60)
    print("Shutting down...")
    print("=" * 60)
    print()

    # Disable plugins
    if plugin_b.state == pkl.PluginState.ENABLED:
        plugin_b.disable()
    
    if plugin_a.state == pkl.PluginState.ENABLED:
        plugin_a.disable()

    print()
    print("Example complete!")

if __name__ == "__main__":
    main()
