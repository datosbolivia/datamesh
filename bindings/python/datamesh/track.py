from __future__ import annotations

import functools
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Union

from datamesh.adapters.storage.sqlite_lineage import SQLiteLineageStore

_default_store: Optional[SQLiteLineageStore] = None


def get_lineage_store(db_path: Optional[str] = None) -> SQLiteLineageStore:
    """Returns the global or contextual SQLite lineage store."""
    global _default_store
    if db_path:
        return SQLiteLineageStore(db_path)
    if _default_store is None:
        _default_store = SQLiteLineageStore()
    return _default_store


def track_lineage(
    target: str,
    sources: Optional[List[str]] = None,
    step_name: Optional[str] = None,
    tool: str = "python",
    store: Optional[SQLiteLineageStore] = None,
) -> Callable:
    """Decorator that intercepts function execution, computes code hash and duration, 
    and records lineage in SQLite memory.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            s = store or get_lineage_store()
            start_time = datetime.now(timezone.utc)
            t0 = time.time()
            error = None
            result = None

            # Compute code hash
            try:
                src_code = inspect.getsource(fn)
                code_hash = hashlib.sha256(src_code.encode("utf-8")).hexdigest()
            except Exception:
                code_hash = hashlib.sha256(fn.__name__.encode("utf-8")).hexdigest()

            s_name = step_name or fn.__name__

            try:
                result = fn(*args, **kwargs)
                return result
            except Exception as e:
                error = e
                raise
            finally:
                duration_ms = int((time.time() - t0) * 1000)
                end_time = datetime.now(timezone.utc)
                exit_code = 0 if error is None else 1

                # Format source list
                source_dicts = []
                for src in (sources or []):
                    source_dicts.append({
                        "name": Path(src).name,
                        "uri": src,
                        "format": Path(src).suffix.lstrip("."),
                    })

                # Check if result is a file path produced
                artifacts = []
                if isinstance(result, (str, Path)) and os.path.exists(str(result)) and os.path.isfile(str(result)):
                    artifacts.append(str(result))

                exec_record = {
                    "target_triad": target,
                    "entrypoint": f"{fn.__module__}:{fn.__name__}",
                    "script_path": inspect.getfile(fn) if hasattr(fn, "__code__") else None,
                    "command": f"python function {fn.__name__}()",
                    "status": "SUCCESS" if error is None else "FAILED",
                    "exit_code": exit_code,
                    "started_at": start_time.isoformat(),
                    "completed_at": end_time.isoformat(),
                    "duration_ms": duration_ms,
                    "sources": source_dicts,
                    "transformations": [
                        {
                            "step": s_name,
                            "tool": tool,
                            "code_hash": code_hash,
                            "params": {k: str(v) for k, v in kwargs.items()}
                        }
                    ],
                    "artifacts": artifacts,
                }
                s.record_execution(exec_record)

        return wrapper
    return decorator


@contextmanager
def track_execution(
    target: str,
    step_name: str = "block",
    sources: Optional[List[str]] = None,
    tool: str = "python",
    store: Optional[SQLiteLineageStore] = None,
) -> Iterator[Dict[str, Any]]:
    """Context manager tracking a block of computation and recording provenance in SQLite."""
    s = store or get_lineage_store()
    start_time = datetime.now(timezone.utc)
    t0 = time.time()
    context_data: Dict[str, Any] = {
        "sources": sources or [],
        "artifacts": [],
        "status": "RUNNING",
    }
    error = None

    try:
        yield context_data
    except Exception as e:
        error = e
        raise
    finally:
        duration_ms = int((time.time() - t0) * 1000)
        end_time = datetime.now(timezone.utc)
        exit_code = 0 if error is None else 1

        source_dicts = []
        for src in context_data.get("sources", []):
            source_dicts.append({
                "name": Path(src).name,
                "uri": src,
                "format": Path(src).suffix.lstrip("."),
            })

        exec_record = {
            "target_triad": target,
            "entrypoint": "context_manager:track_execution",
            "command": f"computation block '{step_name}'",
            "status": "SUCCESS" if error is None else "FAILED",
            "exit_code": exit_code,
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "duration_ms": duration_ms,
            "sources": source_dicts,
            "transformations": [
                {
                    "step": step_name,
                    "tool": tool,
                    "code_hash": hashlib.sha256(step_name.encode("utf-8")).hexdigest(),
                }
            ],
            "artifacts": context_data.get("artifacts", []),
        }
        s.record_execution(exec_record)


def _emit_provenance_event(event: Dict[str, Any]) -> None:
    """Appends a structured JSONL event to OKF_PROVENANCE_OUT if configured."""
    out_path = os.environ.get("OKF_PROVENANCE_OUT")
    if not out_path:
        return
    payload = dict(event)
    payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    try:
        with open(out_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


def read_provenance_events(jsonl_path: str) -> List[Dict[str, Any]]:
    """Reads all valid JSONL provenance events from a sidecar file."""
    events: List[Dict[str, Any]] = []
    if not jsonl_path or not os.path.exists(jsonl_path):
        return events
    with open(jsonl_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return events


def _infer_fields_and_quality(data_or_path: Any) -> Dict[str, Any]:
    """Infers Frictionless schema fields, row count, and completeness from a DataFrame or file path."""
    info: Dict[str, Any] = {}
    # 1. Pandas DataFrame / DuckDB-like object
    if hasattr(data_or_path, "dtypes") and hasattr(data_or_path, "shape"):
        try:
            rows = int(data_or_path.shape[0])
            cols = int(data_or_path.shape[1])
            fields = []
            for col_name, dtype in data_or_path.dtypes.items():
                dt = str(dtype).lower()
                if "int" in dt:
                    ftype = "integer"
                elif "float" in dt or "double" in dt or "decimal" in dt:
                    ftype = "number"
                elif "bool" in dt:
                    ftype = "boolean"
                elif "datetime" in dt or "timestamp" in dt:
                    ftype = "datetime"
                elif "date" in dt:
                    ftype = "date"
                else:
                    ftype = "string"
                fields.append({"name": str(col_name), "type": ftype})
            total_cells = rows * cols
            null_cells = int(data_or_path.isna().sum().sum()) if total_cells > 0 else 0
            completeness = round((total_cells - null_cells) / total_cells, 6) if total_cells > 0 else 1.0
            info["row_count"] = rows
            info["completeness"] = completeness
            info["fields"] = fields
            return info
        except Exception:
            pass

    # 2. Local tabular file via DuckDB (if available)
    if isinstance(data_or_path, (str, Path)) and os.path.isfile(str(data_or_path)):
        p_str = str(data_or_path)
        ext = Path(p_str).suffix.lower()
        try:
            import duckdb
            con = duckdb.connect(":memory:")
            if ext in (".parquet", ".pq"):
                rel_expr = f"read_parquet('{p_str}')"
            elif ext in (".json", ".jsonl"):
                rel_expr = f"read_json_auto('{p_str}')"
            elif ext == ".tsv":
                rel_expr = f"read_csv_auto('{p_str}', delim='\\t')"
            else:
                rel_expr = f"read_csv_auto('{p_str}')"
            desc = con.execute(f"DESCRIBE SELECT * FROM {rel_expr}").fetchall()
            fields = []
            for row in desc:
                c_name = str(row[0])
                d_type = str(row[1]).upper()
                ftype = "string"
                if any(k in d_type for k in ("BIGINT", "INTEGER", "SMALLINT", "TINYINT")):
                    ftype = "integer"
                elif any(k in d_type for k in ("DOUBLE", "FLOAT", "DECIMAL")):
                    ftype = "number"
                elif "BOOLEAN" in d_type:
                    ftype = "boolean"
                elif "TIMESTAMP" in d_type:
                    ftype = "datetime"
                elif "DATE" in d_type:
                    ftype = "date"
                fields.append({"name": c_name, "type": ftype})
            cnt_row = con.execute(f"SELECT COUNT(*) FROM {rel_expr}").fetchone()
            info["row_count"] = int(cnt_row[0]) if cnt_row else 0
            info["fields"] = fields
            return info
        except Exception:
            pass
    return info


@contextmanager
def step(
    name: str,
    tool: str = "python",
    params: Optional[Dict[str, Any]] = None,
    target: Optional[str] = None,
    sources: Optional[List[str]] = None,
    store: Optional[SQLiteLineageStore] = None,
) -> Iterator[Dict[str, Any]]:
    """Streamlit/Papermill-style step context manager emitting OKF_PROVENANCE_OUT events
    and optionally persisting to SQLiteLineageStore."""
    t0 = time.time()
    step_ctx: Dict[str, Any] = {"name": name, "metrics": {}}
    err: Optional[Exception] = None
    try:
        yield step_ctx
    except Exception as e:
        err = e
        raise
    finally:
        duration_ms = int((time.time() - t0) * 1000)
        status = "ok" if err is None else f"failed: {err}"
        _emit_provenance_event({
            "type": "step",
            "step": name,
            "tool": tool,
            "duration_ms": duration_ms,
            "status": status,
            "params": params or {},
            "metrics": step_ctx.get("metrics") or {},
        })
        if target:
            try:
                s = store or get_lineage_store()
                s.record_execution({
                    "target_triad": target,
                    "entrypoint": f"step:{name}",
                    "command": f"step '{name}' ({tool})",
                    "status": "SUCCESS" if err is None else "FAILED",
                    "exit_code": 0 if err is None else 1,
                    "duration_ms": duration_ms,
                    "sources": [{"name": Path(src).name, "uri": src, "format": Path(src).suffix.lstrip(".")} for src in (sources or [])],
                    "transformations": [{"step": name, "tool": tool, "code_hash": hashlib.sha256(name.encode()).hexdigest(), "params": params or {}}],
                })
            except Exception:
                pass


def log_input(uri_or_triad: str, resource: Optional[str] = None, fmt: Optional[str] = None, hash_sha256: Optional[str] = None) -> None:
    """Records an input dataset/resource consumed by the ETL script or notebook."""
    _emit_provenance_event({
        "type": "input",
        "uri": uri_or_triad,
        "resource": resource or "",
        "format": fmt or Path(uri_or_triad).suffix.lstrip("."),
        "hash_sha256": hash_sha256 or "",
    })


def log_output(
    path: Union[str, Path],
    resource: Optional[str] = None,
    fmt: Optional[str] = None,
    data: Optional[Any] = None,
) -> Dict[str, Any]:
    """Records an output Distribution file, computing SHA-256, byte size, and inferring schema fields."""
    p = Path(path)
    res_name = resource or p.stem
    inferred_fmt = fmt or p.suffix.lstrip(".").lower()
    sha = ""
    size = 0
    if p.exists() and p.is_file():
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        sha = h.hexdigest()
        size = p.stat().st_size

    meta = _infer_fields_and_quality(data if data is not None else p)
    ev: Dict[str, Any] = {
        "type": "output",
        "resource": res_name,
        "path": str(path),
        "format": inferred_fmt,
        "hash_sha256": sha,
        "bytes_count": size,
    }
    if "row_count" in meta:
        ev["row_count"] = meta["row_count"]
    if "completeness" in meta:
        ev["completeness"] = meta["completeness"]
    if "fields" in meta:
        ev["fields"] = meta["fields"]
    _emit_provenance_event(ev)
    return ev


def log_quality(data: Any, resource: str = "dataset", min_rows: Optional[int] = None, min_completeness: Optional[float] = None) -> Dict[str, Any]:
    """Computes row count and completeness quality metrics, emitting quality and drift events."""
    meta = _infer_fields_and_quality(data)
    row_count = int(meta.get("row_count", 0))
    completeness = float(meta.get("completeness", 1.0))
    _emit_provenance_event({
        "type": "quality",
        "resource": resource,
        "row_count": row_count,
        "completeness": completeness,
    })
    if min_rows is not None and row_count < min_rows:
        _emit_provenance_event({
            "type": "drift",
            "resource": resource,
            "severity": "ERROR",
            "message": f"Quality threshold failed for '{resource}': row_count {row_count} < min_rows {min_rows}",
        })
    if min_completeness is not None and completeness < min_completeness:
        _emit_provenance_event({
            "type": "drift",
            "resource": resource,
            "severity": "WARNING",
            "message": f"Quality threshold failed for '{resource}': completeness {completeness:.4f} < {min_completeness:.4f}",
        })
    return meta


def log_metric(name: str, value: Any, step_name: Optional[str] = None) -> None:
    """Records a named engineering metric emitted during an ETL step."""
    _emit_provenance_event({
        "type": "metric",
        "step": step_name or "",
        "message": name,
        "metrics": {name: value},
    })


def log_note(message: str) -> None:
    """Records a Markdown narrative note for the optional ETL run report."""
    _emit_provenance_event({
        "type": "note",
        "message": message,
    })


def run_script(
    script_path: str,
    target: Optional[str] = None,
    args: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None,
    store: Optional[SQLiteLineageStore] = None,
) -> Dict[str, Any]:
    """Runs a script (Python, Bash, or executable) in a monitored subprocess,
    capturing execution metrics and persisting lineage in SQLite.
    """
    clean_script = str(Path(script_path).resolve())
    if not os.path.exists(clean_script):
        raise FileNotFoundError(f"Script not found: {clean_script}")

    s = store or get_lineage_store()
    code_hash = s.compute_sha256(clean_script)
    ext = Path(clean_script).suffix.lower()
    if ext == ".ipynb":
        from datamesh.usecases.run_notebook import run_notebook
        return run_notebook(clean_script, target=target, store=s)

    if ext == ".py":
        cmd = [sys.executable, clean_script] + (args or [])
    elif ext == ".sh":
        cmd = ["bash", clean_script] + (args or [])
    else:
        cmd = [clean_script] + (args or [])

    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)

    created_tmp_prov = False
    prov_path = proc_env.get("OKF_PROVENANCE_OUT", "")
    if not prov_path:
        fd, prov_path = tempfile.mkstemp(prefix="okf-prov-", suffix=".jsonl")
        os.close(fd)
        proc_env["OKF_PROVENANCE_OUT"] = prov_path
        created_tmp_prov = True

    start_time = datetime.now(timezone.utc)
    t0 = time.time()

    try:
        proc = subprocess.run(cmd, env=proc_env, capture_output=True, text=True)
        duration_ms = int((time.time() - t0) * 1000)
        end_time = datetime.now(timezone.utc)
        events = read_provenance_events(prov_path)
    finally:
        if created_tmp_prov and prov_path and os.path.exists(prov_path):
            try:
                os.remove(prov_path)
            except Exception:
                pass

    target_name = target or Path(clean_script).stem
    status = "SUCCESS" if proc.returncode == 0 else "FAILED"

    sources_list = [
        {
            "name": Path(clean_script).name,
            "uri": clean_script,
            "format": ext.lstrip("."),
            "hash": code_hash,
        }
    ]
    for ev in events:
        if ev.get("type") == "input" and ev.get("uri"):
            sources_list.append({
                "name": ev.get("resource") or Path(ev["uri"]).name,
                "uri": ev["uri"],
                "format": ev.get("format", ""),
                "hash": ev.get("hash_sha256", ""),
            })

    transformations = [
        {
            "step": f"run_{Path(clean_script).stem}",
            "tool": ext.lstrip(".") or "subprocess",
            "code_hash": code_hash,
            "params": {"args": args or []},
        }
    ]
    for ev in events:
        if ev.get("type") == "step" and ev.get("step"):
            transformations.append({
                "step": ev["step"],
                "tool": ev.get("tool", "python"),
                "code_hash": code_hash,
                "params": ev.get("params") or {},
            })

    artifacts = [ev["path"] for ev in events if ev.get("type") in ("output", "distribution") and ev.get("path") and os.path.exists(ev["path"])]

    exec_record = {
        "target_triad": target_name,
        "script_path": clean_script,
        "entrypoint": Path(clean_script).name,
        "command": " ".join(cmd),
        "status": status,
        "exit_code": proc.returncode,
        "started_at": start_time.isoformat(),
        "completed_at": end_time.isoformat(),
        "duration_ms": duration_ms,
        "sources": sources_list,
        "transformations": transformations,
        "artifacts": artifacts,
    }

    exec_id = s.record_execution(exec_record)

    return {
        "id": exec_id,
        "status": status,
        "exit_code": proc.returncode,
        "duration_ms": duration_ms,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "script_hash": code_hash,
        "target": target_name,
        "events": events,
    }
