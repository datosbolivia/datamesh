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

def test_user_reported_queries():
    # Test Query 1: 2-part triad with spaces and accents
    q1 = 'SELECT lugar_nombre, ROUND(AVG(valor_ica), 1) AS promedio_ica, MAX(valor_ica) AS max_ica, COUNT(*) AS mediciones FROM "air_quality:Compilación de datos de calidad del aire de Bolivia" GROUP BY lugar_nombre ORDER BY promedio_ica DESC LIMIT 15'
    r1 = dm.sql(q1)
    assert r1["row_count"] == 14
    assert r1["rows"][0][0] == "SACABA"

    # Test Query 2: slugified table name from charts
    q2 = 'SELECT lugar_nombre, ROUND(AVG(valor_ica), 1) AS promedio_ica, MAX(valor_ica) AS max_ica, COUNT(*) AS mediciones FROM air_quality_compilaci_n_de_datos_de_calidad_del_aire_de_bolivia GROUP BY lugar_nombre ORDER BY promedio_ica DESC LIMIT 15'
    r2 = dm.sql(q2)
    assert r2["row_count"] == 14
    assert r2["rows"][0][0] == "SACABA"

def test_decimal_and_datetime_json_serialization():
    sql_query = """
    SELECT 
        123.45::DECIMAL(10,2) as dec_float,
        100.00::DECIMAL(10,2) as dec_int,
        DATE '2026-09-28' as sample_date,
        TIMESTAMP '2026-09-28 12:30:00' as sample_ts
    """
    res = dm.sql(sql_query)
    dumped = json.dumps(res)
    loaded = json.loads(dumped)
    assert loaded["rows"][0][0] == 123.45
    assert loaded["rows"][0][1] == 100
    assert loaded["rows"][0][2] == "2026-09-28"
    assert "2026-09-28T12:30:00" in loaded["rows"][0][3]

def test_user_join_query_with_decimal_json_serializable():
    sql = """
    SELECT                                                
        e.departamento,
        SUM(e.votos_validos) as votos_totales,
        p.presupuesto,
        p.sector
    FROM 'bolivia:elecciones:votos' e
    JOIN 'municipal:presupuesto:ejecucion' p ON e.departamento = p.municipio
    GROUP BY e.departamento, p.presupuesto, p.sector
    ORDER BY votos_totales DESC
    """
    res = dm.sql(sql)
    dumped = json.dumps(res, indent=2, ensure_ascii=False)
    parsed = json.loads(dumped)
    assert parsed["row_count"] == 3
    assert parsed["rows"][0][0] == "La Paz"
    assert parsed["rows"][0][1] == 77300
    assert parsed["rows"][0][2] == 1500000
