from __future__ import annotations

import json
from typing import Any, Dict, Optional

from datamesh.adapters.go_bridge import GoCoreBridge
from datamesh.ports.engine import QueryEnginePort


class GoCoreQueryEngine(QueryEnginePort):
    """Query engine that delegates SQL execution to the compiled Go core runtime.

    All ctypes/C-ABI handling is owned by :class:`GoCoreBridge`; this engine only
    maps the query/options onto the ``DataMeshExecuteSQL`` symbol.
    """

    def __init__(
        self,
        lib_path: Optional[str] = None,
        lib_handle: Optional[Any] = None,
        bridge: Optional[GoCoreBridge] = None,
    ):
        self._bridge = bridge or GoCoreBridge(lib_path=lib_path, lib_handle=lib_handle)
        self._table_bindings: Dict[str, str] = {}

    @property
    def name(self) -> str:
        return "go"

    def is_available(self) -> bool:
        return self._bridge.available

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
        """Executes SQL via Go core ``DataMeshExecuteSQL`` C-ABI."""
        if not self._bridge.available:
            raise RuntimeError(
                "Go core shared library (libdatamesh.so) is not compiled or loaded. "
                "Build core-go/ with CGO_ENABLED=1 or use engine='duckdb' / engine='inmem'."
            )

        merged_mapping = dict(self._table_bindings)
        if table_mapping:
            merged_mapping.update(table_mapping)

        options = {"engine_name": "inmem", "table_mapping": merged_mapping}
        resp = self._bridge.call_raw("DataMeshExecuteSQL", sql_query, json.dumps(options))
        if resp is None:
            raise RuntimeError("Go core returned null response pointer")
        if not resp.get("success"):
            raise RuntimeError(f"Go core SQL execution error: {resp.get('error')}")
        return resp.get("data", {"columns": [], "rows": [], "row_count": 0})
