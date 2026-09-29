from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from datamesh.ports.engine import QueryEnginePort

class GoCoreQueryEngine(QueryEnginePort):
    """
    Query engine that delegates SQL execution to the compiled Go core runtime via C-ABI / ctypes.
    """

    def __init__(self, lib_path: Optional[str] = None, lib_handle: Optional[Any] = None):
        self._lib = lib_handle
        self._table_bindings: Dict[str, str] = {}
        if self._lib is None:
            target_path = lib_path or os.environ.get("DATAMESH_LIB_PATH", "libdatamesh.so")
            if os.path.exists(target_path):
                try:
                    import ctypes
                    self._lib = ctypes.CDLL(target_path)
                    self._lib.DataMeshExecuteSQL.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
                    self._lib.DataMeshExecuteSQL.restype = ctypes.c_char_p
                    self._lib.DataMeshFreeString.argtypes = [ctypes.c_char_p]
                    self._lib.DataMeshFreeString.restype = None
                except Exception:
                    self._lib = None

    @property
    def name(self) -> str:
        return "go"

    def is_available(self) -> bool:
        return self._lib is not None

    def supports_format(self, format_name: str) -> bool:
        norm = format_name.lower().strip().lstrip(".")
        return norm in ("csv", "tsv", "parquet", "json", "txt")

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
        Executes SQL via Go core DataMeshExecuteSQL C-ABI.
        """
        if not self._lib:
            raise RuntimeError(
                "Go core shared library (libdatamesh.so) is not compiled or loaded. "
                "Build core-go/ with CGO_ENABLED=1 or use engine='duckdb' / engine='inmem'."
            )

        merged_mapping = dict(self._table_bindings)
        if table_mapping:
            merged_mapping.update(table_mapping)

        options = {
            "engine_name": "inmem",
            "table_mapping": merged_mapping,
        }
        opts_json = json.dumps(options)

        c_query = sql_query.encode("utf-8")
        c_opts = opts_json.encode("utf-8")

        raw_res = self._lib.DataMeshExecuteSQL(c_query, c_opts)
        try:
            if not raw_res:
                raise RuntimeError("Go core returned null response pointer")
            import ctypes
            res_str = ctypes.string_at(raw_res).decode("utf-8")
            parsed = json.loads(res_str)
            if not parsed.get("success", False):
                raise RuntimeError(f"Go core execution error: {parsed.get('error', 'unknown error')}")
            return parsed.get("data", {"columns": [], "rows": [], "row_count": 0})
        finally:
            if raw_res and hasattr(self._lib, "DataMeshFreeString"):
                self._lib.DataMeshFreeString(raw_res)
