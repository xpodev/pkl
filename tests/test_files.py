"""Tests for pkl.files."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkl import NoCurrentPluginError, Plugin, PluginTracker, ResourceRegistry
from pkl.files import Directory, File, TempDirectory, TempFile
from pkl.tracking import ResourceTracker


class Env:
    def __init__(self) -> None:
        self.plugins = PluginTracker[Plugin]()
        self.registry = ResourceRegistry[Plugin]()
        self.tracker = ResourceTracker(self.plugins, self.registry)
        self.file_type = File.with_tracker(self.tracker)
        self.directory_type = Directory.with_tracker(self.tracker)
        self.temp_file_type = TempFile.with_tracker(self.tracker)
        self.temp_directory_type = TempDirectory.with_tracker(self.tracker)


def test_file_is_deleted_on_release(tmp_path: Path) -> None:
    env, plugin = Env(), Plugin()
    path = tmp_path / "data.txt"
    path.write_text("x")
    with env.plugins.executing(plugin):
        file = env.file_type(path)
    assert file.path == path
    assert path.exists()
    env.registry.release(plugin)
    assert not path.exists()


def test_file_that_is_already_gone_is_fine(tmp_path: Path) -> None:
    env, plugin = Env(), Plugin()
    with env.plugins.executing(plugin):
        file = env.file_type(tmp_path / "never-existed")
    file.release()
    assert file.released


def test_directory_is_deleted_with_its_contents(tmp_path: Path) -> None:
    env, plugin = Env(), Plugin()
    root = tmp_path / "plugin-data"
    (root / "nested").mkdir(parents=True)
    (root / "nested" / "file.txt").write_text("x")
    with env.plugins.executing(plugin):
        env.directory_type(root)
    env.registry.release(plugin)
    assert not root.exists()


def test_missing_directory_is_fine(tmp_path: Path) -> None:
    env, plugin = Env(), Plugin()
    with env.plugins.executing(plugin):
        directory = env.directory_type(tmp_path / "missing")
    directory.release()


def test_temp_file_exists_until_released(tmp_path: Path) -> None:
    env, plugin = Env(), Plugin()
    with env.plugins.executing(plugin):
        temp = env.temp_file_type(suffix=".txt", prefix="pkl-", dir=tmp_path)
    assert temp.path.exists()
    assert temp.path.parent == tmp_path
    assert temp.path.name.startswith("pkl-") and temp.path.suffix == ".txt"
    env.registry.release(plugin)
    assert not temp.path.exists()


def test_temp_directory_exists_until_released(tmp_path: Path) -> None:
    env, plugin = Env(), Plugin()
    with env.plugins.executing(plugin):
        temp = env.temp_directory_type(dir=tmp_path)
    (temp.path / "inner.txt").write_text("x")
    assert temp.path.is_dir()
    env.registry.release(plugin)
    assert not temp.path.exists()


def test_files_follow_the_lifetime_of_the_registry_they_are_bound_to(tmp_path: Path) -> None:
    plugins = PluginTracker[Plugin]()
    runtime, persistent = ResourceRegistry[Plugin](), ResourceRegistry[Plugin]()
    runtime_files = TempFile.with_tracker(ResourceTracker(plugins, runtime))
    persistent_files = TempFile.with_tracker(ResourceTracker(plugins, persistent))
    plugin = Plugin()
    with plugins.executing(plugin):
        scratch = runtime_files(dir=tmp_path)
        keep = persistent_files(dir=tmp_path)

    runtime.release(plugin)  # "disable"
    assert not scratch.path.exists()
    assert keep.path.exists()
    persistent.release(plugin)  # "uninstall"
    assert not keep.path.exists()


def test_a_temp_file_is_not_created_without_a_plugin(tmp_path: Path) -> None:
    env = Env()
    with pytest.raises(NoCurrentPluginError):
        env.temp_file_type(dir=tmp_path)
    assert list(tmp_path.iterdir()) == []
