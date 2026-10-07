"""Files and directories that are removed when their owner's lifetime ends.

Which lifetime that is depends on the registry the application binds these
classes to: bind them to a runtime registry and temporary files disappear when
the plugin is disabled; bind them to a persistent registry and a plugin's files
are removed when it is uninstalled.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .tracking import Tracked

__all__ = ["File", "Directory", "TempFile", "TempDirectory"]


class File(Tracked[Any]):
    """A file that is deleted on release. A file that is already gone is fine."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def on_release(self) -> None:
        self.path.unlink(missing_ok=True)


class Directory(Tracked[Any]):
    """A directory that is deleted, with its contents, on release."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def on_release(self) -> None:
        try:
            shutil.rmtree(self.path)
        except FileNotFoundError:
            pass


class TempFile(File):
    """A new, empty temporary file that is deleted on release."""

    def __init__(
        self,
        *,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | os.PathLike[str] | None = None,
    ) -> None:
        descriptor, name = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir)
        os.close(descriptor)
        super().__init__(name)


class TempDirectory(Directory):
    """A new temporary directory that is deleted, with its contents, on release."""

    def __init__(
        self,
        *,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | os.PathLike[str] | None = None,
    ) -> None:
        super().__init__(tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir))
