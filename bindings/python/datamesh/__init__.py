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
    engine: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute full ANSI SQL with canonical triad table names 'catalogo:dataset:resource'.
    Normalizes heterogeneous formats (CSV, TSV, Parquet, JSON) into high-performance execution.
    Optionally select query engine ('duckdb', 'inmem', 'go').
    """
    return _runtime.sql(query_str, table_mapping=table_mapping, engine=engine)

storage = _runtime.storage
config = _runtime.config_adapter

from datamesh.domain.models import StorageConfig, ResourceDescriptor, ResolvedResource, CacheEntryMetadata
from datamesh.ports.storage import StoragePort
from datamesh.ports.resolver import ResourceAdapterPort, ConfigPort
from datamesh.ports.engine import QueryEnginePort
from datamesh.adapters.storage.local_storage import LocalStorageManager
from datamesh.adapters.config.file_config import FileConfigAdapter
from datamesh.adapters.resolvers.local_file import LocalFileAdapter
from datamesh.adapters.resolvers.github import GitHubAdapter
from datamesh.adapters.resolvers.kaggle import KaggleAdapter
from datamesh.adapters.resolvers.http import HttpAdapter
from datamesh.adapters.engine.duckdb_engine import DuckDBQueryEngine
from datamesh.adapters.engine.inmem_engine import InMemTabularQueryEngine
from datamesh.adapters.engine.go_engine import GoCoreQueryEngine
from datamesh.usecases.resolve_resource import ResolveAndCacheResourceUseCase
from datamesh.server import run_server

__all__ = [
    "discover",
    "search",
    "get",
    "query",
    "sql",
    "storage",
    "config",
    "run_server",
    "DataMeshRuntime",
    "StorageConfig",
    "ResourceDescriptor",
    "ResolvedResource",
    "CacheEntryMetadata",
    "StoragePort",
    "ResourceAdapterPort",
    "ConfigPort",
    "QueryEnginePort",
    "LocalStorageManager",
    "FileConfigAdapter",
    "LocalFileAdapter",
    "GitHubAdapter",
    "KaggleAdapter",
    "HttpAdapter",
    "DuckDBQueryEngine",
    "InMemTabularQueryEngine",
    "GoCoreQueryEngine",
    "ResolveAndCacheResourceUseCase",
]
