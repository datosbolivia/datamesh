from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from datamesh.adapters.catalog.llmstxt_catalog import LLMSTxtCatalogFetcher
from datamesh.adapters.go_bridge import GoCoreBridge
from datamesh.adapters.workspace.local_workspace import LocalWorkspaceResolver
from datamesh.adapters.auth import NoAuthAdapter, APIKeyAuthAdapter, BearerTokenAuthAdapter, KeycloakAuthAdapter
from datamesh.adapters.catalog.ckan_client import CKANClientAdapter
from datamesh.adapters.catalog.well_known import WellKnownResolverAdapter
from datamesh.adapters.config.file_config import FileConfigAdapter
from datamesh.adapters.engine.duckdb_engine import DuckDBQueryEngine
from datamesh.adapters.engine.go_engine import GoCoreQueryEngine
from datamesh.adapters.engine.inmem_engine import InMemTabularQueryEngine
from datamesh.adapters.publishers.kaggle_publisher import KagglePublisherAdapter
from datamesh.adapters.publishers.local_publisher import LocalBundlePublisherAdapter
from datamesh.adapters.publishers.portal_publisher import PortalPublisherAdapter
from datamesh.adapters.publishers.ckan_publisher import CKANPublisherAdapter
from datamesh.adapters.resolvers.github import GitHubAdapter
from datamesh.adapters.resolvers.http import HttpAdapter
from datamesh.adapters.resolvers.kaggle import KaggleAdapter
from datamesh.adapters.resolvers.local_file import LocalFileAdapter
from datamesh.adapters.resolvers.s3 import S3Adapter
from datamesh.adapters.storage.local_storage import LocalStorageManager
from datamesh.adapters.storage.s3_storage import S3StorageAdapter
from datamesh.domain.models import (
    StorageConfig,
    WellKnownDiscovery,
    CKANHarvestResult,
    KnowledgeConceptDoc,
    DataPackageBuildResult,
    LineageNode,
    LineageEdge,
    LineageGraph,
)
from datamesh.ports.resolver import ResourceAdapterPort
from datamesh.usecases.create_datapackage import CreateDataPackageUseCase
from datamesh.usecases.datapackage_io import load_datapackage, save_datapackage
from datamesh.usecases.dataset_lineage import DatasetLineageUseCase
from datamesh.usecases.discover_catalog import DiscoverCatalogUseCase
from datamesh.usecases.discover_well_known import DiscoverWellKnownUseCase
from datamesh.usecases.harvest_ckan import HarvestCKANUseCase
from datamesh.usecases.link_knowledge_concepts import LinkKnowledgeConceptsUseCase
from datamesh.usecases.publish_dataset import PublishDatasetUseCase
from datamesh.usecases.query_resource import QueryResourceUseCase
from datamesh.usecases.resolve_dataproduct import ResolveDataProductUseCase
from datamesh.usecases.resolve_resource import ResolveAndCacheResourceUseCase
from datamesh.usecases.semantic_alignment import SemanticAlignmentUseCase
from datamesh.usecases.validate_resource import ValidateResourceUseCase


class DataMeshRuntime:
    """Thin composition root wiring domain services, the Go core bridge and engines.

    The runtime holds no business logic of its own: each method delegates to a
    focused use case or adapter. Heavy lifting (ctypes, catalog parsing, workspace
    lookup, tabular fallbacks) lives in dedicated modules.
    """

    def __init__(self, lib_path: Optional[str] = None):
        self._storage = LocalStorageManager(StorageConfig.default())
        self._config_adapter = FileConfigAdapter(self._storage.config.config_file)
        self._s3_storage = S3StorageAdapter()
        self._resolvers: List[ResourceAdapterPort] = [
            LocalFileAdapter(),
            S3Adapter(s3_storage=self._s3_storage),
            GitHubAdapter(),
            KaggleAdapter(),
            HttpAdapter(config_adapter=self._config_adapter),
        ]

        self._bridge = GoCoreBridge(lib_path=lib_path)
        self._workspace = LocalWorkspaceResolver(catalog_discovery_fn=self.discover)
        self._catalog_fetcher = LLMSTxtCatalogFetcher()
        self._discover_catalog = DiscoverCatalogUseCase(
            bridge=self._bridge,
            fetcher=self._catalog_fetcher,
            urls_provider=self.get_catalog_urls,
        )

        self._resolver_usecase = ResolveAndCacheResourceUseCase(
            storage=self._storage,
            resolvers=self._resolvers,
            catalog_discovery_fn=self.discover,
            workspace_resolver=self._workspace,
        )

        self._duckdb_engine = DuckDBQueryEngine(
            catalog_resolver=self._workspace.resolve_triad_to_path,
            resolver_usecase=self._resolver_usecase,
            storage=self._storage,
            bridge=self._bridge,
        )
        self._inmem_engine = InMemTabularQueryEngine(
            catalog_resolver=self._workspace.resolve_triad_to_path,
            resolver_usecase=self._resolver_usecase,
        )
        self._go_engine = GoCoreQueryEngine(bridge=self._bridge)

        self._engines: Dict[str, Any] = {
            "duckdb": self._duckdb_engine,
            "inmem": self._inmem_engine,
            "go": self._go_engine,
        }

        self._query_resource = QueryResourceUseCase(bridge=self._bridge, resolver_usecase=self._resolver_usecase)
        self._validate_resource = ValidateResourceUseCase(bridge=self._bridge)
        self._resolve_dataproduct = ResolveDataProductUseCase(bridge=self._bridge)

        self._publishers = [
            LocalBundlePublisherAdapter(),
            PortalPublisherAdapter(),
            KagglePublisherAdapter(),
            CKANPublisherAdapter(),
        ]
        self._publish_usecase = PublishDatasetUseCase(publishers=self._publishers)
        self._semantic_aligner = SemanticAlignmentUseCase()

        self._well_known_resolver = WellKnownResolverAdapter()
        self._discover_usecase = DiscoverWellKnownUseCase(self._well_known_resolver)
        self._ckan_client = CKANClientAdapter()
        self._harvest_ckan_usecase = HarvestCKANUseCase(self._ckan_client)
        self._lineage_usecase = DatasetLineageUseCase(catalog_discovery_fn=self.discover)

    @property
    def lineage_usecase(self) -> DatasetLineageUseCase:
        """Dataset provenance, dependency extraction, and lineage DAG graph orchestration."""
        return self._lineage_usecase

    @property
    def storage(self) -> Any:
        """Temporal and persistent storage manager for ~/datamesh."""
        return self._storage

    @property
    def s3(self) -> S3StorageAdapter:
        """S3 and Aistor storage operations adapter."""
        return self._s3_storage

    @property
    def config_adapter(self) -> Any:
        """Configuration adapter for ~/datamesh/config.yaml."""
        return self._config_adapter

    @property
    def resolver_usecase(self) -> ResolveAndCacheResourceUseCase:
        """Resource resolution and caching use case."""
        return self._resolver_usecase

    @property
    def duckdb_engine(self) -> DuckDBQueryEngine:
        return self._duckdb_engine

    @property
    def inmem_engine(self) -> InMemTabularQueryEngine:
        return self._inmem_engine

    @property
    def go_engine(self) -> GoCoreQueryEngine:
        return self._go_engine

    def get_engine(self, engine_name: Optional[str] = None) -> Any:
        """Returns a configured query engine by name ('duckdb', 'inmem', 'go')."""
        if not engine_name or engine_name.lower() in ("auto", "default"):
            return self._duckdb_engine
        key = engine_name.lower().strip()
        if key not in self._engines:
            raise ValueError(f"Unknown query engine '{engine_name}'. Available: {list(self._engines.keys())}")
        return self._engines[key]

    def register_engine(self, engine: Any) -> None:
        """Registers a custom or specialized query engine."""
        self._engines[engine.name.lower()] = engine

    def get_catalog_urls(self) -> List[str]:
        env_catalogs = os.environ.get("DATAMESH_CATALOGS") or os.environ.get("DATAMESH_CATALOG_URLS")
        if env_catalogs:
            return [c.strip() for c in env_catalogs.split(",") if c.strip()]
        urls: List[str] = []
        ckan_url = os.environ.get("CKAN_URL") or os.environ.get("CKAN_BASE_URL")
        if ckan_url and ckan_url.strip():
            urls.append(ckan_url.strip())
        single = os.environ.get("DATAMESH_CATALOG_URL")
        if single and single.strip():
            urls.append(single.strip())
        if not urls:
            urls.append("https://datosbolivia.github.io/llms.txt")
        return urls

    def discover(self, catalog_url: Optional[str] = None) -> Dict[str, Any]:
        """Discovers a specific catalog or aggregates all configured catalogs."""
        return self._discover_catalog.execute(catalog_url)

    def resolve(self, uri: str) -> Dict[str, Any]:
        """Resolves a node document and returns DataProduct metadata."""
        return self._resolve_dataproduct.execute(uri)

    def query(
        self,
        resource_uri: str,
        filters: Optional[Dict[str, str]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Queries a CSV or tabular resource."""
        return self._query_resource.execute(resource_uri, filters=filters, limit=limit)

    def sql(
        self,
        query_str: str,
        table_mapping: Optional[Dict[str, str]] = None,
        engine: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executes full ANSI SQL over canonical triad table names."""
        return self.get_engine(engine).execute_sql(query_str, table_mapping=table_mapping)

    def validate(self, target: str) -> Dict[str, Any]:
        """Validates an OKF/ODKF concept, bundle directory, or canonical triad."""
        return self._validate_resource.execute(target)

    def publish(
        self,
        dataset_path: str,
        targets: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Publishes an ODKF dataset bundle to one or more platforms."""
        results = self._publish_usecase.execute(dataset_path, targets=targets, options=options)
        return [
            {
                "target": r.target,
                "success": r.success,
                "destination_uri": r.destination_uri,
                "message": r.message,
                "error": r.error,
            }
            for r in results
        ]

    def align_semantics(self, datapackage_or_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extracts semantic field mappings from a DataPackage or schema."""
        mappings = self._semantic_aligner.extract_mappings(datapackage_or_schema)
        return [m.to_dict() for m in mappings]

    def discover_endpoint(self, target_url: str) -> Optional[WellKnownDiscovery]:
        """Discovers catalog metadata and auth specs via /.well-known/datamesh.json."""
        return self._discover_usecase.execute(target_url)

    def harvest_ckan(
        self,
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
        """Harvests datasets from a CKAN catalog and reconstructs OKF v0.2 packages."""
        discovery = self.discover_endpoint(ckan_url)
        api_endpoint = discovery.catalog.api_endpoint if (discovery and discovery.catalog.api_endpoint) else ckan_url
        auth_provider = self._discover_usecase.create_auth_provider(
            discovery=discovery,
            token=token,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
        )
        return self._harvest_ckan_usecase.execute(
            base_url=api_endpoint,
            query=query,
            limit=limit,
            offset=offset,
            auth_provider=auth_provider,
            output_dir=output_dir,
            probe_datastore_schema=probe_datastore_schema,
            package_id=package_id,
        )

    def create_datapackage(
        self,
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
        """Creates an OKF/ODKF v0.2 datapackage.yaml manifest."""
        return CreateDataPackageUseCase.build_datapackage(
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
        self,
        target: Optional[str] = None,
        search_dirs: Optional[List[Union[str, Path]]] = None,
        catalog_url: Optional[str] = None,
    ) -> LineageGraph:
        """Builds or queries the DAG lineage graph of sovereign datasets (Go core first)."""
        go_graph = self._go_lineage_graph(search_dirs=search_dirs, catalog_url=catalog_url)
        if go_graph is not None:
            return go_graph
        return self._lineage_usecase.build_graph(search_dirs=search_dirs, catalog_url=catalog_url)

    def get_lineage(
        self,
        dataset_id_or_path: str,
        search_dirs: Optional[List[Union[str, Path]]] = None,
        catalog_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Gets upstream/downstream provenance for a specific dataset (Go core first)."""
        go_res = self._go_get_lineage(dataset_id_or_path, search_dirs=search_dirs, catalog_url=catalog_url)
        if go_res is not None:
            return go_res
        return self._lineage_usecase.get_lineage(
            dataset_id_or_path=dataset_id_or_path,
            search_dirs=search_dirs,
            catalog_url=catalog_url,
        )

    def _go_get_lineage(
        self,
        target: str,
        search_dirs: Optional[List[Union[str, Path]]] = None,
        catalog_url: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        opts = self._lineage_options(search_dirs, catalog_url)
        return self._bridge.call_with_options("DataMeshGetLineage", opts, target)

    def _go_lineage_graph(
        self,
        search_dirs: Optional[List[Union[str, Path]]] = None,
        catalog_url: Optional[str] = None,
    ) -> Optional[LineageGraph]:
        opts = self._lineage_options(search_dirs, catalog_url)
        data = self._bridge.call_with_options("DataMeshLineageGraph", opts)
        if not data:
            return None
        nodes = {
            k: LineageNode(id=n["id"], title=n["title"], type=n.get("type", "dataset"))
            for k, n in (data.get("nodes") or {}).items()
        }
        edges = tuple(
            LineageEdge(source=e["source"], target=e["target"], label=e.get("label"))
            for e in (data.get("edges") or [])
        )
        return LineageGraph(nodes=nodes, edges=edges)

    @staticmethod
    def _lineage_options(
        search_dirs: Optional[List[Union[str, Path]]],
        catalog_url: Optional[str],
    ) -> Dict[str, Any]:
        opts: Dict[str, Any] = {}
        if search_dirs:
            opts["search_dirs"] = [str(d) for d in search_dirs]
        if catalog_url:
            opts["catalog_url"] = catalog_url
        return opts

    def link_concept(
        self,
        datapackage_path_or_dict: Union[str, Path, Dict[str, Any]],
        resource_name: Union[str, int],
        column_name: str,
        concept_ref: Optional[str] = None,
        value_mappings: Optional[Dict[str, Union[str, Dict[str, str]]]] = None,
        save_to_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Links a column and/or its categorical values in a DataPackage to concepts."""
        pkg_data, source_path = load_datapackage(datapackage_path_or_dict)

        if concept_ref:
            pkg_data = LinkKnowledgeConceptsUseCase.link_column_concept(
                datapackage_data=pkg_data,
                resource_name_or_index=resource_name,
                column_name=column_name,
                concept_ref=concept_ref,
            )
        if value_mappings:
            pkg_data = LinkKnowledgeConceptsUseCase.link_categories(
                datapackage_data=pkg_data,
                resource_name_or_index=resource_name,
                column_name=column_name,
                value_mappings=value_mappings,
            )

        target_save = save_to_path or source_path
        if target_save:
            save_datapackage(pkg_data, Path(target_save))
        return pkg_data

    def explain_categories(
        self,
        datapackage_path_or_dict: Union[str, Path, Dict[str, Any]],
        output_concepts_dir: Union[str, Path],
    ) -> List[KnowledgeConceptDoc]:
        """Generates OKF v0.2 SKOS concept markdown files for categorical fields."""
        pkg_data, _ = load_datapackage(datapackage_path_or_dict)
        return LinkKnowledgeConceptsUseCase.generate_concepts_from_field_categories(
            datapackage_data=pkg_data,
            output_concepts_dir=output_concepts_dir,
        )
