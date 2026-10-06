"""The shipped examples run end to end."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EXAMPLES = Path(__file__).parent.parent / "examples"


def run(script: str) -> str:
    result = subprocess.run(
        [sys.executable, str(EXAMPLES / script)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    return result.stdout


def test_main_example_walks_through_both_lifetimes() -> None:
    out = run("main.py")
    assert "alpha: 4 runtime, 1 persistent" in out  # module, timer, temp file + event
    assert "[beta] hello world! (running as beta)" in out
    assert "[alpha] tick, running as alpha" in out
    # beta was disabled before the second greeting, so only one hello.
    assert out.count("[beta] hello") == 1
    assert "beta: 0 runtime, 0 persistent" in out
    assert "scratch exists: False, data exists: True" in out
    assert "data exists: False" in out


def test_zones_example_keeps_hosts_independent() -> None:
    out = run("zones.py")
    assert "forest tracks 1 resource(s)" in out
    assert "desert tracks 1 resource(s)" in out
    assert "after releasing forest: forest=0, desert=1" in out
