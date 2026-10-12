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
            return self._fetcher.fetch(urls[0])

        combined_entries: List[Dict[str, Any]] = []
        source_catalogs: List[str] = []
        seen = set()
        for url in urls:
            try:
                catalog = self._fetcher.fetch(url)
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
