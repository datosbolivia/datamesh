from __future__ import annotations

import json
import sys
from typing import Any, Dict

import datamesh as dm

SERVER_NAME = "datamesh-mcp-server"
SERVER_VERSION = "0.2.0"

TOOLS = [
    {
        "name": "datamesh_discover_catalogs",
        "description": "Discovers and lists sovereign open data products across configured federated catalogs or a specified llms.txt URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "catalog_url": {
                    "type": "string",
                    "description": "Optional catalog URL. If omitted, discovers across all configured sovereign catalogs."
                }
            }
        }
    },
    {
        "name": "datamesh_search_catalog",
        "description": "Searches data products across sovereign catalogs by keyword matching title, description, or domain.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Search keyword (e.g. 'elecciones', 'creditos', 'aire')."
                },
                "catalog_url": {
                    "type": "string",
                    "description": "Optional catalog URL to scope search to."
                }
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "datamesh_get_dataproduct",
        "description": "Resolves an OKF v0.2 Data Product manifest and description from a node URI or URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "Data product node URI or HTTP URL (e.g. https://datosbolivia.github.io/raw/nodes/elecciones-bolivia/index.md)."
                }
            },
            "required": ["uri"]
        }
    },
    {
        "name": "datamesh_query_resource",
        "description": "Queries a tabular CSV/TSV data product resource with column equality filters and row limits.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_uri": {
                    "type": "string",
                    "description": "Direct HTTP URL or local file path to the tabular CSV/TSV file."
                },
                "filters": {
                    "type": "object",
                    "description": "Key-value map of column names and filter values (e.g. {'departamento': 'La Paz'}).",
                    "additionalProperties": {"type": "string"}
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rows to return."
                }
            },
            "required": ["resource_uri"]
        }
    },
    {
        "name": "datamesh_sql_query",
        "description": "Executes full ANSI/DuckDB SQL queries with canonical triad table names 'catalogo:dataset:resource' (e.g. SELECT departamento, SUM(votos_validos) as total FROM \"bolivia:elecciones:votos\" GROUP BY departamento). Seamlessly unifies heterogeneous formats (Parquet, CSV, TSV, JSON) in memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql_query": {
                    "type": "string",
                    "description": "Full ANSI SQL query referencing tables as 'catalogo:dataset:resource'."
                }
            },
            "required": ["sql_query"]
        }
    }
]

def handle_jsonrpc(request: Dict[str, Any]) -> Dict[str, Any]:
    msg_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION
                }
            }
        }

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": TOOLS
            }
        }

    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        try:
            if tool_name == "datamesh_discover_catalogs":
                catalog_url = args.get("catalog_url")
                data = dm.discover(catalog_url)
                return make_tool_result(msg_id, data)

            elif tool_name == "datamesh_search_catalog":
                keyword = args.get("keyword", "")
                catalog_url = args.get("catalog_url")
                data = dm.search(keyword, catalog_url)
                return make_tool_result(msg_id, data)

            elif tool_name == "datamesh_get_dataproduct":
                uri = args.get("uri", "")
                data = dm.get(uri)
                return make_tool_result(msg_id, data)

            elif tool_name == "datamesh_query_resource":
                resource_uri = args.get("resource_uri", "")
                filters = args.get("filters")
                limit = args.get("limit")
                data = dm.query(resource_uri, filters=filters, limit=limit)
                return make_tool_result(msg_id, data)

            elif tool_name == "datamesh_sql_query":
                sql_query = args.get("sql_query", "")
                data = dm.sql(sql_query)
                return make_tool_result(msg_id, data)

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method or tool not found: {tool_name}"
                    }
                }
        except Exception as e:
            return make_tool_error(msg_id, str(e))

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {
            "code": -32601,
            "message": f"Method not supported: {method}"
        }
    }

def make_tool_result(msg_id: Any, data: Any) -> Dict[str, Any]:
    text_content = json.dumps(data, indent=2, ensure_ascii=False)
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": text_content
                }
            ],
            "isError": False
        }
    }

def make_tool_error(msg_id: Any, error_msg: str) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": f"Error executing tool: {error_msg}"
                }
            ],
            "isError": True
        }
    }

def run_mcp_server():
    """Runs the MCP server over standard input/output."""
    sys.stderr.write(f"[{SERVER_NAME}] Server started (stdio mode)\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line_str = line.strip()
        if not line_str:
            continue
        try:
            req = json.loads(line_str)
            resp = handle_jsonrpc(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()
