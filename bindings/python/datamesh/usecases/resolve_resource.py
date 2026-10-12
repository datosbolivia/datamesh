from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from datamesh.adapters.workspace.local_workspace import LocalWorkspaceResolver
from datamesh.domain.models import ResolvedResource, ResourceDescriptor, CanonicalURI
from datamesh.ports.resolver import ResourceAdapterPort
from datamesh.ports.storage import StoragePort

def slugify(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]+', '_', text).lower().strip('_')

class ResolveAndCacheResourceUseCase:
    """
    Application use case orchestrating resource resolution and temporal cache download.
    Decoupled from transport, storage technology, and DuckDB execution.

    Datapackage manifest lookup is delegated to the shared ``LocalWorkspaceResolver``
    so caching, workspace search and catalog fallback have a single implementation.
    """

    def __init__(
        self,
        storage: StoragePort,
        resolvers: List[ResourceAdapterPort],
        catalog_discovery_fn: Optional[Any] = None,
        workspace_resolver: Optional[LocalWorkspaceResolver] = None,
    ):
        self.storage = storage
        self.resolvers = resolvers
        self.catalog_discovery_fn = catalog_discovery_fn
        self._workspace = workspace_resolver or LocalWorkspaceResolver(
            catalog_discovery_fn=catalog_discovery_fn or (lambda: {"entries": []})
        )

    def resolve(self, table_ref: str, context: Optional[Dict[str, Any]] = None) -> Optional[ResolvedResource]:
        """
        Main entry point for resolving any table reference, triad ('ds:res', 'cat:ds:res'),
        datamesh:// URI, URL, or local file path into a local physical file ready for DuckDB.
        """
        ctx = dict(context or {})

        # 1. Parse canonical URI or triad if present
        dataset = ctx.get("dataset", "")
        resource = ctx.get("resource", "")
        parsed_uri = CanonicalURI.parse(table_ref)
        if parsed_uri:
            dataset = parsed_uri.dataset
            resource = parsed_uri.resource
            ctx["dataset"] = dataset
            ctx["resource"] = resource
            if parsed_uri.catalog:
                ctx["catalog"] = parsed_uri.catalog
        elif not dataset and not resource:
            # Maybe slug or direct file
            if not os.path.exists(table_ref):
                parts = table_ref.split("_")
                dataset = parts[0]
                resource = table_ref
                ctx["dataset"] = dataset
                ctx["resource"] = resource

        # 2. Check if already cached in temporal storage
        if self.storage.is_cached(table_ref):
            cached_p = self.storage.get_cached_path(table_ref)
            if cached_p and cached_p.exists():
                meta = self.storage.get_metadata(table_ref)
                fmt = cached_p.suffix.lstrip(".").lower() or "csv"
                return ResolvedResource(
                    descriptor=ResourceDescriptor(
                        raw_reference=table_ref,
                        dataset=dataset or None,
                        resource=resource or None,
                        format=fmt,
                        source_service=meta.source_service if meta else "cache",
                    ),
                    local_path=cached_p,
                    format=fmt,
                    is_cached=True,
                    metadata=meta,
                )

        # 2. Check if table_ref maps to a datapackage manifest resource
        physical_target: Optional[str] = None
        if dataset and resource:
            physical_target = self._workspace.resolve_triad_to_path(table_ref, dataset, resource)
            if "update_frequency" not in ctx and dataset:
                ctx["update_frequency"] = self._workspace.node_update_frequency(dataset)

        target_uri = physical_target or table_ref

        # 3. Match against registered adapters
        for adapter in self.resolvers:
            if adapter.can_handle(target_uri, ctx):
                try:
                    res = adapter.resolve_and_fetch(target_uri, self.storage, ctx)
                    if res:
                        return res
                except Exception:
                    continue

        # 4. Fallback search: try direct adapters on table_ref
        for adapter in self.resolvers:
            if adapter.can_handle(table_ref, ctx):
                try:
                    res = adapter.resolve_and_fetch(table_ref, self.storage, ctx)
                    if res:
                        return res
                except Exception:
                    continue

        return None
