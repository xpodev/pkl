"""Logging support for plugins."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional, cast

from .resource import Resource

if TYPE_CHECKING:
    from .plugin import Plugin
    from .host import PluginHost

__all__ = ["PluginLogger", "get_logger", "LogProxy"]


class PluginLoggerAdapter(logging.LoggerAdapter):  # type: ignore
    """Logger adapter that adds plugin information."""

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:  # type: ignore
        """Process log messages to add plugin context."""
        if self.extra:
            plugin = cast(Any, self.extra.get("plugin"))
            if plugin is not None:
                return f"[{plugin.name}] {msg}", kwargs
        return msg, kwargs


class PluginLogger(Resource):
    """A logger resource for plugins."""

    def __init__(self, plugin: "Plugin", name: Optional[str] = None) -> None:
        """Initialize the logger.

        Args:
            plugin: The plugin that owns this logger.
            name: The logger name (defaults to plugin name).
        """
        super().__init__(plugin)
        self.name = name or plugin.name
        self._logger = logging.getLogger(f"pkl.plugin.{self.name}")
        self._adapter = PluginLoggerAdapter(self._logger, {"plugin": plugin})

    def _cleanup(self) -> None:
        """Disable logging when the plugin is disabled."""
        pass  # Base class handles _enabled flag

    def debug(self, msg: str, *args: object, **kwargs: object) -> None:
        """Log a debug message."""
        if self._enabled:
            self._adapter.debug(msg, *args, **kwargs)  # type: ignore

    def info(self, msg: str, *args: object, **kwargs: object) -> None:
        """Log an info message."""
        if self._enabled:
            self._adapter.info(msg, *args, **kwargs)  # type: ignore

    def warning(self, msg: str, *args: object, **kwargs: object) -> None:
        """Log a warning message."""
        if self._enabled:
            self._adapter.warning(msg, *args, **kwargs)  # type: ignore

    def error(self, msg: str, *args: object, **kwargs: object) -> None:
        """Log an error message."""
        if self._enabled:
            self._adapter.error(msg, *args, **kwargs)  # type: ignore

    def critical(self, msg: str, *args: object, **kwargs: object) -> None:
        """Log a critical message."""
        if self._enabled:
            self._adapter.critical(msg, *args, **kwargs)  # type: ignore

    def exception(self, msg: str, *args: object, **kwargs: object) -> None:
        """Log an exception message."""
        if self._enabled:
            self._adapter.exception(msg, *args, **kwargs)  # type: ignore


def get_logger(name: Optional[str] = None, host: Optional["PluginHost"] = None) -> PluginLogger:
    """Get a logger for the current plugin.

    Args:
        name: Optional logger name (defaults to plugin name).
        host: The plugin host to use (defaults to the default host).

    Returns:
        A logger instance.

    Raises:
        RuntimeError: If called outside a plugin context.
    """
    if host is None:
        from . import get_default_host
        host = get_default_host()
    
    plugin = host.get_current_plugin()
    if plugin is None:
        raise RuntimeError("get_logger() must be called from within a plugin context")

    logger = PluginLogger(plugin, name)
    plugin.host.resource_manager.register(logger)
    return logger


class LogProxy:
    """Proxy object for convenient logging access.
    
    Provides a module-level `log` object that automatically gets the logger
    for the current plugin and caches it.
    """

    def __init__(self, host: Optional["PluginHost"] = None) -> None:
        """Initialize the log proxy.
        
        Args:
            host: The plugin host to use (defaults to the default host).
        """
        self._host = host
        # Cache loggers per plugin
        self._loggers: dict = {}

    def _get_logger(self) -> PluginLogger:
        """Get or create a logger for the current plugin."""
        if self._host is None:
            from . import get_default_host
            host = get_default_host()
        else:
            host = self._host
        
        plugin = host.get_current_plugin()
        if plugin is None:
            raise RuntimeError("log must be called from within a plugin context")
        
        # Check cached logger
        if plugin in self._loggers:
            return self._loggers[plugin]
        
        # Create new logger (will be registered as a resource)
        logger = get_logger(host=self._host)
        self._loggers[plugin] = logger
        return logger

    def __getattr__(self, name: str):  # type: ignore
        """Get logger methods dynamically."""
        logger = self._get_logger()
        return getattr(logger, name)
