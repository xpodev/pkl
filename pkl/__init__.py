"""pkl - attribute resources to plugins and release them on demand.

The core is four small concepts:

* ``Plugin`` - the identity of a plugin.
* ``PluginTracker`` - knows which plugin is currently executing.
* ``Resource`` - a thing that can be released.
* ``ResourceRegistry`` - maps plugins to resources and releases them per plugin.

Everything else (``pkl.tracking``, ``pkl.events``, ``pkl.syscall``, ``pkl.timing``,
``pkl.files``, ``pkl.modules``) is an extension that depends on the core. The core
never imports an extension.
"""

from __future__ import annotations

from .errors import NoCurrentPluginError, PklError
from .plugin import Plugin
from .plugin_tracker import PluginTracker
from .registry import ResourceRegistry
from .resource import Resource

__version__ = "0.2.0"

__all__ = [
    "Plugin",
    "PluginTracker",
    "Resource",
    "ResourceRegistry",
    "PklError",
    "NoCurrentPluginError",
]
