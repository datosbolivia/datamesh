from __future__ import annotations

_CONTROL_CHARS = ("\x00", "\n", "\r")


def sql_string_literal(value: str) -> str:
    """Renders a safe single-quoted SQL string literal for DuckDB.

    Doubles embedded single quotes and rejects control characters that could
    break out of the literal (e.g. newline-separated stacked statements).
    """
    text = str(value)
    if any(c in text for c in _CONTROL_CHARS):
        raise ValueError("Illegal control character in SQL literal")
    return "'" + text.replace("'", "''") + "'"


def sql_identifier(name: str) -> str:
    """Renders a safe double-quoted SQL identifier for DuckDB."""
    text = str(name)
    if any(c in text for c in ('"', "\x00", "\n", "\r")):
        raise ValueError("Illegal character in SQL identifier")
    return '"' + text + '"'


def read_expression(path: str) -> str:
    """Builds a DuckDB table function expression for a local path, format inferred by extension."""
    literal = sql_string_literal(path)
    lower = path.lower()
    if lower.endswith((".parquet", ".pq")):
        return f"read_parquet({literal})"
    if lower.endswith((".json", ".jsonl")):
        return f"read_json_auto({literal})"
    if lower.endswith(".tsv"):
        return f"read_csv_auto({literal}, delim='\\t')"
    return f"read_csv_auto({literal})"
