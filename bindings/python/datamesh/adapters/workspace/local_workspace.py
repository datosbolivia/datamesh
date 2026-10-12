from __future__ import annotations

import glob
import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

from datamesh.constants import get_cache_dir, get_datamesh_home, get_workspace_search_dirs
from datamesh.domain.models import CanonicalURI

try:
    import yaml
except ImportError:
    yaml = None

_MANIFEST_NAMES = ["datapackage.yaml", "datapackage.yml", "datapackage.json"]


class LocalWorkspaceResolver:
    """Resolves canonical triads to concrete files using cache, sibling projects and the catalog.

    Pure local/remote *lookup* logic extracted from the runtime so engines and use cases
    share one implementation of triad→path resolution.
    """

    def __init__(self, catalog_discovery_fn: Callable[[], Dict[str, Any]]):
        self._discover = catalog_discovery_fn

    def find_matching_local_file(self, dataset: str, filename: str) -> Optional[str]:
        """Finds an existing local copy of a dataset file in the cache directory."""
        names_to_try = [filename]
        stem, ext = os.path.splitext(filename)
        if ext.lower() == ".csv":
            names_to_try.insert(0, f"{stem}.parquet")
        elif ext.lower() == ".parquet":
            names_to_try.append(f"{stem}.csv")

        cache_dir = get_cache_dir()
        if os.path.exists(cache_dir):
            for n in names_to_try:
                cp = os.path.join(cache_dir, n)
                if os.path.exists(cp):
                    return os.path.abspath(cp)
        return None

    def find_node_datapackage(self, dataset: str) -> Optional[Tuple[Dict[str, Any], Optional[str]]]:
        """Finds and parses a datapackage manifest locally or from the remote catalog."""
        clean_ds = dataset.strip()
        candidates: List[str] = []
        for env_k in ["DATAMESH_KNOWLEDGE_DIR", "DATAMESH_NODES_DIR", "DATAMESH_CATALOG_DIR"]:
            env_val = os.environ.get(env_k)
            if env_val:
                candidates.append(os.path.join(env_val, clean_ds))
                candidates.append(os.path.join(env_val, "nodes", clean_ds))

        candidates.extend([
            f"knowledge/nodes/{clean_ds}",
            str(get_datamesh_home() / "knowledge" / "nodes" / clean_ds),
            str(get_cache_dir() / "nodes" / clean_ds),
        ])
        for ws in get_workspace_search_dirs():
            candidates.append(str(ws / "catalogo-datamesh" / "knowledge" / "nodes" / clean_ds))
            candidates.append(str(ws / "knowledge" / "nodes" / clean_ds))

        for candidate in candidates:
            manifest = self._read_manifest_from_dir(candidate)
            if manifest is not None:
                return manifest

        return self._read_manifest_from_catalog(clean_ds)

    def node_update_frequency(self, dataset: str) -> Optional[str]:
        """Returns the declared update frequency of a node manifest, if any.

        Reads ``temporal.frequency`` (OKF/ODKF) falling back to a top-level
        ``frequency``/``accrualperiodicity`` key. Used to record how often a
        remote resource is expected to change in the cache metadata.
        """
        pkg = self.find_node_datapackage(dataset)
        if not pkg:
            return None
        manifest = pkg[0] or {}
        temporal = manifest.get("temporal")
        if isinstance(temporal, dict) and temporal.get("frequency"):
            return str(temporal["frequency"])
        for key in ("frequency", "accrualperiodicity", "accrualPeriodicity", "periodicity"):
            if manifest.get(key):
                return str(manifest[key])
        return None

    def _read_manifest_from_dir(self, directory: str) -> Optional[Tuple[Dict[str, Any], str]]:
        for fname in _MANIFEST_NAMES:
            path = os.path.join(directory, fname)
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    if fname.endswith((".yaml", ".yml")) and yaml:
                        return yaml.safe_load(f), os.path.dirname(path)
                    if fname.endswith(".json"):
                        return json.load(f), os.path.dirname(path)
            except Exception:
                continue

        return self._read_manifest_from_index(directory)

    def _read_manifest_from_index(self, directory: str) -> Optional[Tuple[Dict[str, Any], str]]:
        """Reads a bundle manifest whose contracts are referenced by an index.md frontmatter entry."""
        if not yaml:
            return None
        index_path = os.path.join(directory, "index.md")
        if not os.path.exists(index_path):
            return None
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.startswith("---"):
                return None
            parts = content.split("---", 2)
            if len(parts) < 3:
                return None
            frontmatter = yaml.safe_load(parts[1])
            if not isinstance(frontmatter, dict):
                return None
            for entry in frontmatter.get("contracts") or []:
                if not isinstance(entry, dict):
                    continue
                c_ref = entry.get("ref") or entry.get("path")
                if c_ref and not c_ref.startswith(("http://", "https://")):
                    ref_full = os.path.normpath(os.path.join(directory, c_ref))
                    if os.path.exists(ref_full):
                        with open(ref_full, "r", encoding="utf-8") as rf:
                            if ref_full.endswith((".yaml", ".yml")):
                                return yaml.safe_load(rf), os.path.dirname(ref_full)
                            if ref_full.endswith(".json"):
                                return json.load(rf), os.path.dirname(ref_full)
        except Exception:
            return None
        return None

    def _read_manifest_from_catalog(self, clean_ds: str) -> Optional[Tuple[Dict[str, Any], str]]:
        try:
            cat = self._discover()
        except Exception:
            return None
        for entry in cat.get("entries", []):
            uri = entry.get("uri", "")
            resolved_url = entry.get("resolved_url", "")
            if clean_ds.lower() in uri.lower() or (resolved_url and clean_ds.lower() in resolved_url.lower()):
                base_url = resolved_url.rsplit("/", 1)[0]
                for fname in _MANIFEST_NAMES:
                    m_url = f"{base_url}/{fname}"
                    try:
                        req = urllib.request.Request(m_url, headers={"User-Agent": "datamesh-sdk/0.2 (Python)"})
                        with urllib.request.urlopen(req, timeout=3) as resp:
                            content = resp.read().decode("utf-8")
                        if fname.endswith((".yaml", ".yml")) and yaml:
                            return yaml.safe_load(content), base_url
                        if fname.endswith(".json"):
                            return json.loads(content), base_url
                    except Exception:
                        continue
        return None

    def resolve_triad_to_path(self, table_ref: str, *args: Any) -> Optional[str]:
        """Maps a canonical triad (or path) to a concrete local path or URL, or ``None``."""
        from datamesh.adapters.engine.duckdb_engine import slugify

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

        pkg_data = self.find_node_datapackage(dataset)
        if pkg_data:
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
                            base_fname = os.path.basename(urllib.parse.urlparse(target_path).path)
                            local_match = self.find_matching_local_file(dataset, base_fname)
                            if local_match:
                                return local_match

                            if "github.com/" in target_path and "/raw/" in target_path:
                                target_path = re.sub(r'https?://github\.com/([^/]+)/([^/]+)/raw/(.+)', r'https://raw.githubusercontent.com/\1/\2/\3', target_path)
                            elif "github.com/" in target_path and "/blob/" in target_path:
                                target_path = re.sub(r'https?://github\.com/([^/]+)/([^/]+)/blob/(.+)', r'https://raw.githubusercontent.com/\1/\2/\3', target_path)
                            return target_path
                        else:
                            if base_loc and base_loc.startswith(("http://", "https://")):
                                base_url_dir = base_loc if base_loc.endswith("/") else f"{base_loc}/"
                                return urllib.parse.urljoin(base_url_dir, target_path)
                            if base_loc and not base_loc.startswith(("http://", "https://")):
                                candidate = os.path.normpath(os.path.join(base_loc, target_path))
                                if os.path.exists(candidate):
                                    return os.path.abspath(candidate)
                                if "*" in candidate and glob.glob(candidate):
                                    return os.path.abspath(candidate)
                            if os.path.exists(target_path):
                                return os.path.abspath(target_path)
                            if "*" in target_path and glob.glob(target_path):
                                return os.path.abspath(target_path)
                            if curr_zip:
                                return curr_zip

                    nested = r.get("resources", [])
                    if isinstance(nested, list) and nested:
                        found = _search_res(nested, parent_zip=curr_zip)
                        if found:
                            return found
                return None

            res_path = _search_res(manifest.get("resources", []))
            if res_path:
                return res_path

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
