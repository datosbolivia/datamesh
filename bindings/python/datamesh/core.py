from __future__ import annotations

import csv
import io
import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from datamesh.duckdb_engine import DuckDBQueryEngine

class DataMeshRuntime:
    """Python runtime providing local fallback, ctypes bridge to Go core, and DuckDB SQL engine."""

    def __init__(self, lib_path: Optional[str] = None):
        self._lib = None
        self._duckdb_engine = DuckDBQueryEngine(catalog_resolver=self._resolve_triad_to_path)
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
                self._lib.DataMeshFreeString.argtypes = [ctypes.c_char_p]
                self._lib.DataMeshFreeString.restype = None
                self._lib.DataMeshInit(None)
            except Exception:
                self._lib = None

    def get_catalog_urls(self) -> List[str]:
        env_catalogs = os.environ.get("DATAMESH_CATALOGS") or os.environ.get("DATAMESH_CATALOG_URLS")
        if env_catalogs:
            return [c.strip() for c in env_catalogs.split(",") if c.strip()]
        single = os.environ.get("DATAMESH_CATALOG_URL")
        if single:
            return [single]
        return ["https://datosbolivia.github.io/llms.txt"]

    def discover(self, catalog_url: Optional[str] = None) -> Dict[str, Any]:
        """Discovers a specific catalog or aggregates all configured catalogs."""
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
        with urllib.request.urlopen(req) as resp:
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
        """Resolves node index.md and returns DataProduct metadata."""
        if uri.startswith("file://"):
            with open(uri[7:], "r", encoding="utf-8") as f:
                content = f.read()
        elif uri.startswith("http://") or uri.startswith("https://"):
            req = urllib.request.Request(uri, headers={"User-Agent": "datamesh-sdk/0.2 (Python)"})
            with urllib.request.urlopen(req) as resp:
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
        """Queries CSV or tabular resource."""
        if resource_uri.startswith("file://"):
            with open(resource_uri[7:], "r", encoding="utf-8") as f:
                raw_text = f.read()
        elif resource_uri.startswith("http://") or resource_uri.startswith("https://"):
            req = urllib.request.Request(resource_uri, headers={"User-Agent": "datamesh-sdk/0.2 (Python)"})
            with urllib.request.urlopen(req) as resp:
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

    def sql(self, sql_query: str, table_mapping: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Executes full ANSI/DuckDB SQL with canonical triad table names 'catalogo:dataset:resource'."""
        return self._duckdb_engine.execute_sql(sql_query, table_mapping=table_mapping)

    def _resolve_triad_to_path(self, table_ref: str, *args) -> Optional[str]:
        """Resolves table reference ('cat:ds:res', 'ds:res', or slug) to concrete physical file or URL."""
        if args:
            dataset = args[0] if len(args) > 0 else ""
            resource = args[1] if len(args) > 1 else ""
        elif ":" in table_ref:
            parts = table_ref.split(":")
            dataset = parts[-2]
            resource = parts[-1]
        else:
            dataset = table_ref.split("_")[0]
            resource = table_ref
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

        # 2. Search catalog entries for dataset
        try:
            cat = self.discover()
            for entry in cat.get("entries", []):
                uri = entry.get("uri", "")
                title = entry.get("title", "").lower()
                if dataset.lower() in uri.lower() or dataset.lower() in title:
                    # In real catalog, resource would be inside dataset manifest contracts
                    # Fallback to resolved url base + resource name
                    base = entry.get("resolved_url", "").rsplit("/", 1)[0]
                    return f"{base}/{resource}.csv"
        except Exception:
            pass

        return None
