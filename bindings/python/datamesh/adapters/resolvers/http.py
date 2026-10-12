from __future__ import annotations

import logging
import os
from pathlib import Path
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from datamesh.domain.models import ResolvedResource, ResourceDescriptor
from datamesh.net import open_url
from datamesh.ports.resolver import ResourceAdapterPort
from datamesh.ports.storage import StoragePort

logger = logging.getLogger("datamesh.resolvers.http")

class HttpAdapter(ResourceAdapterPort):
    """
    Generic HTTP/HTTPS adapter for streaming open datasets, Google Sheets CSV exports,
    and REST/tabular endpoints into temporal cache.

    Remote-first: the endpoint is always re-fetched and the cache refreshed. A stale
    cached copy is only served when the remote request fails, and a warning is emitted.
    """

    @property
    def name(self) -> str:
        return "http"

    def can_handle(self, uri_or_path: str, context: Optional[Dict[str, Any]] = None) -> bool:
        lower = uri_or_path.lower()
        return lower.startswith("http://") or lower.startswith("https://")

    def _infer_extension(self, url: str, content_type: Optional[str] = None) -> str:
        parsed = urllib.parse.urlparse(url)
        path_lower = parsed.path.lower()
        if path_lower.endswith(".parquet") or path_lower.endswith(".pq"):
            return ".parquet"
        if path_lower.endswith(".json") or path_lower.endswith(".jsonl"):
            return ".json"
        if path_lower.endswith(".tsv"):
            return ".tsv"
        if path_lower.endswith(".csv"):
            return ".csv"

        if content_type:
            ct = content_type.lower()
            if "parquet" in ct:
                return ".parquet"
            if "json" in ct:
                return ".json"
            if "tab-separated" in ct or "tsv" in ct:
                return ".tsv"
            if "csv" in ct or "text/plain" in ct:
                return ".csv"

        # Check query params (e.g. output=csv for Google Sheets)
        query = urllib.parse.parse_qs(parsed.query)
        if query.get("output", [""])[0].lower() == "csv":
            return ".csv"

        return ".csv"

    def resolve_and_fetch(
        self,
        uri_or_path: str,
        storage: StoragePort,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ResolvedResource]:
        update_frequency = (context or {}).get("update_frequency")
        prev_meta = storage.get_metadata(uri_or_path)
        prev_sha = prev_meta.sha256 if prev_meta else None

        # 1. Remote-first: always re-fetch the endpoint and refresh temporal cache.
        req = urllib.request.Request(
            uri_or_path,
            headers={
                "User-Agent": "datamesh-sdk/0.2 (Python/DuckDB)",
                "Accept": "*/*",
            }
        )

        try:
            # TLS verification stays on unless DATAMESH_INSECURE_TLS=1 (see datamesh.net).
            resp = open_url(req, timeout=30)

            with resp:
                content_type = resp.headers.get("Content-Type")
                etag = resp.headers.get("ETag")
                ext = self._infer_extension(uri_or_path, content_type)

                cached_path = storage.save(
                    key_or_uri=uri_or_path,
                    content=resp,
                    extension=ext,
                    source_service="http",
                    etag=etag,
                    update_frequency=update_frequency,
                )
                fmt = ext.lstrip(".").lower()
                meta = storage.get_metadata(uri_or_path)
                if prev_sha and meta and meta.sha256 and prev_sha != meta.sha256:
                    logger.info("HTTP resource '%s' changed (sha256 %s -> %s).", uri_or_path, prev_sha[:12], meta.sha256[:12])
                return ResolvedResource(
                    descriptor=ResourceDescriptor(
                        raw_reference=uri_or_path,
                        format=fmt,
                        source_service="http",
                    ),
                    local_path=cached_path,
                    format=fmt,
                    is_cached=True,
                    metadata=meta,
                )
        except Exception as e:
            # 2. Fallback: cached version (possibly stale) -- always warn.
            if storage.is_cached(uri_or_path):
                cached_p = storage.get_cached_path(uri_or_path)
                if cached_p and cached_p.exists():
                    logger.warning(
                        "HTTP fetch failed for '%s' (%s). Using cached (possibly stale) copy at %s.",
                        uri_or_path,
                        e,
                        cached_p,
                    )
                    meta = storage.get_metadata(uri_or_path)
                    fmt = cached_p.suffix.lstrip(".").lower() or "csv"
                    return ResolvedResource(
                        descriptor=ResourceDescriptor(
                            raw_reference=uri_or_path,
                            format=fmt,
                            source_service="http",
                        ),
                        local_path=cached_p,
                        format=fmt,
                        is_cached=True,
                        metadata=meta,
                    )
            raise RuntimeError(f"HTTP streaming error for '{uri_or_path}': {e}") from e
