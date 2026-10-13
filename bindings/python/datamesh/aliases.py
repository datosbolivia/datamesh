"""Aliases de conveniencia y compatibilidad que retornan directamente pandas.DataFrame."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from datamesh.adapters.catalog.ckan_client import CKANClientAdapter
from datamesh.adapters.storage.s3_storage import S3StorageAdapter


def _leer_como_df(path: Union[str, Path], formato: Optional[str] = None) -> Optional[pd.DataFrame]:
    """Lee un archivo local y lo devuelve como DataFrame según su formato."""
    fmt = (formato or "").strip().lower()
    path_str = str(path)
    if not fmt and path_str:
        fmt = Path(path_str).suffix.lstrip(".").lower()
    if fmt in ("xlsx", "xls"):
        return pd.read_excel(path_str)
    if fmt == "csv":
        return pd.read_csv(path_str)
    if fmt == "parquet":
        return pd.read_parquet(path_str)
    if fmt in ("json", "geojson"):
        return pd.read_json(path_str)
    return None


def to_df(data_or_query_res: Any) -> pd.DataFrame:
    """Convierte un resultado de query/sql o lista de diccionarios a pandas.DataFrame."""
    if isinstance(data_or_query_res, pd.DataFrame):
        return data_or_query_res
    if isinstance(data_or_query_res, dict):
        if "columns" in data_or_query_res and "rows" in data_or_query_res:
            return pd.DataFrame(data_or_query_res["rows"], columns=data_or_query_res["columns"])
    if isinstance(data_or_query_res, list):
        return pd.DataFrame(data_or_query_res)
    return pd.DataFrame()


def datasets_a_df(datasets: List[Dict[str, Any]]) -> pd.DataFrame:
    """Convierte lista de datasets CKAN a DataFrame."""
    if not datasets:
        return pd.DataFrame()
    return pd.DataFrame([
        {
            "nombre": ds.get("name"),
            "titulo": ds.get("title"),
            "organizacion": (ds.get("organization") or {}).get("name") if isinstance(ds.get("organization"), dict) else ds.get("organization"),
            "num_recursos": len(ds.get("resources") or []),
            "privado": bool(ds.get("private")),
        }
        for ds in datasets
    ])


def organizaciones_a_df(orgs: List[Dict[str, Any]]) -> pd.DataFrame:
    """Convierte lista de organizaciones CKAN a DataFrame."""
    if not orgs:
        return pd.DataFrame()
    return pd.DataFrame([
        {
            "nombre": o.get("name"),
            "titulo": o.get("title"),
            "descripcion": o.get("description"),
            "num_datasets": o.get("package_count"),
        }
        for o in orgs
    ])


def recursos_a_df(recursos: List[Dict[str, Any]]) -> pd.DataFrame:
    """Convierte lista de recursos CKAN a DataFrame."""
    if not recursos:
        return pd.DataFrame()
    return pd.DataFrame([
        {
            "nombre": r.get("name"),
            "formato": r.get("format"),
            "tamano": r.get("size"),
            "url": r.get("url"),
            "id": r.get("id"),
        }
        for r in recursos
    ])
