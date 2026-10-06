"""Tests for pkl.modules."""

from __future__ import annotations

import importlib
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from pkl import NoCurrentPluginError, Plugin, PluginTracker, ResourceRegistry
from pkl.modules import ModuleAlreadyLoadedError, ModuleResource
from pkl.tracking import ResourceTracker


class Env:
    def __init__(self) -> None:
        self.plugins = PluginTracker[Plugin]()
        self.registry = ResourceRegistry[Plugin]()
        self.tracker = ResourceTracker(self.plugins, self.registry)
        self.module_type = ModuleResource.with_tracker(self.tracker)


@pytest.fixture
def prefix() -> Iterator[str]:
    """A module-name prefix that is unique to the test, cleaned up afterwards."""
    name = f"pkltest_{uuid.uuid4().hex}"
    yield name
    for key in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
        del sys.modules[key]


def make_package(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True)
    for filename, source in files.items():
        (root / filename).write_text(source, encoding="utf-8")
    return root


def load(env: Env, plugin: Plugin, *args: object, **kwargs: object) -> ModuleResource:
    with env.plugins.executing(plugin):
        return env.module_type(*args, **kwargs)  # type: ignore[arg-type]


def test_loads_a_single_file_and_unloads_it(tmp_path: Path, prefix: str) -> None:
    env, plugin = Env(), Plugin()
    path = tmp_path / "mod.py"
    path.write_text("VALUE = 41 + 1\n")
    resource = load(env, plugin, f"{prefix}.mod", path)
    assert resource.module.VALUE == 42
    assert sys.modules[f"{prefix}.mod"] is resource.module
    assert resource.owner is plugin
    env.registry.release(plugin)
    assert f"{prefix}.mod" not in sys.modules


def test_package_gets_a_real_path_and_relative_imports_work(tmp_path: Path, prefix: str) -> None:
    env, plugin = Env(), Plugin()
    root = make_package(
        tmp_path / "combat",
        {
            "__init__.py": "from .plugin import on_death, Damage\n",
            "plugin.py": "class Damage:\n    pass\n\ndef on_death():\n    return 'dead'\n",
            "helpers.py": "def double(x):\n    return x * 2\n",
        },
    )
    resource = load(env, plugin, f"{prefix}.combat", root, package=True)
    package = resource.module
    assert package.__path__ == [str(root)]
    assert package.on_death() == "dead"
    # A sibling the __init__ did not import is reachable through the package.
    helpers = importlib.import_module(f"{prefix}.combat.helpers")
    assert helpers.double(2) == 4


def test_entrypoint_imported_by_init_runs_exactly_once(tmp_path: Path, prefix: str) -> None:
    env, plugin = Env(), Plugin()
    counter = tmp_path / "runs.txt"
    root = make_package(
        tmp_path / "plug",
        {
            "__init__.py": "from .plugin import Thing\n",
            "plugin.py": (
                f"with open({str(counter)!r}, 'a') as handle:\n"
                "    handle.write('x')\n"
                "class Thing:\n    pass\n"
            ),
        },
    )
    resource = load(env, plugin, f"{prefix}.plug", root, package=True)
    entry = importlib.import_module(f"{prefix}.plug.plugin")
    assert counter.read_text() == "x"
    # One module object, so one class: no duplicate identities.
    assert resource.module.Thing is entry.Thing


def test_a_name_exported_by_init_is_not_clobbered_by_the_submodule(
    tmp_path: Path, prefix: str
) -> None:
    env, plugin = Env(), Plugin()
    root = make_package(
        tmp_path / "plug",
        {
            "__init__.py": "from .plugin import plugin\n",
            "plugin.py": "def plugin():\n    return 'the function'\n",
        },
    )
    resource = load(env, plugin, f"{prefix}.plug", root, package=True)
    assert resource.module.plugin() == "the function"


def test_failed_load_leaves_nothing_behind(tmp_path: Path, prefix: str) -> None:
    env, plugin = Env(), Plugin()
    root = make_package(
        tmp_path / "broken",
        {
            "__init__.py": "from . import helper\nraise RuntimeError('boom')\n",
            "helper.py": "VALUE = 1\n",
        },
    )
    with pytest.raises(RuntimeError, match="boom"):
        load(env, plugin, f"{prefix}.broken", root, package=True)
    assert [k for k in sys.modules if k.startswith(prefix)] == []
    assert env.registry.resources(plugin) == ()


def test_missing_file_is_an_import_error(tmp_path: Path, prefix: str) -> None:
    env, plugin = Env(), Plugin()
    with pytest.raises(ImportError):
        load(env, plugin, f"{prefix}.nothing", tmp_path / "nothing.py")
    with pytest.raises(ImportError):
        load(env, plugin, f"{prefix}.nopkg", tmp_path, package=True)


def test_loading_a_taken_name_raises_unless_replaced(tmp_path: Path, prefix: str) -> None:
    env, a, b = Env(), Plugin(), Plugin()
    path = tmp_path / "mod.py"
    path.write_text("class Marker:\n    pass\n")
    first = load(env, a, f"{prefix}.mod", path)
    with pytest.raises(ModuleAlreadyLoadedError):
        load(env, b, f"{prefix}.mod", path)
    second = load(env, b, f"{prefix}.mod", path, replace=True)
    assert second.module is not first.module
    # The replaced module's resource must not unload its successor.
    first.release()
    assert sys.modules[f"{prefix}.mod"] is second.module


def test_reloading_after_release_gives_a_fresh_module(tmp_path: Path, prefix: str) -> None:
    env, plugin = Env(), Plugin()
    root = make_package(
        tmp_path / "plug",
        {
            "__init__.py": "from .plugin import Marker\n",
            "plugin.py": "class Marker:\n    pass\n",
        },
    )
    first = load(env, plugin, f"{prefix}.plug", root, package=True)
    first_marker = first.module.Marker
    env.registry.release(plugin)
    assert [k for k in sys.modules if k.startswith(prefix)] == []

    second = load(env, plugin, f"{prefix}.plug", root, package=True)
    assert second.module.Marker is not first_marker  # nothing stale was reused


def test_same_directory_can_be_loaded_under_different_prefixes(
    tmp_path: Path, prefix: str
) -> None:
    one, two = Env(), Env()
    plugin = Plugin()
    root = make_package(
        tmp_path / "plug",
        {"__init__.py": "from .plugin import Marker\n", "plugin.py": "class Marker: ...\n"},
    )
    first = load(one, plugin, f"{prefix}_one.plug", root, package=True)
    second = load(two, plugin, f"{prefix}_two.plug", root, package=True)
    try:
        assert first.module.Marker is not second.module.Marker
        one.registry.release(plugin)
        assert f"{prefix}_two.plug" in sys.modules
    finally:
        two.registry.release(plugin)


def test_module_code_runs_as_the_loading_plugin(tmp_path: Path, prefix: str) -> None:
    env, plugin = Env(), Plugin()
    holder = prefix + "_holder"
    path = tmp_path / "mod.py"
    path.write_text(f"import sys\nSEEN = sys.modules[{holder!r}].plugins.current\n")
    support = type(sys)(holder)
    support.plugins = env.plugins  # type: ignore[attr-defined]
    sys.modules[holder] = support
    try:
        resource = load(env, plugin, f"{prefix}.mod", path)
    finally:
        del sys.modules[holder]
    assert resource.module.SEEN is plugin


def test_a_module_needs_a_plugin_by_default(tmp_path: Path, prefix: str) -> None:
    env = Env()
    path = tmp_path / "mod.py"
    path.write_text("X = 1\n")
    with pytest.raises(NoCurrentPluginError):
        env.module_type(f"{prefix}.mod", path)
    assert [k for k in sys.modules if k.startswith(prefix)] == []


def test_from_dot_import_inside_init_works_without_importable_parents(
    tmp_path: Path, prefix: str
) -> None:
    env, plugin = Env(), Plugin()
    root = make_package(
        tmp_path / "plug",
        {
            "__init__.py": "from . import components\nVALUE = components.VALUE\n",
            "components.py": "VALUE = 7\n",
        },
    )
    resource = load(env, plugin, f"{prefix}.deep.plug", root, package=True)
    assert resource.module.VALUE == 7


def test_stub_parents_are_shared_and_removed_with_the_last_child(
    tmp_path: Path, prefix: str
) -> None:
    env, a, b = Env(), Plugin(), Plugin()
    first, second = tmp_path / "one.py", tmp_path / "two.py"
    first.write_text("X = 1\n")
    second.write_text("X = 2\n")
    one = load(env, a, f"{prefix}.plugins.one", first)
    two = load(env, b, f"{prefix}.plugins.two", second)
    assert f"{prefix}.plugins" in sys.modules
    one.release()
    assert f"{prefix}.plugins" in sys.modules  # `two` still lives below it
    two.release()
    assert [k for k in sys.modules if k.startswith(prefix)] == []
