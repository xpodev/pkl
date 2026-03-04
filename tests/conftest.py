"""Pytest configuration."""

import sys
from pathlib import Path

# Add pkl to path
pkl_path = Path(__file__).parent.parent
sys.path.insert(0, str(pkl_path))
