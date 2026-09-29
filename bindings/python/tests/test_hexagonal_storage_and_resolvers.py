import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import datamesh as dm
from datamesh.domain.models import StorageConfig, ResourceDescriptor, ResolvedResource
from datamesh.ports.storage import StoragePort
from datamesh.ports.resolver import ResourceAdapterPort
from datamesh.adapters.storage.local_storage import LocalStorageManager
from datamesh.adapters.config.file_config import FileConfigAdapter
from datamesh.adapters.resolvers.local_file import LocalFileAdapter
from datamesh.adapters.resolvers.github import GitHubAdapter
from datamesh.adapters.resolvers.kaggle import KaggleAdapter
from datamesh.adapters.resolvers.http import HttpAdapter
from datamesh.usecases.resolve_resource import ResolveAndCacheResourceUseCase

TESTDATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "core-go", "testdata"))
CSV_PATH = os.path.join(TESTDATA_DIR, "mock_data_elecciones.csv")

def test_storage_config_and_local_storage_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir) / "datamesh"
        cache = home / "cache"
        conf_file = home / "config.yaml"
        conf = StorageConfig(home_dir=home, cache_dir=cache, config_file=conf_file)
        storage = LocalStorageManager(conf)

        assert storage.get_cache_dir() == cache
        assert cache.exists()
        assert home.exists()

        # Save sample data to cache
        test_key = "https://example.com/dataset/sample.csv"
        csv_content = b"col1,col2\nval1,10\nval2,20\n"
        saved_path = storage.save(
            key_or_uri=test_key,
            content=csv_content,
            extension=".csv",
            source_service="http",
            etag="abc-123",
        )

        assert saved_path.exists()
        assert saved_path.suffix == ".csv"
        assert storage.is_cached(test_key) is True
        assert storage.get_cached_path(test_key) == saved_path

        # Check metadata
        meta = storage.get_metadata(test_key)
        assert meta is not None
        assert meta.original_uri == test_key
        assert meta.size_bytes == len(csv_content)
        assert meta.etag == "abc-123"
        assert meta.format == "csv"

        # Evict
        evicted = storage.evict(test_key)
        assert evicted is True
        assert storage.is_cached(test_key) is False
        assert not saved_path.exists()

def test_file_config_adapter():
    with tempfile.TemporaryDirectory() as tmpdir:
        conf_path = Path(tmpdir) / "datamesh" / "config.yaml"
        adapter = FileConfigAdapter(conf_path)
        cfg = adapter.load_config()

        assert "base" in cfg
        assert "adapters" in cfg
        assert cfg["adapters"]["github"]["enabled"] is True
        assert cfg["adapters"]["kaggle"]["enabled"] is True

        # Custom update and save
        cfg["base"]["timeout"] = 60
        adapter.save_config(cfg)

        reloaded = adapter.load_config()
        assert reloaded["base"]["timeout"] == 60

def test_local_file_adapter():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageManager(StorageConfig(
            home_dir=Path(tmpdir) / "datamesh",
            cache_dir=Path(tmpdir) / "datamesh" / "cache",
            config_file=Path(tmpdir) / "datamesh" / "config.yaml",
        ))
        adapter = LocalFileAdapter()

        assert adapter.name == "local"
        assert adapter.can_handle(CSV_PATH) is True
        assert adapter.can_handle("file:///tmp/something.parquet") is True

        resolved = adapter.resolve_and_fetch(CSV_PATH, storage)
        assert resolved is not None
        assert resolved.local_path.exists()
        assert resolved.format == "csv"

def test_github_adapter_normalization_and_local_clone():
    adapter = GitHubAdapter()
    assert adapter.name == "github"

    # URL normalization
    blob_url = "https://github.com/datosbolivia/elecciones2025/blob/main/resultados/2020.parquet"
    raw_url = "https://github.com/datosbolivia/elecciones2025/raw/main/resultados/2020.parquet"

    assert adapter.can_handle(blob_url) is True
    assert adapter.can_handle(raw_url) is True
    assert adapter.can_handle("https://raw.githubusercontent.com/org/repo/main/data.csv") is True

    norm_blob = adapter._normalize_github_url(blob_url)
    assert norm_blob == "https://raw.githubusercontent.com/datosbolivia/elecciones2025/main/resultados/2020.parquet"

    norm_raw = adapter._normalize_github_url(raw_url)
    assert norm_raw == "https://raw.githubusercontent.com/datosbolivia/elecciones2025/main/resultados/2020.parquet"

def test_kaggle_adapter_parsing_and_resolution():
    adapter = KaggleAdapter()
    assert adapter.name == "kaggle"

    k_url = "https://www.kaggle.com/datasets/sociest/calidad-aire-monica/air_quality_consolidated.csv"
    assert adapter.can_handle(k_url) is True
    assert adapter.can_handle("kaggle://datasets/owner/ds/file.csv") is True

    owner, ds, fname = adapter._parse_kaggle_ref(k_url)
    assert owner == "sociest"
    assert ds == "calidad-aire-monica"
    assert fname == "air_quality_consolidated.csv"

def test_resolve_and_cache_usecase_with_duckdb():
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir) / "datamesh"
        cache = home / "cache"
        conf = StorageConfig(home_dir=home, cache_dir=cache, config_file=home / "config.yaml")
        storage = LocalStorageManager(conf)

        resolvers = [
            LocalFileAdapter(),
            GitHubAdapter(),
            KaggleAdapter(),
            HttpAdapter(),
        ]
        usecase = ResolveAndCacheResourceUseCase(storage=storage, resolvers=resolvers)

        # Pre-cache a mock dataset in temporal storage
        test_triad = "demo:indicators:population"
        mock_data = b"city,pop\nLa Paz,800000\nSanta Cruz,1500000\nCochabamba,700000\n"
        storage.save(test_triad, mock_data, extension=".csv", source_service="http")

        resolved = usecase.resolve(test_triad)
        assert resolved is not None
        assert resolved.local_path.exists()
        assert resolved.is_cached is True

        # Run DuckDB query directly against this use case
        engine = dm.DuckDBQueryEngine(resolver_usecase=usecase, storage=storage)
        res = engine.execute_sql(f"SELECT city, pop FROM '{test_triad}' ORDER BY pop DESC")

        assert res["row_count"] == 3
        assert res["columns"] == ["city", "pop"]
        assert res["rows"][0][0] == "Santa Cruz"
        assert res["rows"][0][1] == 1500000

def test_global_storage_instance():
    # Verifies datamesh.storage points to active LocalStorageManager
    assert dm.storage is not None
    assert isinstance(dm.storage, StoragePort)
    assert dm.storage.get_cache_dir().exists()
