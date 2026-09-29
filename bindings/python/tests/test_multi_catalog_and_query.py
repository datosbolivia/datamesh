import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import datamesh as dm

TESTDATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "core-go", "testdata"))

def test_mock_catalog_discovery():
    cat_path = os.path.join(TESTDATA_DIR, "mock_catalog_primary.txt")
    res = dm.discover(f"file://{cat_path}")
    assert res["title"] == "Catálogo Primario Soberano"
    assert len(res["entries"]) == 2
    assert res["entries"][0]["title"] == "Atlas Electoral de Bolivia"
    assert res["entries"][0]["domain"] == "Demografía y Sociedad"

def test_multi_catalog_aggregation(monkeypatch):
    cat1_path = os.path.join(TESTDATA_DIR, "mock_catalog_primary.txt")
    cat2_path = os.path.join(TESTDATA_DIR, "mock_catalog_secondary.txt")

    monkeypatch.setenv("DATAMESH_CATALOGS", f"file://{cat1_path},file://{cat2_path}")

    res = dm.discover()
    assert len(res["entries"]) == 4
    assert len(res["source_catalogs"]) == 2

    # Verify search across aggregated catalogs
    search_res = dm.search("transporte")
    assert len(search_res) == 1
    assert search_res[0]["title"] == "Rutas de Transporte Urbano"

def test_query_execution():
    csv_path = os.path.join(TESTDATA_DIR, "mock_data_elecciones.csv")
    res = dm.query(f"file://{csv_path}", filters={"departamento": "La Paz"})

    assert res["row_count"] == 2
    assert len(res["columns"]) == 5
    assert res["rows"][0][1] == "La Paz"

    # Test limit
    res_limit = dm.query(f"file://{csv_path}", limit=1)
    assert res_limit["row_count"] == 1
