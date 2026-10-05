from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

import datamesh as dm

class DataMeshServerHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler providing REST API, CORS Proxy, and MCP JSON-RPC 2.0 endpoints."""

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query_params = urllib.parse.parse_qs(parsed.query)

        # 1. Health check & Ping
        if path in ("/health", "/ping", "/proxy/ping"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            resp = {
                "status": "ok",
                "pong": True,
                "service": "datamesh-server",
                "runtime": "python",
                "version": "0.2.0",
                "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        # 2. CORS Proxy Endpoint (/proxy?url=...)
        if path == "/proxy":
            target_url = query_params.get("url", [None])[0]
            if not target_url:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(b'{"error": "Missing \'url\' query parameter"}')
                return

            # A. First check if DataMesh runtime resolver can resolve target_url
            try:
                resolved = dm._runtime.resolver_usecase.resolve(target_url)
                if resolved and resolved.local_path and os.path.exists(resolved.local_path):
                    local_p = str(resolved.local_path)
                    # If target requested .csv but resolved is .parquet or .zip, convert on the fly if needed or stream
                    wants_csv = target_url.lower().endswith(".csv")
                    is_parquet = local_p.lower().endswith(".parquet")
                    is_zip = local_p.lower().endswith(".zip")
                    
                    if wants_csv and is_parquet:
                        import duckdb
                        csv_data = duckdb.query(f"SELECT * FROM read_parquet('{local_p}')").to_df().to_csv(index=False).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "text/csv; charset=utf-8")
                        self._send_cors_headers()
                        self.end_headers()
                        self.wfile.write(csv_data)
                        return
                    elif wants_csv and is_zip:
                        from datamesh.adapters.storage.zip_extractor import extract_zip_tabular_resource
                        extracted_p, _ = extract_zip_tabular_resource(local_p)
                        if extracted_p:
                            import duckdb
                            csv_data = duckdb.query(f"SELECT * FROM read_csv_auto('{extracted_p}')").to_df().to_csv(index=False).encode("utf-8")
                            self.send_response(200)
                            self.send_header("Content-Type", "text/csv; charset=utf-8")
                            self._send_cors_headers()
                            self.end_headers()
                            self.wfile.write(csv_data)
                            return
                    else:
                        content_type = "application/octet-stream"
                        if local_p.endswith(".parquet"):
                            content_type = "application/vnd.apache.parquet"
                        elif local_p.endswith(".csv"):
                            content_type = "text/csv; charset=utf-8"
                        elif local_p.endswith(".json"):
                            content_type = "application/json"
                        elif local_p.endswith(".zip"):
                            content_type = "application/zip"
                        
                        with open(local_p, "rb") as f:
                            file_bytes = f.read()

                        self.send_response(200)
                        self.send_header("Content-Type", content_type)
                        self._send_cors_headers()
                        self.end_headers()
                        self.wfile.write(file_bytes)
                        return
            except Exception as resolve_err:
                sys.stderr.write(f"[datamesh serve] Resolver fallback skipped: {resolve_err}\n")

            # B. Direct HTTP fetch attempt
            import ssl
            try:
                req = urllib.request.Request(
                    target_url,
                    headers={"User-Agent": "DataMesh-Sovereign-Proxy/0.2.0 (+https://datosbolivia.org)"},
                )
                try:
                    resp_ctx = urllib.request.urlopen(req, timeout=30)
                except urllib.error.URLError as u_err:
                    if isinstance(u_err.reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(u_err) or "certificate" in str(u_err).lower():
                        unverified = ssl.create_default_context()
                        unverified.check_hostname = False
                        unverified.verify_mode = ssl.CERT_NONE
                        resp_ctx = urllib.request.urlopen(req, timeout=30, context=unverified)
                    else:
                        raise

                with resp_ctx as resp:
                    status_code = resp.status
                    content_type = resp.headers.get("Content-Type", "application/octet-stream")
                    body = resp.read()

                self.send_response(status_code)
                self.send_header("Content-Type", content_type)
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(body)
                return
            except urllib.error.HTTPError as e:
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Upstream HTTP {e.code}: {e.reason}"}).encode("utf-8"))
                return
            except Exception as e:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Proxy request failed: {str(e)}"}).encode("utf-8"))
                return

        # 3. REST API: /api/catalog
        if path == "/api/catalog":
            cat_url = query_params.get("url", [None])[0]
            try:
                res = dm.discover(cat_url)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(res, default=str).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # 4. REST API: /api/sql?q=...
        if path == "/api/sql":
            sql_query = query_params.get("q", [None])[0]
            if not sql_query:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(b'{"error": "Missing \'q\' SQL query parameter"}')
                return

            try:
                res = dm.sql(sql_query)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(res, default=str).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # Not found
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(b'{"error": "Endpoint not found"}')

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # 1. MCP Server / JSON-RPC 2.0 Endpoint (/mcp)
        if path in ("/mcp", "/rpc"):
            try:
                rpc_req = json.loads(body.decode("utf-8"))
                from datamesh.mcp_server import handle_jsonrpc
                rpc_resp = handle_jsonrpc(rpc_req)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(rpc_resp, default=str).encode("utf-8"))
            except Exception as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse or execution error: {str(e)}"},
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(err_resp).encode("utf-8"))
            return

        # 2. REST API: POST /api/sql
        if path == "/api/sql":
            try:
                req_json = json.loads(body.decode("utf-8"))
                sql_query = req_json.get("query") or req_json.get("sql")
                if not sql_query:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(b'{"error": "Missing \'query\' in request body"}')
                    return

                res = dm.sql(sql_query)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(res, default=str).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # Not found
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(b'{"error": "Endpoint not found"}')

    def log_message(self, format, *args):
        # Terse logging
        sys.stderr.write(f"[datamesh serve] {args[0]} {args[1]} -> {args[2]}\n")
        sys.stderr.flush()

class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Starts the DataMesh HTTP REST, CORS proxy, and MCP server."""
    server_address = (host, port)
    httpd = ReusableHTTPServer(server_address, DataMeshServerHandler)

    addr_display = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}"
    sys.stderr.write(f"DataMesh Sovereign Server started on {addr_display}\n")
    sys.stderr.write(f"  - Health:     {addr_display}/health\n")
    sys.stderr.write(f"  - CORS Proxy: {addr_display}/proxy?url=<target_url>\n")
    sys.stderr.write(f"  - REST Cat:   {addr_display}/api/catalog\n")
    sys.stderr.write(f"  - REST SQL:   {addr_display}/api/sql?q=<sql_query>\n")
    sys.stderr.write(f"  - MCP RPC:    {addr_display}/mcp\n")
    sys.stderr.flush()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\nDataMesh Server shutting down gracefully...\n")
        httpd.server_close()
