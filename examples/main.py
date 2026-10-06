"""Two plugins, one host, two lifetimes. Run with ``python examples/main.py``."""

from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))  # so that plugins can `import sdk`

import sdk  # noqa: E402


def describe(plugin: sdk.AppPlugin) -> str:
    return (
        f"{plugin.name}: {len(sdk.runtime.resources(plugin))} runtime, "
        f"{len(sdk.persistent.resources(plugin))} persistent resources"
    )


def main() -> None:
    alpha = sdk.AppPlugin(id="a1", name="alpha", metadata={"version": "1.0"})
    beta = sdk.AppPlugin(id="b1", name="beta", metadata={"version": "0.3"})

    print("== load")
    alpha_module = sdk.load(alpha, HERE / "plugins" / "alpha")
    sdk.load(beta, HERE / "plugins" / "beta")
    print(describe(alpha))
    print(describe(beta))

    print("== alpha greets (the host calls alpha's syscall)")
    alpha_module.module.greet("world")
    time.sleep(0.12)

    print("== disable beta: its subscription is released, alpha is unaffected")
    sdk.disable(beta)
    alpha_module.module.greet("again")  # nobody answers any more
    print(describe(beta))

    print("== disable alpha: timer and temp file go, the data directory stays")
    data_path = alpha_module.module.data.path
    scratch_path = alpha_module.module.scratch.path
    sdk.disable(alpha)
    print(f"scratch exists: {scratch_path.exists()}, data exists: {data_path.exists()}")
    print(describe(alpha))

    print("== uninstall alpha: now the data directory goes too")
    sdk.uninstall(alpha)
    print(f"data exists: {data_path.exists()}")


if __name__ == "__main__":
    main()
