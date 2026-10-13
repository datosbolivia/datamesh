from __future__ import annotations

import os
from pathlib import Path
from typing import List

# Standard DataMesh paths and configuration constants
DEFAULT_DATAMESH_HOME: Path = Path.home() / "datamesh"
DEFAULT_CACHE_DIR: Path = DEFAULT_DATAMESH_HOME / "cache"
DEFAULT_CONFIG_FILE: Path = DEFAULT_DATAMESH_HOME / "config.yaml"
DEFAULT_CATALOG_URL: str = "https://datosbolivia.github.io/llms.txt"
DEFAULT_TIMEOUT_SECONDS: int = 30
DEFAULT_MAX_CACHE_SIZE_BYTES: int = 10 * 1024 * 1024 * 1024  # 10 GB

# Environment variable keys
ENV_DATAMESH_HOME = "DATAMESH_HOME"
ENV_DATAMESH_STORAGE_PATH = "DATAMESH_STORAGE_PATH"
ENV_DATAMESH_CACHE_DIR = "DATAMESH_CACHE_DIR"
ENV_DATAMESH_CONFIG_FILE = "DATAMESH_CONFIG_FILE"
ENV_DATAMESH_CATALOG_URL = "DATAMESH_CATALOG_URL"
ENV_DATAMESH_CATALOGS = "DATAMESH_CATALOGS"
ENV_DATAMESH_CATALOG_URLS = "DATAMESH_CATALOG_URLS"
ENV_DATAMESH_PROJECTS_DIR = "DATAMESH_PROJECTS_DIR"
ENV_DATAMESH_WORKSPACE_DIR = "DATAMESH_WORKSPACE_DIR"
ENV_DATAMESH_KNOWLEDGE_DIR = "DATAMESH_KNOWLEDGE_DIR"
ENV_DATAMESH_NODES_DIR = "DATAMESH_NODES_DIR"

def get_datamesh_home() -> Path:
    """Returns active datamesh home directory, respecting DATAMESH_HOME or defaulting to ~/datamesh."""
    env_val = os.environ.get(ENV_DATAMESH_HOME)
    if env_val:
        return Path(env_val).expanduser().resolve()
    primary = Path.home() / "datamesh"
    legacy = Path.home() / ".datamesh"
    if primary.exists():
        return primary
    if legacy.exists():
        return legacy
    return primary

def get_cache_dir() -> Path:
    """Returns active cache directory, respecting DATAMESH_STORAGE_PATH / DATAMESH_CACHE_DIR."""
    env_cache = os.environ.get(ENV_DATAMESH_STORAGE_PATH) or os.environ.get(ENV_DATAMESH_CACHE_DIR)
    if env_cache:
        return Path(env_cache).expanduser().resolve()
    return get_datamesh_home() / "cache"

def get_workspace_search_dirs() -> List[Path]:
    """Returns workspace and project search directories dynamically without hardcoded machine paths.

    When ``DATAMESH_PROJECTS_DIR``/``DATAMESH_WORKSPACE_DIR`` is explicitly set it is treated
    as the *sole* workspace root (exclusive override), which makes resolution hermetic and
    reproducible in tests and CI instead of scanning the user's whole home directory.
    """
    dirs: List[Path] = []

    # 1. Explicit environment variable (exclusive override)
    explicit: List[Path] = []
    for env_k in [ENV_DATAMESH_PROJECTS_DIR, ENV_DATAMESH_WORKSPACE_DIR]:
        val = os.environ.get(env_k)
        if val:
            p = Path(val).expanduser().resolve()
            if p.exists() and p.is_dir() and p not in explicit:
                explicit.append(p)
    if explicit:
        return explicit

    return dirs


def load_environment() -> None:
    """Auto-loads environment variables from datamesh.env and .env files if present.

    Searches current working directory and its parents up to repository boundary.
    Existing environment variables are never overwritten.
    """
    try:
        cwd = Path.cwd()
    except Exception:
        return

    search_dirs = [cwd]
    try:
        for parent in cwd.parents:
            search_dirs.append(parent)
            if (parent / ".git").exists():
                break
    except Exception:
        pass

    loaded = False
    try:
        from dotenv import load_dotenv  # type: ignore

        for d in search_dirs:
            for fname in ("datamesh.env", ".env"):
                p = d / fname
                if p.is_file():
                    if "PROJECT_ROOT" not in os.environ:
                        os.environ["PROJECT_ROOT"] = str(d.resolve())
                    try:
                        import io
                        with open(p, "r", encoding="utf-8") as f:
                            lines = [ln for ln in f if "$(" not in ln]
                        load_dotenv(stream=io.StringIO("".join(lines)), override=False)
                        loaded = True
                    except Exception:
                        load_dotenv(p, override=False)
                        loaded = True
    except ImportError:
        pass

    if not loaded:
        for d in search_dirs:
            for fname in ("datamesh.env", ".env"):
                p = d / fname
                if p.is_file():
                    if "PROJECT_ROOT" not in os.environ:
                        os.environ["PROJECT_ROOT"] = str(d.resolve())
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if not line or line.startswith("#"):
                                    continue
                                if line.startswith("export "):
                                    line = line[7:].strip()
                                if "=" in line:
                                    k, v = line.split("=", 1)
                                    k = k.strip()
                                    v = v.strip().strip("'\"")
                                    if "${PROJECT_ROOT}" in v:
                                        v = v.replace("${PROJECT_ROOT}", os.environ["PROJECT_ROOT"])
                                    if k and k not in os.environ and not v.startswith("$("):
                                        os.environ[k] = v
                    except Exception:
                        pass

    # Sanity check: fix any accidental root-level paths from unexpanded ${PROJECT_ROOT}
    for k in ("DATAMESH_HOME", "DATAMESH_CACHE_DIR", "DATAMESH_PROJECTS_DIR", "DATAMESH_WORKSPACE_DIR"):
        v = os.environ.get(k)
        if v and (v.startswith("/.datamesh") or v == "/"):
            proj_root = os.environ.get("PROJECT_ROOT", str(cwd.resolve()))
            rel = v.lstrip("/")
            os.environ[k] = str(Path(proj_root) / rel)


load_environment()

