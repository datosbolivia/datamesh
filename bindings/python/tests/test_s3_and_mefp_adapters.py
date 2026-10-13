import io
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import pytest
import datamesh as dm
from datamesh.adapters.storage.s3_storage import S3StorageAdapter
from datamesh.adapters.resolvers.s3 import S3Adapter
from datamesh.adapters.publishers.ckan_publisher import CKANPublisherAdapter
from datamesh.aliases import to_df, datasets_a_df, organizaciones_a_df, recursos_a_df


def test_s3_storage_adapter_config(monkeypatch):
    monkeypatch.setenv("AISTOR_ENDPOINT", "http://test-minio:9000")
    monkeypatch.setenv("AISTOR_BUCKET", "test-bucket")
    monkeypatch.setenv("AISTOR_ACCESS_KEY", "minio-key")
    monkeypatch.setenv("AISTOR_SECRET_KEY", "minio-secret")

    storage = S3StorageAdapter()
    cfg = storage.get_config()

    assert cfg["endpoint_url"] == "http://test-minio:9000"
    assert cfg["bucket"] == "test-bucket"
    assert cfg["access_key"] == "minio-key"
    assert cfg["secret_key"] == "minio-secret"


def test_s3_storage_operations():
    mock_boto = MagicMock()
    storage = S3StorageAdapter(client=mock_boto, bucket="lake")

    # repo_prefix
    prefix = storage.repo_prefix("dump_raw", repo_name="mefp-org/my-repo")
    assert prefix == "mefp-org/my-repo/dump_raw"

    # escribir_objeto
    uri = storage.escribir_objeto("my-repo/dump_raw/file.csv", b"a,b\n1,2")
    assert uri == "s3://lake/my-repo/dump_raw/file.csv"
    mock_boto.put_object.assert_called_with(Bucket="lake", Key="my-repo/dump_raw/file.csv", Body=b"a,b\n1,2")

    # leer_objeto
    mock_body = MagicMock()
    mock_body.read.return_value = b"sample,data\n1,2"
    mock_boto.get_object.return_value = {"Body": mock_body}
    data = storage.leer_objeto("my-repo/dump_raw/file.csv")
    assert data == b"sample,data\n1,2"

    # existe_objeto
    mock_boto.head_object.return_value = {}
    assert storage.existe_objeto("my-repo/dump_raw/file.csv") is True

    # eliminar_objeto
    del_uri = storage.eliminar_objeto("my-repo/dump_raw/file.csv")
    assert del_uri == "s3://lake/my-repo/dump_raw/file.csv"
    mock_boto.delete_object.assert_called_with(Bucket="lake", Key="my-repo/dump_raw/file.csv")


def test_s3_resolver_and_duckdb_integration(tmp_path):
    mock_boto = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = b"id,monto,categoria\n1,100,salario\n2,200,inversion\n"
    mock_boto.get_object.return_value = {"Body": mock_body}

    storage = S3StorageAdapter(client=mock_boto, bucket="lake")
    s3_resolver = S3Adapter(s3_storage=storage)

    # Resolve s3://lake/presupuesto/gastos.csv
    resolved = s3_resolver.resolve_and_fetch(
        "s3://lake/presupuesto/gastos.csv",
        storage=dm.storage,
        context={"dataset": "presupuesto", "resource": "gastos"},
    )
    assert resolved is not None
    assert resolved.local_path.exists()
    assert resolved.format == "csv"

    # Execute SQL through datamesh DuckDB engine
    res = dm.sql("SELECT SUM(monto) AS total FROM 's3://lake/presupuesto/gastos.csv'")
    assert res["rows"][0][0] == 300


def test_ckan_publisher_adapter(tmp_path):
    pkg_dir = tmp_path / "test_pkg"
    pkg_dir.mkdir()
    data_file = pkg_dir / "datos.csv"
    data_file.write_text("col1,col2\n10,20\n", encoding="utf-8")

    manifest = {
        "name": "presupuesto_2026",
        "title": "Presupuesto General 2026",
        "owner_org": "mefp-org",
        "resources": [
            {
                "name": "datos",
                "path": "datos.csv",
                "format": "csv",
                "filas": 1,
                "columnas": 2,
            }
        ],
    }

    mock_ckan = MagicMock()
    mock_ckan.action.package_show.side_effect = Exception("Not found")
    mock_ckan.action.package_create.return_value = {
        "id": "pkg-123",
        "name": "presupuesto_2026",
        "resources": [],
    }

    publisher = CKANPublisherAdapter()
    with patch.object(publisher, "get_ckan_client", return_value=mock_ckan):
        result = publisher.publish(pkg_dir, manifest, options={"url": "http://ckan-test:5000"})
        assert result.success is True
        assert "presupuesto_2026" in result.destination_uri
        assert mock_ckan.action.package_create.called
        assert mock_ckan.action.resource_create.called


def test_aliases_to_dataframe():
    data = {"columns": ["a", "b"], "rows": [[1, 2], [3, 4]]}
    df = to_df(data)
    assert len(df) == 2
    assert list(df.columns) == ["a", "b"]

    ds_df = datasets_a_df([{"name": "ds1", "title": "Dataset 1", "resources": [1, 2]}])
    assert len(ds_df) == 1
    assert ds_df["nombre"].iloc[0] == "ds1"
