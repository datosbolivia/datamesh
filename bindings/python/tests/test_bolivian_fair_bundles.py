from __future__ import annotations

import os
import json
import pytest
from pathlib import Path
import datamesh as dm
from datamesh.adapters.storage.zip_extractor import extract_zip_tabular_resource

BUNDLES_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "examples" / "bundles"

def test_air_quality_bolivia_bundle_exists_and_valid():
    bundle_path = BUNDLES_ROOT / "air_quality_bolivia"
    assert bundle_path.exists(), f"Bundle not found at {bundle_path}"

    dp_path = bundle_path / "datapackage.json"
    assert dp_path.exists()
    with open(dp_path, "r", encoding="utf-8") as f:
        dp = json.load(f)
    assert dp["name"] == "air_quality_bolivia"
    assert dp["spatial"]["country"] == "BO"
    assert len(dp["resources"]) == 2

    index_md = bundle_path / "index.md"
    assert index_md.exists()
    val = dm.validate(str(index_md))
    assert val["valid"] is True
    assert val["total_errors"] == 0

def test_air_quality_bolivia_parquet_query():
    parquet_path = BUNDLES_ROOT / "air_quality_bolivia" / "data" / "calidad_aire_2024.parquet"
    assert parquet_path.exists()

    # Query through dm.query
    q_res = dm.query(str(parquet_path), limit=5)
    assert "pm25" in q_res["columns"]
    assert len(q_res["rows"]) > 0

    # Query through dm.sql with DuckDB engine
    sql_res = dm.sql(
        "SELECT ciudad, ROUND(AVG(pm25), 2) as avg_pm25, MAX(aqi) as max_aqi FROM aire GROUP BY ciudad ORDER BY avg_pm25 DESC",
        table_mapping={"aire": str(parquet_path)}
    )
    assert "avg_pm25" in sql_res["columns"]
    assert len(sql_res["rows"]) == 3
    # Cochabamba should have highest average in sample
    assert sql_res["rows"][0][0] == "Cochabamba"

def test_cndc_despacho_electrico_bundle_and_query():
    bundle_path = BUNDLES_ROOT / "cndc_despacho_electrico"
    assert bundle_path.exists()

    dp_path = bundle_path / "datapackage.json"
    with open(dp_path, "r", encoding="utf-8") as f:
        dp = json.load(f)
    assert dp["name"] == "cndc_despacho_electrico"
    assert dp["provenance"]["wasAttributedTo"] == "urn:cndc:bolivia:operaciones"

    index_md = bundle_path / "index.md"
    val = dm.validate(str(index_md))
    assert val["valid"] is True

    parquet_path = bundle_path / "data" / "snapshot_despacho.parquet"
    assert parquet_path.exists()
    sql_res = dm.sql(
        "SELECT tipo_generacion, SUM(potencia_mw) as total_potencia FROM cndc GROUP BY tipo_generacion ORDER BY total_potencia DESC",
        table_mapping={"cndc": str(parquet_path)}
    )
    assert len(sql_res["rows"]) >= 4
    assert any(row[0] == "Ciclo Combinado" for row in sql_res["rows"])

def test_censo_2024_cartografia_zip_selective_extraction():
    bundle_path = BUNDLES_ROOT / "censo_2024_cartografia"
    assert bundle_path.exists()

    zip_path = bundle_path / "data" / "censo_cartografia.zip"
    assert zip_path.exists()

    # Extract SCZ manzanas
    scz_path, scz_fmt = extract_zip_tabular_resource(str(zip_path), target_hint="scz_manzanas")
    assert scz_path is not None
    assert os.path.exists(scz_path)

    sql_scz = dm.sql(
        "SELECT municipio, SUM(viviendas) as total_viv FROM scz_table GROUP BY municipio",
        table_mapping={"scz_table": scz_path}
    )
    assert len(sql_scz["rows"]) == 2

    # Extract LPZ manzanas
    lpz_path, lpz_fmt = extract_zip_tabular_resource(str(zip_path), target_hint="lpz_manzanas")
    assert lpz_path is not None
    assert os.path.exists(lpz_path)

    sql_lpz = dm.sql(
        "SELECT municipio, SUM(poblacion_estimada) as total_pob FROM lpz_table GROUP BY municipio",
        table_mapping={"lpz_table": lpz_path}
    )
    assert len(sql_lpz["rows"]) == 2

def test_udabol_salud_syndicated_bundle_and_sovereign_dns():
    bundle_path = BUNDLES_ROOT / "udabol_salud_syndicated"
    assert bundle_path.exists()

    dp_path = bundle_path / "datapackage.json"
    with open(dp_path, "r", encoding="utf-8") as f:
        dp = json.load(f)
    assert dp["name"] == "udabol_salud_syndicated"
    assert dp["sovereign_dns"]["fqdn"] == "dengue_2024.series_tiempo@udabol_salud"
    assert len(dp["syndication"]["catalog_records"]) == 3

    index_md = bundle_path / "index.md"
    val = dm.validate(str(index_md))
    assert val["valid"] is True

    parquet_path = bundle_path / "data" / "dengue_bolivia_2024.parquet"
    assert parquet_path.exists()
    sql_res = dm.sql(
        "SELECT departamento, SUM(casos_confirmados) as sum_casos FROM dengue GROUP BY departamento ORDER BY sum_casos DESC",
        table_mapping={"dengue": str(parquet_path)}
    )
    assert len(sql_res["rows"]) == 3
    assert sql_res["rows"][0][0] == "BO-S"
