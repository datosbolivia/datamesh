from __future__ import annotations

import csv
import os
import tempfile
import pytest

import datamesh as dm
from datamesh.ports.engine import QueryEnginePort
from datamesh.adapters.engine.duckdb_engine import DuckDBQueryEngine
from datamesh.adapters.engine.inmem_engine import InMemTabularQueryEngine
from datamesh.adapters.engine.go_engine import GoCoreQueryEngine

def test_engine_ports_inheritance():
    duckdb_eng = DuckDBQueryEngine()
    inmem_eng = InMemTabularQueryEngine()
    go_eng = GoCoreQueryEngine()

    assert isinstance(duckdb_eng, QueryEnginePort)
    assert isinstance(inmem_eng, QueryEnginePort)
    assert isinstance(go_eng, QueryEnginePort)

    assert duckdb_eng.name == "duckdb"
    assert inmem_eng.name == "inmem"
    assert go_eng.name == "go"

    assert duckdb_eng.supports_format("csv") is True
    assert duckdb_eng.supports_format("parquet") is True
    assert duckdb_eng.supports_cross_format_join() is True

    assert inmem_eng.supports_format("csv") is True
    assert inmem_eng.supports_format("parquet") is False
    assert inmem_eng.supports_cross_format_join() is False

    assert go_eng.supports_format("csv") is True
    assert go_eng.supports_format("parquet") is True

def test_inmem_query_engine_basic_execution():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "ciudades.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "ciudad", "poblacion"])
            writer.writerow(["1", "La Paz", "950000"])
            writer.writerow(["2", "Santa Cruz", "1800000"])
            writer.writerow(["3", "Cochabamba", "700000"])
            writer.writerow(["4", "Oruro", "280000"])

        inmem_eng = InMemTabularQueryEngine()
        inmem_eng.register_table("ciudades", csv_path)

        # 1. Full scan
        res = inmem_eng.execute_sql("SELECT * FROM ciudades")
        assert res["row_count"] == 4
        assert res["columns"] == ["id", "ciudad", "poblacion"]

        # 2. Projection & Limit
        res = inmem_eng.execute_sql("SELECT ciudad FROM ciudades LIMIT 2")
        assert res["row_count"] == 2
        assert res["columns"] == ["ciudad"]
        assert res["rows"] == [["La Paz"], ["Santa Cruz"]]

        # 3. Filter WHERE
        res = inmem_eng.execute_sql("SELECT ciudad, poblacion FROM ciudades WHERE ciudad = 'Cochabamba'")
        assert res["row_count"] == 1
        assert res["rows"][0][0] == "Cochabamba"
        assert res["rows"][0][1] == "700000"

def test_runtime_engine_selection_and_execution():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "votos.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["departamento", "votos"])
            writer.writerow(["Beni", "15000"])
            writer.writerow(["Pando", "9000"])

        # Test duckdb engine
        res_duckdb = dm.sql(
            "SELECT * FROM 'bolivia:elecciones:votos'",
            table_mapping={"bolivia:elecciones:votos": csv_path},
            engine="duckdb",
        )
        assert res_duckdb["row_count"] == 2
        assert res_duckdb["columns"] == ["departamento", "votos"]

        # Test inmem engine
        res_inmem = dm.sql(
            "SELECT departamento FROM 'bolivia:elecciones:votos' LIMIT 1",
            table_mapping={"bolivia:elecciones:votos": csv_path},
            engine="inmem",
        )
        assert res_inmem["row_count"] == 1
        assert res_inmem["rows"][0][0] == "Beni"

def test_runtime_unknown_engine_raises():
    with pytest.raises(ValueError, match="Unknown query engine 'unreal_engine'"):
        dm.sql("SELECT 1", engine="unreal_engine")

def test_go_engine_unavailable_message():
    go_eng = GoCoreQueryEngine(lib_handle=None)
    with pytest.raises(RuntimeError, match="Go core shared library .* is not compiled or loaded"):
        go_eng.execute_sql("SELECT 1")
