from __future__ import annotations

from typing import Any, Dict, List, Optional
from datamesh.core import DataMeshRuntime

__version__ = "0.2.1"

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

def resolve_resource(resource_uri: str):
    """Resolve a resource reference to its local/cached descriptor (triad, URL or path)."""
    return _runtime.resolver_usecase.resolve(resource_uri)

def get_engine(name: Optional[str] = None):
    """Return a configured query engine by name ('duckdb', 'inmem', 'go')."""
    return _runtime.get_engine(name)

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
    package_id: Optional[str] = None,
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
        package_id=package_id,
    )

def create_datapackage(
    name: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    resources: Optional[List[Dict[str, Any]]] = None,
    files: Optional[List[str | Path]] = None,
    output_file: Optional[str | Path] = None,
    metadata: Optional[Dict[str, Any]] = None,
    sources: Optional[List[Union[str, Dict[str, Any]]]] = None,
    transformations: Optional[List[Dict[str, Any]]] = None,
    lineage: Optional[Dict[str, Any]] = None,
) -> DataPackageBuildResult:
    """Create an OKF v0.2 datapackage.yaml manifest from described files or schemas."""
    return _runtime.create_datapackage(
        name=name,
        title=title,
        description=description,
        resources=resources,
        files=files,
        output_file=output_file,
        metadata=metadata,
        sources=sources,
        transformations=transformations,
        lineage=lineage,
    )

def lineage(
    target: Optional[str] = None,
    search_dirs: Optional[List[Union[str, Path]]] = None,
    catalog_url: Optional[str] = None,
) -> LineageGraph:
    """Build or query the DAG lineage graph of sovereign datasets and their derivations."""
    return _runtime.lineage(target=target, search_dirs=search_dirs, catalog_url=catalog_url)

def get_lineage(
    dataset_id_or_path: str,
    search_dirs: Optional[List[Union[str, Path]]] = None,
    catalog_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Get detailed upstream and downstream provenance for a specific dataset."""
    return _runtime.get_lineage(dataset_id_or_path=dataset_id_or_path, search_dirs=search_dirs, catalog_url=catalog_url)

# Aliases with _ prefix directly exposing core functionality
_discover = discover
_search = search
_get = get
_query = query
_sql = sql
_validate = validate
_publish = publish
_lineage = lineage
_get_lineage = get_lineage



def link_concept(
    datapackage_path_or_dict: Union[str, Path, Dict[str, Any]],
    resource_name: Union[str, int],
    column_name: str,
    concept_ref: Optional[str] = None,
    value_mappings: Optional[Dict[str, Union[str, Dict[str, str]]]] = None,
    save_to_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Link a column and/or its categorical values in a DataPackage to knowledge concepts."""
    return _runtime.link_concept(
        datapackage_path_or_dict=datapackage_path_or_dict,
        resource_name=resource_name,
        column_name=column_name,
        concept_ref=concept_ref,
        value_mappings=value_mappings,
        save_to_path=save_to_path,
    )

def explain_categories(
    datapackage_path_or_dict: Union[str, Path, Dict[str, Any]],
    output_concepts_dir: Union[str, Path],
) -> List[KnowledgeConceptDoc]:
    """Generate OKF v0.2 SKOS concept markdown files (concepts/*.md) for categorical fields."""
    return _runtime.explain_categories(
        datapackage_path_or_dict=datapackage_path_or_dict,
        output_concepts_dir=output_concepts_dir,
    )

storage = _runtime.storage
s3 = _runtime.s3
config = _runtime.config_adapter

from datamesh.aliases import to_df, datasets_a_df, organizaciones_a_df, recursos_a_df
from datamesh.adapters.storage.s3_storage import S3StorageAdapter
from datamesh.adapters.resolvers.s3 import S3Adapter
from datamesh.adapters.publishers.ckan_publisher import CKANPublisherAdapter

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
    LineageSource,
    LineageTransformation,
    LineageInfo,
    LineageNode,
    LineageEdge,
    LineageGraph,
    CatalogPatternRule,
)
from datamesh.domain.errors import (
    DataMeshError,
    AuthenticationRequiredError,
    InvalidContentTypeError,
    CatalogConnectionError,
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
from datamesh.usecases.dataset_lineage import DatasetLineageUseCase
from datamesh.server import run_server

__all__ = [
    "__version__",
    "discover",
    "discover_endpoint",
    "search",
    "get",
    "query",
    "sql",
    "resolve_resource",
    "get_engine",
    "validate",
    "publish",
    "align_semantics",
    "harvest_ckan",
    "lineage",
    "get_lineage",
    "create_datapackage",
    "link_concept",
    "explain_categories",
    "storage",
    "s3",
    "config",
    "to_df",
    "datasets_a_df",
    "organizaciones_a_df",
    "recursos_a_df",
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
    "LineageSource",
    "LineageTransformation",
    "LineageInfo",
    "LineageNode",
    "LineageEdge",
    "LineageGraph",
    "StoragePort",
    "ResourceAdapterPort",
    "ConfigPort",
    "QueryEnginePort",
    "PublisherPort",
    "AuthProviderPort",
    "WellKnownResolverPort",
    "CKANClientPort",
    "LocalStorageManager",
    "S3StorageAdapter",
    "FileConfigAdapter",
    "LocalFileAdapter",
    "S3Adapter",
    "GitHubAdapter",
    "KaggleAdapter",
    "HttpAdapter",
    "CKANPublisherAdapter",
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
    "DatasetLineageUseCase",
    "CatalogPatternRule",
    "DataMeshError",
    "AuthenticationRequiredError",
    "InvalidContentTypeError",
    "CatalogConnectionError",
]

