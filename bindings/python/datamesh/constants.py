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
    """Returns workspace and project search directories dynamically without hardcoded machine paths."""
    dirs: List[Path] = []

    # 1. Explicit environment variable
    for env_k in [ENV_DATAMESH_PROJECTS_DIR, ENV_DATAMESH_WORKSPACE_DIR]:
        val = os.environ.get(env_k)
        if val:
            p = Path(val).expanduser().resolve()
            if p.exists() and p.is_dir() and p not in dirs:
                dirs.append(p)

    # 2. Sibling directory to current working directory (e.g. parent of cloned repo)
    try:
        parent_dir = Path.cwd().parent.resolve()
        if parent_dir.exists() and parent_dir.is_dir() and parent_dir != Path.home() and parent_dir not in dirs:
            dirs.append(parent_dir)
    except Exception:
        pass

    # 3. Standard user project directories (Projects, Proyectos, workspace, src)
    home = Path.home()
    for sub in ["Projects", "Proyectos", "workspace", "src"]:
        p = home / sub
        if p.exists() and p.is_dir() and p not in dirs:
            dirs.append(p)

    return dirs
