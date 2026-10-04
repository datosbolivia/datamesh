from __future__ import annotations

import os
from pathlib import Path
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from datamesh.domain.models import ResolvedResource, ResourceDescriptor
from datamesh.ports.resolver import ResourceAdapterPort
from datamesh.ports.storage import StoragePort

class HttpAdapter(ResourceAdapterPort):
    """
    Generic HTTP/HTTPS adapter for streaming open datasets, Google Sheets CSV exports,
    and REST/tabular endpoints into temporal cache.
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
        # 1. Check if already cached in temporal storage
        if storage.is_cached(uri_or_path):
            cached_p = storage.get_cached_path(uri_or_path)
            if cached_p and cached_p.exists():
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

        # 2. Stream download via HTTP
        req = urllib.request.Request(
            uri_or_path,
            headers={
                "User-Agent": "datamesh-sdk/0.2 (Python/DuckDB)",
                "Accept": "*/*",
            }
        )

        import ssl
        try:
            try:
                resp = urllib.request.urlopen(req, timeout=30)
            except urllib.error.URLError as url_err:
                # Fallback on SSL verification failure (e.g. self-signed, expired, or non-standard government CAs)
                if isinstance(url_err.reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(url_err) or "certificate" in str(url_err).lower():
                    unverified_ctx = ssl.create_default_context()
                    unverified_ctx.check_hostname = False
                    unverified_ctx.verify_mode = ssl.CERT_NONE
                    resp = urllib.request.urlopen(req, timeout=30, context=unverified_ctx)
                else:
                    raise

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
                )
                fmt = ext.lstrip(".").lower()
                meta = storage.get_metadata(uri_or_path)
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
            raise RuntimeError(f"HTTP streaming error for '{uri_or_path}': {e}") from e
