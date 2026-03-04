"""Resource management system."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from .plugin import Plugin

__all__ = ["Resource", "ResourceManager", "ResourceHook"]


class Resource:
    """Base class for plugin resources.

    Resources are objects created by plugins that need to be tracked
    and cleaned up when the plugin is disabled.
    """

    def __init__(self, plugin: "Plugin") -> None:
        """Initialize the resource.

        Args:
            plugin: The plugin that owns this resource.
        """
        self.plugin = plugin
        self._enabled = True

    def _cleanup(self) -> None:
        """Clean up the resource.

        This is called when the plugin is disabled or the resource is manually released.
        Subclasses should override this to perform cleanup.
        """
        pass

    def disable(self) -> None:
        """Disable the resource and perform cleanup."""
        if self._enabled:
            self._enabled = False
            self._cleanup()

    @property
    def enabled(self) -> bool:
        """Check if the resource is enabled."""
        return self._enabled


ResourceHook = Callable[[Resource], None]


class ResourceManager:
    """Manages resources for plugins."""

    def __init__(self) -> None:
        """Initialize the resource manager."""
        # Map plugin -> list of resources
        self._resources: Dict[Plugin, List[Resource]] = {}
        # Hooks called when resources are registered
        self._register_hooks: List[ResourceHook] = []
        # Hooks called when resources are cleaned up
        self._cleanup_hooks: List[ResourceHook] = []

    def register(self, resource: Resource) -> None:
        """Register a resource with a plugin.

        Args:
            resource: The resource to register.
        """
        plugin = resource.plugin
        if plugin not in self._resources:
            self._resources[plugin] = []
        self._resources[plugin].append(resource)

        # Call register hooks
        for hook in self._register_hooks:
            hook(resource)

    def cleanup_plugin(self, plugin: "Plugin") -> None:
        """Clean up all resources for a plugin.

        Args:
            plugin: The plugin whose resources should be cleaned up.
        """
        if plugin not in self._resources:
            return

        resources = self._resources[plugin]
        for resource in resources:
            # Call cleanup hooks
            for hook in self._cleanup_hooks:
                hook(resource)
            # Clean up the resource
            resource.disable()

        # Remove all resources for this plugin
        del self._resources[plugin]

    def get_resources(self, plugin: Optional["Plugin"] = None) -> List[Resource]:
        """Get all resources for a plugin.

        Args:
            plugin: The plugin to get resources for. If None, returns all resources.

        Returns:
            A list of resources owned by the plugin, or all resources if plugin is None.
        """
        if plugin is None:
            # Return all resources from all plugins
            all_resources: List[Resource] = []
            for resources in self._resources.values():
                all_resources.extend(resources)
            return all_resources
        return self._resources.get(plugin, [])

    def add_register_hook(self, hook: ResourceHook) -> None:
        """Add a hook that's called when a resource is registered.

        Args:
            hook: The hook function to call.
        """
        self._register_hooks.append(hook)

    def add_cleanup_hook(self, hook: ResourceHook) -> None:
        """Add a hook that's called when a resource is cleaned up.

        Args:
            hook: The hook function to call.
        """
        self._cleanup_hooks.append(hook)
