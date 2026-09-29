from __future__ import annotations

import datetime
from decimal import Decimal
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
import duckdb

# Matches table names in FROM and JOIN clauses (quoted or unquoted)
TABLE_REF_PATTERN = re.compile(
    r'\b(?:FROM|JOIN)\s+(?:ONLY\s+)?(?:["\']([^"\']+)["\']|([a-zA-Z0-9_\-\.:]+))',
    re.IGNORECASE
)

# Matches any quoted identifier containing colons (e.g. "dataset:resource" or "cat:ds:res")
QUOTED_COLON_PATTERN = re.compile(r'["\']([^"\':\s]+:[^"\']+)["\']')

def slugify(text: str) -> str:
    """Sanitizes text replacing non-alphanumeric chars with underscores."""
    return re.sub(r'[^a-zA-Z0-9]+', '_', text).lower().strip('_')

def _normalize_cell_value(val: Any) -> Any:
    """Recursively converts DuckDB/Python types (Decimal, datetime, date, UUID, bytes) to JSON-serializable primitives."""
    if val is None:
        return None
    if isinstance(val, (int, str, bool)):
        return val
    if isinstance(val, float):
        return val
    if isinstance(val, Decimal):
        return int(val) if val % 1 == 0 else float(val)
    if isinstance(val, (datetime.date, datetime.datetime, datetime.time)):
        return val.isoformat()
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, (list, tuple)):
        return [_normalize_cell_value(x) for x in val]
    if isinstance(val, dict):
        return {str(k): _normalize_cell_value(v) for k, v in val.items()}
    try:
        import numpy as np
        if isinstance(val, (np.integer,)):
            return int(val)
        if isinstance(val, (np.floating,)):
            return float(val)
        if isinstance(val, (np.bool_,)):
            return bool(val)
    except ImportError:
        pass
    return str(val)

class DuckDBQueryEngine:
    """Full ANSI/DuckDB SQL execution engine with canonical triad resolution and format normalization."""

    def __init__(self, catalog_resolver: Optional[Any] = None):
        self.conn = duckdb.connect(database=":memory:")
        self.catalog_resolver = catalog_resolver
        self._registered_views: Set[str] = set()

    def execute_sql(self, sql_query: str, table_mapping: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Executes a full SQL query against registered or dynamically resolved triad tables.
        
        Args:
            sql_query: ANSI SQL string (e.g. 'SELECT departamento, SUM(votos_validos) FROM "bolivia:elecciones:votos" GROUP BY departamento')
            table_mapping: Optional direct mapping of triad to physical file/URL (for tests/custom overrides).
        """
        # 1. Extract all table references in the query
        tables = self._extract_table_references(sql_query)

        # 2. Resolve and register virtual views in DuckDB for each table reference
        for table_ref in tables:
            physical_path = None
            if table_mapping and table_ref in table_mapping:
                physical_path = table_mapping[table_ref]
            elif self.catalog_resolver:
                physical_path = self.catalog_resolver(table_ref)

            if not physical_path:
                physical_path = self._resolve_table_locally(table_ref)

            if physical_path:
                self.register_table_aliases(table_ref, physical_path)

        # 3. Execute query with DuckDB
        try:
            rel = self.conn.sql(sql_query)
            if rel is None:
                return {"columns": [], "rows": [], "row_count": 0}

            columns = rel.columns
            rows = rel.fetchall()

            # Convert row tuples to list of lists (JSON-serializable)
            formatted_rows = [[_normalize_cell_value(cell) for cell in r] for r in rows]

            return {
                "columns": columns,
                "rows": formatted_rows,
                "row_count": len(formatted_rows),
            }
        except Exception as e:
            raise RuntimeError(f"DuckDB SQL execution error: {e}") from e

    def register_table(self, table_name: str, file_path_or_url: str):
        """Backward-compatible alias for register_table_aliases."""
        self.register_table_aliases(table_name, file_path_or_url)

    def register_table_aliases(self, table_ref: str, file_path_or_url: str):
        """
        Registers a physical resource as a DuckDB virtual view under multiple canonical and slugified aliases.
        """
        read_expr = self._get_read_expression(file_path_or_url)
        aliases = self._generate_aliases(table_ref)

        for alias in aliases:
            if alias not in self._registered_views:
                view_sql = f'CREATE OR REPLACE VIEW "{alias}" AS SELECT * FROM {read_expr}'
                try:
                    self.conn.execute(view_sql)
                    self._registered_views.add(alias)
                    # Also register unquoted if valid SQL identifier
                    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', alias):
                        self.conn.execute(f'CREATE OR REPLACE VIEW {alias} AS SELECT * FROM {read_expr}')
                except Exception:
                    pass

    def _generate_aliases(self, table_ref: str) -> List[str]:
        aliases = [table_ref]
        clean_slug = slugify(table_ref)
        if clean_slug:
            aliases.append(clean_slug)

        if ":" in table_ref:
            parts = table_ref.split(":")
            # If 3 parts (cat:ds:res) -> add ds:res
            if len(parts) == 3:
                aliases.append(f"{parts[1]}:{parts[2]}")
                aliases.append(parts[1])
                aliases.append(slugify(f"{parts[1]}_{parts[2]}"))
            elif len(parts) == 2:
                # ds:res -> add ds
                aliases.append(parts[0])
                aliases.append(slugify(f"{parts[0]}_{parts[1]}"))

        return list(dict.fromkeys(aliases))

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
            return f"read_csv_auto('{clean_path}')"

    def _extract_table_references(self, query: str) -> List[str]:
        candidates = []
        for m in TABLE_REF_PATTERN.finditer(query):
            table = m.group(1) or m.group(2)
            if table and table not in candidates:
                candidates.append(table.strip())

        for m in QUOTED_COLON_PATTERN.finditer(query):
            table = m.group(1)
            if table and table not in candidates:
                candidates.append(table.strip())

        return candidates

    def _resolve_table_locally(self, table_ref: str) -> Optional[str]:
        """Searches local projects and datasets to locate data files."""
        # Check direct path
        if os.path.exists(table_ref):
            return os.path.abspath(table_ref)

        # Decompose identifier
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

        keywords = [dataset.lower(), slugify(resource)]
        for w in re.split(r'[^a-zA-Z0-9]+', resource):
            if len(w) > 3:
                keywords.append(w.lower())

        # Search sibling project directories
        search_roots = [
            os.path.abspath("core-go/testdata"),
            os.path.abspath(".datamesh/cache"),
            "/home/andreschirinos/Proyectos",
        ]

        # 1. Search in testdata and cache first
        for root in search_roots[:2]:
            if os.path.exists(root):
                for f in os.listdir(root):
                    full_p = os.path.join(root, f)
                    if os.path.isfile(full_p) and full_p.endswith((".parquet", ".csv", ".json", ".tsv")):
                        f_low = f.lower()
                        if any(kw in f_low for kw in keywords if len(kw) > 3):
                            return full_p

        # 2. Targeted search across /home/andreschirinos/Proyectos
        proyectos_dir = "/home/andreschirinos/Proyectos"
        if os.path.exists(proyectos_dir):
            for proj in os.listdir(proyectos_dir):
                proj_dir = os.path.join(proyectos_dir, proj)
                if not os.path.isdir(proj_dir):
                    continue
                # Target data directories only
                for sub in ["data/consolidated", "data", "dist/data", "knowledge/nodes"]:
                    target_dir = os.path.join(proj_dir, sub)
                    if os.path.exists(target_dir):
                        for root_dir, _, files in os.walk(target_dir):
                            # Prefer parquet over csv
                            sorted_files = sorted(files, key=lambda f: (0 if f.endswith(".parquet") else 1))
                            for f in sorted_files:
                                if f.endswith((".parquet", ".csv", ".json", ".tsv")):
                                    f_low = f.lower()
                                    if dataset.lower() in f_low or any(kw in f_low for kw in keywords if len(kw) > 4):
                                        return os.path.join(root_dir, f)

        return None
