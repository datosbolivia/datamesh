import io
import logging
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from datamesh.adapters.resolvers.kaggle import KaggleAdapter
from datamesh.adapters.resolvers.http import HttpAdapter
from datamesh.adapters.storage.local_storage import LocalStorageManager
from datamesh.domain.models import ResolvedResource, ResourceDescriptor, StorageConfig


def _storage(tmp_path: Path) -> LocalStorageManager:
    home = tmp_path / "datamesh"
    return LocalStorageManager(
        StorageConfig(home_dir=home, cache_dir=home / "cache", config_file=home / "config.yaml")
    )


def _isolate_workspace(monkeypatch, tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DATAMESH_PROJECTS_DIR", str(ws))
    monkeypatch.setenv("DATAMESH_WORKSPACE_DIR", str(ws))
    return ws


KAGGLE_URL = "https://www.kaggle.com/datasets/andreschirinos/p2p-bob-exchange/advice.parquet"


def test_kaggle_adapter_is_remote_first(monkeypatch, tmp_path):
    """A fresh remote fetch must win over a stale local sibling file."""
    storage = _storage(tmp_path)
    ws = _isolate_workspace(monkeypatch, tmp_path)

    sibling = ws / "p2p-bob-exchange" / "data"
    sibling.mkdir(parents=True)
    (sibling / "advice.parquet").write_bytes(b"stale-sibling")

    fresh = tmp_path / "fresh.parquet"
    fresh.write_bytes(b"fresh-remote")

    adapter = KaggleAdapter()
    calls = {}

    def fake_download(uri, stor, owner, dataset, ref, filename, freq, prev):
        calls["hit"] = True
        return ResolvedResource(
            descriptor=ResourceDescriptor(
                raw_reference=uri, dataset=dataset, resource=filename,
                format="parquet", source_service="kaggle",
            ),
            local_path=fresh,
            format="parquet",
            is_cached=True,
        )

    monkeypatch.setattr(adapter, "_download_latest", fake_download)

    resolved = adapter.resolve_and_fetch(KAGGLE_URL, storage, {"dataset": "p2p-bob-exchange", "resource": "advice"})

    assert calls.get("hit") is True
    assert resolved.local_path == fresh.resolve()
    assert resolved.local_path.read_bytes() == b"fresh-remote"


def test_kaggle_adapter_falls_back_to_cache_with_warning(monkeypatch, tmp_path, caplog):
    storage = _storage(tmp_path)
    _isolate_workspace(monkeypatch, tmp_path)
    storage.save(KAGGLE_URL, b"cached-stale", extension=".parquet", source_service="kaggle")

    adapter = KaggleAdapter()

    def boom(*args, **kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(adapter, "_download_latest", boom)

    with caplog.at_level(logging.WARNING, logger="datamesh.resolvers.kaggle"):
        resolved = adapter.resolve_and_fetch(KAGGLE_URL, storage, {})

    assert resolved.is_cached is True
    assert resolved.local_path.read_bytes() == b"cached-stale"
    assert any("stale" in m for m in caplog.messages)


def test_kaggle_adapter_warns_on_sibling_fallback(monkeypatch, tmp_path, caplog):
    storage = _storage(tmp_path)
    ws = _isolate_workspace(monkeypatch, tmp_path)

    sibling = ws / "p2p-bob-exchange" / "data"
    sibling.mkdir(parents=True)
    (sibling / "advice.parquet").write_bytes(b"stale-sibling")

    adapter = KaggleAdapter()
    monkeypatch.setattr(adapter, "_download_latest", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))

    with caplog.at_level(logging.WARNING, logger="datamesh.resolvers.kaggle"):
        resolved = adapter.resolve_and_fetch(KAGGLE_URL, storage, {"dataset": "p2p-bob-exchange", "resource": "advice"})

    assert resolved.local_path.read_bytes() == b"stale-sibling"
    assert resolved.is_cached is False
    assert any("stale" in m or "out of sync" in m for m in caplog.messages)


class _FakeResponse:
    def __init__(self, data: bytes, content_type: str = "text/csv"):
        self._buf = io.BytesIO(data)
        self.headers = {"Content-Type": content_type}

    def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_http_adapter_remote_first_refreshes_cache(monkeypatch, tmp_path, caplog):
    storage = _storage(tmp_path)
    url = "https://example.com/data/advice.csv"
    storage.save(url, b"old-content", extension=".csv", source_service="http")

    import datamesh.adapters.resolvers.http as http_mod
    monkeypatch.setattr(http_mod, "open_url", lambda req, timeout=30: _FakeResponse(b"new-content"))

    adapter = HttpAdapter()
    with caplog.at_level(logging.INFO, logger="datamesh.resolvers.http"):
        resolved = adapter.resolve_and_fetch(url, storage, {})

    assert resolved.local_path.read_bytes() == b"new-content"
    assert any("changed" in m for m in caplog.messages)


def test_http_adapter_falls_back_to_cache_with_warning(monkeypatch, tmp_path, caplog):
    storage = _storage(tmp_path)
    url = "https://example.com/data/advice.csv"
    storage.save(url, b"cached-stale", extension=".csv", source_service="http")

    import datamesh.adapters.resolvers.http as http_mod

    def boom(req, timeout=30):
        raise RuntimeError("network down")

    monkeypatch.setattr(http_mod, "open_url", boom)

    adapter = HttpAdapter()
    with caplog.at_level(logging.WARNING, logger="datamesh.resolvers.http"):
        resolved = adapter.resolve_and_fetch(url, storage, {})

    assert resolved.local_path.read_bytes() == b"cached-stale"
    assert resolved.is_cached is True
    assert any("stale" in m for m in caplog.messages)


def test_metadata_records_update_frequency(tmp_path):
    storage = _storage(tmp_path)
    url = "https://example.com/data/advice.csv"
    storage.save(url, b"payload", extension=".csv", source_service="http", update_frequency="daily")
    meta = storage.get_metadata(url)
    assert meta is not None
    assert meta.update_frequency == "daily"


def test_node_update_frequency_reads_temporal_block(monkeypatch, tmp_path):
    from datamesh.adapters.workspace.local_workspace import LocalWorkspaceResolver

    nodes = tmp_path / "nodes"
    node = nodes / "p2p-bob-exchange"
    node.mkdir(parents=True)
    (node / "datapackage.yaml").write_text(
        "temporal:\n  frequency: daily\nresources:\n  - name: advice\n    path: advice.parquet\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATAMESH_NODES_DIR", str(nodes))

    resolver = LocalWorkspaceResolver(catalog_discovery_fn=lambda: {"entries": []})
    assert resolver.node_update_frequency("p2p-bob-exchange") == "daily"
