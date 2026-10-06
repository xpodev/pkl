"""Python modules loaded from files, unloaded when their owner's lifetime ends.

``sys.modules`` is process-global, so unlike the rest of pkl this extension
shares state between hosts: the caller chooses the dotted names and is
responsible for keeping them unique, e.g. ``f"myapp.plugins.{plugin.name}"``.
Missing parent packages (``myapp.plugins``) are created as empty stubs and
removed again once nothing is loaded below them.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType
from typing import Any

from .errors import PklError
from .tracking import Tracked

__all__ = ["ModuleResource", "ModuleAlreadyLoadedError"]


class ModuleAlreadyLoadedError(PklError, ImportError):
    """Raised when a module name is already taken in ``sys.modules``."""


def _entries(name: str) -> list[str]:
    return [key for key in sys.modules if key == name or key.startswith(name + ".")]


def _purge(name: str) -> None:
    for key in _entries(name):
        sys.modules.pop(key, None)
    _prune_ancestors(name)


_STUB_MARKER = "__pkl_stub__"


def _ancestors(name: str) -> list[str]:
    """The dotted prefixes of ``name`` above it, outermost first."""
    parts = name.split(".")
    return [".".join(parts[:end]) for end in range(1, len(parts))]


def _ensure_ancestors(name: str) -> None:
    """Make every ancestor of ``name`` importable.

    Python resolves ``from . import sibling`` inside ``a.b.c`` through the whole
    chain ``a``, ``a.b``, so missing ancestors get an empty stub package.
    """
    for ancestor in _ancestors(name):
        if ancestor not in sys.modules:
            stub = ModuleType(ancestor)
            stub.__path__ = []
            stub.__spec__ = ModuleSpec(ancestor, None, is_package=True)
            setattr(stub, _STUB_MARKER, True)
            sys.modules[ancestor] = stub


def _prune_ancestors(name: str) -> None:
    """Remove the stub ancestors of ``name`` that nothing is nested under any more."""
    for ancestor in reversed(_ancestors(name)):
        module = sys.modules.get(ancestor)
        if module is not None and getattr(module, _STUB_MARKER, False):
            if _entries(ancestor) == [ancestor]:
                del sys.modules[ancestor]


class ModuleResource(Tracked[Any]):
    """A module (or package) loaded from ``path`` under the dotted name ``name``.

    With ``package=False`` (default) ``path`` is a ``.py`` file. With
    ``package=True`` ``path`` is a directory containing ``__init__.py``; the
    result is a real package whose ``__path__`` is that directory, so relative
    imports (``from .plugin import entry``) and ``importlib.import_module(
    f"{name}.plugin")`` resolve against it like against any package on disk.

    The module's top-level code runs while it is loaded, as whichever plugin is
    executing, so what it creates is attributed to that plugin.

    Releasing removes the module and everything nested under it from
    ``sys.modules``, so loading the same name again starts from a clean slate.
    A load that fails leaves nothing behind.

    Args:
        name: The dotted module name to load under.
        path: The ``.py`` file, or the package directory.
        package: Whether ``path`` is a package directory.
        replace: Unload whatever is registered under ``name`` instead of raising.

    Raises:
        ModuleAlreadyLoadedError: If ``name`` (or a module nested under it) is taken
            and ``replace`` is false.
        ImportError: If the file cannot be loaded.
    """

    def __init__(
        self,
        name: str,
        path: str | os.PathLike[str],
        *,
        package: bool = False,
        replace: bool = False,
    ) -> None:
        self.name = name
        self.path = Path(path)
        self.package = package

        if package:
            source = self.path / "__init__.py"
            locations: list[str] | None = [str(self.path)]
        else:
            source = self.path
            locations = None
        if not source.is_file():
            raise ImportError(f"cannot load module {name!r}: {source} is not a file")

        taken = _entries(name)
        if taken:
            if not replace:
                raise ModuleAlreadyLoadedError(
                    f"module {name!r} is already loaded (release it first, or pass replace=True)"
                )
            _purge(name)

        spec = importlib.util.spec_from_file_location(
            name, source, submodule_search_locations=locations
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot create a module spec for {source}")

        module = importlib.util.module_from_spec(spec)
        _ensure_ancestors(name)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            _purge(name)
            raise
        self.module: ModuleType = module

    def _release(self) -> None:
        # Another load may have replaced our module; never unload someone else's.
        if sys.modules.get(self.name) is self.module:
            _purge(self.name)
