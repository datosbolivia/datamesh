from __future__ import annotations

import csv
import json
import os
import re
from typing import Any, Dict, List, Optional, Set
from datamesh.ports.engine import QueryEnginePort
from datamesh.constants import DEFAULT_CACHE_DIR, get_workspace_search_dirs

class InMemTabularQueryEngine(QueryEnginePort):
    """
    Pure Python tabular query engine executing column selection, filters, and limits
    over CSV, TSV, and JSON datasets without external C-extensions.
    """

    def __init__(
        self,
        catalog_resolver: Optional[Any] = None,
        resolver_usecase: Optional[Any] = None,
    ):
        self.catalog_resolver = catalog_resolver
        self.resolver_usecase = resolver_usecase
        self._table_bindings: Dict[str, str] = {}

    @property
    def name(self) -> str:
        return "inmem"

    def supports_format(self, format_name: str) -> bool:
        norm = format_name.lower().strip().lstrip(".")
        return norm in ("csv", "tsv", "json", "jsonl", "txt")

    def supports_cross_format_join(self) -> bool:
        return False

    def register_table(self, table_ref: str, file_path_or_url: str) -> None:
        self._table_bindings[table_ref] = file_path_or_url

    def execute_sql(
        self,
        sql_query: str,
        table_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes basic ANSI SQL (SELECT, WHERE, LIMIT) in pure Python over tabular data.
        """
        # Parse table name
        match = re.search(r'\bFROM\s+(?:ONLY\s+)?(?:["\']([^"\']+)["\']|([a-zA-Z0-9_\-\.:]+))', sql_query, re.IGNORECASE)
        if not match:
            raise ValueError(f"Could not extract FROM table reference from SQL query: {sql_query}")

        table_ref = (match.group(1) or match.group(2)).strip()

        # Resolve physical path
        physical_path = None
        if table_mapping and table_ref in table_mapping:
            physical_path = table_mapping[table_ref]
        elif table_ref in self._table_bindings:
            physical_path = self._table_bindings[table_ref]
        elif self.resolver_usecase:
            resolved = self.resolver_usecase.resolve(table_ref)
            if resolved:
                physical_path = str(resolved.local_path)

        if not physical_path and self.catalog_resolver:
            physical_path = self.catalog_resolver(table_ref)

        if not physical_path:
            physical_path = self._resolve_table_locally(table_ref)

        if not physical_path:
            raise RuntimeError(f"InMem engine could not resolve table '{table_ref}' to any physical resource.")

        # Read dataset into rows
        headers, rows = self._read_data_file(physical_path)

        # Parse LIMIT
        limit_match = re.search(r'\bLIMIT\s+(\d+)', sql_query, re.IGNORECASE)
        limit = int(limit_match.group(1)) if limit_match else None

        # Parse WHERE condition (simple equality: col = 'val' or col = val)
        where_match = re.search(r'\bWHERE\s+([a-zA-Z0-9_]+)\s*=\s*(?:["\']([^"\']+)["\']|([^\s;]+))', sql_query, re.IGNORECASE)
        filter_col = None
        filter_val = None
        if where_match:
            filter_col = where_match.group(1).lower().strip()
            filter_val = (where_match.group(2) or where_match.group(3)).lower().strip()

        # Filter rows
        filtered_rows: List[List[Any]] = []
        col_index = {h.lower().strip(): idx for idx, h in enumerate(headers)}

        for r in rows:
            if filter_col and filter_val:
                idx = col_index.get(filter_col)
                if idx is None or idx >= len(r) or str(r[idx]).lower().strip() != filter_val:
                    continue
            filtered_rows.append(r)
            if limit and len(filtered_rows) >= limit:
                break

        # Parse SELECT columns
        select_match = re.search(r'\bSELECT\s+(.*?)\s+\bFROM\b', sql_query, re.IGNORECASE | re.DOTALL)
        if not select_match:
            return {"columns": headers, "rows": filtered_rows, "row_count": len(filtered_rows)}

        cols_str = select_match.group(1).strip()
        if cols_str == "*":
            return {"columns": headers, "rows": filtered_rows, "row_count": len(filtered_rows)}

        projected_cols = [c.strip() for c in cols_str.split(",")]
        proj_indices = []
        out_columns = []
        for c in projected_cols:
            c_norm = c.lower().strip()
            if c_norm in col_index:
                proj_indices.append(col_index[c_norm])
                out_columns.append(headers[col_index[c_norm]])

        if not proj_indices:
            return {"columns": headers, "rows": filtered_rows, "row_count": len(filtered_rows)}

        final_rows = [[r[idx] for idx in proj_indices if idx < len(r)] for r in filtered_rows]
        return {
            "columns": out_columns,
            "rows": final_rows,
            "row_count": len(final_rows),
        }

    def _read_data_file(self, path: str) -> Tuple[List[str], List[List[Any]]]:
        clean_p = path.replace("file://", "")
        lower = clean_p.lower()

        if lower.endswith(".tsv"):
            with open(clean_p, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                headers = next(reader, [])
                rows = [row for row in reader]
                return headers, rows

        elif lower.endswith((".json", ".jsonl")):
            with open(clean_p, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                f.seek(0)
                if first_line.startswith("["):
                    data = json.load(f)
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        headers = list(data[0].keys())
                        rows = [[item.get(h) for h in headers] for item in data]
                        return headers, rows
                # JSONL
                rows_dict = []
                for line in f:
                    line = line.strip()
                    if line:
                        rows_dict.append(json.loads(line))
                if rows_dict:
                    headers = list(rows_dict[0].keys())
                    rows = [[item.get(h) for h in headers] for item in rows_dict]
                    return headers, rows
            return [], []

        else:
            with open(clean_p, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                rows = [row for row in reader]
                return headers, rows

    def _resolve_table_locally(self, table_ref: str) -> Optional[str]:
        if os.path.exists(table_ref):
            return os.path.abspath(table_ref)

        dataset = ""
        resource = ""
        if ":" in table_ref:
            parts = table_ref.split(":")
            dataset = parts[-2]
            resource = parts[-1]
        else:
            parts = table_ref.split("_")
            dataset = parts[0]
            resource = table_ref

        search_roots = [
            os.path.abspath("core-go/testdata"),
            str(DEFAULT_CACHE_DIR),
            os.path.abspath(".datamesh/cache"),
        ]
        for s_dir in get_workspace_search_dirs():
            search_roots.append(str(s_dir))

        for root in search_roots:
            if os.path.exists(root):
                for dirpath, _, filenames in os.walk(root):
                    for f in filenames:
                        full_p = os.path.join(dirpath, f)
                        if os.path.isfile(full_p) and (resource.lower() in f.lower() or dataset.lower() in f.lower()):
                            if full_p.endswith((".csv", ".tsv", ".json", ".jsonl")):
                                return full_p
        return None
