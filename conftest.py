# ruff: noqa: INP001  # pytest rootdir conftest, deliberately not a package
"""Pytest configuration for the ALL4100 custom component.

Puts this directory on ``sys.path`` so the tests can import the component as
``custom_components.all4100``, the same name Home Assistant loads it under.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
