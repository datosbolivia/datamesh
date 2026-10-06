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

    # publish
    pub_parser = subparsers.add_parser("publish", help="Publish ODKF dataset bundle to target platforms (local, portal, kaggle)")
    pub_parser.add_argument("path", help="Path to dataset directory or datapackage.yaml")
    pub_parser.add_argument("--target", "-t", action="append", dest="targets", help="Target platform (local, portal, kaggle)")
    pub_parser.add_argument("--dest", "-d", help="Destination path or directory (optional)")

    # align
    align_parser = subparsers.add_parser("align", help="Extract semantic field mappings from a DataPackage")
    align_parser.add_argument("path", help="Path to datapackage.yaml or JSON")

    # discover
    disc_parser = subparsers.add_parser("discover", help="Discover catalog metadata and auth specs via /.well-known/datamesh.json or active probing")
    disc_parser.add_argument("url", help="Target catalog URL or domain (e.g. 'datos.gob.bo')")

    # harvest-ckan
    harvest_parser = subparsers.add_parser("harvest-ckan", help="Harvest datasets from a CKAN portal and reconstruct OKF v0.2 knowledge packages")
    harvest_parser.add_argument("url", help="CKAN portal or API URL")
    harvest_parser.add_argument("--query", "-q", default="", help="Search filter query")
    harvest_parser.add_argument("--limit", "-l", type=int, default=100, help="Max packages to harvest")
    harvest_parser.add_argument("--offset", type=int, default=0, help="Pagination offset")
    harvest_parser.add_argument("--out-dir", "-o", default=None, help="Directory to output reconstructed OKF bundles")
    harvest_parser.add_argument("--token", help="API token or Bearer key")
    harvest_parser.add_argument("--client-id", help="OAuth2 / Keycloak Client ID")
    harvest_parser.add_argument("--client-secret", help="OAuth2 / Keycloak Client Secret")
    harvest_parser.add_argument("--scope", help="OAuth2 scope")

    # package-create
    pkg_create_parser = subparsers.add_parser("package-create", help="Create datapackage.yaml manifest from files or schemas")
    pkg_create_parser.add_argument("name", help="Package slug/name")
    pkg_create_parser.add_argument("--file", "-f", action="append", dest="files", help="File or archive to include (CSV, Parquet, ZIP)")
    pkg_create_parser.add_argument("--title", help="Package title")
    pkg_create_parser.add_argument("--desc", help="Package description")
    pkg_create_parser.add_argument("--out", "-o", help="Output file path (default: datapackage.yaml)")

    # package-link
    pkg_link_parser = subparsers.add_parser("package-link", help="Link column or categories to knowledge concepts in datapackage.yaml")
    pkg_link_parser.add_argument("path", help="Path to datapackage.yaml")
    pkg_link_parser.add_argument("--resource", "-r", required=True, help="Resource name or index")
    pkg_link_parser.add_argument("--column", "-c", required=True, help="Column name to link")
    pkg_link_parser.add_argument("--concept", help="Target concept path or URI (e.g. 'concepts/genero.md')")
    pkg_link_parser.add_argument("--map", "-m", action="append", dest="mappings", help="Category mapping formatted as 'VAL=Label' or 'VAL=Label:concept_path'")

    # package-explain
    pkg_exp_parser = subparsers.add_parser("package-explain", help="Generate OKF SKOS concept docs for categorical variables")
    pkg_exp_parser.add_argument("path", help="Path to datapackage.yaml")
    pkg_exp_parser.add_argument("--out-dir", "-o", default="concepts", help="Directory to output concept files (default: concepts)")

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

    elif args.command == "publish":
        opts = {}
        if args.dest:
            opts["destination"] = args.dest
        res = dm.publish(args.path, targets=args.targets, options=opts)
        print(json.dumps(res, indent=2, ensure_ascii=False, default=str))

    elif args.command == "align":
        import yaml
        from pathlib import Path
        p = Path(args.path)
        content = p.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content) if p.suffix in (".yaml", ".yml") else json.loads(content)
        res = dm.align_semantics(parsed)
        print(json.dumps(res, indent=2, ensure_ascii=False, default=str))

    elif args.command == "discover":
        disc = dm.discover_endpoint(args.url)
        if disc:
            out = {
                "schema_version": disc.schema_version,
                "catalog": {
                    "name": disc.catalog.name,
                    "title": disc.catalog.title,
                    "catalog_url": disc.catalog.catalog_url,
                    "type": disc.catalog.catalog_type,
                    "api_endpoint": disc.catalog.api_endpoint,
                    "description": disc.catalog.description,
                    "version": disc.catalog.version,
                },
                "auth": {
                    "type": disc.auth.auth_type,
                    "required": disc.auth.required,
                    "keycloak": {
                        "realm_url": disc.auth.keycloak.realm_url,
                        "token_endpoint": disc.auth.keycloak.token_endpoint,
                        "client_id": disc.auth.keycloak.client_id,
                        "scopes_supported": list(disc.auth.keycloak.scopes_supported),
                    } if disc.auth.keycloak else None,
                    "api_key": {
                        "header_name": disc.auth.api_key.header_name,
                        "prefix": disc.auth.api_key.prefix,
                    } if disc.auth.api_key else None,
                },
                "capabilities": disc.capabilities,
            }
            print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        else:
            print(json.dumps({"error": f"No catalog or well-known endpoint discovered at {args.url}"}))
            sys.exit(1)

    elif args.command == "harvest-ckan":
        res = dm.harvest_ckan(
            ckan_url=args.url,
            query=args.query,
            limit=args.limit,
            offset=args.offset,
            token=args.token,
            client_id=args.client_id,
            client_secret=args.client_secret,
            scope=args.scope,
            output_dir=args.out_dir,
        )
        out = {
            "catalog_url": res.catalog_url,
            "total_discovered": res.total_discovered,
            "harvested_count": len(res.harvested_packages),
            "output_directory": res.output_directory,
            "execution_time_ms": res.execution_time_ms,
            "packages": [p["name"] for p in res.harvested_packages],
        }
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))

    elif args.command == "package-create":
        res = dm.create_datapackage(
            name=args.name,
            title=args.title,
            description=args.desc,
            files=args.files,
            output_file=args.out or "datapackage.yaml",
        )
        out = {
            "name": res.name,
            "title": res.title,
            "output_path": res.output_path,
            "resource_count": len(res.datapackage.get("resources", [])),
        }
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))

    elif args.command == "package-link":
        mapping_dict = {}
        if args.mappings:
            for m in args.mappings:
                if "=" in m:
                    k, rest = m.split("=", 1)
                    if ":" in rest:
                        lbl, c_ref = rest.split(":", 1)
                        mapping_dict[k.strip()] = {"label": lbl.strip(), "concept": c_ref.strip()}
                    else:
                        mapping_dict[k.strip()] = rest.strip()
        res_pkg = dm.link_concept(
            datapackage_path_or_dict=args.path,
            resource_name=args.resource,
            column_name=args.column,
            concept_ref=args.concept,
            value_mappings=mapping_dict if mapping_dict else None,
            save_to_path=args.path,
        )
        print(json.dumps({
            "status": "updated",
            "path": args.path,
            "resource": args.resource,
            "column": args.column,
            "concept": args.concept,
        }, indent=2, ensure_ascii=False))

    elif args.command == "package-explain":
        docs = dm.explain_categories(
            datapackage_path_or_dict=args.path,
            output_concepts_dir=args.out_dir,
        )
        print(json.dumps({
            "status": "success",
            "output_directory": args.out_dir,
            "generated_concepts": [d.id for d in docs],
            "total": len(docs),
        }, indent=2, ensure_ascii=False))

    elif args.command == "mcp-serve":
        from datamesh.mcp_server import run_mcp_server
        run_mcp_server()

    elif args.command == "serve":
        from datamesh.server import run_server
        run_server(host=args.host, port=args.port)

if __name__ == "__main__":
    main()
