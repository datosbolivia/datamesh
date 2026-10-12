from __future__ import annotations

import json
from typing import Any, Dict, Optional

from datamesh.adapters.engine.sql_utils import read_expression, sql_identifier, sql_string_literal
from datamesh.adapters.go_bridge import GoCoreBridge
from datamesh.adapters.web import fetch_text


class QueryResourceUseCase:
    """Queries a CSV/JSON/JSONL/tabular resource (Go core first, pure-Python fallback)."""

    def __init__(self, bridge: GoCoreBridge, resolver_usecase: Any):
        self._bridge = bridge
        self._resolver_usecase = resolver_usecase

    def execute(
        self,
        resource_uri: str,
        filters: Optional[Dict[str, str]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        options: Dict[str, Any] = {}
        if filters:
            options["filters"] = filters
        if limit:
            options["limit"] = limit
        go_result = self._bridge.call_with_options("DataMeshQueryResource", options, resource_uri)
        if go_result:
            return go_result

        return self._query_python(resource_uri, filters, limit)

    def _query_python(
        self,
        resource_uri: str,
        filters: Optional[Dict[str, str]],
        limit: Optional[int],
    ) -> Dict[str, Any]:
        import os

        target_path = resource_uri
        if not os.path.exists(target_path) and not target_path.startswith(("http://", "https://", "file://")):
            try:
                resolved = self._resolver_usecase.resolve(resource_uri)
                if resolved and resolved.local_path and os.path.exists(resolved.local_path):
                    target_path = str(resolved.local_path)
                    fmt = (resolved.format or "").lower()
                    if target_path.lower().endswith(".zip") or fmt == "zip":
                        from datamesh.adapters.storage.zip_extractor import extract_zip_tabular_resource
                        target_hint = None
                        if resolved.descriptor:
                            target_hint = resolved.descriptor.resource or resolved.descriptor.raw_reference
                        if not target_hint:
                            target_hint = os.path.basename(resource_uri)
                        extracted_p, _ = extract_zip_tabular_resource(target_path, target_hint=target_hint, preview_limit=limit)
                        if extracted_p:
                            target_path = extracted_p
            except Exception:
                pass

        duckdb_result = self._query_duckdb(target_path, filters, limit)
        if duckdb_result is not None:
            return duckdb_result

        raw_text = fetch_text(target_path, timeout=2)

        target_lower = target_path.lower()
        is_jsonl = target_lower.endswith(".jsonl") or (raw_text.lstrip().startswith("{") and "\n" in raw_text.strip())
        is_json_arr = target_lower.endswith(".json") or (raw_text.lstrip().startswith("[") and raw_text.rstrip().endswith("]"))

        if is_jsonl or is_json_arr:
            result = self._query_json(raw_text, is_json_arr, filters, limit)
            if result is not None:
                return result

        return self._query_csv(raw_text, filters, limit)

    def _query_duckdb(self, target_path: str, filters: Optional[Dict[str, str]], limit: Optional[int]) -> Optional[Dict[str, Any]]:
        if target_path.startswith(("http://", "https://")):
            return None
        try:
            import duckdb
            local_clean = target_path[7:] if target_path.startswith("file://") else target_path
            read_clause = read_expression(local_clean)
            where_clauses = []
            if filters:
                for k, v in filters.items():
                    where_clauses.append(f"{sql_identifier(k)} = {sql_string_literal(v)}")
            where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            limit_sql = f" LIMIT {int(limit)}" if limit else ""
            df = duckdb.query(f"SELECT * FROM {read_clause}{where_sql}{limit_sql}").to_df()
            cols = list(df.columns)
            rows = df.astype(str).values.tolist()
            return {"columns": cols, "rows": rows, "row_count": len(rows)}
        except Exception:
            return None

    def _query_json(
        self,
        raw_text: str,
        is_json_arr: bool,
        filters: Optional[Dict[str, str]],
        limit: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        objects: list = []
        if is_json_arr:
            try:
                loaded = json.loads(raw_text)
                if isinstance(loaded, list):
                    objects = [item for item in loaded if isinstance(item, dict)]
            except Exception:
                pass
        if not objects:
            for line in raw_text.splitlines():
                s_line = line.strip()
                if not s_line:
                    continue
                try:
                    obj = json.loads(s_line)
                    if isinstance(obj, dict):
                        objects.append(obj)
                except Exception:
                    continue

        if not objects:
            return None

        col_keys: list = []
        for obj in objects:
            for k in obj.keys():
                if k not in col_keys:
                    col_keys.append(k)

        matched_rows = []
        for obj in objects:
            matches = True
            if filters:
                for k, v in filters.items():
                    val = obj.get(k)
                    if val is None or str(val).strip().lower() != str(v).strip().lower():
                        matches = False
                        break
            if matches:
                row = [
                    json.dumps(obj[c], ensure_ascii=False) if isinstance(obj.get(c), (dict, list)) else ("" if obj.get(c) is None else str(obj.get(c)))
                    for c in col_keys
                ]
                matched_rows.append(row)
                if limit and len(matched_rows) >= limit:
                    break

        return {"columns": col_keys, "rows": matched_rows, "row_count": len(matched_rows)}

    def _query_csv(self, raw_text: str, filters: Optional[Dict[str, str]], limit: Optional[int]) -> Dict[str, Any]:
        import csv as _csv
        import io as _io
        reader = _csv.reader(_io.StringIO(raw_text))
        headers = next(reader, None)
        if not headers:
            return {"columns": [], "rows": [], "row_count": 0}

        headers_norm = [h.strip().lower() for h in headers]
        filter_indices: Dict[int, str] = {}
        if filters:
            for k, v in filters.items():
                kn = k.strip().lower()
                if kn in headers_norm:
                    filter_indices[headers_norm.index(kn)] = str(v).strip().lower()

        matched_rows = []
        for row in reader:
            matches = True
            for idx, exp_val in filter_indices.items():
                if idx >= len(row) or row[idx].strip().lower() != exp_val:
                    matches = False
                    break
            if matches:
                matched_rows.append(row)
                if limit and len(matched_rows) >= limit:
                    break

        return {"columns": headers, "rows": matched_rows, "row_count": len(matched_rows)}
