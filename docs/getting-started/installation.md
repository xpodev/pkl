# Installation

PKL is a pure Python package with no required dependencies.

## Using uv (Recommended)

[uv](https://docs.astral.sh/uv/) is a fast Python package manager that we recommend for the best experience:

```bash
# Install uv (if not already installed)
pip install uv

# Install pkl
uv pip install pkl
```

## Using pip

Standard pip installation:

```bash
pip install pkl
```

## Development Installation

To contribute or work with the source code:

```bash
# Clone the repository
git clone https://github.com/xpodev/pkl.git
cd pkl

# Install in editable mode
uv pip install -e .

# Or with pip
pip install -e .
```

## Requirements

- **Python 3.9 or higher**
- No required runtime dependencies (uses stdlib only)

## Optional Dependencies

- `tomli` - For TOML manifest support on Python <3.11 (built-in on 3.11+)
- `pyyaml` - For YAML manifest file support

Install optional dependencies:

```bash
uv pip install pkl[yaml]
```

## Verify Installation

Check that PKL is installed correctly:

```python
import pkl
print(pkl.__version__)
```

## Next Steps

- [Quick Start](quick-start.md) - Create your first plugin
- [Core Concepts](concepts.md) - Understand PKL's architecture
