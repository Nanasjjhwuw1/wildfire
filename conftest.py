"""Pytest bootstrap: put the repo root on sys.path so tests can do
`from backend.models... import ...` regardless of where pytest is invoked from.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
