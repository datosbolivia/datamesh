from __future__ import annotations

import csv
import json
import os
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import yaml
except ImportError:
    yaml = None

try:
    import duckdb
except ImportError:
    duckdb = None

from datamesh.domain.models import DataPackageBuildResult, KnowledgeConceptDoc


class CreateDataPackageUseCase:
    """
    Creates or updates an OKF / ODKF v0.2 datapackage.yaml manifest from described files,
    ZIP archives, or directory trees, automatically inferring schemas when omitted.
    """

    @classmethod
    def infer_schema_from_csv(
        cls,
        file_path: Union[str, Path],
        encoding: str = "utf-8",
        delimiter: Optional[str] = None,
        max_rows: int = 50,
    ) -> Dict[str, Any]:
        """Infers Frictionless DataPackage field schema from CSV file."""
        path_str = str(file_path)
        if duckdb is not None and os.path.exists(path_str):
            try:
                con = duckdb.connect(":memory:")
                # Let duckdb sniff columns and types
                delim_sql = f", delim='{delimiter}'" if delimiter else ""
                df_desc = con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{path_str}'{delim_sql})").fetchall()
                fields = []
                type_map = {
                    "VARCHAR": "string",
                    "BIGINT": "integer",
                    "INTEGER": "integer",
                    "SMALLINT": "integer",
                    "TINYINT": "integer",
                    "DOUBLE": "number",
                    "FLOAT": "number",
                    "BOOLEAN": "boolean",
                    "DATE": "date",
                    "TIMESTAMP": "datetime",
                    "TIME": "time",
                }
                for row in df_desc:
                    col_name = str(row[0])
                    duck_type = str(row[1]).upper()
                    matched_type = "string"
                    for k, v in type_map.items():
                        if k in duck_type:
                            matched_type = v
                            break
                    fields.append({
                        "name": col_name,
                        "type": matched_type,
                        "description": f"Columna {col_name}",
                    })
                return {"fields": fields}
            except Exception:
                pass

        # Fallback to pure python csv sniffer
        fields = []
        if os.path.exists(path_str):
            try:
                with open(path_str, "r", encoding=encoding, errors="replace") as f:
                    sample = f.read(8192)
                    delim = delimiter
                    if not delim:
                        try:
                            dialect = csv.Sniffer().sniff(sample)
                            delim = dialect.delimiter
                        except Exception:
                            delim = ","
                    f.seek(0)
                    reader = csv.reader(f, delimiter=delim)
                    headers = next(reader, [])
                    for h in headers:
                        fields.append({
                            "name": h.strip(),
                            "type": "string",
                            "description": f"Columna {h.strip()}",
                        })
            except Exception:
                pass
        return {"fields": fields}

    @classmethod
    def infer_schema_from_parquet(cls, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Infers Frictionless schema from Parquet file using DuckDB."""
        path_str = str(file_path)
        fields = []
        if duckdb is not None and os.path.exists(path_str):
            try:
                con = duckdb.connect(":memory:")
                df_desc = con.execute(f"DESCRIBE SELECT * FROM parquet_scan('{path_str}')").fetchall()
                type_map = {
                    "VARCHAR": "string",
                    "BIGINT": "integer",
                    "INTEGER": "integer",
                    "SMALLINT": "integer",
                    "DOUBLE": "number",
                    "FLOAT": "number",
                    "BOOLEAN": "boolean",
                    "DATE": "date",
                    "TIMESTAMP": "datetime",
                }
                for row in df_desc:
                    col_name = str(row[0])
                    duck_type = str(row[1]).upper()
                    matched_type = "string"
                    for k, v in type_map.items():
                        if k in duck_type:
                            matched_type = v
                            break
                    fields.append({
                        "name": col_name,
                        "type": matched_type,
                        "description": f"Columna {col_name}",
                    })
                return {"fields": fields}
            except Exception:
                pass
        return {"fields": fields}

    @classmethod
    def inspect_zip_resource(cls, zip_path: Union[str, Path]) -> Dict[str, Any]:
        """Inspects inner members of a zip file and extracts nested resource descriptors."""
        path_obj = Path(zip_path)
        inner_resources = []
        if path_obj.exists() and zipfile.is_zipfile(path_obj):
            with zipfile.ZipFile(path_obj, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir() or info.filename.startswith("__MACOSX"):
                        continue
                    fname = os.path.basename(info.filename)
                    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
                    if ext in ("csv", "tsv", "parquet", "json", "jsonl"):
                        inner_res: Dict[str, Any] = {
                            "name": fname.rsplit(".", 1)[0],
                            "type": "table",
                            "path": info.filename,
                            "format": ext,
                            "mediatype": f"text/{ext}" if ext in ("csv", "tsv") else f"application/{ext}",
                            "description": f"Recurso interno {fname} contenido en archivo comprimido.",
                        }
                        inner_resources.append(inner_res)
        return {
            "path": str(path_obj),
            "mediatype": "zip",
            "resources": inner_resources,
        }

    @classmethod
    def build_datapackage(
        cls,
        name: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        resources: Optional[List[Dict[str, Any]]] = None,
        files: Optional[List[Union[str, Path]]] = None,
        output_file: Optional[Union[str, Path]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DataPackageBuildResult:
        """
        Builds a full Frictionless / OKF v0.2 DataPackage dictionary and optionally writes it to YAML.
        """
        pkg_title = title or name.replace("-", " ").replace("_", " ").title()
        datapackage: Dict[str, Any] = {
            "name": name,
            "title": pkg_title,
            "description": description or f"Data Product package for {pkg_title}",
        }

        # Merge additional metadata (spatial, temporal, quality, etc.)
        if metadata:
            for k, v in metadata.items():
                if k not in datapackage:
                    datapackage[k] = v

        all_resources: List[Dict[str, Any]] = []

        # Explicit resources provided
        if resources:
            for r in resources:
                all_resources.append(dict(r))

        # Files to inspect and add
        if files:
            for f in files:
                fpath = Path(f)
                ext = fpath.suffix.lower()
                fname = fpath.name
                base_name = fpath.stem

                if ext == ".zip":
                    zip_res = cls.inspect_zip_resource(fpath)
                    all_resources.append(zip_res)
                elif ext in (".csv", ".tsv"):
                    schema = cls.infer_schema_from_csv(fpath, delimiter="\t" if ext == ".tsv" else None)
                    all_resources.append({
                        "name": base_name,
                        "type": "table",
                        "path": fname,
                        "format": ext.lstrip("."),
                        "mediatype": "text/tab-separated-values" if ext == ".tsv" else "text/csv",
                        "description": f"Tabla de datos {fname}",
                        "schema": schema,
                    })
                elif ext == ".parquet":
                    schema = cls.infer_schema_from_parquet(fpath)
                    all_resources.append({
                        "name": base_name,
                        "type": "table",
                        "path": fname,
                        "format": "parquet",
                        "mediatype": "application/vnd.apache.parquet",
                        "description": f"Tabla columnar Parquet {fname}",
                        "schema": schema,
                    })
                elif ext in (".json", ".jsonl"):
                    all_resources.append({
                        "name": base_name,
                        "type": "table",
                        "path": fname,
                        "format": ext.lstrip("."),
                        "mediatype": "application/json",
                        "description": f"Archivo de datos {fname}",
                    })
                else:
                    all_resources.append({
                        "name": base_name,
                        "path": fname,
                        "description": f"Recurso de datos {fname}",
                    })

        datapackage["resources"] = all_resources

        # Render YAML / JSON
        if yaml is not None:
            yaml_str = yaml.dump(datapackage, sort_keys=False, allow_unicode=True)
        else:
            yaml_str = json.dumps(datapackage, indent=2, ensure_ascii=False)

        out_path_str = None
        if output_file:
            out_p = Path(output_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as out_f:
                out_f.write(yaml_str)
            out_path_str = str(out_p.resolve())

        return DataPackageBuildResult(
            name=name,
            title=pkg_title,
            datapackage=datapackage,
            yaml_content=yaml_str,
            output_path=out_path_str,
            generated_concepts=(),
        )
