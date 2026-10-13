from __future__ import annotations

import logging
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from datamesh.domain.errors import (
    AuthenticationRequiredError,
    InvalidContentTypeError,
    CatalogConnectionError,
)
from datamesh.domain.models import ResolvedResource, ResourceDescriptor, CatalogPatternRule
from datamesh.net import open_url
from datamesh.ports.resolver import ResourceAdapterPort, ConfigPort
from datamesh.ports.storage import StoragePort

logger = logging.getLogger("datamesh.resolvers.http")


class HttpAdapter(ResourceAdapterPort):
    """
    Generic HTTP/HTTPS adapter for streaming open datasets, Google Sheets CSV exports,
    and REST/tabular endpoints into temporal cache.

    Remote-first: the endpoint is always re-fetched and the cache refreshed. A stale
    cached copy is only served when the remote request fails, and a warning is emitted.
    """

    def __init__(self, config_adapter: Optional[ConfigPort] = None):
        self._config_adapter = config_adapter

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

        target_url = uri_or_path
        rule_matched: Optional[CatalogPatternRule] = None

        # 1. Match catalog pattern recognition and rewrite rules
        if self._config_adapter:
            rules = self._config_adapter.get_catalog_rules()
            for r in rules:
                if r.matches(uri_or_path):
                    rule_matched = r
                    target_url = r.rewrite(uri_or_path)
                    logger.info("Catalog rule '%s' matched: %s -> %s", r.name, uri_or_path, target_url)
                    break

        # 2. Build headers
        headers = {
            "User-Agent": "datamesh-sdk/0.2 (Python/DuckDB)",
            "Accept": "*/*",
        }
        if rule_matched and rule_matched.auth_type.lower() != "none":
            auth_hdrs = rule_matched.get_auth_headers()
            if not auth_hdrs:
                err_msg = (
                    f"Authentication required for '{uri_or_path}' by catalog rule '{rule_matched.name}'. "
                    f"Environment variable '{rule_matched.auth_token_env}' is missing or empty. Please set it."
                )
                logger.error(err_msg)
                raise AuthenticationRequiredError(err_msg)
            headers.update(auth_hdrs)
        else:
            auth_token = (
                (context or {}).get("token")
                or os.environ.get("CKAN_ACCESS_KEY", "").strip()
                or os.environ.get("DATAMESH_AUTH_TOKEN", "").strip()
            )
            if auth_token:
                headers["Authorization"] = auth_token

        req = urllib.request.Request(
            target_url,
            headers=headers,
        )

        try:
            resp = open_url(req, timeout=30)
            with resp:
                final_url = resp.geturl() if hasattr(resp, "geturl") else target_url
                content_type = (resp.headers.get("Content-Type") or "").lower()
                etag = resp.headers.get("ETag") if hasattr(resp, "headers") else None
                ext = self._infer_extension(target_url, content_type)

                # Guard 1: Detect OAuth2/SSO interactive login redirects
                is_auth_redirect = any(
                    k in final_url.lower()
                    for k in ("/realms/", "/oauth2/", "/login", "auth.economiayfinanzas", "openid-connect")
                ) and not any(k in uri_or_path.lower() for k in ("/realms/", "/oauth2/", "/login"))
                if is_auth_redirect:
                    err_msg = (
                        f"Request for '{uri_or_path}' was redirected to authentication portal '{final_url}'. "
                        "Access requires active credentials. Configure CKAN_ACCESS_KEY or catalog auth rule."
                    )
                    logger.error(err_msg)
                    raise AuthenticationRequiredError(err_msg)

                # Guard 2: Reject HTML content when fetching tabular data files
                if "text/html" in content_type:
                    err_msg = (
                        f"Remote server returned HTML (Content-Type: '{content_type}') instead of expected data ('{ext}') "
                        f"for '{uri_or_path}' (resolved: '{target_url}'). Aborting: will not cache HTML as dataset."
                    )
                    logger.error(err_msg)
                    raise InvalidContentTypeError(err_msg)

                # Guard 3: Peek file bytes to verify signatures (reject HTML doctype and invalid parquet)
                first_chunk = resp.read(512)
                lower_chunk = first_chunk.lower().strip()
                if lower_chunk.startswith(b"<!doctype html") or lower_chunk.startswith(b"<html"):
                    err_msg = (
                        f"Content received for '{uri_or_path}' starts with HTML markup ({first_chunk[:40]!r}). "
                        "Remote endpoint returned an HTML webpage instead of dataset content."
                    )
                    logger.error(err_msg)
                    raise InvalidContentTypeError(err_msg)

                if ext in (".parquet", ".pq") and not first_chunk.startswith(b"PAR1"):
                    err_msg = (
                        f"Invalid Parquet file for '{uri_or_path}'. Expected magic bytes 'PAR1' at file start, "
                        f"but received {first_chunk[:16]!r}."
                    )
                    logger.error(err_msg)
                    raise InvalidContentTypeError(err_msg)

                class PrefixedStream:
                    def __init__(self, prefix: bytes, stream: Any):
                        self._prefix = prefix
                        self._stream = stream
                        self._prefix_read = False

                    def read(self, n: int = -1) -> bytes:
                        if not self._prefix_read:
                            self._prefix_read = True
                            if n == -1 or n >= len(self._prefix):
                                rest_n = -1 if n == -1 else n - len(self._prefix)
                                return self._prefix + (self._stream.read(rest_n) if rest_n != 0 else b"")
                            else:
                                ret = self._prefix[:n]
                                self._prefix = self._prefix[n:]
                                self._prefix_read = False
                                return ret
                        return self._stream.read(n)

                cached_stream = PrefixedStream(first_chunk, resp)

                cached_path = storage.save(
                    key_or_uri=uri_or_path,
                    content=cached_stream,
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
        except urllib.error.HTTPError as he:
            if he.code in (401, 403):
                err_msg = f"HTTP {he.code} Unauthorized for '{target_url}' (original: '{uri_or_path}'). Verify credentials/headers."
                logger.error(err_msg)
                raise AuthenticationRequiredError(err_msg) from he
            elif he.code == 404:
                err_msg = f"HTTP 404 Resource not found at '{target_url}' (original: '{uri_or_path}')."
                logger.error(err_msg)
                raise FileNotFoundError(err_msg) from he
            elif he.code >= 500:
                err_msg = f"HTTP {he.code} Server error from '{target_url}' (original: '{uri_or_path}'): {he.reason}."
                logger.error(err_msg)
                raise CatalogConnectionError(err_msg) from he
            raise RuntimeError(f"HTTP streaming error {he.code} for '{uri_or_path}': {he}") from he
        except (AuthenticationRequiredError, InvalidContentTypeError, FileNotFoundError, CatalogConnectionError) as explicit_err:
            raise explicit_err
        except Exception as e:
            # Fallback: only for other transient network failures if valid cache exists
            if storage.is_cached(uri_or_path):
                cached_p = storage.get_cached_path(uri_or_path)
                if cached_p and cached_p.exists() and cached_p.stat().st_size > 0:
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
