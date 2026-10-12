import pytest
from datamesh.domain.models import CanonicalURI, EpistemicActor, LineageInfo, LineageSource, LineageTransformation

def test_epistemic_actor_and_lineage_serialization():
    emitter = EpistemicActor(
        by="agent:collector/v1.0",
        at="2026-10-01T12:00:00Z",
        role="raw-data-producer",
        verdict="verified",
        trust_tier="machine-confirmed",
    )
    attester = EpistemicActor(
        by="human:expert-auditor",
        at="2026-10-02T09:00:00Z",
        role="methodology-validator",
        verdict="verified",
        trust_tier="human-reviewed",
    )

    info = LineageInfo(
        dataset_id="air_quality",
        title="Air Quality Sensor Data",
        version="2.0.0",
        emitter=emitter,
        attester=attester,
        ref="./lineage.yaml",
        nature="structured",
        status="verified",
        supersedes="odkf://org.gob.bolivia/salud/air-preliminar:v1.0",
        sources=(
            LineageSource(name="raw_sensor", url="https://snia.gob.bo/raw.csv"),
        ),
    )

    d = info.to_dict()
    assert d["dataset_id"] == "air_quality"
    assert d["emitter"]["by"] == "agent:collector/v1.0"
    assert d["attester"]["by"] == "human:expert-auditor"
    assert d["attester"]["trust_tier"] == "human-reviewed"
    assert d["ref"] == "./lineage.yaml"
    assert d["nature"] == "structured"
    assert d["status"] == "verified"
    assert d["supersedes"] == "odkf://org.gob.bolivia/salud/air-preliminar:v1.0"

    rebuilt = LineageInfo.from_dict(d)
    assert rebuilt.emitter is not None
    assert rebuilt.emitter.by == "agent:collector/v1.0"
    assert rebuilt.attester is not None
    assert rebuilt.attester.by == "human:expert-auditor"
    assert rebuilt.ref == "./lineage.yaml"
    assert rebuilt.status == "verified"

def test_odkf_canonical_uri_scheme():
    # odkf://namespace/catalog/dataset:version
    uri1 = CanonicalURI.parse("odkf://org.gob.bolivia/salud/calidad-aire:v1.2.0")
    assert uri1 is not None
    assert uri1.catalog == "salud"
    assert uri1.dataset == "calidad-aire"
    assert uri1.resource == "v1.2.0"

    # odkf://catalog/dataset
    uri2 = CanonicalURI.parse("odkf://economia/inflacion")
    assert uri2 is not None
    assert uri2.catalog is None
    assert uri2.dataset == "economia"
    assert uri2.resource == "inflacion"
