"""
Pytest configuration: add scripts/ to sys.path so tests can import
from the common package without needing an installed distribution.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))
