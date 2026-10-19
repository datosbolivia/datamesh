import os
import sys
from pathlib import Path
import pytest
from datamesh.domain.models import StorageConfig
from datamesh.usecases.dataset_lineage import DatasetLineageUseCase
import datamesh as dm

FMI_ROOT = Path("/home/andreschirinos/Proyectos/ministeriomefp/fmi")
FMI_COMPONENTS = FMI_ROOT / "knowledge" / "components"
FMI_CKAN_SOURCES = FMI_ROOT / "src" / "lib" / "ckan_sources.json"
FMI_DATAMESH_YML = FMI_ROOT / "datamesh.yml"


def test_storage_config_respects_env_datamesh_config_file(monkeypatch):
    monkeypatch.setenv("DATAMESH_CONFIG_FILE", str(FMI_DATAMESH_YML))
    cfg = StorageConfig.default()
    assert cfg.config_file == FMI_DATAMESH_YML


def test_component_lineage_extraction_req_01_a():
    usecase = DatasetLineageUseCase()
    comp_file = FMI_COMPONENTS / "req_01_a" / "datapackage.yml"
    assert comp_file.exists()

    info = usecase.extract_from_file(comp_file)
    assert info is not None
    assert info.dataset_id == "req_01_a"
    assert "fmi-bcb:tabla_rin_componentes" in info.was_derived_from
    assert len(info.was_derived_from) == 1


def test_lineage_graph_3_level_upstream_resolution():
    if str(FMI_ROOT / "knowledge" / "lib") not in sys.path:
        sys.path.insert(0, str(FMI_ROOT / "knowledge" / "lib"))
    from lineage_catalog import get_ckan_lineage_records

    usecase = DatasetLineageUseCase()
    ckan_recs = get_ckan_lineage_records()
    graph = usecase.build_graph(records=ckan_recs, search_dirs=[FMI_COMPONENTS])
    upstream = graph.upstream("req_01_a")
    assert upstream == [
        "fmi-bcb:tabla_rin_componentes",
        "fmi-bcb:raw_3_rin_bcb_componentes",
        "https://www.bcb.gob.bo",
    ]


def test_lineage_catalog_3_level_trace():
    if str(FMI_ROOT / "knowledge" / "lib") not in sys.path:
        sys.path.insert(0, str(FMI_ROOT / "knowledge" / "lib"))
    from lineage_catalog import trace_lineage_to_raw

    tr = trace_lineage_to_raw("req_01_a")
    assert tr["dataset_id"] == "req_01_a"
    assert tr["depth"] == 3
    assert tr["upstream"] == [
        "fmi-bcb:tabla_rin_componentes",
        "fmi-bcb:raw_3_rin_bcb_componentes",
        "https://www.bcb.gob.bo",
    ]
    assert "Level 1" in tr["ascii_tree"]
    assert "Level 2" in tr["ascii_tree"]
    assert "Level 3" in tr["ascii_tree"]
