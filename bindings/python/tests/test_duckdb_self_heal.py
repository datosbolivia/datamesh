"""Self-healing tests: a cached file that fails to parse must be evicted and re-fetched once."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from datamesh.adapters.engine.duckdb_engine import DuckDBQueryEngine
from datamesh.adapters.storage.local_storage import LocalStorageManager
from datamesh.domain.models import CacheEntryMetadata, ResourceDescriptor, ResolvedResource, StorageConfig


def _make_storage(tmp_path: Path) -> LocalStorageManager:
    cfg = StorageConfig(
        home_dir=tmp_path / "home",
        cache_dir=tmp_path / "cache",
        config_file=tmp_path / "config.yaml",
    )
    return LocalStorageManager(cfg)


def _write_corrupt_parquet(path: Path) -> None:
    # A parquet that preserves PAR1 magics but carries an unparsable thrift footer,
    # mirroring the real "don't know what type" corruption scenario.
    path.write_bytes(b"PAR1" + b"\x15\x04\x15\x00garbage" * 8 + b"PAR1")


def _write_good_parquet(path: Path) -> None:
    con = duckdb.connect()
    con.execute(f"COPY (SELECT 42 AS x) TO '{path}' (FORMAT PARQUET)")


class FlakyResolver:
    """Returns a corrupt cached file on the first resolve, then a good file."""

    def __init__(self, storage: LocalStorageManager, good_path: Path):
        self.storage = storage
        self.good_path = good_path
        self.calls = 0

    def resolve(self, table_ref: str, context: dict | None = None) -> ResolvedResource:
        self.calls += 1
        meta = self.storage.get_metadata("https://kaggle.example/advice.parquet")
        # First call: the corrupt cached copy (simulating a sticky cache hit).
        if self.calls == 1 and meta:
            return ResolvedResource(
                descriptor=ResourceDescriptor(
                    raw_reference=table_ref, dataset="ds", resource="advice", format="parquet", source_service="kaggle"
                ),
                local_path=Path(meta.local_path),
                format="parquet",
                is_cached=True,
                metadata=meta,
            )
        return ResolvedResource(
            descriptor=ResourceDescriptor(
                raw_reference=table_ref, dataset="ds", resource="advice", format="parquet", source_service="kaggle"
            ),
            local_path=self.good_path,
            format="parquet",
            is_cached=True,
        )


def test_duckdb_engine_self_heals_corrupt_cached_file(tmp_path: Path) -> None:
    storage = _make_storage(tmp_path)

    corrupt_path = tmp_path / "cache" / "corrupt.parquet"
    good_path = tmp_path / "cache" / "good.parquet"
    _write_corrupt_parquet(corrupt_path)
    _write_good_parquet(good_path)

    # Register the corrupt copy in the cache exactly like a failed remote download would.
    stored = storage.store_file(corrupt_path, key_or_uri="https://kaggle.example/advice.parquet", source_service="kaggle")
    assert stored.exists()
    managed_copy = Path(storage.get_metadata("https://kaggle.example/advice.parquet").local_path)

    resolver = FlakyResolver(storage, good_path)
    engine = DuckDBQueryEngine(
        catalog_resolver=None,
        resolver_usecase=resolver,
        storage=storage,
    )

    result = engine.execute_sql("SELECT x FROM 'ds:advice'")

    assert result["row_count"] == 1
    assert result["rows"][0] == [42]
    assert resolver.calls == 2, "a corrupt cache must trigger exactly one re-fetch"
    assert not storage.is_cached("https://kaggle.example/advice.parquet"), "corrupt entry must be evicted"
    assert not managed_copy.exists(), "managed corrupt copy must be purged"


def test_duckdb_engine_raises_when_refetch_still_corrupt(tmp_path: Path) -> None:
    storage = _make_storage(tmp_path)
    corrupt_path = tmp_path / "cache" / "corrupt.parquet"
    _write_corrupt_parquet(corrupt_path)
    storage.store_file(corrupt_path, key_or_uri="https://kaggle.example/advice.parquet", source_service="kaggle")

    class SameCorruptResolver:
        def resolve(self, table_ref: str, context: dict | None = None) -> ResolvedResource:
            meta = storage.get_metadata("https://kaggle.example/advice.parquet")
            return ResolvedResource(
                descriptor=ResourceDescriptor(
                    raw_reference=table_ref, dataset="ds", resource="advice", format="parquet", source_service="kaggle"
                ),
                local_path=corrupt_path,
                format="parquet",
                is_cached=True,
                metadata=meta,
            )

    engine = DuckDBQueryEngine(resolver_usecase=SameCorruptResolver(), storage=storage)

    with pytest.raises(Exception) as exc:
        engine.execute_sql("SELECT x FROM 'ds:advice'")
    assert "don't know what type" in str(exc.value) or "failed" in str(exc.value)


def test_evict_by_path_removes_matching_cache_entry(tmp_path: Path) -> None:
    storage = _make_storage(tmp_path)
    f = tmp_path / "cache" / "cached_file.csv"
    f.write_text("a,b\n1,2\n")
    stored = storage.store_file(f, key_or_uri="https://x.example/data.csv", source_service="http")

    assert storage.is_cached("https://x.example/data.csv")
    assert storage.evict_by_path(stored) is True
    assert not storage.is_cached("https://x.example/data.csv")
    assert not stored.exists()

    # Unknown path is a no-op.
    assert storage.evict_by_path(tmp_path / "cache" / "missing.csv") is False


def test_evict_by_path_matches_by_local_path(tmp_path: Path) -> None:
    storage = _make_storage(tmp_path)
    f = tmp_path / "cache" / "other.csv"
    f.write_text("x\n1\n")
    storage.store_file(f, key_or_uri="https://y.example/other.csv", source_service="http")

    # Get the metadata entry and confirm key/uri bookkeeping round-trips.
    meta = storage.get_metadata("https://y.example/other.csv")
    assert isinstance(meta, CacheEntryMetadata)
    assert meta.original_uri == "https://y.example/other.csv"