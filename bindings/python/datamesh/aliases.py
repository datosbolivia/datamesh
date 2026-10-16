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


def _as_dict(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        return item
    if hasattr(item, "to_dict") and callable(item.to_dict):
        return item.to_dict()
    if hasattr(item, "__dict__"):
        return item.__dict__
    return {}


def datasets_a_df(datasets: List[Any]) -> pd.DataFrame:
    """Convierte lista de datasets CKAN a DataFrame."""
    if not datasets:
        return pd.DataFrame()
    rows = []
    for raw in datasets:
        ds = _as_dict(raw)
        org = ds.get("organization") or ds.get("organization_title")
        org_name = org.get("name") if isinstance(org, dict) else org
        rows.append({
            "nombre": ds.get("name"),
            "titulo": ds.get("title"),
            "organizacion": org_name,
            "num_recursos": len(ds.get("resources") or []),
            "privado": bool(ds.get("private")),
        })
    return pd.DataFrame(rows)


def organizaciones_a_df(orgs: List[Any]) -> pd.DataFrame:
    """Convierte lista de organizaciones CKAN a DataFrame."""
    if not orgs:
        return pd.DataFrame()
    return pd.DataFrame([
        {
            "nombre": _as_dict(o).get("name"),
            "titulo": _as_dict(o).get("title"),
            "descripcion": _as_dict(o).get("description"),
            "num_datasets": _as_dict(o).get("package_count"),
        }
        for o in orgs
    ])


def recursos_a_df(recursos_o_datasets: List[Any]) -> pd.DataFrame:
    """Convierte lista de recursos o datasets CKAN a DataFrame de recursos."""
    if not recursos_o_datasets:
        return pd.DataFrame()
    rows = []
    for item in recursos_o_datasets:
        d = _as_dict(item)
        if "resources" in d:
            # Es un dataset con recursos anidados
            ds_name = d.get("name", "")
            for r in d.get("resources", []):
                rd = _as_dict(r)
                rows.append({
                    "dataset_name": ds_name,
                    "resource_name": rd.get("name"),
                    "format": rd.get("format"),
                    "size": rd.get("size"),
                    "url": rd.get("url"),
                    "id": rd.get("id"),
                })
        else:
            rows.append({
                "dataset_name": "",
                "resource_name": d.get("name"),
                "format": d.get("format"),
                "size": d.get("size"),
                "url": d.get("url"),
                "id": d.get("id"),
            })
    return pd.DataFrame(rows)
