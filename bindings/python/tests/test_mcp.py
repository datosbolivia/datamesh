import os
import sys
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from datamesh.mcp_server import handle_jsonrpc

TESTDATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "core-go", "testdata"))

def test_mcp_initialize():
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    resp = handle_jsonrpc(req)
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "datamesh-mcp-server"

def test_mcp_tools_list():
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    resp = handle_jsonrpc(req)
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "datamesh_discover_catalogs" in tool_names
    assert "datamesh_search_catalog" in tool_names
    assert "datamesh_query_resource" in tool_names

def test_mcp_tool_call_query():
    csv_path = os.path.join(TESTDATA_DIR, "mock_data_elecciones.csv")
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "datamesh_query_resource",
            "arguments": {
                "resource_uri": f"file://{csv_path}",
                "filters": {"departamento": "Santa Cruz"}
            }
        }
    }
    resp = handle_jsonrpc(req)
    assert resp["id"] == 3
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["row_count"] == 2
    assert content["rows"][0][1] == "Santa Cruz"
