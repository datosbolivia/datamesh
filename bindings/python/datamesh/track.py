from __future__ import annotations

import functools
import hashlib
import inspect
import os
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

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

    if ext == ".py":
        cmd = ["python3", clean_script] + (args or [])
    elif ext == ".sh":
        cmd = ["bash", clean_script] + (args or [])
    else:
        cmd = [clean_script] + (args or [])

    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)

    start_time = datetime.now(timezone.utc)
    t0 = time.time()

    proc = subprocess.run(cmd, env=proc_env, capture_output=True, text=True)
    duration_ms = int((time.time() - t0) * 1000)
    end_time = datetime.now(timezone.utc)

    target_name = target or Path(clean_script).stem
    status = "SUCCESS" if proc.returncode == 0 else "FAILED"

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
        "sources": [
            {
                "name": Path(clean_script).name,
                "uri": clean_script,
                "format": ext.lstrip("."),
                "hash": code_hash,
            }
        ],
        "transformations": [
            {
                "step": f"run_{Path(clean_script).stem}",
                "tool": ext.lstrip(".") or "subprocess",
                "code_hash": code_hash,
                "params": {"args": args or []},
            }
        ],
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
    }
