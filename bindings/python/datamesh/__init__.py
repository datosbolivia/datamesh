from __future__ import annotations

from typing import Any, Dict, List, Optional
from datamesh.core import DataMeshRuntime

_runtime = DataMeshRuntime()

def discover(catalog_url: Optional[str] = None) -> Dict[str, Any]:
    """Discover federated sovereign catalog (default: llms.txt)."""
    return _runtime.discover(catalog_url)

def search(keyword: str, catalog_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search catalog entries by keyword."""
    cat = discover(catalog_url)
    kw = keyword.lower()
    return [
        e for e in cat.get("entries", [])
        if kw in e.get("title", "").lower()
        or kw in e.get("description", "").lower()
        or kw in e.get("domain", "").lower()
    ]

__all__ = ["discover", "search", "DataMeshRuntime"]
