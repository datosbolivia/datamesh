from __future__ import annotations

import logging
import os
from pathlib import Path
import re
import urllib.parse
from typing import Any, Dict, Optional
import zipfile

from datamesh.domain.models import ResolvedResource, ResourceDescriptor
from datamesh.ports.resolver import ResourceAdapterPort
from datamesh.ports.storage import StoragePort

logger = logging.getLogger("datamesh.resolvers.kaggle")

class KaggleAdapter(ResourceAdapterPort):
    """
    Adapter for discovering, downloading, and caching datasets from Kaggle.

    Remote-first: the latest published version is always downloaded and refreshed
    (change is detected by comparing the stored ``sha256`` with the fresh download).
    Local sibling files and stale cache entries are used **only** when the remote
    fetch fails, and always emit a warning (they may be outdated, unversioned copies).
    """

    @property
    def name(self) -> str:
        return "kaggle"

    def can_handle(self, uri_or_path: str, context: Optional[Dict[str, Any]] = None) -> bool:
        lower = uri_or_path.lower()
        if "kaggle.com" in lower or uri_or_path.startswith("kaggle://"):
            return True
        if context and context.get("source") == "kaggle":
            return True
        return False

    def _parse_kaggle_ref(self, uri: str) -> tuple[str, str, Optional[str]]:
        """Extracts (owner, dataset, filename) from Kaggle URL or URI."""
        clean = uri.replace("kaggle://datasets/", "").replace("kaggle://", "")
        # e.g. https://www.kaggle.com/datasets/sociest/calidad-aire-monica/air_quality_consolidated.csv
        m = re.search(r'kaggle\.com/datasets/([^/]+)/([^/]+)(?:/(.+))?', clean)
        if m:
            owner = m.group(1)
            dataset = m.group(2)
            fname = m.group(3)
            return owner, dataset, fname

        parts = clean.split("/")
        if len(parts) >= 2:
            owner = parts[0]
            dataset = parts[1]
            fname = parts[2] if len(parts) > 2 else None
            return owner, dataset, fname

        return "", "", None

    def resolve_and_fetch(
        self,
        uri_or_path: str,
        storage: StoragePort,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ResolvedResource]:
        owner, dataset, filename = self._parse_kaggle_ref(uri_or_path)
        dataset_ref = f"{owner}/{dataset}" if owner and dataset else uri_or_path
        update_frequency = (context or {}).get("update_frequency")

        prev_meta = storage.get_metadata(uri_or_path)
        prev_sha = prev_meta.sha256 if prev_meta else None

        # 1. Remote-first: always fetch the latest published version and refresh cache.
        download_error: Optional[Exception] = None
        try:
            fresh = self._download_latest(
                uri_or_path, storage, owner, dataset, dataset_ref, filename, update_frequency, prev_sha
            )
            if fresh is not None:
                return fresh
        except Exception as e:
            download_error = e
            logger.warning("Kaggle fetch failed for '%s': %s", dataset_ref, e)

        # 2. Fallback: cached version (possibly stale) -- always warn.
        cached = self._cached_resolution(uri_or_path, storage, dataset, filename)
        if cached is not None:
            logger.warning(
                "Using cached (possibly stale) copy of '%s' because the remote fetch failed.",
                uri_or_path,
            )
            return cached

        # 3. Fallback: local sibling file (possibly stale, unversioned) -- always warn.
        local = self._local_sibling_resolution(uri_or_path, dataset, filename)
        if local is not None:
            logger.warning(
                "Using local sibling file '%s' for '%s'; it may be stale or out of sync with Kaggle.",
                local.local_path,
                dataset_ref,
            )
            return local

        raise RuntimeError(f"Failed to fetch Kaggle dataset '{dataset_ref}': {download_error}")

    def _download_latest(
        self,
        uri_or_path: str,
        storage: StoragePort,
        owner: str,
        dataset: str,
        dataset_ref: str,
        filename: Optional[str],
        update_frequency: Optional[str],
        prev_sha: Optional[str],
    ) -> Optional[ResolvedResource]:
        """Downloads the latest version via the Kaggle API and refreshes temporal cache."""
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()

        dest_dir = storage.get_cache_dir() / "kaggle" / f"{owner}_{dataset}"
        dest_dir.mkdir(parents=True, exist_ok=True)

        if filename and not filename.endswith(".zip"):
            api.dataset_download_file(dataset_ref, file_name=filename, path=str(dest_dir))
            zip_cand = dest_dir / f"{filename}.zip"
            if zip_cand.exists():
                with zipfile.ZipFile(zip_cand, 'r') as zf:
                    zf.extractall(dest_dir)
                zip_cand.unlink()
        else:
            api.dataset_download_files(dataset_ref, path=str(dest_dir), unzip=True)

        target = None
        if filename:
            cand = dest_dir / filename
            if cand.exists():
                target = cand
        if not target:
            for f in dest_dir.glob("*"):
                if f.suffix.lower() in [".parquet", ".csv", ".json", ".tsv"]:
                    target = f
                    break

        if not (target and target.exists()):
            return None

        stored = storage.store_file(
            target,
            key_or_uri=uri_or_path,
            source_service="kaggle",
            update_frequency=update_frequency,
        )
        fmt = stored.suffix.lstrip(".").lower() or "csv"
        meta = storage.get_metadata(uri_or_path)
        if prev_sha and meta and meta.sha256 and prev_sha != meta.sha256:
            logger.info("Kaggle resource '%s' changed (sha256 %s -> %s).", uri_or_path, prev_sha[:12], meta.sha256[:12])
        return ResolvedResource(
            descriptor=ResourceDescriptor(
                raw_reference=uri_or_path,
                dataset=dataset,
                resource=filename or target.name,
                format=fmt,
                source_service="kaggle",
            ),
            local_path=stored,
            format=fmt,
            is_cached=True,
            metadata=meta,
        )

    def _cached_resolution(
        self, uri_or_path: str, storage: StoragePort, dataset: str, filename: Optional[str]
    ) -> Optional[ResolvedResource]:
        """Returns an already-cached copy of the resource, if present."""
        if not storage.is_cached(uri_or_path):
            return None
        cached_p = storage.get_cached_path(uri_or_path)
        if not (cached_p and cached_p.exists()):
            return None
        meta = storage.get_metadata(uri_or_path)
        fmt = cached_p.suffix.lstrip(".").lower() or "csv"
        return ResolvedResource(
            descriptor=ResourceDescriptor(
                raw_reference=uri_or_path,
                dataset=dataset,
                resource=filename,
                format=fmt,
                source_service="kaggle",
            ),
            local_path=cached_p,
            format=fmt,
            is_cached=True,
            metadata=meta,
        )

    def _local_sibling_resolution(
        self, uri_or_path: str, dataset: str, filename: Optional[str]
    ) -> Optional[ResolvedResource]:
        """Returns a local sibling file matching the resource, if present."""
        local_match = self._find_local_sibling_file(dataset, filename)
        if not (local_match and os.path.exists(local_match)):
            return None
        p = Path(local_match).resolve()
        fmt = p.suffix.lstrip(".").lower() or "csv"
        return ResolvedResource(
            descriptor=ResourceDescriptor(
                raw_reference=uri_or_path,
                dataset=dataset,
                resource=filename,
                format=fmt,
                source_service="local",
            ),
            local_path=p,
            format=fmt,
            is_cached=False,
        )

    def _find_local_sibling_file(self, dataset: str, filename: Optional[str]) -> Optional[str]:
        names_to_try = []
        if filename:
            names_to_try.append(filename)
            stem, ext = os.path.splitext(filename)
            if ext.lower() == ".csv":
                names_to_try.insert(0, f"{stem}.parquet")
            elif ext.lower() == ".parquet":
                names_to_try.append(f"{stem}.csv")

        from datamesh.constants import get_workspace_search_dirs
        search_dirs = get_workspace_search_dirs()
        ds_clean = dataset.replace("_", "-").lower() if dataset else ""

        for workspace_dir in search_dirs:
            if not workspace_dir.exists() or not workspace_dir.is_dir():
                continue
            for proj in os.listdir(workspace_dir):
                proj_low = proj.lower()
                if ds_clean and (ds_clean in proj_low or ds_clean.replace("-", "_") in proj_low):
                    p_path = os.path.join(workspace_dir, proj)
                    if os.path.isdir(p_path):
                        for root_dir, dirs, files in os.walk(p_path):
                            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "dist", "__pycache__", "build", ".cache", ".git")]
                            for n in names_to_try:
                                if n in files:
                                    return os.path.join(root_dir, n)
                            for f in sorted(files, key=lambda x: (0 if x.endswith(".parquet") else 1)):
                                if f.endswith((".parquet", ".csv")):
                                    if (ds_clean and ds_clean in f.lower()) or (filename and Path(f).stem.lower() == Path(filename).stem.lower()):
                                        return os.path.join(root_dir, f)
        return None
