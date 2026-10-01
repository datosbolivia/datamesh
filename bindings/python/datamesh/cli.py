from __future__ import annotations

import argparse
import json
import sys
from typing import Dict

import datamesh as dm

def main():
    parser = argparse.ArgumentParser(
        prog="datamesh",
        description="DataMesh Sovereign SDK CLI (Python)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # catalog
    cat_parser = subparsers.add_parser("catalog", help="Discover sovereign catalogs")
    cat_parser.add_argument("url", nargs="?", default=None, help="Catalog URL (optional)")

    # search
    search_parser = subparsers.add_parser("search", help="Search catalog entries")
    search_parser.add_argument("keyword", help="Search keyword")
    search_parser.add_argument("url", nargs="?", default=None, help="Catalog URL (optional)")

    # get
    get_parser = subparsers.add_parser("get", help="Get Data Product manifest")
    get_parser.add_argument("uri", help="Data Product node URI or URL")

    # query
    query_parser = subparsers.add_parser("query", help="Query tabular resource")
    query_parser.add_argument("uri", help="Resource CSV/TSV URI")
    query_parser.add_argument("--filter", action="append", dest="filters", help="Filter formatted as key=value")
    query_parser.add_argument("--limit", type=int, default=None, help="Max rows to return")

    # sql
    sql_parser = subparsers.add_parser("sql", help="Execute full ANSI/DuckDB SQL with triad URIs ('catalogo:dataset:resource')")
    sql_parser.add_argument("query", help="SQL query string")
    sql_parser.add_argument("--engine", choices=["duckdb", "inmem", "go"], default=None, help="Query engine to use (default: duckdb)")

    # mcp-serve
    subparsers.add_parser("mcp-serve", help="Run Model Context Protocol (MCP) server over stdio")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Run full HTTP REST, CORS proxy, and MCP server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    serve_parser.add_argument("--port", "-p", type=int, default=8000, help="Bind port (default: 8000)")

    args = parser.parse_args()

    if args.command == "catalog":
        res = dm.discover(args.url)
        print(json.dumps(res, indent=2, ensure_ascii=False, default=str))

    elif args.command == "search":
        res = dm.search(args.keyword, args.url)
        print(json.dumps(res, indent=2, ensure_ascii=False, default=str))

    elif args.command == "get":
        res = dm.get(args.uri)
        print(json.dumps(res, indent=2, ensure_ascii=False, default=str))

    elif args.command == "query":
        filter_dict: Dict[str, str] = {}
        if args.filters:
            for f in args.filters:
                if "=" in f:
                    k, v = f.split("=", 1)
                    filter_dict[k.strip()] = v.strip()
        res = dm.query(args.uri, filters=filter_dict, limit=args.limit)
        print(json.dumps(res, indent=2, ensure_ascii=False, default=str))

    elif args.command == "sql":
        res = dm.sql(args.query, engine=args.engine)
        print(json.dumps(res, indent=2, ensure_ascii=False, default=str))

    elif args.command == "mcp-serve":
        from datamesh.mcp_server import run_mcp_server
        run_mcp_server()

    elif args.command == "serve":
        from datamesh.server import run_server
        run_server(host=args.host, port=args.port)

if __name__ == "__main__":
    main()
