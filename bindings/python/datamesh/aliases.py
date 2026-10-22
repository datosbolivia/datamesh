"""Aliases de conveniencia y compatibilidad que retornan directamente pandas.DataFrame."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore

from datamesh.adapters.catalog.ckan_client import CKANClientAdapter
from datamesh.adapters.storage.s3_storage import S3StorageAdapter


def _require_pandas() -> Any:
    if pd is None:
        raise ImportError(
            "pandas is required for DataFrame conversion operations. "
            "Install it via 'pip install pandas' or 'pip install datamesh-sdk'."
        )
    return pd


def _leer_como_df(path: Union[str, Path], formato: Optional[str] = None) -> Any:
    """Lee un archivo local y lo devuelve como DataFrame según su formato."""
    p = _require_pandas()
    fmt = (formato or "").strip().lower()
    path_str = str(path)
    if not fmt and path_str:
        fmt = Path(path_str).suffix.lstrip(".").lower()
    if fmt in ("xlsx", "xls"):
        return p.read_excel(path_str)
    if fmt == "csv":
        return p.read_csv(path_str)
    if fmt == "parquet":
        return p.read_parquet(path_str)
    if fmt in ("json", "geojson"):
        return p.read_json(path_str)
    return None


def to_df(data_or_query_res: Any) -> Any:
    """Convierte un resultado de query/sql o lista de diccionarios a pandas.DataFrame."""
    p = _require_pandas()
    if isinstance(data_or_query_res, p.DataFrame):
        return data_or_query_res
    if isinstance(data_or_query_res, dict):
        if "columns" in data_or_query_res and "rows" in data_or_query_res:
            return p.DataFrame(data_or_query_res["rows"], columns=data_or_query_res["columns"])
    if isinstance(data_or_query_res, list):
        return p.DataFrame(data_or_query_res)
    return p.DataFrame()


def _as_dict(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        return item
    if hasattr(item, "to_dict") and callable(item.to_dict):
        return item.to_dict()
    if hasattr(item, "__dict__"):
        return item.__dict__
    return {}


def datasets_a_df(datasets: List[Any]) -> Any:
    """Convierte lista de datasets CKAN a DataFrame."""
    p = _require_pandas()
    if not datasets:
        return p.DataFrame()
    rows = []
    for raw in datasets:
        ds = _as_dict(raw)
        resources = ds.get("resources", [])
        rows.append({
            "id": ds.get("id"),
            "nombre": ds.get("name"),
            "titulo": ds.get("title"),
            "organizacion": (ds.get("organization") or {}).get("title") or ds.get("organization_title"),
            "num_recursos": len(resources),
            "recursos": [r.get("name") if isinstance(r, dict) else getattr(r, "name", "") for r in resources],
        })
    return p.DataFrame(rows)


def organizaciones_a_df(orgs: List[Any]) -> Any:
    """Convierte lista de organizaciones a DataFrame."""
    p = _require_pandas()
    if not orgs:
        return p.DataFrame()
    rows = []
    for raw in orgs:
        o = _as_dict(raw)
        rows.append({
            "id": o.get("id"),
            "nombre": o.get("name"),
            "titulo": o.get("title"),
            "paquetes": o.get("package_count", 0),
        })
    return p.DataFrame(rows)


def recursos_a_df(datasets: List[Any]) -> Any:
    """Aparador aplanado de todos los recursos de una lista de datasets en un solo DataFrame."""
    p = _require_pandas()
    if not datasets:
        return p.DataFrame()
    rows = []
    for raw in datasets:
        ds = _as_dict(raw)
        ds_name = ds.get("name") or ds.get("id")
        org_title = (ds.get("organization") or {}).get("title") or ds.get("organization_title")
        for res in ds.get("resources", []):
            r = _as_dict(res)
            rows.append({
                "dataset_name": ds_name,
                "dataset_title": ds.get("title"),
                "organizacion": org_title,
                "resource_id": r.get("id"),
                "resource_name": r.get("name"),
                "format": r.get("format"),
                "url": r.get("url"),
                "size": r.get("size"),
            })
    return p.DataFrame(rows)
