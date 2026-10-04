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
