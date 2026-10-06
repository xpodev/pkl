"""The dependency rule: extensions depend on the core, never the reverse."""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).parent.parent / "pkl"

CORE = {"plugin", "plugin_tracker", "resource", "registry", "errors"}
# `__init__` only re-exports the core.
ALLOWED = {
    **{name: CORE for name in CORE},
    "__init__": CORE,
}


def imported_pkl_modules(path: Path) -> set[str]:
    """The sibling modules of the package that ``path`` imports."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            if node.level == 1:
                if node.module:
                    found.add(node.module.split(".")[0])
                else:
                    found.update(alias.name for alias in node.names)
            elif node.level == 0 and node.module and node.module.split(".")[0] == "pkl":
                parts = node.module.split(".")
                if len(parts) > 1:
                    found.add(parts[1])
                else:
                    found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "pkl" and len(parts) > 1:
                    found.add(parts[1])
    return found


def modules() -> dict[str, Path]:
    return {path.stem: path for path in PACKAGE.glob("*.py")}


def test_core_modules_import_only_the_core() -> None:
    for name in sorted(CORE | {"__init__"}):
        imports = imported_pkl_modules(modules()[name])
        assert imports <= CORE, f"core module {name} imports extension(s) {imports - CORE}"


def test_extensions_import_only_core_and_tracking() -> None:
    allowed = CORE | {"tracking"}
    for name, path in sorted(modules().items()):
        if name in CORE or name == "__init__":
            continue
        imports = imported_pkl_modules(path)
        assert imports <= allowed, (
            f"extension {name} imports {imports - allowed}; extensions may only depend on "
            "the core and on `tracking`, never on each other"
        )


def test_tracking_imports_only_the_core() -> None:
    imports = imported_pkl_modules(modules()["tracking"])
    assert imports <= CORE, f"tracking imports {imports - CORE}"


def test_the_checker_sees_imports() -> None:
    # Guard against the test passing vacuously.
    assert "plugin_tracker" in imported_pkl_modules(modules()["tracking"])
    assert "tracking" not in imported_pkl_modules(modules()["registry"])
