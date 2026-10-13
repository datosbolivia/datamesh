from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from datamesh.adapters.catalog.llmstxt_catalog import LLMSTxtCatalogFetcher
from datamesh.adapters.go_bridge import GoCoreBridge


class DiscoverCatalogUseCase:
    """Discovers a single catalog or aggregates all configured federated catalogs.

    Prefers the Go core via the C-ABI bridge and falls back to the pure-Python
    llms.txt fetcher/parser.
    """

    def __init__(
        self,
        bridge: GoCoreBridge,
        fetcher: LLMSTxtCatalogFetcher,
        urls_provider: Callable[[], List[str]],
    ):
        self._bridge = bridge
        self._fetcher = fetcher
        self._urls_provider = urls_provider

    def execute(self, catalog_url: Optional[str] = None) -> Dict[str, Any]:
        go_result = self._bridge.call("DataMeshDiscoverCatalog", catalog_url or None)
        if go_result:
            return go_result

        urls = [catalog_url] if catalog_url else self._urls_provider()
        if len(urls) == 1:
            return self._fetch_catalog(urls[0])

        combined_entries: List[Dict[str, Any]] = []
        source_catalogs: List[str] = []
        seen = set()
        for url in urls:
            try:
                catalog = self._fetch_catalog(url)
            except Exception:
                continue
            source_catalogs.append(url)
            for entry in catalog.get("entries", []):
                entry["catalog_source"] = url
                key = entry.get("resolved_url") or entry.get("title")
                if key not in seen:
                    seen.add(key)
                    combined_entries.append(entry)

        return {
            "title": "DataMesh Federated Catalog",
            "source_catalogs": source_catalogs,
            "entries": combined_entries,
        }

    def _is_ckan(self, url: str) -> bool:
        import os
        env_ckan = (os.environ.get("CKAN_URL") or os.environ.get("CKAN_BASE_URL") or "").rstrip("/")
        return "/api/3" in url.lower() or url.startswith("ckan://") or "ckan" in url.lower()

    def _fetch_catalog(self, url: str) -> Dict[str, Any]:
        if url.startswith("ckan://") or self._is_ckan(url):
            return self._fetch_ckan(url)
        try:
            return self._fetcher.fetch(url)
        except Exception:
            if self._is_ckan(url):
                return self._fetch_ckan(url)
            raise

    def _fetch_ckan(self, url: str) -> Dict[str, Any]:
        from datamesh.adapters.catalog.ckan_client import CKANClientAdapter
        client = CKANClientAdapter()
        base_url = url[7:] if url.startswith("ckan://") else url
        packages, _ = client.search_packages(base_url, limit=50)
        entries = []
        for pkg in packages:
            entries.append({
                "title": pkg.title or pkg.name,
                "uri": f"ckan:{pkg.name}",
                "name": pkg.name,
                "resolved_url": f"{base_url.rstrip('/')}/dataset/{pkg.name}",
                "description": pkg.notes or "",
                "catalog_source": base_url,
                "resources": [r.name or r.id for r in pkg.resources],
                "type": "ckan_package",
            })
        return {
            "title": f"CKAN Catalog ({base_url})",
            "source_catalogs": [base_url],
            "entries": entries,
        }
