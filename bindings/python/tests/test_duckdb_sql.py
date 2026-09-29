import os
import sys
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import datamesh as dm
from datamesh.mcp_server import handle_jsonrpc

TESTDATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "core-go", "testdata"))
CSV_PATH = os.path.join(TESTDATA_DIR, "mock_data_elecciones.csv")
PARQUET_PATH = os.path.join(TESTDATA_DIR, "mock_data_presupuesto.parquet")

def test_duckdb_sql_single_table_aggregation():
    mapping = {
        "bolivia:elecciones:votos": CSV_PATH,
    }
    sql_query = """
    SELECT departamento, SUM(votos_validos) as total_votos
    FROM "bolivia:elecciones:votos"
    GROUP BY departamento
    ORDER BY total_votos DESC
    """
    res = dm.sql(sql_query, table_mapping=mapping)

    assert res["row_count"] == 3
    assert res["columns"] == ["departamento", "total_votos"]
    assert res["rows"][0][0] == "La Paz"
    assert res["rows"][0][1] == 77300

def test_duckdb_sql_heterogeneous_cross_format_join():
    """Demonstrates cross-format JOIN between CSV and Parquet resolving heterogeneity."""
    mapping = {
        "bolivia:elecciones:votos": CSV_PATH,
        "municipal:presupuesto:ejecucion": PARQUET_PATH,
    }
    sql_query = """
    SELECT 
        e.departamento,
        SUM(e.votos_validos) as votos_totales,
        p.presupuesto,
        p.sector
    FROM "bolivia:elecciones:votos" e
    JOIN "municipal:presupuesto:ejecucion" p ON e.departamento = p.municipio
    GROUP BY e.departamento, p.presupuesto, p.sector
    ORDER BY votos_totales DESC
    """
    res = dm.sql(sql_query, table_mapping=mapping)

    assert res["row_count"] == 3
    assert "presupuesto" in res["columns"]
    assert "votos_totales" in res["columns"]
    # Verify values joined from Parquet (presupuesto) and CSV (votos_totales)
    row_la_paz = next(r for r in res["rows"] if r[0] == "La Paz")
    assert row_la_paz[1] == 77300
    assert row_la_paz[2] == 1500000.0

def test_mcp_sql_tool():
    mapping = {
        "bolivia:elecciones:votos": CSV_PATH,
    }
    # Pre-register for MCP tool test
    dm._runtime._duckdb_engine.register_table("bolivia:elecciones:votos", CSV_PATH)

    req = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "datamesh_sql_query",
            "arguments": {
                "sql_query": "SELECT COUNT(*) as total_rows FROM 'bolivia:elecciones:votos' WHERE partido = 'MAS'"
            }
        }
    }
    resp = handle_jsonrpc(req)
    assert resp["id"] == 10
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["row_count"] == 1
    assert content["rows"][0][0] == 3
