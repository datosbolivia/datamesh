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

def test_mcp_guardrails_instructions_and_prompts():
    # 1. Verify instructions in initialize
    init_req = {"jsonrpc": "2.0", "id": 4, "method": "initialize", "params": {}}
    init_resp = handle_jsonrpc(init_req)
    instructions = init_resp["result"]["serverInfo"]["instructions"]
    assert "STRICT GROUNDEDNESS" in instructions
    assert "MANDATORY CITATION" in instructions
    assert "NULL TRANSPARENCY" in instructions

    # 2. Verify prompts/list
    p_req = {"jsonrpc": "2.0", "id": 5, "method": "prompts/list", "params": {}}
    p_resp = handle_jsonrpc(p_req)
    prompt_names = [p["name"] for p in p_resp["result"]["prompts"]]
    assert "grounded_sql_analysis" in prompt_names
    assert "dataset_provenance_audit" in prompt_names

    # 3. Verify prompts/get
    get_req = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "prompts/get",
        "params": {
            "name": "grounded_sql_analysis",
            "arguments": {"user_question": "What was the highest ICA in 2024?"}
        }
    }
    get_resp = handle_jsonrpc(get_req)
    msg_text = get_resp["result"]["messages"][0]["content"]["text"]
    assert "STRICT GUARDRAILS" in msg_text
    assert "Never hallucinate numbers" in msg_text
