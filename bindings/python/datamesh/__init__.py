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

def validate(target: str) -> Dict[str, Any]:
    """Validate OKF/ODKF concept document, bundle directory, or canonical triad."""
    return _runtime.validate(target)

def publish(
    dataset_path: str,
    targets: Optional[List[str]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Publish an ODKF dataset bundle to target platforms (local, portal, kaggle)."""
    return _runtime.publish(dataset_path, targets=targets, options=options)

def align_semantics(datapackage_or_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract semantic field mappings from a DataPackage or schema."""
    return _runtime.align_semantics(datapackage_or_schema)

def discover_endpoint(target_url: str) -> Optional[WellKnownDiscovery]:
    """Discover catalog metadata, capabilities, and auth specifications via /.well-known/datamesh.json or active probing."""
    return _runtime.discover_endpoint(target_url)

def harvest_ckan(
    ckan_url: str,
    query: str = "",
    limit: int = 100,
    offset: int = 0,
    token: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    scope: Optional[str] = None,
    output_dir: Optional[str | Path] = None,
    probe_datastore_schema: bool = True,
) -> CKANHarvestResult:
    """Harvest datasets from a CKAN catalog and reconstruct OKF v0.2 knowledge packages."""
    return _runtime.harvest_ckan(
        ckan_url=ckan_url,
        query=query,
        limit=limit,
        offset=offset,
        token=token,
        client_id=client_id,
        client_secret=client_secret,
        scope=scope,
        output_dir=output_dir,
        probe_datastore_schema=probe_datastore_schema,
    )

storage = _runtime.storage
config = _runtime.config_adapter

from datamesh.domain.models import (
    StorageConfig,
    ResourceDescriptor,
    ResolvedResource,
    CacheEntryMetadata,
    SpatialCoverage,
    TemporalCoverage,
    QualityProfile,
    SemanticFieldMapping,
    PublicationTargetResult,
    WellKnownDiscovery,
    CatalogMetadata,
    AuthConfiguration,
    KeycloakAuth,
    APIKeyAuth,
    CKANPackage,
    CKANResource,
    CKANHarvestResult,
)
from datamesh.ports.storage import StoragePort
from datamesh.ports.resolver import ResourceAdapterPort, ConfigPort
from datamesh.ports.engine import QueryEnginePort
from datamesh.ports.publisher import PublisherPort
from datamesh.ports.harvester import AuthProviderPort, WellKnownResolverPort, CKANClientPort
from datamesh.adapters.storage.local_storage import LocalStorageManager
from datamesh.adapters.config.file_config import FileConfigAdapter
from datamesh.adapters.resolvers.local_file import LocalFileAdapter
from datamesh.adapters.resolvers.github import GitHubAdapter
from datamesh.adapters.resolvers.kaggle import KaggleAdapter
from datamesh.adapters.resolvers.http import HttpAdapter
from datamesh.adapters.auth import NoAuthAdapter, APIKeyAuthAdapter, BearerTokenAuthAdapter, KeycloakAuthAdapter
from datamesh.adapters.catalog.well_known import WellKnownResolverAdapter
from datamesh.adapters.catalog.ckan_client import CKANClientAdapter
from datamesh.adapters.engine.duckdb_engine import DuckDBQueryEngine
from datamesh.adapters.engine.inmem_engine import InMemTabularQueryEngine
from datamesh.adapters.engine.go_engine import GoCoreQueryEngine
from datamesh.usecases.resolve_resource import ResolveAndCacheResourceUseCase
from datamesh.usecases.discover_well_known import DiscoverWellKnownUseCase
from datamesh.usecases.harvest_ckan import HarvestCKANUseCase
from datamesh.server import run_server

__all__ = [
    "discover",
    "discover_endpoint",
    "search",
    "get",
    "query",
    "sql",
    "validate",
    "publish",
    "align_semantics",
    "harvest_ckan",
    "storage",
    "config",
    "run_server",
    "DataMeshRuntime",
    "StorageConfig",
    "ResourceDescriptor",
    "ResolvedResource",
    "CacheEntryMetadata",
    "SpatialCoverage",
    "TemporalCoverage",
    "QualityProfile",
    "SemanticFieldMapping",
    "PublicationTargetResult",
    "WellKnownDiscovery",
    "CatalogMetadata",
    "AuthConfiguration",
    "KeycloakAuth",
    "APIKeyAuth",
    "CKANPackage",
    "CKANResource",
    "CKANHarvestResult",
    "StoragePort",
    "ResourceAdapterPort",
    "ConfigPort",
    "QueryEnginePort",
    "PublisherPort",
    "AuthProviderPort",
    "WellKnownResolverPort",
    "CKANClientPort",
    "LocalStorageManager",
    "FileConfigAdapter",
    "LocalFileAdapter",
    "GitHubAdapter",
    "KaggleAdapter",
    "HttpAdapter",
    "NoAuthAdapter",
    "APIKeyAuthAdapter",
    "BearerTokenAuthAdapter",
    "KeycloakAuthAdapter",
    "WellKnownResolverAdapter",
    "CKANClientAdapter",
    "DuckDBQueryEngine",
    "InMemTabularQueryEngine",
    "GoCoreQueryEngine",
    "ResolveAndCacheResourceUseCase",
    "DiscoverWellKnownUseCase",
    "HarvestCKANUseCase",
]
