from __future__ import annotations

import os
import tempfile
from pathlib import Path
import pytest

import datamesh as dm
from datamesh.adapters.storage.sqlite_lineage import SQLiteLineageStore
from datamesh.track import track_lineage, track_execution, run_script


def test_sqlite_lineage_store_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_lineage.db")
        store = SQLiteLineageStore(db_path)

        # 1. Record an execution
        exec_id = store.record_execution({
            "target_triad": "bolivia:macro:inflacion",
            "entrypoint": "etl_inflacion:run",
            "command": "python etl_inflacion.py",
            "status": "SUCCESS",
            "exit_code": 0,
            "duration_ms": 250,
            "sources": [
                {"name": "raw_ipc.csv", "uri": "https://ine.gob.bo/ipc.csv", "format": "csv"}
            ],
            "transformations": [
                {"step": "clean_nulls", "tool": "pandas", "code_hash": "a1b2c3d4", "params": {"impute": "median"}}
            ]
        })
        assert exec_id.startswith("exec-")

        # 2. Get execution
        retrieved = store.get_execution(exec_id)
        assert retrieved is not None
        assert retrieved["target_triad"] == "bolivia:macro:inflacion"
        assert len(retrieved["sources"]) == 1
        assert retrieved["sources"][0]["source_name"] == "raw_ipc.csv"
        assert len(retrieved["transformations"]) == 1
        assert retrieved["transformations"][0]["params"] == {"impute": "median"}

        # 3. Create a dummy artifact and record it
        art_path = os.path.join(tmpdir, "inflacion_limpia.parquet")
        with open(art_path, "wb") as f:
            f.write(b"PARQUET_TEST_CONTENT_12345")

        art_meta = store.record_artifact(exec_id, art_path, "parquet")
        assert art_meta["sha256"] != ""
        assert art_meta["bytes_size"] > 0
        assert art_meta["format"] == "parquet"

        artifacts = store.get_artifacts_for_execution(exec_id)
        assert len(artifacts) == 1
        assert artifacts[0]["path"] == str(Path(art_path).resolve())

        # 4. List executions
        exec_list = store.list_executions(target="bolivia:macro:inflacion")
        assert len(exec_list) == 1

        # 5. Get lineage for target (W3C PROV-O format)
        lineage_dict = store.get_lineage_for_target("bolivia:macro:inflacion")
        assert lineage_dict["dataset_id"] == "bolivia:macro:inflacion"
        assert len(lineage_dict["sources"]) == 1
        assert len(lineage_dict["transformations"]) == 1
        assert "https://ine.gob.bo/ipc.csv" in lineage_dict["was_derived_from"]


def test_track_lineage_decorator():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "decorator_lineage.db")
        store = SQLiteLineageStore(db_path)

        out_file = os.path.join(tmpdir, "summary.csv")

        @track_lineage(
            target="p2p:binance:cotizaciones",
            sources=["data/raw_trades.parquet"],
            step_name="aggregate_daily_spread",
            store=store,
        )
        def compute_summary(factor: int) -> str:
            with open(out_file, "w") as f:
                f.write(f"price_summary,count\n11.85,{factor * 100}\n")
            return out_file

        result = compute_summary(5)
        assert result == out_file

        # Verify lineage stored
        execs = store.list_executions(target="p2p:binance:cotizaciones")
        assert len(execs) == 1
        rec = store.get_execution(execs[0]["id"])
        assert rec["status"] == "SUCCESS"
        assert rec["duration_ms"] >= 0
        assert len(rec["sources"]) == 1
        assert len(rec["artifacts"]) == 1
        assert rec["artifacts"][0]["path"] == str(Path(out_file).resolve())


def test_track_execution_context_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "context_lineage.db")
        store = SQLiteLineageStore(db_path)
        out_parquet = os.path.join(tmpdir, "out.parquet")
        with open(out_parquet, "wb") as f:
            f.write(b"PARQUET_BYTES")

        with track_execution(
            target="clima:temperatura:historico",
            step_name="clean_sensors",
            sources=["sensor_01.csv", "sensor_02.csv"],
            store=store,
        ) as ctx:
            ctx["artifacts"].append(out_parquet)

        execs = store.list_executions(target="clima:temperatura:historico")
        assert len(execs) == 1
        rec = store.get_execution(execs[0]["id"])
        assert rec["status"] == "SUCCESS"
        assert len(rec["sources"]) == 2
        assert len(rec["artifacts"]) == 1


def test_run_script():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "runner_lineage.db")
        store = SQLiteLineageStore(db_path)

        script_path = os.path.join(tmpdir, "test_job.py")
        with open(script_path, "w") as f:
            f.write("""
import sys
print(f"Processed args: {sys.argv[1:]}")
""")

        res = run_script(
            script_path=script_path,
            target="salud:dengue:casos",
            args=["--region", "Santa Cruz", "--year", "2026"],
            store=store,
        )

        assert res["status"] == "SUCCESS"
        assert res["exit_code"] == 0
        assert "Processed args: ['--region', 'Santa Cruz', '--year', '2026']" in res["stdout"]
        assert len(res["script_hash"]) == 64

        execs = store.list_executions(target="salud:dengue:casos")
        assert len(execs) == 1
        rec = store.get_execution(execs[0]["id"])
        assert rec["status"] == "SUCCESS"
        assert rec["script_path"] == str(Path(script_path).resolve())

def test_unified_metadata_db_and_cache_cross_referencing():
    with tempfile.TemporaryDirectory() as tmpdir:
        home_dir = Path(tmpdir) / "datamesh"
        cache_dir = home_dir / "cache"
        cfg_file = home_dir / "config.yaml"
        db_file = home_dir / "metadata.db"

        cfg = dm.StorageConfig(
            home_dir=home_dir,
            cache_dir=cache_dir,
            config_file=cfg_file,
            metadata_db_path=db_file,
        )
        storage = dm.LocalStorageManager(cfg)
        store = SQLiteLineageStore(str(db_file))

        # 1. Save an external dataset into cache
        cached_file = storage.save(
            key_or_uri="https://ine.gob.bo/censo2024.csv",
            content="departamento,poblacion\nLa Paz,3022566\nSanta Cruz,3115386\n",
            extension="csv",
            source_service="http",
        )
        assert cached_file.exists()
        cache_key = storage._hash_key("https://ine.gob.bo/censo2024.csv")
        assert storage.is_cached("https://ine.gob.bo/censo2024.csv")

        # 2. Record execution that consumes this cached resource
        out_art = Path(tmpdir) / "resumen_poblacion.parquet"
        with open(out_art, "wb") as f:
            f.write(b"PARQUET_PROCESSED_DATA")

        exec_id = store.record_execution({
            "target_triad": "ine:censo:resumen",
            "entrypoint": "etl_censo:process",
            "sources": [
                {"name": "censo2024.csv", "uri": "https://ine.gob.bo/censo2024.csv"}
            ],
            "transformations": [
                {"step": "agrupar_por_depto", "tool": "duckdb", "code_hash": "c0d3h4sh"}
            ],
            "artifacts": [
                str(out_art)
            ],
        })

        # 3. Verify cross-referencing to cache_entries in the unified DB
        rec = store.get_execution(exec_id)
        assert rec is not None
        assert len(rec["sources"]) == 1
        assert rec["sources"][0]["cache_key"] == cache_key

        # 4. Find executions by cache_key
        related = store.find_executions_for_cache_key(cache_key)
        assert len(related) == 1
        assert related[0]["id"] == exec_id
        assert related[0]["target_triad"] == "ine:censo:resumen"


def test_local_storage_manager_sqlite_and_json_migration():
    with tempfile.TemporaryDirectory() as tmpdir:
        home_dir = Path(tmpdir) / "datamesh"
        cache_dir = home_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        db_file = home_dir / "metadata.db"
        json_file = cache_dir / "metadata.json"

        # Pre-create legacy metadata.json
        import hashlib, json
        raw_uri = "https://example.org/legacy.csv"
        k = hashlib.sha256(raw_uri.encode("utf-8")).hexdigest()[:24]
        legacy_data = {
            k: {
                "key": k,
                "original_uri": raw_uri,
                "local_path": str(cache_dir / "legacy.csv"),
                "format": "csv",
                "size_bytes": 100,
                "cached_at": "2026-01-01T00:00:00Z",
                "source_service": "http",
            }
        }
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        # Initialize LocalStorageManager - should migrate legacy.json to SQLite
        cfg = dm.StorageConfig(
            home_dir=home_dir,
            cache_dir=cache_dir,
            config_file=home_dir / "config.yaml",
            metadata_db_path=db_file,
        )
        storage = dm.LocalStorageManager(cfg)

        # Verify entry loaded into memory and DB
        assert k in storage._metadata_cache
        meta = storage.get_metadata(raw_uri)
        assert meta is not None
        assert meta.key == k

        # Verify SQLite has the record
        import sqlite3
        with sqlite3.connect(str(db_file)) as conn:
            row = conn.execute("SELECT * FROM cache_entries WHERE key = ?", (k,)).fetchone()
            assert row is not None


class TestProvenanceAPIAndNotebookRunner:
    def test_step_and_log_helpers_emit_provenance_jsonl(self, tmp_path, monkeypatch):
        import json

        prov_file = tmp_path / "provenance.jsonl"
        out_csv = tmp_path / "cleaned.csv"
        out_csv.write_text("id,amount\n1,10.5\n2,\n", encoding="utf-8")

        monkeypatch.setenv("OKF_PROVENANCE_OUT", str(prov_file))

        dm.log_input("raw_source.csv", resource="raw", fmt="csv")
        with dm.step("clean_data", tool="python", params={"drop_na": False}):
            dm.log_metric("rows_processed", 2, step_name="clean_data")
            dm.log_note("kept null amount row for downstream check")

        qc = dm.log_quality(str(out_csv), resource="cleaned", min_rows=2, min_completeness=0.5)
        assert qc.get("row_count") == 2

        out_ev = dm.log_output(out_csv, resource="cleaned", fmt="csv")
        assert out_ev["format"] == "csv"
        assert len(out_ev["hash_sha256"]) == 64

        events = [
            json.loads(line)
            for line in prov_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        types = [e["type"] for e in events]
        assert "input" in types
        assert "step" in types
        assert "metric" in types
        assert "note" in types
        assert "quality" in types
        assert "output" in types

    def test_run_notebook_executes_papermill_and_writes_report(self, tmp_path, monkeypatch):
        import sys

        nb_file = tmp_path / "etl.ipynb"
        nb_file.write_text('{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}', encoding="utf-8")
        out_nb = tmp_path / "etl.out.ipynb"
        report_md = tmp_path / "run-report.md"
        db_file = tmp_path / "lineage.db"
        store = dm.SQLiteLineageStore(db_path=str(db_file))

        captured_calls = []

        class FakePapermill:
            @staticmethod
            def execute_notebook(input_path, output_path, parameters=None):
                captured_calls.append((input_path, output_path, parameters))
                Path(output_path).write_text("executed", encoding="utf-8")
                dm.log_input("s3://bucket/raw.parquet", resource="raw", fmt="parquet")
                with dm.step("notebook_transform", tool="papermill", params=parameters):
                    dm.log_metric("accuracy", 0.99)
                dm.log_note("notebook run complete")

        monkeypatch.setitem(sys.modules, "papermill", FakePapermill())

        result = dm.run_notebook(
            str(nb_file),
            parameters={"year": "2026"},
            output_notebook=str(out_nb),
            target="dataset://sales",
            report_path=str(report_md),
            store=store,
        )

        assert len(captured_calls) == 1
        assert captured_calls[0][2] == {"year": "2026"}
        assert out_nb.exists()
        assert result["target"] == "dataset://sales"
        assert "s3://bucket/raw.parquet" in result["sources"]
        assert report_md.exists()
        report_text = report_md.read_text(encoding="utf-8")
        assert "type: run_report" in report_text
        assert "notebook_transform" in report_text
        assert "accuracy" in report_text

        records = store.list_executions(target="dataset://sales")
        assert len(records) == 1
        assert records[0]["status"] == "SUCCESS"


