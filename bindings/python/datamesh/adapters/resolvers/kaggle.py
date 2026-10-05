from __future__ import annotations

import os
from pathlib import Path
import re
import urllib.parse
from typing import Any, Dict, Optional
import zipfile

from datamesh.domain.models import ResolvedResource, ResourceDescriptor
from datamesh.ports.resolver import ResourceAdapterPort
from datamesh.ports.storage import StoragePort

class KaggleAdapter(ResourceAdapterPort):
    """
    Adapter for discovering, downloading, and caching datasets from Kaggle.
    Uses Kaggle API / ~/.kaggle/kaggle.json credentials and local sibling fallback.
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

        # 1. Check if already cached in temporal storage
        if storage.is_cached(uri_or_path):
            cached_p = storage.get_cached_path(uri_or_path)
            if cached_p and cached_p.exists():
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

        # 2. Check local sibling projects fallback (e.g. air-quality-lapaz data files)
        local_match = self._find_local_sibling_file(dataset, filename)
        if local_match and os.path.exists(local_match):
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

        # 3. Download via Kaggle Python API
        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
            api = KaggleApi()
            api.authenticate()

            dest_dir = storage.get_cache_dir() / "kaggle" / f"{owner}_{dataset}"
            dest_dir.mkdir(parents=True, exist_ok=True)

            if filename and not filename.endswith(".zip"):
                api.dataset_download_file(dataset_ref, file_name=filename, path=str(dest_dir))
                target_file = dest_dir / filename
                # If downloaded as zip, extract
                zip_cand = dest_dir / f"{filename}.zip"
                if zip_cand.exists():
                    with zipfile.ZipFile(zip_cand, 'r') as zf:
                        zf.extractall(dest_dir)
                    zip_cand.unlink()
            else:
                api.dataset_download_files(dataset_ref, path=str(dest_dir), unzip=True)

            # Find matching file in dest_dir
            target = None
            if filename:
                cand = dest_dir / filename
                if cand.exists():
                    target = cand
            if not target:
                # Find first csv or parquet in dest_dir
                for f in dest_dir.glob("*"):
                    if f.suffix.lower() in [".parquet", ".csv", ".json", ".tsv"]:
                        target = f
                        break

            if target and target.exists():
                stored = storage.store_file(target, key_or_uri=uri_or_path, source_service="kaggle")
                fmt = stored.suffix.lstrip(".").lower() or "csv"
                meta = storage.get_metadata(uri_or_path)
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
        except Exception as e:
            # If Kaggle API fails or network unavailable, re-check local fallback
            if local_match and os.path.exists(local_match):
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
            raise RuntimeError(f"Failed to fetch Kaggle dataset '{dataset_ref}': {e}") from e

        return None

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
