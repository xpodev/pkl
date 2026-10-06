"""Alpha's public surface; other plugins import it as ``example_plugins.alpha``."""

from .plugin import data, greet, greeted, scratch

__all__ = ["data", "greet", "greeted", "scratch"]
