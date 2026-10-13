from __future__ import annotations

import io
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from datamesh.domain.errors import (
    AuthenticationRequiredError,
    InvalidContentTypeError,
    CatalogConnectionError,
)
from datamesh.domain.models import CatalogPatternRule, StorageConfig
from datamesh.adapters.resolvers.http import HttpAdapter
from datamesh.adapters.catalog.ckan_client import CKANClientAdapter
from datamesh.adapters.storage.local_storage import LocalStorageManager


class MockStreamResponse:
    def __init__(self, data: bytes, headers: dict | None = None, url: str = "http://example.com"):
        self._buf = io.BytesIO(data)
        self.headers = headers or {"Content-Type": "text/csv"}
        self._url = url

    def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _storage(tmp_path: Path) -> LocalStorageManager:
    home = tmp_path / "datamesh"
    return LocalStorageManager(
        StorageConfig(home_dir=home, cache_dir=home / "cache", config_file=home / "config.yaml")
    )


def test_catalog_pattern_rule_rewrite_and_auth(monkeypatch):
    monkeypatch.setenv("TEST_CATALOG_KEY", "secret-token-123")
    rule = CatalogPatternRule(
        name="test_portal",
        pattern="*portales.economiayfinanzas.gob.bo/datahub*",
        rewrite_to="http://ckan-backend.internal.local",
        auth_type="bearer",
        auth_token_env="TEST_CATALOG_KEY",
    )

    url = "https://portales.economiayfinanzas.gob.bo/datahub/dataset/fmi-bcb/resource/123/download/file.parquet"
    assert rule.matches(url) is True
    assert rule.matches("https://other.com/data") is False

    rewritten = rule.rewrite(url)
    assert rewritten == "http://ckan-backend.internal.local/dataset/fmi-bcb/resource/123/download/file.parquet"

    hdrs = rule.get_auth_headers()
    assert hdrs == {"Authorization": "Bearer secret-token-123"}


def test_http_adapter_rejects_html_content_type(monkeypatch, tmp_path):
    storage = _storage(tmp_path)
    url = "https://example.com/dataset/data.parquet"

    html_resp = MockStreamResponse(
        b"<html><body>Login Portal</body></html>",
        headers={"Content-Type": "text/html; charset=utf-8"},
    )
    import datamesh.adapters.resolvers.http as http_mod
    monkeypatch.setattr(http_mod, "open_url", lambda req, timeout=30: html_resp)

    adapter = HttpAdapter()
    with pytest.raises(InvalidContentTypeError) as exc_info:
        adapter.resolve_and_fetch(url, storage)

    assert "returned HTML" in str(exc_info.value)
    # Ensure cache is not poisoned with HTML
    assert not storage.is_cached(url)


def test_http_adapter_rejects_html_doctype_body(monkeypatch, tmp_path):
    storage = _storage(tmp_path)
    url = "https://example.com/dataset/data.csv"

    html_resp = MockStreamResponse(
        b"<!DOCTYPE html><html><body>Error</body></html>",
        headers={"Content-Type": "text/plain"},
    )
    import datamesh.adapters.resolvers.http as http_mod
    monkeypatch.setattr(http_mod, "open_url", lambda req, timeout=30: html_resp)

    adapter = HttpAdapter()
    with pytest.raises(InvalidContentTypeError) as exc_info:
        adapter.resolve_and_fetch(url, storage)

    assert "HTML markup" in str(exc_info.value)
    assert not storage.is_cached(url)


def test_http_adapter_rejects_invalid_parquet_magic_bytes(monkeypatch, tmp_path):
    storage = _storage(tmp_path)
    url = "https://example.com/dataset/corrupt.parquet"

    bad_parquet = MockStreamResponse(
        b"NOT_PARQUET_MAGIC_BYTES_12345",
        headers={"Content-Type": "application/octet-stream"},
    )
    import datamesh.adapters.resolvers.http as http_mod
    monkeypatch.setattr(http_mod, "open_url", lambda req, timeout=30: bad_parquet)

    adapter = HttpAdapter()
    with pytest.raises(InvalidContentTypeError) as exc_info:
        adapter.resolve_and_fetch(url, storage)

    assert "magic bytes 'PAR1'" in str(exc_info.value)
    assert not storage.is_cached(url)


def test_http_adapter_detects_sso_redirect(monkeypatch, tmp_path):
    storage = _storage(tmp_path)
    url = "https://portales.economiayfinanzas.gob.bo/datahub/dataset/fmi-bcb/data.parquet"

    redirect_resp = MockStreamResponse(
        b"PAR1validparquet",
        headers={"Content-Type": "application/octet-stream"},
        url="https://auth.economiayfinanzas.gob.bo/realms/datalake/protocol/openid-connect/auth?code=123",
    )
    import datamesh.adapters.resolvers.http as http_mod
    monkeypatch.setattr(http_mod, "open_url", lambda req, timeout=30: redirect_resp)

    adapter = HttpAdapter()
    with pytest.raises(AuthenticationRequiredError) as exc_info:
        adapter.resolve_and_fetch(url, storage)

    assert "redirected to authentication portal" in str(exc_info.value)
    assert not storage.is_cached(url)


def test_http_adapter_raises_on_http_401_and_403(monkeypatch, tmp_path):
    storage = _storage(tmp_path)
    url = "https://example.com/dataset/private.parquet"

    def _raise_401(req, timeout=30):
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)

    import datamesh.adapters.resolvers.http as http_mod
    monkeypatch.setattr(http_mod, "open_url", _raise_401)

    adapter = HttpAdapter()
    with pytest.raises(AuthenticationRequiredError) as exc_info:
        adapter.resolve_and_fetch(url, storage)

    assert "HTTP 401 Unauthorized" in str(exc_info.value)
    assert not storage.is_cached(url)


def test_ckan_client_rejects_html_response(monkeypatch):
    client = CKANClientAdapter()
    html_resp = MockStreamResponse(
        b"<html>Keycloak Sign In</html>",
        headers={"Content-Type": "text/html"},
        url="https://auth.economiayfinanzas.gob.bo/realms/datalake/login",
    )

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=15: html_resp)

    with pytest.raises(InvalidContentTypeError) as exc_info:
        client.get_package("http://example.com", "pkg-1")

    assert "returned HTML webpage" in str(exc_info.value)


def test_ckan_client_raises_on_http_403(monkeypatch):
    client = CKANClientAdapter()

    def _raise_403(req, timeout=15):
        raise urllib.error.HTTPError("http://example.com", 403, "Forbidden", {}, None)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _raise_403)

    with pytest.raises(AuthenticationRequiredError) as exc_info:
        client.get_package("http://example.com", "pkg-1")

    assert "HTTP 403" in str(exc_info.value)
