# Installation

pkl needs Python 3.11 or newer and has no dependencies.

```bash
uv add plugins-kernel
# or
pip install plugins-kernel
```

The package is typed (`py.typed`) and checked with `mypy --strict`.

## Development

```bash
git clone https://github.com/xpodev/pkl.git
cd pkl
uv sync
uv run pytest
uv run mypy --strict pkl tests
```
