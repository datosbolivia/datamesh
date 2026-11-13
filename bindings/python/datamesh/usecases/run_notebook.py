"""Parameterized Jupyter notebook execution via papermill with OKF provenance tracking."""

from __future__ import annotations

import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from datamesh.adapters.storage.sqlite_lineage import SQLiteLineageStore
from datamesh.track import get_lineage_store, read_provenance_events


def _render_notebook_report_markdown(
    notebook_path: Path,
    output_notebook: Path,
    parameters: Dict[str, Any],
    events: List[Dict[str, Any]],
    elapsed: float,
    error: Optional[str] = None,
) -> str:
    """Render an OKF-compatible Markdown run report for a notebook execution."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status = "error" if error else "success"
    lines = [
        "---",
        "type: run_report",
        f"script: {notebook_path}",
        f"output_notebook: {output_notebook}",
        f"status: {status}",
        f"executed_at: {now_iso}",
        f"duration_seconds: {elapsed:.2f}",
        "---",
        "",
        f"# Run Report: `{notebook_path.name}`",
        "",
        f"- **Status**: `{status}`",
        f"- **Executed at**: `{now_iso}`",
        f"- **Duration**: `{elapsed:.2f}s`",
        f"- **Output notebook**: `{output_notebook}`",
    ]
    if parameters:
        lines.append(f"- **Parameters**: `{parameters}`")
    if error:
        lines.extend(["", "## Error", "", f"```text\n{error}\n```"])

    inputs = [e for e in events if e.get("type") == "input"]
    outputs = [e for e in events if e.get("type") == "output"]
    steps = [e for e in events if e.get("type") == "step"]
    quality = [e for e in events if e.get("type") == "quality"]
    metrics = [e for e in events if e.get("type") == "metric"]
    notes = [e for e in events if e.get("type") == "note"]

    if inputs:
        lines.extend(["", "## Inputs", ""])
        for ev in inputs:
            lines.append(f"- `{ev.get('uri') or ev.get('resource')}` ({ev.get('format') or 'unknown'})")

    if outputs:
        lines.extend(["", "## Outputs", ""])
        for ev in outputs:
            rows = ev.get("row_count", "-")
            lines.append(f"- `{ev.get('path') or ev.get('resource')}` ({ev.get('format') or 'unknown'}, rows={rows})")

    if steps:
        lines.extend(["", "## Steps", ""])
        for ev in steps:
            lines.append(f"- **{ev.get('step') or 'step'}** ({ev.get('tool') or 'python'})")

    if quality:
        lines.extend(["", "## Quality Checks", ""])
        for ev in quality:
            lines.append(
                f"- `{ev.get('resource') or 'dataset'}`: rows={ev.get('row_count')}, "
                f"completeness={ev.get('completeness')}"
            )

    if metrics:
        lines.extend(["", "## Metrics", ""])
        for ev in metrics:
            m_dict = ev.get("metrics") or {}
            if m_dict:
                for mk, mv in m_dict.items():
                    lines.append(f"- `{mk}` = `{mv}`")
            else:
                lines.append(f"- `{ev.get('message')}`")

    if notes:
        lines.extend(["", "## Notes", ""])
        for ev in notes:
            lines.append(f"- {ev.get('message')}")

    lines.append("")
    return "\n".join(lines)


def run_notebook(
    notebook_path: str,
    parameters: Optional[Dict[str, Any]] = None,
    output_notebook: Optional[str] = None,
    target: Optional[str] = None,
    no_sync: bool = False,
    report_path: Optional[str] = None,
    store: Optional[SQLiteLineageStore] = None,
) -> Dict[str, Any]:
    """Execute a Jupyter notebook via papermill and capture OKF provenance events."""
    try:
        import papermill as pm
    except ImportError as exc:
        raise ImportError(
            "papermill is required to run .ipynb notebooks. "
            "Install it with: pip install datamesh-sdk[notebook]"
        ) from exc

    nb_path = Path(notebook_path).resolve()
    if not nb_path.exists():
        raise FileNotFoundError(f"Notebook not found: {notebook_path}")

    out_nb = (
        Path(output_notebook).resolve()
        if output_notebook
        else nb_path.with_name(f"{nb_path.stem}.out.ipynb")
    )
    params = dict(parameters or {})

    # Preserve caller-supplied OKF_PROVENANCE_OUT (e.g. from `okf run`), or create a temp JSONL.
    existing_prov = os.environ.get("OKF_PROVENANCE_OUT")
    created_temp = False
    if existing_prov:
        prov_path = existing_prov
    else:
        fd, prov_path = tempfile.mkstemp(prefix="datamesh-nb-prov-", suffix=".jsonl")
        os.close(fd)
        created_temp = True
        os.environ["OKF_PROVENANCE_OUT"] = prov_path

    # Expose OKF_PARAM_* env vars as fallback alongside papermill parameter injection.
    injected_env_keys: List[str] = []
    for k, v in params.items():
        env_key = f"OKF_PARAM_{k}"
        if env_key not in os.environ:
            os.environ[env_key] = str(v)
            injected_env_keys.append(env_key)

    start = time.monotonic()
    exec_error: Optional[str] = None
    try:
        pm.execute_notebook(str(nb_path), str(out_nb), parameters=params)
    except Exception as exc:
        exec_error = str(exc)
        raise
    finally:
        elapsed = time.monotonic() - start
        events = read_provenance_events(prov_path)
        for env_key in injected_env_keys:
            os.environ.pop(env_key, None)
        if created_temp:
            os.environ.pop("OKF_PROVENANCE_OUT", None)
            try:
                Path(prov_path).unlink(missing_ok=True)
            except OSError:
                pass

        if report_path:
            rp = Path(report_path)
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(
                _render_notebook_report_markdown(
                    nb_path, out_nb, params, events, elapsed, error=exec_error
                ),
                encoding="utf-8",
            )

    sources: List[Dict[str, Any]] = []
    source_uris: List[str] = []
    steps_recorded: List[Dict[str, Any]] = []
    artifacts: List[str] = [str(out_nb)]
    for ev in events:
        ev_type = ev.get("type")
        if ev_type == "input":
            src = ev.get("uri") or ev.get("resource") or ev.get("path")
            if src and src not in source_uris:
                source_uris.append(src)
                sources.append({
                    "name": ev.get("resource") or Path(src).name,
                    "uri": src,
                    "format": ev.get("format") or Path(src).suffix.lstrip("."),
                })
        elif ev_type == "output":
            outp = ev.get("path") or ev.get("resource")
            if outp and outp not in artifacts:
                artifacts.append(outp)
        elif ev_type == "step":
            steps_recorded.append(
                {
                    "step": ev.get("step") or "step",
                    "tool": ev.get("tool") or "papermill",
                    "params": ev.get("params") or {},
                }
            )

    if not steps_recorded:
        steps_recorded.append(
            {
                "step": nb_path.name,
                "tool": "papermill",
                "params": params,
            }
        )

    active_store = store or get_lineage_store()
    resolved_target = target or f"notebook://{nb_path.name}"
    record_id = active_store.record_execution(
        {
            "target_triad": resolved_target,
            "entrypoint": str(nb_path),
            "command": f"papermill {nb_path.name} {out_nb.name}",
            "status": "SUCCESS",
            "exit_code": 0,
            "duration_ms": int(elapsed * 1000),
            "sources": sources,
            "transformations": steps_recorded,
            "artifacts": artifacts,
        }
    )

    return {
        "record_id": record_id,
        "notebook": str(nb_path),
        "output_notebook": str(out_nb),
        "target": resolved_target,
        "parameters": params,
        "no_sync": no_sync,
        "duration_seconds": elapsed,
        "events": events,
        "sources": source_uris,
        "artifacts": artifacts,
    }
