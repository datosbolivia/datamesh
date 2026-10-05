import os
import sys
import tempfile
import zipfile
import json
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import datamesh as dm
from datamesh.adapters.storage.zip_extractor import extract_zip_tabular_resource
from datamesh.mcp_server import handle_jsonrpc

def test_extract_zip_single_csv():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        zip_path = tmp_p / "test_data.zip"
        
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("test_table.csv", "id,name,value\n1,Alpha,100\n2,Beta,200\n")
            
        extracted_p, fmt = extract_zip_tabular_resource(zip_path, cache_dir=tmp_p / "cache")
        assert extracted_p is not None
        assert fmt == "csv"
        assert os.path.exists(extracted_p)
        assert extracted_p.endswith("test_table.csv")

def test_extract_zip_with_datapackage_manifest():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        zip_path = tmp_p / "package_data.zip"
        
        dp_manifest = {
            "name": "sample_pkg",
            "resources": [
                {
                    "name": "sample_resource",
                    "path": "subfolder/metrics_*.csv",
                    "format": "csv"
                }
            ]
        }
        
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("datapackage.json", json.dumps(dp_manifest))
            z.writestr("subfolder/metrics_01.csv", "code,score\nA,95\n")
            z.writestr("subfolder/metrics_02.csv", "code,score\nB,88\n")
            
        extracted_p, fmt = extract_zip_tabular_resource(zip_path, target_hint="sample_resource", cache_dir=tmp_p / "cache")
        assert extracted_p is not None
        assert fmt == "csv"
        assert "subfolder/metrics_*.csv" in extracted_p
        assert (tmp_p / "cache" / "unpacked").exists()

def test_mcp_read_resource_from_zip():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        zip_path = tmp_p / "mcp_test.zip"
        
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("dataset.csv", "dept,population\nLP,3000000\nSC,3500000\nCB,2000000\n")
            
        req = {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {
                "name": "read_resource",
                "arguments": {
                    "resource_uri": str(zip_path),
                    "limit": 2
                }
            }
        }
        resp = handle_jsonrpc(req)
        assert resp["id"] == 99
        content = json.loads(resp["result"]["content"][0]["text"])
        assert content["columns"] == ["dept", "population"]
        assert content["row_count"] == 2
        assert content["rows"][0] == ["LP", "3000000"]

def test_duckdb_sql_query_from_zip_table():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        zip_path = tmp_p / "sql_test.zip"
        
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("records.csv", "category,amount\nFood,50\nTech,200\nFood,30\n")
            
        sql_q = f"SELECT category, SUM(amount) as total FROM '{zip_path}' GROUP BY category ORDER BY total DESC"
        res = dm.sql(sql_q)
        assert res["row_count"] == 2
        assert res["columns"] == ["category", "total"]
        assert res["rows"][0] == ["Tech", 200]
        assert res["rows"][1] == ["Food", 80]
