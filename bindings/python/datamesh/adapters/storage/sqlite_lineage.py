from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from datamesh.ports.lineage_store import LineageStorePort


class SQLiteLineageStore(LineageStorePort):
    """Authoritative local operational lineage store persisted in an embedded SQLite database.

    Persists script executions, function provenance, and artifact hashes within the unified
    client metadata database (metadata.db), cross-referencing cache_entries.
    Adheres to KISS/YAGNI principles using Python's standard library sqlite3 without external services.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS executions (
        id TEXT PRIMARY KEY,
        target_triad TEXT NOT NULL,
        script_path TEXT,
        entrypoint TEXT,
        command TEXT,
        status TEXT NOT NULL,
        exit_code INTEGER,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        duration_ms INTEGER,
        user_identity TEXT
    );

    CREATE TABLE IF NOT EXISTS lineage_sources (
        id TEXT PRIMARY KEY,
        execution_id TEXT NOT NULL,
        source_name TEXT NOT NULL,
        source_uri TEXT NOT NULL,
        source_hash TEXT,
        format TEXT,
        cache_key TEXT,
        FOREIGN KEY(execution_id) REFERENCES executions(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS lineage_transformations (
        id TEXT PRIMARY KEY,
        execution_id TEXT NOT NULL,
        step_name TEXT NOT NULL,
        tool TEXT NOT NULL,
        code_hash TEXT NOT NULL,
        query_text TEXT,
        parameters_json TEXT,
        FOREIGN KEY(execution_id) REFERENCES executions(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS artifacts (
        id TEXT PRIMARY KEY,
        execution_id TEXT NOT NULL,
        path TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        bytes_size INTEGER NOT NULL,
        format TEXT NOT NULL,
        cache_key TEXT,
        FOREIGN KEY(execution_id) REFERENCES executions(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_exec_target ON executions(target_triad);
    CREATE INDEX IF NOT EXISTS idx_sources_exec ON lineage_sources(execution_id);
    CREATE INDEX IF NOT EXISTS idx_sources_cache ON lineage_sources(cache_key);
    CREATE INDEX IF NOT EXISTS idx_trans_exec ON lineage_transformations(execution_id);
    CREATE INDEX IF NOT EXISTS idx_art_exec ON artifacts(execution_id);
    CREATE INDEX IF NOT EXISTS idx_art_cache ON artifacts(cache_key);
    """

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            env_db = os.environ.get("DATAMESH_METADATA_DB")
            if env_db:
                db_path = env_db
            else:
                from datamesh.constants import get_datamesh_home
                base_dir = get_datamesh_home()
                db_path = str(base_dir / "metadata.db")

        self.db_path = str(Path(db_path).resolve())
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)
            # Safe schema upgrade for cache_key columns
            try:
                conn.execute("ALTER TABLE lineage_sources ADD COLUMN cache_key TEXT;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE artifacts ADD COLUMN cache_key TEXT;")
            except Exception:
                pass

    @staticmethod
    def compute_sha256(file_path: str) -> str:
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return ""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _find_cache_key(self, conn: sqlite3.Connection, uri_or_path: str, sha256_hash: Optional[str] = None) -> Optional[str]:
        """Resolves cache_key from cache_entries table if present in the unified database."""
        try:
            row = conn.execute(
                "SELECT key FROM cache_entries WHERE original_uri = ? OR local_path = ? LIMIT 1",
                (uri_or_path, uri_or_path)
            ).fetchone()
            if row:
                return row["key"]
            if sha256_hash:
                row_h = conn.execute(
                    "SELECT key FROM cache_entries WHERE sha256 = ? LIMIT 1",
                    (sha256_hash,)
                ).fetchone()
                if row_h:
                    return row_h["key"]
        except Exception:
            pass
        return None

    def record_execution(self, record: Dict[str, Any]) -> str:
        exec_id = record.get("id") or f"exec-{int(time.time() * 1000)}-{os.urandom(4).hex()}"
        target_triad = record.get("target_triad") or record.get("target") or "unknown"
        script_path = record.get("script_path")
        entrypoint = record.get("entrypoint")
        command = record.get("command")
        status = record.get("status") or ("SUCCESS" if record.get("exit_code", 0) == 0 else "FAILED")
        exit_code = record.get("exit_code", 0)
        started_at = record.get("started_at") or datetime.now(timezone.utc).isoformat()
        completed_at = record.get("completed_at") or datetime.now(timezone.utc).isoformat()
        duration_ms = record.get("duration_ms", 0)
        user_identity = record.get("user_identity") or os.environ.get("USER", "anonymous")

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO executions 
                (id, target_triad, script_path, entrypoint, command, status, exit_code, started_at, completed_at, duration_ms, user_identity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (exec_id, target_triad, script_path, entrypoint, command, status, exit_code, started_at, completed_at, duration_ms, user_identity),
            )

            # Insert sources
            for idx, s in enumerate(record.get("sources", [])):
                s_name = s.get("name") or f"src-{idx}"
                s_uri = s.get("uri") or s.get("path") or "unknown"
                s_hash = s.get("hash") or (self.compute_sha256(s_uri) if os.path.exists(s_uri) else "")
                s_fmt = s.get("format") or Path(s_uri).suffix.lstrip(".")
                s_cache_key = s.get("cache_key") or self._find_cache_key(conn, s_uri, s_hash)
                conn.execute(
                    """
                    INSERT INTO lineage_sources (id, execution_id, source_name, source_uri, source_hash, format, cache_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (f"{exec_id}-src-{idx}", exec_id, s_name, s_uri, s_hash, s_fmt, s_cache_key),
                )

            # Insert transformations
            for idx, t in enumerate(record.get("transformations", [])):
                t_name = t.get("step") or t.get("name") or f"step-{idx}"
                t_tool = t.get("tool") or "python"
                t_hash = t.get("code_hash") or t.get("hash") or ""
                t_query = t.get("query")
                t_params = json.dumps(t.get("params", {})) if isinstance(t.get("params"), dict) else None
                conn.execute(
                    """
                    INSERT INTO lineage_transformations (id, execution_id, step_name, tool, code_hash, query_text, parameters_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (f"{exec_id}-trans-{idx}", exec_id, t_name, t_tool, t_hash, t_query, t_params),
                )

            # Insert artifacts
            for idx, a in enumerate(record.get("artifacts", [])):
                a_path = a.get("path") if isinstance(a, dict) else str(a)
                if os.path.exists(a_path):
                    a_hash = self.compute_sha256(a_path)
                    a_size = os.path.getsize(a_path)
                    a_fmt = Path(a_path).suffix.lstrip(".") or "binary"
                    a_cache_key = (a.get("cache_key") if isinstance(a, dict) else None) or self._find_cache_key(conn, a_path, a_hash)
                    conn.execute(
                        """
                        INSERT INTO artifacts (id, execution_id, path, sha256, bytes_size, format, cache_key)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (f"{exec_id}-art-{idx}", exec_id, a_path, a_hash, a_size, a_fmt, a_cache_key),
                    )

        return exec_id

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM executions WHERE id = ?", (execution_id,)).fetchone()
            if not row:
                return None
            res = dict(row)

            # Sources
            sources = conn.execute("SELECT * FROM lineage_sources WHERE execution_id = ?", (execution_id,)).fetchall()
            res["sources"] = [dict(s) for s in sources]

            # Transformations
            trans = conn.execute("SELECT * FROM lineage_transformations WHERE execution_id = ?", (execution_id,)).fetchall()
            res["transformations"] = [
                {
                    **dict(t),
                    "params": json.loads(t["parameters_json"]) if t["parameters_json"] else {},
                }
                for t in trans
            ]

            # Artifacts
            arts = conn.execute("SELECT * FROM artifacts WHERE execution_id = ?", (execution_id,)).fetchall()
            res["artifacts"] = [dict(a) for a in arts]

            return res

    def list_executions(self, target: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if target:
                rows = conn.execute(
                    "SELECT * FROM executions WHERE target_triad = ? ORDER BY started_at DESC LIMIT ?",
                    (target, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM executions ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def record_artifact(self, execution_id: str, artifact_path: str, format_name: Optional[str] = None) -> Dict[str, Any]:
        clean_path = str(Path(artifact_path).resolve())
        if not os.path.exists(clean_path):
            raise FileNotFoundError(f"Artifact path does not exist: {clean_path}")

        sha256 = self.compute_sha256(clean_path)
        size = os.path.getsize(clean_path)
        fmt = format_name or Path(clean_path).suffix.lstrip(".") or "binary"
        art_id = f"{execution_id}-art-{int(time.time()*1000)}"

        with self._get_connection() as conn:
            cache_key = self._find_cache_key(conn, clean_path, sha256)
            conn.execute(
                """
                INSERT OR REPLACE INTO artifacts (id, execution_id, path, sha256, bytes_size, format, cache_key)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (art_id, execution_id, clean_path, sha256, size, fmt, cache_key),
            )

        return {
            "id": art_id,
            "execution_id": execution_id,
            "path": clean_path,
            "sha256": sha256,
            "bytes_size": size,
            "format": fmt,
            "cache_key": cache_key,
        }

    def get_artifacts_for_execution(self, execution_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM artifacts WHERE execution_id = ?", (execution_id,)).fetchall()
            return [dict(r) for r in rows]

    def find_executions_for_cache_key(self, cache_key: str) -> List[Dict[str, Any]]:
        """Finds executions that produced or consumed the given cached entry key."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT e.* FROM executions e
                LEFT JOIN lineage_sources s ON s.execution_id = e.id
                LEFT JOIN artifacts a ON a.execution_id = e.id
                WHERE s.cache_key = ? OR a.cache_key = ?
                ORDER BY e.started_at DESC
                """,
                (cache_key, cache_key),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_lineage_for_target(self, target: str) -> Dict[str, Any]:
        """Reconstructs synthesized W3C PROV-O lineage dictionary for a target dataset."""
        execs = self.list_executions(target=target, limit=10)
        sources: List[Dict[str, Any]] = []
        transformations: List[Dict[str, Any]] = []
        seen_src = set()

        for e in execs:
            full = self.get_execution(e["id"])
            if not full:
                continue
            for s in full.get("sources", []):
                key = (s.get("source_name"), s.get("source_uri"))
                if key not in seen_src:
                    seen_src.add(key)
                    sources.append({
                        "name": s.get("source_name"),
                        "url": s.get("source_uri"),
                        "hash": s.get("source_hash"),
                        "format": s.get("format"),
                        "cache_key": s.get("cache_key"),
                    })
            for t in full.get("transformations", []):
                transformations.append({
                    "step": t.get("step_name"),
                    "tool": t.get("tool"),
                    "hash": t.get("code_hash"),
                    "query": t.get("query_text"),
                })

        return {
            "dataset_id": target,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "sources": sources,
            "transformations": transformations,
            "was_derived_from": [s.get("url") for s in sources if s.get("url")],
        }
