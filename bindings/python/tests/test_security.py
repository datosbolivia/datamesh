from __future__ import annotations

import os
import ssl
import sys
import unittest.mock as mock
from pathlib import Path

import pytest
import urllib.error
import urllib.request

TESTDATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "testdata"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datamesh.net import (
    host_is_allowed,
    is_forbidden_local_ref,
    open_url,
    validate_proxy_url,
)


def test_private_ip_targets_rejected():
    for url in (
        "http://127.0.0.1:8000/data.csv",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/x",
        "http://192.168.0.1/x",
    ):
        with pytest.raises(PermissionError):
            validate_proxy_url(url)


def test_public_ip_target_allowed():
    validate_proxy_url("http://8.8.8.8/data.csv")


def test_non_http_scheme_rejected():
    with pytest.raises(ValueError):
        validate_proxy_url("ftp://example.com/file.csv")
    with pytest.raises(ValueError):
        validate_proxy_url("file:///etc/passwd")


def test_allowlist_overrides_private_block(monkeypatch):
    monkeypatch.setenv("DATAMESH_PROXY_ALLOWED_HOSTS", "data.gob.bo")
    assert host_is_allowed("data.gob.bo") is True
    assert host_is_allowed("127.0.0.1") is False


def test_forbidden_local_refs():
    assert is_forbidden_local_ref("/etc/passwd") is True
    assert is_forbidden_local_ref("file:///etc/passwd") is True
    assert is_forbidden_local_ref("../../etc/passwd") is True
    assert is_forbidden_local_ref("air_quality:datasets:pm25") is False


@mock.patch("datamesh.net.urllib.request.urlopen")
def test_tls_failure_raises_without_optin(mock_urlopen, monkeypatch):
    monkeypatch.delenv("DATAMESH_INSECURE_TLS", raising=False)
    mock_urlopen.side_effect = urllib.error.URLError(ssl.SSLError(1, "CERTIFICATE_VERIFY_FAILED"))
    with pytest.raises(RuntimeError):
        open_url("https://example.gov/x.csv", timeout=5)


@mock.patch("datamesh.net.urllib.request.urlopen")
def test_tls_failure_retries_unverified_with_optin(mock_urlopen, monkeypatch):
    monkeypatch.setenv("DATAMESH_INSECURE_TLS", "1")
    valid_response = mock.Mock()
    mock_urlopen.side_effect = [
        urllib.error.URLError(ssl.SSLError(1, "CERTIFICATE_VERIFY_FAILED")),
        valid_response,
    ]
    resp = open_url("https://example.gov/x.csv", timeout=5)
    assert resp is valid_response
    assert mock_urlopen.call_count == 2