from __future__ import annotations

import os
from pathlib import Path
import pytest
import datamesh as dm
from datamesh.domain.models import SpatialCoverage, TemporalCoverage, QualityProfile, SemanticFieldMapping
from datamesh.usecases.semantic_alignment import SemanticAlignmentUseCase

def test_spatial_coverage_model():
    sp = SpatialCoverage(
        country="BO",
        regions=("BO-L", "BO-C", "BO-S"),
        bbox=(-69.64, -22.90, -57.45, -9.67),
        granularity="municipality",
    )
    d = sp.to_dict()
    assert d["country"] == "BO"
    assert d["regions"] == ["BO-L", "BO-C", "BO-S"]
    assert d["bbox"] == [-69.64, -22.90, -57.45, -9.67]

    reconstructed = SpatialCoverage.from_dict(d)
    assert reconstructed.country == "BO"
    assert reconstructed.bbox == (-69.64, -22.90, -57.45, -9.67)

def test_temporal_coverage_model():
    tp = TemporalCoverage(
        start="2020-01-01T00:00:00Z",
        end="2026-12-31T23:59:59Z",
        frequency="daily",
        timezone="America/La_Paz",
    )
    d = tp.to_dict()
    assert d["frequency"] == "daily"
    reconstructed = TemporalCoverage.from_dict(d)
    assert reconstructed.start == "2020-01-01T00:00:00Z"
    assert reconstructed.timezone == "America/La_Paz"

def test_semantic_alignment_usecase():
    schema = {
        "fields": [
            {
                "name": "cod_dep",
                "type": "string",
                "concept": "concepts/departamentos.md",
                "value_mapping": {
                    "LPZ": "concept:departamentos:la_paz",
                    "02": "concept:departamentos:la_paz",
                    "SCZ": "concept:departamentos:santa_cruz",
                },
            }
        ]
    }
    mappings = SemanticAlignmentUseCase.extract_mappings(schema)
    assert len(mappings) == 1
    m = mappings[0]
    assert m.field_name == "cod_dep"
    assert m.concept_ref == "concepts/departamentos.md"
    assert m.value_mapping["LPZ"] == "concept:departamentos:la_paz"

    case_expr = SemanticAlignmentUseCase.generate_case_expression(m, table_prefix="t")
    assert "WHEN t.cod_dep = 'LPZ' THEN 'concept:departamentos:la_paz'" in case_expr
    assert "ELSE t.cod_dep END" in case_expr

def test_publish_usecase_local(tmp_path: Path):
    sample_manifest = {
        "name": "sample-dataset",
        "title": "Sample Dataset for Testing",
        "description": "Standardized publication test",
        "spatial": {"country": "BO", "granularity": "point"},
        "temporal": {"start": "2026-01-01T00:00:00Z", "end": "2026-12-31T23:59:59Z"},
        "quality": {"status": "verified", "completeness": 0.99},
        "resources": [
            {
                "name": "datos",
                "path": "datos.csv",
                "format": "csv",
            }
        ],
    }
    src_file = tmp_path / "datapackage.yaml"
    import yaml
    src_file.write_text(yaml.dump(sample_manifest), encoding="utf-8")

    out_dir = tmp_path / "published_bundle"
    results = dm.publish(str(src_file), targets=["local"], options={"destination": str(out_dir)})
    assert len(results) == 1
    assert results[0]["success"] is True

    pub_dp = out_dir / "sample-dataset" / "datapackage.yaml"
    assert pub_dp.exists()
    pub_index = out_dir / "sample-dataset" / "index.md"
    assert pub_index.exists()
    assert "type: dataset" in pub_index.read_text(encoding="utf-8")

def test_publish_usecase_with_lineage_and_dependencies(tmp_path: Path):
    sample_manifest = {
        "name": "indicadores-macro-fmi",
        "title": "Monitoreo FMI",
        "description": "Publicación con trazabilidad multinivel",
        "lineage": {
            "version": "0.2.0",
            "was_derived_from": ["fmi-bcb:tabla_rin_componentes"],
            "sources": [{"name": "fmi-bcb:tabla_rin_componentes", "dataset": "fmi-bcb"}],
            "transformations": [{"tool": "transform.py", "description": "Normalización SDMX"}]
        },
        "was_derived_from": ["fmi-bcb:tabla_rin_componentes"],
        "resources": [
            {
                "name": "req_01_a",
                "path": "req_01_a.csv",
                "format": "csv",
                "lineage": {
                    "was_derived_from": ["fmi-bcb:tabla_rin_componentes"],
                },
                "was_derived_from": ["fmi-bcb:tabla_rin_componentes"],
                "transformation": "Normalización dimensional y validación SDMX"
            }
        ],
    }
    src_file = tmp_path / "datapackage.yaml"
    import yaml
    src_file.write_text(yaml.dump(sample_manifest), encoding="utf-8")

    out_dir = tmp_path / "published_bundle"
    results = dm.publish(str(src_file), targets=["local"], options={"destination": str(out_dir)})
    assert len(results) == 1
    assert results[0]["success"] is True

    pub_dp = out_dir / "indicadores-macro-fmi" / "datapackage.yaml"
    assert pub_dp.exists()
    loaded_dp = yaml.safe_load(pub_dp.read_text(encoding="utf-8"))
    assert loaded_dp["lineage"]["version"] == "0.2.0"
    assert loaded_dp["was_derived_from"] == ["fmi-bcb:tabla_rin_componentes"]
    assert loaded_dp["resources"][0]["was_derived_from"] == ["fmi-bcb:tabla_rin_componentes"]

    pub_index = out_dir / "indicadores-macro-fmi" / "index.md"
    assert pub_index.exists()
    content = pub_index.read_text(encoding="utf-8")
    assert "was_derived_from:" in content
    assert "fmi-bcb:tabla_rin_componentes" in content


def test_value_label_concept_skos_correspondence_and_go_core_bridge():
    from datamesh.domain.models import CanonicalURI

    # 1. Sovereign DNS (@), okf://, and #fragment parsing
    u1 = CanonicalURI.parse("elecciones_2025.votos_municipales@bolivia#scz.parquet")
    assert u1 is not None
    assert u1.catalog == "bolivia"
    assert u1.dataset == "elecciones_2025"
    assert u1.resource == "votos_municipales"
    assert u1.fragment == "scz.parquet"

    u2 = CanonicalURI.parse("okf://ine_bolivia/censo_2024/manzanas#lapaz.csv")
    assert u2 is not None
    assert u2.catalog == "ine_bolivia"
    assert u2.dataset == "censo_2024"
    assert u2.resource == "manzanas"
    assert u2.fragment == "lapaz.csv"

    # 2. ValueLabel -> Concept -> SKOS correspondence resolution across two datasets
    src_map = {
        "field_name": "entidad_municipal",
        "value_labels": [
            {
                "raw_value": "Gobierno Autónomo Municipal De La Paz",
                "concept_id": "presupuesto_2025:concepts/gam_la_paz.md",
                "alt_labels": ["GAMLP"],
            },
            {
                "raw_value": "Gobierno Autónomo Municipal de Santa Cruz",
                "concept_id": "presupuesto_2025:concepts/gam_scz.md",
            },
        ],
    }
    tgt_map = {
        "field_name": "cod_ine",
        "value_labels": [
            {
                "raw_value": "020101",
                "concept_id": "censo_2024:concepts/mun_020101.md",
            },
            {
                "raw_value": "070101",
                "concept_id": "censo_2024:concepts/mun_070101.md",
            },
        ],
    }
    catalog = {
        "presupuesto_2025:concepts/gam_la_paz.md": {
            "concept_id": "presupuesto_2025:concepts/gam_la_paz.md",
            "exact_match": ["http://www.wikidata.org/entity/Q1491"],
        },
        "censo_2024:concepts/mun_020101.md": {
            "concept_id": "censo_2024:concepts/mun_020101.md",
            "exact_match": ["http://www.wikidata.org/entity/Q1491"],
        },
        "presupuesto_2025:concepts/gam_scz.md": {
            "concept_id": "presupuesto_2025:concepts/gam_scz.md",
            "exact_match": ["censo_2024:concepts/mun_070101.md"],
        },
        "censo_2024:concepts/mun_070101.md": {
            "concept_id": "censo_2024:concepts/mun_070101.md",
            "skos": ["http://www.wikidata.org/entity/Q170688"],
        },
    }

    corrs = dm.resolve_concept_correspondences(src_map, tgt_map, catalog)
    assert len(corrs) == 2
    assert corrs[0]["source_value"] == "Gobierno Autónomo Municipal De La Paz"
    assert corrs[0]["target_value"] == "020101"
    assert corrs[0]["shared_anchor_uri"] == "http://www.wikidata.org/entity/Q1491"
    assert corrs[0]["match_predicate"] == "skos:exactMatch"

    assert corrs[1]["source_value"] == "Gobierno Autónomo Municipal de Santa Cruz"
    assert corrs[1]["target_value"] == "070101"
    assert corrs[1]["shared_anchor_uri"] == "censo_2024:concepts/mun_070101.md"
    assert corrs[1]["match_predicate"] == "direct_concept_ref"

    join_sql = dm.generate_cross_dataset_join_sql(src_map, "a", tgt_map, "b", catalog)
    assert "WHEN a.entidad_municipal = 'Gobierno Autónomo Municipal De La Paz' THEN 'http://www.wikidata.org/entity/Q1491'" in join_sql
    assert "WHEN b.cod_ine = '020101' THEN 'http://www.wikidata.org/entity/Q1491'" in join_sql


