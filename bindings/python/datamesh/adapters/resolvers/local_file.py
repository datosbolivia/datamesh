from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any, Dict, Optional

from datamesh.domain.models import ResolvedResource, ResourceDescriptor
from datamesh.ports.resolver import ResourceAdapterPort
from datamesh.ports.storage import StoragePort

def slugify(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]+', '_', text).lower().strip('_')

class LocalFileAdapter(ResourceAdapterPort):
    """
    Adapter for discovering and accessing data files residing on the local filesystem,
    including project repositories, sibling directories, and test datasets.
    """

    @property
    def name(self) -> str:
        return "local"

    def can_handle(self, uri_or_path: str, context: Optional[Dict[str, Any]] = None) -> bool:
        clean = uri_or_path.replace("file://", "")
        if os.path.exists(clean):
            return True
        if uri_or_path.startswith("file://") or clean.startswith(("/", "./", "../", "~")):
            return True
        # If context indicates dataset and resource, can search locally
        if context and ("dataset" in context or "resource" in context):
            return True
        return False

    def resolve_and_fetch(
        self,
        uri_or_path: str,
        storage: StoragePort,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ResolvedResource]:
        clean = uri_or_path.replace("file://", "")
        # Expand user home
        if clean.startswith("~"):
            clean = str(Path(clean).expanduser().resolve())

        # 1. Direct path exists
        if os.path.exists(clean) and os.path.isfile(clean):
            p = Path(clean).resolve()
            fmt = p.suffix.lstrip(".").lower() or "csv"
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

        # 2. Search local sibling projects and testdata
        dataset = ""
        resource = ""
        if context:
            dataset = context.get("dataset", "")
            resource = context.get("resource", "")

        if not dataset and ":" in uri_or_path:
            parts = uri_or_path.split(":")
            dataset = parts[-2]
            resource = parts[-1]
        elif not resource:
            resource = clean

        found_path = self._search_local_paths(dataset, resource)
        if found_path:
            p = Path(found_path).resolve()
            fmt = p.suffix.lstrip(".").lower() or "csv"
            return ResolvedResource(
                descriptor=ResourceDescriptor(
                    raw_reference=uri_or_path,
                    dataset=dataset or None,
                    resource=resource or None,
                    format=fmt,
                    source_service="local",
                ),
                local_path=p,
                format=fmt,
                is_cached=False,
            )

        return None

    def _search_local_paths(self, dataset: str, resource: str) -> Optional[str]:
        # 1. Direct relative testdata paths
        possible = [
            f"core-go/testdata/{resource}.csv",
            f"core-go/testdata/{resource}.parquet",
            f"core-go/testdata/{resource}.json",
            f"core-go/testdata/mock_data_{dataset}.csv",
            f"core-go/testdata/mock_data_{resource}.parquet",
            f"{resource}",
            f"{resource}.csv",
            f"{resource}.parquet",
        ]
        for p in possible:
            if os.path.exists(p) and os.path.isfile(p):
                return os.path.abspath(p)

        # 2. Local sibling projects in workspace directories
        from datamesh.constants import get_workspace_search_dirs
        search_dirs = get_workspace_search_dirs()
        if search_dirs and (dataset or resource):
            ds_clean = dataset.replace("_", "-").lower() if dataset else ""
            ds_clean_under = dataset.replace("-", "_").lower() if dataset else ""
            res_slug = slugify(resource) if resource else ""

            STOPWORDS = {"table", "data", "dataset", "file", "resource", "json", "csv", "parquet", "tsv", "mock"}
            raw_keywords = [ds_clean, ds_clean_under, res_slug]
            for w in re.split(r'[^a-zA-Z0-9]+', resource):
                if len(w) > 3:
                    raw_keywords.append(w.lower())
            keywords = [k for k in dict.fromkeys(raw_keywords) if k and k not in STOPWORDS]

            for workspace_dir in search_dirs:
                if not workspace_dir.exists() or not workspace_dir.is_dir():
                    continue
                for proj in os.listdir(workspace_dir):
                    proj_dir = os.path.join(workspace_dir, proj)
                    if not os.path.isdir(proj_dir):
                        continue
                    proj_low = proj.lower()

                    # If project name matches dataset, prioritize searching all subfolders
                    if (ds_clean and ds_clean in proj_low) or (ds_clean_under and ds_clean_under in proj_low):
                        for root_dir, _, files in os.walk(proj_dir):
                            if "/.git" in root_dir or "/node_modules" in root_dir or "/.cache" in root_dir:
                                continue
                            sorted_files = sorted(files, key=lambda f: (0 if f.endswith(".parquet") else 1))
                            for f in sorted_files:
                                if f.endswith((".parquet", ".csv", ".json", ".tsv")):
                                    f_low = f.lower()
                                    if any(kw in f_low for kw in keywords if len(kw) > 3):
                                        return os.path.join(root_dir, f)

                    # Standard data & test directories
                    for sub in ["data/consolidated", "data", "dist/data", "knowledge/nodes", "test", "tests"]:
                        target_dir = os.path.join(proj_dir, sub)
                    if os.path.exists(target_dir):
                        for root_dir, _, files in os.walk(target_dir):
                            sorted_files = sorted(files, key=lambda f: (0 if f.endswith(".parquet") else 1))
                            for f in sorted_files:
                                if f.endswith((".parquet", ".csv", ".json", ".tsv")):
                                    f_low = f.lower()
                                    if any(kw in f_low for kw in keywords if len(kw) > 4):
                                        return os.path.join(root_dir, f)

        return None
