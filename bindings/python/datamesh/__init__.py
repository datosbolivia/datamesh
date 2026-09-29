from __future__ import annotations

from typing import Any, Dict, List, Optional
from datamesh.core import DataMeshRuntime

_runtime = DataMeshRuntime()

def discover(catalog_url: Optional[str] = None) -> Dict[str, Any]:
    """Discover federated sovereign catalogs (default: all configured or llms.txt)."""
    return _runtime.discover(catalog_url)

def search(keyword: str, catalog_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search catalog entries across sovereign catalogs by keyword."""
    cat = discover(catalog_url)
    kw = keyword.lower()
    return [
        e for e in cat.get("entries", [])
        if kw in e.get("title", "").lower()
        or kw in e.get("description", "").lower()
        or kw in e.get("domain", "").lower()
    ]

def get(uri_or_url: str) -> Dict[str, Any]:
    """Resolve and validate OKF v0.2 Data Product manifest and description."""
    return _runtime.resolve(uri_or_url)

def query(
    resource_uri: str,
    filters: Optional[Dict[str, str]] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute simple tabular query with optional filters and limits."""
    return _runtime.query(resource_uri, filters=filters, limit=limit)

def sql(
    query_str: str,
    table_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Execute full ANSI/DuckDB SQL with canonical triad table names 'catalogo:dataset:resource'.
    Normalizes heterogeneous formats (CSV, TSV, Parquet, JSON) into high-performance columnar execution.
    """
    return _runtime.sql(query_str, table_mapping=table_mapping)

__all__ = ["discover", "search", "get", "query", "sql", "DataMeshRuntime"]
