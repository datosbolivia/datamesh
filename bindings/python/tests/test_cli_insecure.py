from __future__ import annotations

import os
import sys
from unittest import mock
import pytest

from datamesh import cli


def test_cli_insecure_flag_sets_env(monkeypatch):
    monkeypatch.delenv("DATAMESH_INSECURE_TLS", raising=False)
    assert os.environ.get("DATAMESH_INSECURE_TLS") is None

    with mock.patch("sys.argv", ["datamesh", "--insecure", "sql", "SELECT 1"]):
        with mock.patch("datamesh.sql") as mock_sql:
            mock_sql.return_value = {"columns": ["1"], "rows": [[1]], "row_count": 1}
            cli.main()
            assert os.environ.get("DATAMESH_INSECURE_TLS") == "1"


def test_cli_short_k_flag_sets_env(monkeypatch):
    monkeypatch.delenv("DATAMESH_INSECURE_TLS", raising=False)
    assert os.environ.get("DATAMESH_INSECURE_TLS") is None

    with mock.patch("sys.argv", ["datamesh", "sql", "-k", "SELECT 1"]):
        with mock.patch("datamesh.sql") as mock_sql:
            mock_sql.return_value = {"columns": ["1"], "rows": [[1]], "row_count": 1}
            cli.main()
            assert os.environ.get("DATAMESH_INSECURE_TLS") == "1"
