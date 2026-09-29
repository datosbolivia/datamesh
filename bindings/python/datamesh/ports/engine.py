from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class QueryEnginePort(ABC):
    """Abstract port for query engine execution (DuckDB, InMem tabular, Go core runtime)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the engine (e.g. 'duckdb', 'inmem', 'go')."""
        ...

    @abstractmethod
    def supports_format(self, format_name: str) -> bool:
        """Checks if format (csv, parquet, json, tsv) is supported by this engine."""
        ...

    @abstractmethod
    def supports_cross_format_join(self) -> bool:
        """Checks whether the engine can join different formats in a single query."""
        ...

    @abstractmethod
    def execute_sql(
        self,
        sql_query: str,
        table_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes an ANSI/SQL query against registered or resolved tables.
        Returns a dictionary with 'columns', 'rows', and 'row_count'.
        """
        ...

    @abstractmethod
    def register_table(self, table_ref: str, file_path_or_url: str) -> None:
        """Registers a physical resource under a table alias."""
        ...
