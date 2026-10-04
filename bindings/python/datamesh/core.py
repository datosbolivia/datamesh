from __future__ import annotations

import csv
import glob
import io
import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
try:
    import yaml
except ImportError:
    yaml = None
from datamesh.constants import DEFAULT_CACHE_DIR, DEFAULT_DATAMESH_HOME, get_workspace_search_dirs
from datamesh.domain.models import StorageConfig, CanonicalURI
from datamesh.ports.storage import StoragePort
from datamesh.ports.resolver import ConfigPort, ResourceAdapterPort
from datamesh.ports.engine import QueryEnginePort
from datamesh.adapters.storage.local_storage import LocalStorageManager
from datamesh.adapters.config.file_config import FileConfigAdapter
from datamesh.adapters.resolvers.local_file import LocalFileAdapter
from datamesh.adapters.resolvers.github import GitHubAdapter
from datamesh.adapters.resolvers.kaggle import KaggleAdapter
from datamesh.adapters.resolvers.http import HttpAdapter
from datamesh.adapters.engine.duckdb_engine import DuckDBQueryEngine, slugify
from datamesh.adapters.engine.inmem_engine import InMemTabularQueryEngine
from datamesh.adapters.engine.go_engine import GoCoreQueryEngine
from datamesh.usecases.resolve_resource import ResolveAndCacheResourceUseCase

def _safe_urlopen(req: Any, timeout: int = 2) -> Any:
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except TypeError:
        return urllib.request.urlopen(req)

class DataMeshRuntime:
    """Python runtime providing local fallback, ctypes bridge to Go core, and abstract SQL engines."""

    def __init__(self, lib_path: Optional[str] = None):
        self._lib = None
        self._storage = LocalStorageManager(StorageConfig.default())
        self._config_adapter = FileConfigAdapter(self._storage.config.config_file)
        self._resolvers: List[ResourceAdapterPort] = [
            LocalFileAdapter(),
            GitHubAdapter(),
            KaggleAdapter(),
            HttpAdapter(),
        ]
        self._resolver_usecase = ResolveAndCacheResourceUseCase(
            storage=self._storage,
            resolvers=self._resolvers,
            catalog_discovery_fn=self.discover,
        )

        target_path = lib_path or os.environ.get("DATAMESH_LIB_PATH", "libdatamesh.so")
        if os.path.exists(target_path):
            try:
                import ctypes
                self._lib = ctypes.CDLL(target_path)
                self._lib.DataMeshInit.argtypes = [ctypes.c_char_p]
                self._lib.DataMeshInit.restype = ctypes.c_char_p
                self._lib.DataMeshDiscoverCatalog.argtypes = [ctypes.c_char_p]
                self._lib.DataMeshDiscoverCatalog.restype = ctypes.c_char_p
                self._lib.DataMeshResolveDataProduct.argtypes = [ctypes.c_char_p]
                self._lib.DataMeshResolveDataProduct.restype = ctypes.c_char_p
                if hasattr(self._lib, "DataMeshSearchCatalog"):
                    self._lib.DataMeshSearchCatalog.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
                    self._lib.DataMeshSearchCatalog.restype = ctypes.c_char_p
                if hasattr(self._lib, "DataMeshQueryResource"):
                    self._lib.DataMeshQueryResource.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
                    self._lib.DataMeshQueryResource.restype = ctypes.c_char_p
                if hasattr(self._lib, "DataMeshExecuteSQL"):
                    self._lib.DataMeshExecuteSQL.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
                    self._lib.DataMeshExecuteSQL.restype = ctypes.c_char_p
                if hasattr(self._lib, "DataMeshValidate"):
                    self._lib.DataMeshValidate.argtypes = [ctypes.c_char_p]
                    self._lib.DataMeshValidate.restype = ctypes.c_char_p
                self._lib.DataMeshFreeString.argtypes = [ctypes.c_char_p]
                self._lib.DataMeshFreeString.restype = None
                self._lib.DataMeshInit(None)
            except Exception:
                self._lib = None

        self._duckdb_engine = DuckDBQueryEngine(
            catalog_resolver=self._resolve_triad_to_path,
            resolver_usecase=self._resolver_usecase,
            storage=self._storage,
        )
        self._inmem_engine = InMemTabularQueryEngine(
            catalog_resolver=self._resolve_triad_to_path,
            resolver_usecase=self._resolver_usecase,
        )
        self._go_engine = GoCoreQueryEngine(lib_handle=self._lib)

        self._engines: Dict[str, QueryEnginePort] = {
            "duckdb": self._duckdb_engine,
            "inmem": self._inmem_engine,
            "go": self._go_engine,
        }

    @property
    def storage(self) -> StoragePort:
        """Temporal and persistent storage manager for ~/datamesh/cache."""
        return self._storage

    @property
    def config_adapter(self) -> ConfigPort:
        """Configuration manager for ~/datamesh/config.yaml."""
        return self._config_adapter

    @property
    def resolver_usecase(self) -> ResolveAndCacheResourceUseCase:
        """Resource resolution and caching orchestration use case."""
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

    def get_engine(self, engine_name: Optional[str] = None) -> QueryEnginePort:
        """Retrieves a configured query engine by name ('duckdb', 'inmem', 'go')."""
        if not engine_name or engine_name.lower() in ("auto", "default"):
            return self._duckdb_engine
        key = engine_name.lower().strip()
        if key not in self._engines:
            raise ValueError(f"Unknown query engine '{engine_name}'. Available: {list(self._engines.keys())}")
        return self._engines[key]

    def register_engine(self, engine: QueryEnginePort) -> None:
        """Registers a custom or specialized query engine."""
        self._engines[engine.name.lower()] = engine

    def get_catalog_urls(self) -> List[str]:
        env_catalogs = os.environ.get("DATAMESH_CATALOGS") or os.environ.get("DATAMESH_CATALOG_URLS")
        if env_catalogs:
            return [c.strip() for c in env_catalogs.split(",") if c.strip()]
        single = os.environ.get("DATAMESH_CATALOG_URL")
        if single:
            return [single]
        return ["https://datosbolivia.github.io/llms.txt"]

    def discover(self, catalog_url: Optional[str] = None) -> Dict[str, Any]:
        """Discovers a specific catalog or aggregates all configured catalogs via Go core or fallback."""
        if self._lib and hasattr(self._lib, "DataMeshDiscoverCatalog"):
            try:
                import ctypes
                c_url = catalog_url.encode("utf-8") if catalog_url else None
                raw = self._lib.DataMeshDiscoverCatalog(c_url)
                if raw:
                    try:
                        resp = json.loads(ctypes.string_at(raw).decode("utf-8"))
                        if resp.get("success") and resp.get("data"):
                            return resp["data"]
                    finally:
                        if hasattr(self._lib, "DataMeshFreeString"):
                            self._lib.DataMeshFreeString(raw)
            except Exception:
                pass

        if catalog_url:
            urls = [catalog_url]
        else:
            urls = self.get_catalog_urls()

        if len(urls) == 1:
            return self._fetch_single_catalog(urls[0])

        # Aggregate multiple catalogs
        combined_entries = []
        source_catalogs = []
        seen = set()

        for u in urls:
            try:
                cat = self._fetch_single_catalog(u)
                source_catalogs.append(u)
                for entry in cat.get("entries", []):
                    entry["catalog_source"] = u
                    key = entry.get("resolved_url") or entry.get("title")
                    if key not in seen:
                        seen.add(key)
                        combined_entries.append(entry)
            except Exception as err:
                continue

        return {
            "title": "DataMesh Federated Catalog",
            "source_catalogs": source_catalogs,
            "entries": combined_entries,
        }

    def _fetch_single_catalog(self, url: str) -> Dict[str, Any]:
        if url.startswith("file://"):
            with open(url[7:], "r", encoding="utf-8") as f:
                content = f.read()
            return self._parse_llms_txt(content, url)

        req = urllib.request.Request(url, headers={"User-Agent": "datamesh-sdk/0.2 (Python)"})
        with _safe_urlopen(req, timeout=2) as resp:
            content = resp.read().decode("utf-8")
        return self._parse_llms_txt(content, url)

    def _parse_llms_txt(self, content: str, source_url: str) -> Dict[str, Any]:
        entries = []
        entry_pattern = re.compile(r"^-\s*\[(.*?)\]\((.*?)\)(?::\s*(.*))?$")
        domain_pattern = re.compile(r"\(Dominio:\s*([^)]*?)(?:\.|\)|Recursos:)")
        rec_pattern = re.compile(r"Recursos:\s*([^)]+)\)")
        
        title = ""
        description = ""

        for line in content.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith("# ") and not title:
                title = line_str[2:].strip()
                continue
            if line_str.startswith("> ") and not description:
                description = line_str[2:].strip()
                continue

            m = entry_pattern.match(line_str)
            if m:
                item_title, raw_uri, desc = m.group(1), m.group(2), m.group(3) or ""
                resolved = urllib.parse.urljoin(source_url, raw_uri)
                dm = domain_pattern.search(desc)
                domain = dm.group(1).strip() if dm else ""
                
                rm = rec_pattern.search(desc)
                recs = [r.strip() for r in rm.group(1).split(",")] if rm else []
                clean_desc = desc.split("(Dominio:")[0].strip()
                
                entries.append({
                    "title": item_title,
                    "uri": raw_uri,
                    "resolved_url": resolved,
                    "description": clean_desc,
                    "domain": domain,
                    "resources": recs,
                    "catalog_source": source_url,
                })

        return {
            "title": title or "Sovereign Catalog",
            "description": description,
            "source_url": source_url,
            "entries": entries,
        }

    def resolve(self, uri: str) -> Dict[str, Any]:
        """Resolves node index.md and returns DataProduct metadata via Go core or fallback."""
        if self._lib and hasattr(self._lib, "DataMeshResolveDataProduct"):
            try:
                import ctypes
                c_uri = uri.encode("utf-8")
                raw = self._lib.DataMeshResolveDataProduct(c_uri)
                if raw:
                    try:
                        resp = json.loads(ctypes.string_at(raw).decode("utf-8"))
                        if resp.get("success") and resp.get("data"):
                            return resp["data"]
                    finally:
                        if hasattr(self._lib, "DataMeshFreeString"):
                            self._lib.DataMeshFreeString(raw)
            except Exception:
                pass

        if uri.startswith("file://"):
            with open(uri[7:], "r", encoding="utf-8") as f:
                content = f.read()
        elif uri.startswith("http://") or uri.startswith("https://"):
            req = urllib.request.Request(uri, headers={"User-Agent": "datamesh-sdk/0.2 (Python)"})
            with _safe_urlopen(req, timeout=2) as resp:
                content = resp.read().decode("utf-8")
        else:
            with open(uri, "r", encoding="utf-8") as f:
                content = f.read()

        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError("No YAML frontmatter found in node markdown")

        frontmatter = parts[1]
        body = parts[2].strip()

        manifest: Dict[str, Any] = {"dimensions": [], "contracts": []}
        for line in frontmatter.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            if line_str.startswith("title:"):
                manifest["title"] = line_str.split(":", 1)[1].strip().strip("\"'")
            elif line_str.startswith("type:"):
                manifest["type"] = line_str.split(":", 1)[1].strip().strip("\"'")
            elif line_str.startswith("- ") and "dimensions" in manifest:
                manifest["dimensions"].append(line_str[2:].strip().strip("\"'"))

        return {
            "id": uri,
            "manifest": manifest,
            "description": body,
        }

    def query(
        self,
        resource_uri: str,
        filters: Optional[Dict[str, str]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Queries CSV or tabular resource via Go core or fallback."""
        if self._lib and hasattr(self._lib, "DataMeshQueryResource"):
            try:
                import ctypes
                c_uri = resource_uri.encode("utf-8")
                opts = {}
                if filters:
                    opts["filters"] = filters
                if limit:
                    opts["limit"] = limit
                c_opts = json.dumps(opts).encode("utf-8")
                raw = self._lib.DataMeshQueryResource(c_uri, c_opts)
                if raw:
                    try:
                        resp = json.loads(ctypes.string_at(raw).decode("utf-8"))
                        if resp.get("success") and resp.get("data"):
                            return resp["data"]
                    finally:
                        if hasattr(self._lib, "DataMeshFreeString"):
                            self._lib.DataMeshFreeString(raw)
            except Exception:
                pass

        if resource_uri.startswith("file://"):
            with open(resource_uri[7:], "r", encoding="utf-8") as f:
                raw_text = f.read()
        elif resource_uri.startswith("http://") or resource_uri.startswith("https://"):
            req = urllib.request.Request(resource_uri, headers={"User-Agent": "datamesh-sdk/0.2 (Python)"})
            with _safe_urlopen(req, timeout=2) as resp:
                raw_text = resp.read().decode("utf-8")
        else:
            with open(resource_uri, "r", encoding="utf-8") as f:
                raw_text = f.read()

        reader = csv.reader(io.StringIO(raw_text))
        headers = next(reader, None)
        if not headers:
            return {"columns": [], "rows": [], "row_count": 0}

        headers_norm = [h.strip().lower() for h in headers]
        filter_indices = {}
        if filters:
            for k, v in filters.items():
                kn = k.strip().lower()
                if kn in headers_norm:
                    filter_indices[headers_norm.index(kn)] = str(v).strip().lower()

        matched_rows = []
        for row in reader:
            matches = True
            for idx, exp_val in filter_indices.items():
                if idx >= len(row) or row[idx].strip().lower() != exp_val:
                    matches = False
                    break
            if matches:
                matched_rows.append(row)
                if limit and len(matched_rows) >= limit:
                    break

        return {
            "columns": headers,
            "rows": matched_rows,
            "row_count": len(matched_rows),
        }

    def sql(
        self,
        sql_query: str,
        table_mapping: Optional[Dict[str, str]] = None,
        engine: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes full ANSI SQL with canonical triad table names 'catalogo:dataset:resource'
        using the selected query engine (default: DuckDB, or 'inmem', 'go').
        """
        query_engine = self.get_engine(engine)
        return query_engine.execute_sql(sql_query, table_mapping=table_mapping)

    def validate(self, target: str) -> Dict[str, Any]:
        """Validates an OKF/ODKF concept document, bundle directory, or canonical triad."""
        if self._lib and hasattr(self._lib, "DataMeshValidate"):
            try:
                import ctypes
                c_target = target.encode("utf-8")
                raw = self._lib.DataMeshValidate(c_target)
                if raw:
                    try:
                        resp = json.loads(ctypes.string_at(raw).decode("utf-8"))
                        if resp.get("success") and resp.get("data"):
                            return resp["data"]
                    finally:
                        if hasattr(self._lib, "DataMeshFreeString"):
                            self._lib.DataMeshFreeString(raw)
            except Exception:
                pass

        # Python fallback validator
        try:
            from reference_agent.bundle.validator import validate_concept_content, validate_bundle, validate_triad
            if os.path.isdir(target):
                return validate_bundle(target).to_dict()
            elif os.path.isfile(target):
                with open(target, "r", encoding="utf-8") as f:
                    return validate_concept_content(f.read(), file_path=target).to_dict()
            elif ":" in target or "/" in target:
                return validate_triad(target).to_dict()
        except ImportError:
            pass

        clean = target.strip().strip("\"'")
        is_triad = bool(re.match(r"^[a-zA-Z0-9_\-\.]+[:/][a-zA-Z0-9_\-\. ]+([:/][a-zA-Z0-9_\-\. ]+)?$", clean))
        valid = is_triad or os.path.exists(target)
        return {
            "valid": valid,
            "target": target,
            "total_errors": 0 if valid else 1,
            "total_warnings": 0,
            "issues": [] if valid else [{"code": "VALIDATION-FAILED", "severity": "ERROR", "message": f"Could not validate target '{target}'"}],
        }

    def _find_matching_local_file(self, dataset: str, filename: str) -> Optional[str]:
        """Finds existing local copy of a dataset file in cache or sibling projects."""
        names_to_try = [filename]
        stem, ext = os.path.splitext(filename)
        if ext.lower() == ".csv":
            names_to_try.insert(0, f"{stem}.parquet")
        elif ext.lower() == ".parquet":
            names_to_try.append(f"{stem}.csv")

        # 1. Cache
        if os.path.exists(DEFAULT_CACHE_DIR):
            for n in names_to_try:
                cp = os.path.join(DEFAULT_CACHE_DIR, n)
                if os.path.exists(cp):
                    return os.path.abspath(cp)

    def _find_node_datapackage(self, dataset: str) -> Optional[Tuple[Dict[str, Any], Optional[str]]]:
        """Finds and parses datapackage manifest locally or from remote catalog."""
        clean_ds = dataset.strip()
        candidates = []
        for env_k in ["DATAMESH_KNOWLEDGE_DIR", "DATAMESH_NODES_DIR", "DATAMESH_CATALOG_DIR"]:
            env_val = os.environ.get(env_k)
            if env_val:
                candidates.append(os.path.join(env_val, clean_ds))
                candidates.append(os.path.join(env_val, "nodes", clean_ds))

        candidates.extend([
            f"knowledge/nodes/{clean_ds}",
            f"../catalogo-datamesh/knowledge/nodes/{clean_ds}",
            f"../../catalogo-datamesh/knowledge/nodes/{clean_ds}",
            str(DEFAULT_DATAMESH_HOME / "knowledge" / "nodes" / clean_ds),
            str(DEFAULT_CACHE_DIR / "nodes" / clean_ds),
        ])
        for ws in get_workspace_search_dirs():
            candidates.append(str(ws / "catalogo-datamesh" / "knowledge" / "nodes" / clean_ds))
            candidates.append(str(ws / "knowledge" / "nodes" / clean_ds))
            candidates.append(str(ws / clean_ds))
            candidates.append(str(ws / clean_ds / "knowledge"))

        # 1. Local check
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

        # 2. Remote check via catalog discovery
        try:
            cat = self.discover()
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

    def _resolve_triad_to_path(self, table_ref: str, *args) -> Optional[str]:
        # 1. Direct file path
        if os.path.exists(table_ref):
            return os.path.abspath(table_ref)

        parsed_uri = CanonicalURI.parse(table_ref)
        if args:
            dataset = args[0] if len(args) > 0 else ""
            resource = args[1] if len(args) > 1 else ""
        elif parsed_uri:
            dataset = parsed_uri.dataset
            resource = parsed_uri.resource
        elif ":" in table_ref:
            parts = table_ref.split(":")
            dataset = parts[-2]
            resource = parts[-1]
        elif "/" in table_ref:
            parts = [p.strip() for p in table_ref.split("/") if p.strip()]
            dataset = parts[-2]
            resource = parts[-1]
        else:
            dataset = table_ref.split("_")[0]
            resource = table_ref

        # 2. Datapackage manifest lookup
        pkg_data = self._find_node_datapackage(dataset)
        if pkg_data:
            manifest, base_loc = pkg_data
            res_slug = slugify(resource)
            for r in manifest.get("resources", []):
                r_name = str(r.get("name", ""))
                if (
                    r_name == resource
                    or r_name.lower() == resource.lower()
                    or slugify(r_name) == res_slug
                    or (res_slug and res_slug in slugify(r_name))
                ):
                    target_path = r.get("path")
                    if not target_path:
                        continue
                    if target_path.startswith(("http://", "https://", "ftp://")):
                        # Check local copy first for performance & offline resilience
                        base_fname = os.path.basename(urllib.parse.urlparse(target_path).path)
                        local_match = self._find_matching_local_file(dataset, base_fname)
                        if local_match:
                            return local_match

                        # Normalize GitHub URLs to avoid redirects
                        if "github.com/" in target_path and "/raw/" in target_path:
                            target_path = re.sub(r'https?://github\.com/([^/]+)/([^/]+)/raw/(.+)', r'https://raw.githubusercontent.com/\1/\2/\3', target_path)
                        elif "github.com/" in target_path and "/blob/" in target_path:
                            target_path = re.sub(r'https?://github\.com/([^/]+)/([^/]+)/blob/(.+)', r'https://raw.githubusercontent.com/\1/\2/\3', target_path)
                        return target_path
                    else:
                        if base_loc and base_loc.startswith(("http://", "https://")):
                            # Remote node with relative path (e.g. ../data_abastecimiento/*.csv)
                            base_url_dir = base_loc if base_loc.endswith("/") else f"{base_loc}/"
                            return urllib.parse.urljoin(base_url_dir, target_path)
                        elif base_loc and not base_loc.startswith(("http://", "https://")):
                            candidate = os.path.normpath(os.path.join(base_loc, target_path))
                            if os.path.exists(candidate):
                                return os.path.abspath(candidate)
                            if "*" in candidate and glob.glob(candidate):
                                return os.path.abspath(candidate)
                        if os.path.exists(target_path):
                            return os.path.abspath(target_path)
                        if "*" in target_path and glob.glob(target_path):
                            return os.path.abspath(target_path)

        # 3. Testdata and mock fallback
        possible_paths = [
            f"core-go/testdata/{resource}.csv",
            f"core-go/testdata/{resource}.parquet",
            f"core-go/testdata/{resource}.json",
            f"core-go/testdata/mock_data_{dataset}.csv",
            f"{resource}",
            f"{resource}.csv",
            f"{resource}.parquet",
        ]
        for p in possible_paths:
            if os.path.exists(p):
                return os.path.abspath(p)

        return None
