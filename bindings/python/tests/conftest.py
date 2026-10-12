"""Hermetic test environment for the DataMesh SDK Python binding.

The SDK resolves canonical triads through the user workspace (``~/Proyectos``),
the temporal cache (``~/datamesh/cache``) and any sibling ``catalogo-datamesh``
checkout. That makes query tests depend on whatever happens to live on the
developer machine, so they pass or fail for reasons unrelated to the code.

This module runs *before* test modules import ``datamesh`` (pytest loads
``conftest.py`` first) and pins every lookup root to a committed fixture
workspace plus a throwaway home/cache directory. Tests therefore resolve the
same resources everywhere: locally, in CI, on any machine.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_HOME = Path(tempfile.mkdtemp(prefix="datamesh-tests-home-"))
_CACHE = _HOME / "cache"
_CACHE.mkdir(parents=True, exist_ok=True)

os.environ["DATAMESH_HOME"] = str(_HOME)
os.environ["DATAMESH_CACHE_DIR"] = str(_CACHE)
os.environ["DATAMESH_STORAGE_PATH"] = str(_CACHE)
os.environ["DATAMESH_PROJECTS_DIR"] = str(_FIXTURES)
os.environ["DATAMESH_WORKSPACE_DIR"] = str(_FIXTURES)
