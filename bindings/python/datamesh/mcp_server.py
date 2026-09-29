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

GUARDRAILS_INSTRUCTIONS = (
    "DataMesh Sovereign Agent Guardrails:\n"
    "1. STRICT GROUNDEDNESS: You must answer questions using exclusively the data returned by datamesh tools. "
    "Never invent, guess, or extrapolate figures, dates, column names, or table rows.\n"
    "2. MANDATORY CITATION: Always cite the canonical triad 'catalogo:dataset:resource' (e.g. 'air_quality:Compilación de datos de calidad del aire de Bolivia').\n"
    "3. NULL TRANSPARENCY: If a query returns 0 rows or null values, explicitly tell the user that no matching records exist. Do NOT generate mock or speculative answers.\n"
    "4. SCHEMA VERIFICATION: Before complex SQL, verify column names using datamesh_get_dataproduct or LIMIT 1 queries.\n"
    "5. FACT VS HYPOTHESIS: Clearly separate verified database rows from external hypotheses or interpretations."
)

PROMPTS = [
    {
        "name": "grounded_sql_analysis",
        "description": "Formulates and executes a verified, non-hallucinated SQL analysis against sovereign datasets with strict provenance citations.",
        "arguments": [
            {
                "name": "user_question",
                "description": "Natural language analytical question about sovereign datasets.",
                "required": True
            }
        ]
    },
    {
        "name": "dataset_provenance_audit",
        "description": "Inspects dataset schemas, contracts, dimensions, and null ratios ensuring complete factual grounding.",
        "arguments": [
            {
                "name": "dataset_uri",
                "description": "Dataset node URI or table triad to audit.",
                "required": True
            }
        ]
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
                    "tools": {},
                    "prompts": {}
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                    "instructions": GUARDRAILS_INSTRUCTIONS
                }
            }
        }

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "prompts/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "prompts": PROMPTS
            }
        }

    if method == "prompts/get":
        prompt_name = params.get("name")
        args = params.get("arguments", {})
        if prompt_name == "grounded_sql_analysis":
            q = args.get("user_question", "")
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "description": "Strictly grounded SQL query workflow",
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": (
                                    f"Analyze the following question: '{q}'.\n"
                                    "STRICT GUARDRAILS:\n"
                                    "1. First call datamesh_search_catalog or datamesh_get_dataproduct to confirm table and column names.\n"
                                    "2. Run datamesh_sql_query with precise SQL.\n"
                                    "3. Base your final response ONLY on the rows returned. Cite the dataset triad. Never hallucinate numbers."
                                )
                            }
                        }
                    ]
                }
            }
        elif prompt_name == "dataset_provenance_audit":
            ds = args.get("dataset_uri", "")
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "description": "Audit dataset conformance and structure",
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": f"Audit dataset '{ds}' using datamesh_get_dataproduct and datamesh_sql_query. Verify dimensions, column types, row counts, and null presence without assumptions."
                            }
                        }
                    ]
                }
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Prompt not found: {prompt_name}"}
            }

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
