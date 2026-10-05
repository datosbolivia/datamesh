from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
import urllib.request
try:
    import yaml
except ImportError:
    yaml = None

from datamesh.domain.models import ResolvedResource, ResourceDescriptor, CanonicalURI
from datamesh.ports.resolver import ResourceAdapterPort
from datamesh.ports.storage import StoragePort

def slugify(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]+', '_', text).lower().strip('_')

class ResolveAndCacheResourceUseCase:
    """
    Application use case orchestrating resource resolution and temporal cache download.
    Decoupled from transport, storage technology, and DuckDB execution.
    """

    def __init__(
        self,
        storage: StoragePort,
        resolvers: List[ResourceAdapterPort],
        catalog_discovery_fn: Optional[Any] = None,
    ):
        self.storage = storage
        self.resolvers = resolvers
        self.catalog_discovery_fn = catalog_discovery_fn

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
            pkg_res = self._lookup_datapackage_resource(dataset, resource)
            if pkg_res:
                physical_target = pkg_res

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

    def _find_node_datapackage(self, dataset: str) -> Optional[Tuple[Dict[str, Any], Optional[str]]]:
        clean_ds = dataset.strip()
        candidates = []
        for env_k in ["DATAMESH_KNOWLEDGE_DIR", "DATAMESH_NODES_DIR", "DATAMESH_CATALOG_DIR"]:
            env_val = os.environ.get(env_k)
            if env_val:
                candidates.append(os.path.join(env_val, clean_ds))
                candidates.append(os.path.join(env_val, "nodes", clean_ds))

        from datamesh.constants import get_workspace_search_dirs
        candidates.extend([
            f"knowledge/nodes/{clean_ds}",
            f"../catalogo-datamesh/knowledge/nodes/{clean_ds}",
            f"../../catalogo-datamesh/knowledge/nodes/{clean_ds}",
            str(self.storage.config.home_dir / "knowledge" / "nodes" / clean_ds),
            str(self.storage.config.cache_dir / "nodes" / clean_ds),
        ])
        for ws in get_workspace_search_dirs():
            candidates.append(str(ws / "catalogo-datamesh" / "knowledge" / "nodes" / clean_ds))
            candidates.append(str(ws / "knowledge" / "nodes" / clean_ds))

        for c in candidates:
            if os.path.isdir(c):
                for fname in ["datapackage.yaml", "datapackage.yml", "datapackage.json"]:
                    full_p = os.path.join(c, fname)
                    if os.path.exists(full_p):
                        try:
                            with open(full_p, "r", encoding="utf-8") as f:
                                if full_p.endswith((".yaml", ".yml")) and yaml:
                                    return yaml.safe_load(f), os.path.dirname(full_p)
                                elif full_p.endswith(".json"):
                                    return json.load(f), os.path.dirname(full_p)
                        except Exception:
                            continue

        # Remote check via catalog discovery
        if self.catalog_discovery_fn:
            try:
                cat = self.catalog_discovery_fn()
                for entry in cat.get("entries", []):
                    uri = entry.get("uri", "")
                    resolved_url = entry.get("resolved_url", "")
                    if clean_ds.lower() in uri.lower() or (resolved_url and clean_ds.lower() in resolved_url.lower()):
                        base_url = resolved_url.rsplit("/", 1)[0]
                        for fname in ["datapackage.yaml", "datapackage.yml", "datapackage.json"]:
                            m_url = f"{base_url}/{fname}"
                            try:
                                req = urllib.request.Request(m_url, headers={"User-Agent": "datamesh-sdk/0.2 (Python)"})
                                with urllib.request.urlopen(req, timeout=3) as resp:
                                    content = resp.read().decode("utf-8")
                                    if fname.endswith((".yaml", ".yml")) and yaml:
                                        return yaml.safe_load(content), base_url
                                    elif fname.endswith(".json"):
                                        return json.loads(content), base_url
                            except Exception:
                                continue
            except Exception:
                pass

        return None

    def _lookup_datapackage_resource(self, dataset: str, resource: str) -> Optional[str]:
        pkg_data = self._find_node_datapackage(dataset)
        if not pkg_data:
            return None

        manifest, base_loc = pkg_data
        res_slug = slugify(resource)

        def _search_res(r_list: List[Dict[str, Any]], parent_zip: Optional[str] = None) -> Optional[str]:
            for r in r_list:
                is_zip = r.get("mediatype") == "zip" or r.get("format") == "zip" or str(r.get("path", "")).endswith(".zip")
                curr_zip = r.get("path") if is_zip else parent_zip

                r_name = str(r.get("name", ""))
                r_title = str(r.get("title", ""))
                r_path = str(r.get("path", ""))
                if (
                    r_name == resource
                    or r_name.lower() == resource.lower()
                    or slugify(r_name) == res_slug
                    or (res_slug and res_slug in slugify(r_name))
                    or (r_title and (r_title == resource or slugify(r_title) == res_slug or (res_slug and res_slug in slugify(r_title))))
                ):
                    target_path = r_path or curr_zip
                    if not target_path:
                        continue
                    if target_path.startswith(("http://", "https://", "ftp://")):
                        return target_path
                    else:
                        if base_loc and not base_loc.startswith(("http://", "https://")):
                            candidate = os.path.normpath(os.path.join(base_loc, target_path))
                            if os.path.exists(candidate):
                                return os.path.abspath(candidate)
                        if os.path.exists(target_path):
                            return os.path.abspath(target_path)
                        if curr_zip:
                            return curr_zip

                nested = r.get("resources", [])
                if isinstance(nested, list) and nested:
                    found = _search_res(nested, parent_zip=curr_zip)
                    if found:
                        return found
            return None

        return _search_res(manifest.get("resources", []))
