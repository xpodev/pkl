"""Interleaved execution of async plugins."""

from __future__ import annotations

import asyncio
import contextvars

from pkl import Plugin, PluginTracker, ResourceRegistry
from pkl.syscall import syscall
from pkl.tracking import ResourceTracker, Tracked


class Env:
    def __init__(self) -> None:
        self.plugins = PluginTracker[Plugin]()
        self.registry = ResourceRegistry[Plugin]()
        self.tracker = ResourceTracker(self.plugins, self.registry)


class Item(Tracked[Plugin]):
    def on_release(self) -> None: ...


async def test_interleaved_plugins_never_see_each_other() -> None:
    env = Env()
    plugins = [Plugin() for _ in range(5)]
    mismatches: list[tuple[int, int, Plugin | None]] = []

    async def run(index: int, plugin: Plugin) -> None:
        with env.plugins.executing(plugin):
            for step in range(6):
                # Stagger so that the tasks genuinely interleave.
                await asyncio.sleep(0.001 * ((index + step) % 4))
                if env.plugins.current is not plugin:
                    mismatches.append((index, step, env.plugins.current))
        assert env.plugins.current is None or env.plugins.current is not plugin

    await asyncio.gather(*(run(i, p) for i, p in enumerate(plugins)))
    assert mismatches == []
    assert env.plugins.current is None


async def test_resources_created_by_interleaved_tasks_land_under_the_right_plugin() -> None:
    env = Env()
    item_type = Item.with_tracker(env.tracker)
    a, b, c = Plugin(), Plugin(), Plugin()

    async def run(plugin: Plugin, count: int, delay: float) -> list[Item]:
        created: list[Item] = []
        with env.plugins.executing(plugin):
            for _ in range(count):
                await asyncio.sleep(delay)
                created.append(item_type())
        return created

    ra, rb, rc = await asyncio.gather(run(a, 3, 0.002), run(b, 4, 0.001), run(c, 2, 0.003))
    assert env.registry.resources(a) == tuple(ra)
    assert env.registry.resources(b) == tuple(rb)
    assert env.registry.resources(c) == tuple(rc)
    assert all(item.owner is a for item in ra)


async def test_async_syscall_runs_as_its_definer_and_restores_the_awaiting_plugin() -> None:
    env = Env()
    provider, b = Plugin(), Plugin()
    seen: list[tuple[str, Plugin | None]] = []

    with env.plugins.executing(provider):

        async def api() -> None:
            seen.append(("before", env.plugins.current))
            await asyncio.sleep(0.002)
            seen.append(("after", env.plugins.current))

        wrapped = syscall(env.plugins, api)

    async def run_b() -> None:
        with env.plugins.executing(b):
            await wrapped()
            assert env.plugins.current is b

    async def other_noise() -> None:
        other = Plugin()
        with env.plugins.executing(other):
            for _ in range(5):
                await asyncio.sleep(0.001)
                assert env.plugins.current is other

    await asyncio.gather(run_b(), other_noise())
    assert seen == [("before", provider), ("after", provider)]


async def test_releasing_one_plugin_mid_flight_leaves_the_others() -> None:
    env = Env()
    item_type = Item.with_tracker(env.tracker)
    a, b = Plugin(), Plugin()
    released_a = asyncio.Event()

    async def run_a() -> Item:
        with env.plugins.executing(a):
            item = item_type()
        await asyncio.sleep(0.002)
        env.registry.release(a)
        released_a.set()
        return item

    async def run_b() -> tuple[Item, Item]:
        with env.plugins.executing(b):
            first = item_type()
            await released_a.wait()
            second = item_type()
        return first, second

    item_a, (first_b, second_b) = await asyncio.gather(run_a(), run_b())
    assert item_a.released
    assert not first_b.released and not second_b.released
    assert env.registry.resources(b) == (first_b, second_b)


async def test_tasks_inherit_the_plugin_they_were_created_under() -> None:
    env = Env()
    a = Plugin()

    async def child() -> Plugin | None:
        await asyncio.sleep(0)
        return env.plugins.current

    with env.plugins.executing(a):
        task = asyncio.create_task(child())
    # The task copied the context at creation, so it keeps `a` after we left.
    assert await task is a


async def test_task_group_children_each_keep_their_own_plugin() -> None:
    env = Env()
    plugins = [Plugin() for _ in range(4)]
    results: dict[int, list[Plugin | None]] = {i: [] for i in range(4)}

    async def run(index: int) -> None:
        with env.plugins.executing(plugins[index]):
            for _ in range(3):
                await asyncio.sleep(0.001 * (index + 1))
                results[index].append(env.plugins.current)

    async with asyncio.TaskGroup() as group:
        for index in range(4):
            group.create_task(run(index))

    for index, seen in results.items():
        assert seen == [plugins[index]] * 3


async def test_executor_threads_need_a_copied_context() -> None:
    env = Env()
    a = Plugin()
    loop = asyncio.get_running_loop()

    def current() -> Plugin | None:
        return env.plugins.current

    with env.plugins.executing(a):
        plain = await loop.run_in_executor(None, current)
        copied = await loop.run_in_executor(None, contextvars.copy_context().run, current)
    assert plain is None  # worker threads start with an empty context
    assert copied is a
