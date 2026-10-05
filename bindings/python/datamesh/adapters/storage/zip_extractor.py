from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import zipfile

try:
    import yaml
except ImportError:
    yaml = None

from datamesh.constants import DEFAULT_CACHE_DIR

def extract_zip_tabular_resource(
    zip_path: str | Path,
    target_hint: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    preview_limit: Optional[int] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Inspects a zip archive containing tabular data (CSV, Parquet, TSV, or JSON),
    optionally specified by an embedded datapackage manifest or target resource hint,
    extracts the target resource into temporal cache, and returns
    (path_or_glob, format) suitable for DuckDB execution.
    """
    zip_p = Path(zip_path).resolve()
    if not zip_p.exists() or not zip_p.is_file():
        return None, None

    if not zipfile.is_zipfile(zip_p):
        return None, None

    cdir = cache_dir or DEFAULT_CACHE_DIR
    safe_stem = zip_p.stem[:32]
    hash_prefix = hashlib.sha256(str(zip_p).encode("utf-8")).hexdigest()[:12]
    unpacked_root = cdir / "unpacked" / f"{safe_stem}_{hash_prefix}"
    unpacked_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_p, "r") as z:
        namelist = [m for m in z.namelist() if not m.startswith("__MACOSX") and not m.endswith("/")]
        target_path: Optional[str] = None
        target_format = "csv"

        # 1. Exact or basename match with target_hint
        if target_hint:
            hint_clean = target_hint.strip()
            hint_base = Path(hint_clean).name
            for m in namelist:
                if m == hint_clean or Path(m).name == hint_base or Path(m).name.lower() == hint_base.lower():
                    target_path = m
                    break
                if hint_clean.lower() in m.lower():
                    target_path = m
                    break

        # 2. Check for embedded datapackage.json or datapackage.yaml manifest inside zip
        if not target_path:
            manifest_name = None
            if "datapackage.json" in namelist:
                manifest_name = "datapackage.json"
            elif "datapackage.yaml" in namelist:
                manifest_name = "datapackage.yaml"
            elif "datapackage.yml" in namelist:
                manifest_name = "datapackage.yml"

            if manifest_name:
                try:
                    raw_content = z.read(manifest_name).decode("utf-8", errors="replace")
                    dp_data = json.loads(raw_content) if manifest_name.endswith(".json") else (yaml.safe_load(raw_content) if yaml else None)
                    if isinstance(dp_data, dict) and "resources" in dp_data:
                        resources = dp_data.get("resources", [])
                        # Look for matching resource in manifest
                        for r in resources:
                            r_name = str(r.get("name", ""))
                            r_path = str(r.get("path", ""))
                            if target_hint and (
                                target_hint.lower() in r_name.lower()
                                or target_hint.lower() in r_path.lower()
                            ):
                                target_path = r_path
                                target_format = r.get("format") or ("parquet" if r_path.endswith(".parquet") else "csv")
                                break
                        # Fallback to first resource in manifest
                        if not target_path and resources:
                            first_r = resources[0]
                            target_path = first_r.get("path")
                            target_format = first_r.get("format") or ("parquet" if str(target_path).endswith(".parquet") else "csv")
                except Exception:
                    pass

        # 3. Direct tabular members inspection in archive
        if not target_path:
            parquets = [m for m in namelist if m.lower().endswith((".parquet", ".pq"))]
            if parquets:
                target_path = parquets[0] if len(parquets) == 1 else "*.parquet"
                target_format = "parquet"
            else:
                csvs = [m for m in namelist if m.lower().endswith((".csv", ".tsv"))]
                if len(csvs) == 1:
                    target_path = csvs[0]
                    target_format = "tsv" if csvs[0].lower().endswith(".tsv") else "csv"
                elif csvs:
                    common_parent = str(Path(csvs[0]).parent)
                    if common_parent and common_parent != "." and all(str(Path(c).parent) == common_parent for c in csvs):
                        target_path = f"{common_parent}/*.csv"
                    else:
                        target_path = "*.csv"
                    target_format = "csv"

        if not target_path:
            return None, None

        # 4. Extract into unpacked directory
        if "*" in target_path or "?" in target_path:
            matched = [m for m in namelist if fnmatch.fnmatch(m, target_path)]
            if not matched:
                matched = [m for m in namelist if m.lower().endswith((".csv", ".parquet", ".tsv"))]

            to_extract = matched
            if preview_limit and len(matched) > 5:
                to_extract = matched[:min(5, len(matched))]

            for m in to_extract:
                dest_file = unpacked_root / m
                if not dest_file.exists() or dest_file.stat().st_size == 0:
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    z.extract(m, unpacked_root)

            extracted_glob = str(unpacked_root / target_path)
            return extracted_glob, target_format
        else:
            dest_file = unpacked_root / target_path
            if not dest_file.exists() or dest_file.stat().st_size == 0:
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                z.extract(target_path, unpacked_root)
            return str(dest_file), target_format
