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
