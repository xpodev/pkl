"""Child plugin resource management."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from .resource import Resource

if TYPE_CHECKING:
    from .plugin import Plugin
    from .host import PluginHost

__all__ = ["ChildPluginResource", "load_plugin"]


class ChildPluginResource(Resource):
    """Resource that manages a child plugin.

    When the parent plugin is disabled, child plugins are also disabled
    unless they were loaded as detached.
    """

    def __init__(self, parent: "Plugin", child: "Plugin", detached: bool = False) -> None:
        """Initialize the child plugin resource.

        Args:
            parent: The parent plugin.
            child: The child plugin.
            detached: If True, the child plugin won't be disabled with the parent.
        """
        super().__init__(parent)
        self.child = child
        self.detached = detached

    def _cleanup(self) -> None:
        """Clean up the child plugin."""
        if not self.detached and self.child.state.value == "enabled":
            self.child.disable()


def load_plugin(source: Union[str, Path], detached: bool = False) -> "Plugin":
    """Load a plugin from the current context.

    If called from within a plugin context, the loaded plugin becomes a child
    of the current plugin. If called outside a plugin context (root level),
    the plugin is loaded as a root plugin.

    Args:
        source: The plugin source (path or name).
        detached: If True and loading as a child, the child plugin becomes 
                  independent of its parent.

    Returns:
        The loaded plugin.
    """
    from . import host

    parent = host.get_current_plugin()

    # Load the plugin with parent relationship
    plugin = host.load_plugin(source, parent=parent)

    # If there's a parent, create a child plugin resource to track the relationship
    if parent is not None:
        child_resource = ChildPluginResource(parent, plugin, detached)
        parent.host.resource_manager.register(child_resource)

    return plugin
