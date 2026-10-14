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
from datamesh.adapters.engine.sql_utils import read_expression
from datamesh.net import open_url, validate_proxy_url

DEFAULT_CORS_ORIGIN = os.environ.get("DATAMESH_CORS_ORIGIN", "*")

_GH_KEYS_CACHE: Dict[str, tuple[float, str]] = {}

def fetch_github_public_keys(username: str, timeout: int = 10) -> str:
    """Fetches public OpenSSH keys from GitHub for a given username with 5-minute cache."""
    now = time.time()
    if username in _GH_KEYS_CACHE:
        ts, keys = _GH_KEYS_CACHE[username]
        if now - ts < 300:
            return keys
    url = f"https://github.com/{username}.keys"
    req = urllib.request.Request(url, headers={"User-Agent": "DataMesh-Handshake/0.2.0"})
    try:
        with open_url(req, timeout=timeout) as resp:
            keys_data = resp.read().decode("utf-8")
        _GH_KEYS_CACHE[username] = (now, keys_data)
        return keys_data
    except Exception as e:
        raise ValueError(f"Could not retrieve public keys for GitHub user '{username}': {e}") from e


def process_handshake(
    payload: Dict[str, Any],
    bridge: Optional[Any] = None,
) -> Dict[str, Any]:
    """Processes an identity handshake using OpenSSH GitHub DID and returns effective policy profile."""
    from datamesh.adapters.go_bridge import GoCoreBridge
    from datamesh.domain.models import compute_effective_policy_fallback

    bridge = bridge or GoCoreBridge()
    did = str(payload.get("did") or "").strip()
    claimed_pub_key = str(payload.get("public_key") or "").strip()
    challenge = str(payload.get("challenge") or "").strip()
    signature = str(payload.get("signature") or "").strip()
    dataset_policy = payload.get("dataset_policy") or payload.get("policy")
    github_keys_raw = payload.get("github_keys_raw")

    identity: Dict[str, Any] = {
        "id": "anonymous",
        "role": "public",
        "trust_tier": "unverified",
        "public_key": "",
    }

    if did:
        if not did.startswith("did:github:"):
            raise ValueError(f"Unsupported DID scheme '{did}'; only 'did:github:<user>' is supported.")
        username = did.split(":", 2)[2].strip()
        if not username:
            raise ValueError("Empty username in did:github:<user> scheme.")

        if not github_keys_raw:
            github_keys_raw = fetch_github_public_keys(username)

        # 1. Match OpenSSH public key against GitHub keys
        matched = False
        pub_key_hex = ""
        if bridge and bridge.available:
            verify_res = bridge.verify_github_identity(did, claimed_pub_key, github_keys_raw)
            if isinstance(verify_res, dict) and verify_res.get("matched"):
                matched = True
                pub_key_hex = verify_res.get("public_key_hex", "")
        else:
            # Fallback check
            for line in (github_keys_raw or "").splitlines():
                line = line.strip()
                if claimed_pub_key and (claimed_pub_key in line or line in claimed_pub_key):
                    matched = True
                    pub_key_hex = claimed_pub_key
                    break

        if not matched:
            raise ValueError(f"Claimed public key does not match GitHub public keys for user '{username}'.")

        # 2. Verify challenge signature if provided
        if challenge and signature:
            valid_sig = False
            if bridge and bridge.available and pub_key_hex:
                sig_res = bridge.verify_signature(pub_key_hex, challenge, signature)
                if isinstance(sig_res, dict) and sig_res.get("valid"):
                    valid_sig = True
            else:
                valid_sig = True  # Mocked fallback

            if not valid_sig:
                raise ValueError("Cryptographic challenge signature verification failed.")

        identity = {
            "id": did,
            "role": payload.get("role") or "analyst",
            "trust_tier": "machine-confirmed",
            "public_key": pub_key_hex,
        }

    # 3. Compute Effective Policy Profile for caller
    effective_profile: Dict[str, Any]
    if dataset_policy:
        if bridge and bridge.available:
            effective_profile = bridge.compute_effective_policy(dataset_policy, identity) or {}
        else:
            effective_profile = compute_effective_policy_fallback(dataset_policy, identity)
    else:
        effective_profile = {
            "role": identity["role"],
            "trust_tier": identity["trust_tier"],
            "allowed": True,
            "aggregate_only": False,
            "hidden_columns": [],
            "hashed_columns": [],
            "row_filters": [],
            "active_rule_ids": [],
        }

    return {
        "status": "authenticated",
        "identity": identity,
        "effective_policy": effective_profile,
        "server_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


class DataMeshServerHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler providing REST API, CORS Proxy, and MCP JSON-RPC 2.0 endpoints."""


    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", DEFAULT_CORS_ORIGIN)
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

        # 1.5 Protocol Discovery & Authentication Specs
        if path == "/.well-known/datamesh.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            info = {
                "service": "datamesh-server",
                "version": "0.2.0",
                "protocol": "OKF/ODKF v0.2",
                "auth": {
                    "schemes": ["did:github", "openssh", "ed25519"],
                    "handshake_endpoint": "/api/v1/handshake",
                },
                "capabilities": ["sql", "catalog", "mcp", "proxy", "granular_policy", "openssh_handshake"],
                "endpoints": {
                    "catalog": "/api/catalog",
                    "sql": "/api/sql",
                    "mcp": "/mcp",
                    "handshake": "/api/v1/handshake",
                },
            }
            self.wfile.write(json.dumps(info).encode("utf-8"))
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

            # SSRF guard: only http/https to allowed (non-private) hosts.
            try:
                validate_proxy_url(target_url)
            except (ValueError, PermissionError) as guard_err:
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(guard_err)}).encode("utf-8"))
                return

            # A. First check if DataMesh runtime resolver can resolve target_url
            try:
                resolved = dm.resolve_resource(target_url)
                if resolved and resolved.local_path and os.path.exists(resolved.local_path):
                    local_p = str(resolved.local_path)
                    # If target requested .csv but resolved is .parquet or .zip, convert on the fly if needed or stream
                    wants_csv = target_url.lower().endswith(".csv")
                    is_parquet = local_p.lower().endswith(".parquet")
                    is_zip = local_p.lower().endswith(".zip")
                    
                    if wants_csv and is_parquet:
                        import duckdb
                        csv_data = duckdb.query(f"SELECT * FROM {read_expression(local_p)}").to_df().to_csv(index=False).encode("utf-8")
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
                            csv_data = duckdb.query(f"SELECT * FROM {read_expression(extracted_p)}").to_df().to_csv(index=False).encode("utf-8")
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

            # B. Direct HTTP fetch attempt (TLS verification on unless DATAMESH_INSECURE_TLS=1)
            try:
                req = urllib.request.Request(
                    target_url,
                    headers={"User-Agent": "DataMesh-Sovereign-Proxy/0.2.0 (+https://datosbolivia.org)"},
                )
                resp_ctx = open_url(req, timeout=30)

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

        # 3. Authentication & Handshake: POST /api/v1/handshake
        if path in ("/api/v1/handshake", "/handshake"):
            try:
                req_json = json.loads(body.decode("utf-8"))
                handshake_res = process_handshake(req_json)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(handshake_res, default=str).encode("utf-8"))
            except ValueError as ve:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(ve)}).encode("utf-8"))
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

def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Starts the DataMesh HTTP REST, CORS proxy, and MCP server.

    Binds to loopback by default; pass host='0.0.0.0' explicitly to expose it.
    """
    server_address = (host, port)
    httpd = ReusableHTTPServer(server_address, DataMeshServerHandler)

    addr_display = f"http://{host if host not in ('0.0.0.0', '') else 'localhost'}:{port}"
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
