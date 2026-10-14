from __future__ import annotations

import base64
import json
import os
import struct
import tempfile
import pytest

from datamesh.adapters.engine.duckdb_engine import DuckDBQueryEngine
from datamesh.adapters.go_bridge import GoCoreBridge
from datamesh.domain.errors import PolicyViolationError
from datamesh.mcp_server import handle_jsonrpc
from datamesh.server import process_handshake


def _make_openssh_key(seed_byte: bytes = b"A") -> str:
    raw = seed_byte * 32
    blob = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", len(raw)) + raw
    b64 = base64.b64encode(blob).decode("ascii")
    return f"ssh-ed25519 {b64} octocat@github"


def test_handshake_with_github_did_and_openssh_key():
    bridge = GoCoreBridge("/tmp/libdatamesh.so")
    ssh_line = _make_openssh_key(b"B")

    granular_policy = {
        "name": "censo_governance",
        "rules": [
            {
                "id": "rule_public_strict",
                "description": "Public users cannot access microdata, hidden CI and filtered before 2026",
                "applies_to": ["public", "unverified"],
                "hidden_columns": ["ci"],
                "hashed_columns": ["email"],
                "row_filters": ["gestion >= 2026"],
                "aggregate_only": True,
            },
            {
                "id": "rule_analyst_verified",
                "description": "Verified analysts can access microdata but with masked emails and hidden CI",
                "applies_to": ["analyst"],
                "hidden_columns": ["ci"],
                "hashed_columns": ["email"],
                "row_filters": ["gestion >= 2026"],
                "aggregate_only": False,
            },
        ],
    }

    # 1. Handshake with matching GitHub DID
    payload = {
        "did": "did:github:octocat",
        "public_key": ssh_line,
        "github_keys_raw": ssh_line,
        "role": "analyst",
        "dataset_policy": granular_policy,
    }

    res = process_handshake(payload, bridge=bridge)
    assert res["status"] == "authenticated"
    assert res["identity"]["id"] == "did:github:octocat"
    assert res["identity"]["role"] == "analyst"
    assert res["identity"]["trust_tier"] == "machine-confirmed"

    profile = res["effective_policy"]
    assert profile["allowed"] is True
    assert profile["aggregate_only"] is False
    assert "ci" in profile["hidden_columns"]
    assert "email" in profile["hashed_columns"]
    assert "gestion >= 2026" in profile["row_filters"]
    assert "rule_analyst_verified" in profile["active_rule_ids"]


def test_handshake_rejects_unauthorized_key():
    bridge = GoCoreBridge("/tmp/libdatamesh.so")
    real_ssh_line = _make_openssh_key(b"C")
    fake_ssh_line = _make_openssh_key(b"D")

    payload = {
        "did": "did:github:octocat",
        "public_key": fake_ssh_line,
        "github_keys_raw": real_ssh_line,
    }

    with pytest.raises(ValueError, match="does not match GitHub public keys"):
        process_handshake(payload, bridge=bridge)


def test_handshake_rejects_invalid_did():
    bridge = GoCoreBridge("/tmp/libdatamesh.so")
    ssh_line = _make_openssh_key(b"E")

    payload = {
        "did": "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvKtH",
        "public_key": ssh_line,
    }

    with pytest.raises(ValueError, match="Unsupported DID scheme"):
        process_handshake(payload, bridge=bridge)


def test_mcp_handshake_tool():
    ssh_line = _make_openssh_key(b"F")
    req = {
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tools/call",
        "params": {
            "name": "datamesh_handshake",
            "arguments": {
                "did": "did:github:octocat",
                "public_key": ssh_line,
                "github_keys_raw": ssh_line,
                "role": "analyst",
            },
        },
    }

    resp = handle_jsonrpc(req)
    assert resp["id"] == 101
    assert "result" in resp
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["status"] == "authenticated"
    assert content["identity"]["id"] == "did:github:octocat"


def test_duckdb_granular_policy_enforcement():
    bridge = GoCoreBridge("/tmp/libdatamesh.so")
    engine = DuckDBQueryEngine(bridge=bridge)

    # Prepare temporary CSV data
    with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as tf:
        tf.write("id,nombre,ci,email,gestion\n")
        tf.write("1,Alice,111111,alice@example.com,2024\n")
        tf.write("2,Bob,222222,bob@example.com,2026\n")
        tf.write("3,Charlie,333333,charlie@example.com,2027\n")
        tf.flush()
        csv_path = tf.name

    try:
        granular_policy = {
            "name": "censo_granular",
            "rules": [
                {
                    "id": "rule_public",
                    "applies_to": ["public", "unverified"],
                    "hidden_columns": ["ci"],
                    "hashed_columns": ["email"],
                    "row_filters": ["gestion >= 2026"],
                    "aggregate_only": True,
                },
                {
                    "id": "rule_analyst",
                    "applies_to": ["analyst"],
                    "hidden_columns": ["ci"],
                    "hashed_columns": ["email"],
                    "row_filters": ["gestion >= 2026"],
                    "aggregate_only": False,
                },
            ],
        }

        table_ref = "bolivia:censo:personas"
        engine.register_table(table_ref, csv_path)
        engine.set_table_policy(table_ref, granular_policy)

        # 1. Public caller (aggregate_only = True) -> raw SELECT * must fail
        with pytest.raises(PolicyViolationError, match="zero_microdata"):
            engine.execute_sql(
                f"SELECT * FROM \"{table_ref}\"",
                table_mapping={"__identity__": {"role": "public"}},
            )

        # 2. Public caller -> aggregate query is allowed
        agg_res = engine.execute_sql(
            f"SELECT COUNT(*) as total FROM \"{table_ref}\"",
            table_mapping={"__identity__": {"role": "public"}},
        )
        assert agg_res["row_count"] == 1

        # 3. Verified analyst -> SELECT * succeeds, but:
        #    - 'ci' column is excluded/hidden
        #    - 'email' is hashed with SHA-256
        #    - row 1 (gestion 2024) is filtered out (< 2026)
        analyst_identity = {"role": "analyst", "trust_tier": "machine-confirmed"}
        raw_res = engine.execute_sql(
            f"SELECT * FROM \"{table_ref}\"",
            table_mapping={"__identity__": analyst_identity},
        )

        assert "ci" not in raw_res["columns"]
        assert "email" in raw_res["columns"]
        assert "gestion" in raw_res["columns"]
        assert "nombre" in raw_res["columns"]

        # Only rows for 2026 and 2027 should exist (row 1 with 2024 excluded)
        assert raw_res["row_count"] == 2
        gestiones = [r[raw_res["columns"].index("gestion")] for r in raw_res["rows"]]
        assert 2024 not in gestiones
        assert 2026 in gestiones
        assert 2027 in gestiones

        # Email must be hashed (64-char hex SHA-256), not plaintext "bob@example.com"
        email_idx = raw_res["columns"].index("email")
        for r in raw_res["rows"]:
            email_val = str(r[email_idx])
            assert len(email_val) == 64
            assert "@" not in email_val

        # 4. Explicit attempt to query hidden column 'ci' must be rejected
        with pytest.raises(PolicyViolationError, match="hidden/restricted"):
            engine.execute_sql(
                f"SELECT ci, nombre FROM \"{table_ref}\"",
                table_mapping={"__identity__": analyst_identity},
            )

    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)
