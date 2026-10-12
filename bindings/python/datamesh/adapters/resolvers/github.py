from __future__ import annotations

import logging
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from datamesh.domain.models import ResolvedResource, ResourceDescriptor
from datamesh.ports.resolver import ResourceAdapterPort
from datamesh.ports.storage import StoragePort

logger = logging.getLogger("datamesh.resolvers.github")

class GitHubAdapter(ResourceAdapterPort):
    """
    Adapter for downloading and caching datasets hosted on GitHub repositories
    (raw files, releases, and blob URLs). Converts GitHub links to raw CDN endpoints.

    Remote-first: the raw URL is always re-fetched and the cache refreshed. Local
    clones and stale cache entries are only used when the download fails, with a warning.
    """

    @property
    def name(self) -> str:
        return "github"

    def can_handle(self, uri_or_path: str, context: Optional[Dict[str, Any]] = None) -> bool:
        lower = uri_or_path.lower()
        return "github.com" in lower or "raw.githubusercontent.com" in lower

    def _normalize_github_url(self, url: str) -> str:
        """Converts standard github.com/raw or blob URLs to raw.githubusercontent.com URLs."""
        if "github.com/" in url and "/raw/" in url:
            return re.sub(
                r'https?://github\.com/([^/]+)/([^/]+)/raw/(.+)',
                r'https://raw.githubusercontent.com/\1/\2/\3',
                url,
            )
        elif "github.com/" in url and "/blob/" in url:
            return re.sub(
                r'https?://github\.com/([^/]+)/([^/]+)/blob/(.+)',
                r'https://raw.githubusercontent.com/\1/\2/\3',
                url,
            )
        return url

    def resolve_and_fetch(
        self,
        uri_or_path: str,
        storage: StoragePort,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ResolvedResource]:
        normalized_url = self._normalize_github_url(uri_or_path)

        # Infer format and filename
        parsed = urllib.parse.urlparse(normalized_url)
        fname = os.path.basename(parsed.path)
        ext = os.path.splitext(fname)[1].lower() or ".csv"
        fmt = ext.lstrip(".")

        update_frequency = (context or {}).get("update_frequency")
        prev_meta = storage.get_metadata(normalized_url)
        prev_sha = prev_meta.sha256 if prev_meta else None

        # 1. Remote-first: always stream the latest file from the raw CDN.
        req = urllib.request.Request(
            normalized_url,
            headers={
                "User-Agent": "datamesh-sdk/0.2 (Python/DuckDB)",
                "Accept": "*/*",
            }
        )

        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            req.add_header("Authorization", f"token {token}")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                etag = resp.headers.get("ETag")
                cached_path = storage.save(
                    key_or_uri=normalized_url,
                    content=resp,
                    extension=ext,
                    source_service="github",
                    etag=etag,
                    update_frequency=update_frequency,
                )
                meta = storage.get_metadata(normalized_url)
                if prev_sha and meta and meta.sha256 and prev_sha != meta.sha256:
                    logger.info("GitHub resource '%s' changed (sha256 %s -> %s).", normalized_url, prev_sha[:12], meta.sha256[:12])
                return ResolvedResource(
                    descriptor=ResourceDescriptor(
                        raw_reference=uri_or_path,
                        format=fmt,
                        source_service="github",
                    ),
                    local_path=cached_path,
                    format=fmt,
                    is_cached=True,
                    metadata=meta,
                )
        except Exception as e:
            # 2. Fallback: cached version (possibly stale) -- always warn.
            if storage.is_cached(normalized_url):
                cached_path = storage.get_cached_path(normalized_url)
                if cached_path and cached_path.exists():
                    logger.warning(
                        "GitHub download failed for '%s' (%s). Using cached (possibly stale) copy at %s.",
                        normalized_url,
                        e,
                        cached_path,
                    )
                    meta = storage.get_metadata(normalized_url)
                    return ResolvedResource(
                        descriptor=ResourceDescriptor(
                            raw_reference=uri_or_path,
                            format=fmt,
                            source_service="github",
                        ),
                        local_path=cached_path,
                        format=fmt,
                        is_cached=True,
                        metadata=meta,
                    )

            # 3. Fallback: local clone (possibly stale) -- always warn.
            local_repo_match = self._find_in_local_clone(normalized_url, fname)
            if local_repo_match and os.path.exists(local_repo_match):
                p = Path(local_repo_match).resolve()
                logger.warning(
                    "GitHub download failed for '%s' (%s). Using local clone file '%s'; it may be stale.",
                    normalized_url,
                    e,
                    p,
                )
                return ResolvedResource(
                    descriptor=ResourceDescriptor(
                        raw_reference=uri_or_path,
                        format=fmt,
                        source_service="local",
                    ),
                    local_path=p,
                    format=fmt,
                    is_cached=False,
                )
            raise RuntimeError(f"Failed to fetch resource from GitHub ({normalized_url}): {e}") from e

    def _find_in_local_clone(self, url: str, target_filename: str) -> Optional[str]:
        """Checks if the user already has this repo cloned locally in any workspace directory."""
        m = re.search(r'github\.com/([^/]+)/([^/]+)', url) or re.search(r'raw\.githubusercontent\.com/([^/]+)/([^/]+)', url)
        if not m:
            return None
        repo_name = m.group(2).lower()
        from datamesh.constants import get_workspace_search_dirs
        search_dirs = get_workspace_search_dirs()
        for workspace_dir in search_dirs:
            if not workspace_dir.exists() or not workspace_dir.is_dir():
                continue
            for proj in os.listdir(workspace_dir):
                if repo_name in proj.lower() or proj.lower() in repo_name:
                    p_path = os.path.join(workspace_dir, proj)
                    if os.path.isdir(p_path):
                        for root_dir, _, files in os.walk(p_path):
                            if "/.git" in root_dir or "/node_modules" in root_dir:
                                continue
                            if target_filename in files:
                                return os.path.join(root_dir, target_filename)
        return None
