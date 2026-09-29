from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple
import duckdb

# Matches canonical triad table names: "catalogo:dataset:resource" or 'catalogo:dataset:resource'
TRIAD_PATTERN = re.compile(r'["\']?([a-zA-Z0-9_\-\.]+):([a-zA-Z0-9_\-\.]+):([a-zA-Z0-9_\-\.]+)["\']?')

class DuckDBQueryEngine:
    """Full ANSI/DuckDB SQL execution engine with canonical triad resolution and format normalization."""

    def __init__(self, catalog_resolver: Optional[Any] = None):
        self.conn = duckdb.connect(database=":memory:")
        self.catalog_resolver = catalog_resolver
        self._registered_views: set[str] = set()

    def execute_sql(self, sql_query: str, table_mapping: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Executes a full SQL query against registered or dynamically resolved triad tables.
        
        Args:
            sql_query: ANSI SQL string (e.g. 'SELECT departamento, SUM(votos_validos) FROM "bolivia:elecciones:votos" GROUP BY departamento')
            table_mapping: Optional direct mapping of triad to physical file/URL (for tests/custom overrides).
        """
        # 1. Extract all triads referenced in the query
        triads = self._extract_triads(sql_query)

        # 2. Register virtual views in DuckDB for each triad
        clean_sql = sql_query
        for triad_str, (cat, ds, res) in triads.items():
            physical_path = None
            if table_mapping and triad_str in table_mapping:
                physical_path = table_mapping[triad_str]
            elif self.catalog_resolver:
                physical_path = self.catalog_resolver(cat, ds, res)
            
            if not physical_path:
                # If path exists directly on local disk matching resource
                if os.path.exists(res):
                    physical_path = res

            if physical_path:
                self.register_table(triad_str, physical_path)

        # 3. Execute query with DuckDB
        try:
            rel = self.conn.sql(sql_query)
            if rel is None:
                return {"columns": [], "rows": [], "row_count": 0}

            columns = rel.columns
            rows = rel.fetchall()

            # Convert row tuples to list of lists (JSON-serializable)
            formatted_rows = [list(r) for r in rows]

            return {
                "columns": columns,
                "rows": formatted_rows,
                "row_count": len(formatted_rows),
            }
        except Exception as e:
            raise RuntimeError(f"DuckDB SQL execution error: {e}") from e

    def register_table(self, table_name: str, file_path_or_url: str):
        """
        Registers a physical resource as a DuckDB virtual view, resolving format heterogeneity.
        Supported formats: Parquet, CSV, TSV, JSON, JSONL.
        """
        read_expr = self._get_read_expression(file_path_or_url)
        # Register view with quoted triad name
        view_sql = f'CREATE OR REPLACE VIEW "{table_name}" AS SELECT * FROM {read_expr}'
        self.conn.execute(view_sql)
        self._registered_views.add(table_name)

    def _get_read_expression(self, path: str) -> str:
        clean_path = path.replace("file://", "")
        lower = clean_path.lower()

        if lower.endswith(".parquet") or lower.endswith(".pq"):
            return f"read_parquet('{clean_path}')"
        elif lower.endswith(".json") or lower.endswith(".jsonl"):
            return f"read_json_auto('{clean_path}')"
        elif lower.endswith(".tsv"):
            return f"read_csv_auto('{clean_path}', delim='\\t')"
        else:
            # Default to auto-detecting CSV
            return f"read_csv_auto('{clean_path}')"

    def _extract_triads(self, query: str) -> Dict[str, Tuple[str, str, str]]:
        found = {}
        for m in TRIAD_PATTERN.finditer(query):
            triad_str = f"{m.group(1)}:{m.group(2)}:{m.group(3)}"
            found[triad_str] = (m.group(1), m.group(2), m.group(3))
        return found
