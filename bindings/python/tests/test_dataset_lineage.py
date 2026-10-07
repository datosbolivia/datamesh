from __future__ import annotations

import json
import tempfile
from pathlib import Path
import pytest
import yaml

import datamesh as dm
from datamesh.domain.models import (
    LineageSource,
    LineageTransformation,
    LineageInfo,
    LineageNode,
    LineageEdge,
    LineageGraph,
)
from datamesh.usecases.dataset_lineage import DatasetLineageUseCase
from datamesh.mcp_server import handle_jsonrpc


def test_lineage_domain_models():
    # 1. Source parsing
    s1 = LineageSource.from_dict("https://ine.gob.bo/censo_2024.csv")
    assert s1.url == "https://ine.gob.bo/censo_2024.csv"
    assert s1.dataset == "censo_2024"


    s2 = LineageSource.from_dict("bolivia:censo:raw_hogares")
    assert s2.dataset == "censo"
    assert s2.resource == "raw_hogares"

    s3 = LineageSource.from_dict({
        "name": "raw_dataset",
        "dataset": "ine-censo",
        "format": "csv",
        "hash": "sha256:abc12345",
    })
    assert s3.name == "raw_dataset"
    assert s3.hash == "sha256:abc12345"

    # 2. Transformation parsing
    t1 = LineageTransformation.from_dict({
        "tool": "scripts/clean_data.py",
        "type": "script",
        "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "description": "Limpieza y desduplicación",
    })
    assert t1.tool == "scripts/clean_data.py"
    assert t1.type == "script"

    # 3. LineageInfo parsing
    info = LineageInfo.from_dict({
        "name": "censo_clean",
        "title": "Censo Limpio",
        "lineage": {
            "source": [{"name": "censo_raw", "dataset": "censo_raw"}],
            "transformations": [t1.to_dict()],
            "version": "1.0.0",
        }
    })
    assert info.dataset_id == "censo_clean"
    assert len(info.sources) == 1
    assert "censo_raw" in info.was_derived_from


def test_lineage_graph_dag_traversal():
    nodes = {
        "raw_a": LineageNode("raw_a", "Raw Dataset A"),
        "curated_b": LineageNode("curated_b", "Curated Dataset B"),
        "aggregated_c": LineageNode("aggregated_c", "Aggregated Dataset C"),
    }
    edges = (
        LineageEdge(source="raw_a", target="curated_b", label="clean_script.py"),
        LineageEdge(source="curated_b", target="aggregated_c", label="group_by.sql"),
    )
    graph = LineageGraph(nodes=nodes, edges=edges)

    # Aggregated C upstream is curated_b and raw_a
    c_upstream = graph.upstream("aggregated_c")
    assert "curated_b" in c_upstream
    assert "raw_a" in c_upstream

    # Raw A downstream is curated_b and aggregated_c
    a_downstream = graph.downstream("raw_a")
    assert "curated_b" in a_downstream
    assert "aggregated_c" in a_downstream

    # Curated B is in the middle
    assert graph.upstream("curated_b") == ["raw_a"]
    assert graph.downstream("curated_b") == ["aggregated_c"]

    # Mermaid rendering
    mermaid = graph.to_mermaid(highlight_id="curated_b")
    assert "flowchart LR" in mermaid
    assert "raw_a -->|clean_script.py| curated_b" in mermaid
    assert "curated_b -->|group_by.sql| aggregated_c" in mermaid
    assert "style curated_b fill:" in mermaid

    # ASCII rendering
    ascii_tree = graph.to_ascii("curated_b")
    assert "Dataset: curated_b" in ascii_tree
    assert "Upstream" in ascii_tree
    assert "Downstream" in ascii_tree


def test_create_datapackage_with_lineage_and_scan():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # 1. Parent dataset: raw_data
        p1 = root / "raw_pkg"
        p1.mkdir()
        f1 = p1 / "raw.csv"
        f1.write_text("id,val\n1,10\n2,20\n", encoding="utf-8")
        dm.create_datapackage(
            name="dataset-raw",
            title="Raw Dataset",
            files=[f1],
            output_file=p1 / "datapackage.yaml",
        )

        # 2. Child dataset: curated_data derived from dataset-raw
        p2 = root / "curated_pkg"
        p2.mkdir()
        f2 = p2 / "curated.csv"
        f2.write_text("id,val_clean\n1,10\n2,20\n", encoding="utf-8")
        dm.create_datapackage(
            name="dataset-curated",
            title="Curated Dataset",
            files=[f2],
            sources=["dataset-raw"],
            transformations=[{
                "tool": "clean.py",
                "type": "script",
                "description": "Limpieza de valores nulos",
            }],
            output_file=p2 / "datapackage.yaml",
        )

        # 3. Grandchild dataset: aggregated_data derived from dataset-curated
        p3 = root / "aggregated_pkg"
        p3.mkdir()
        f3 = p3 / "aggregated.csv"
        f3.write_text("total\n30\n", encoding="utf-8")
        dm.create_datapackage(
            name="dataset-aggregated",
            title="Aggregated Dataset",
            files=[f3],
            sources=["dataset-curated"],
            transformations=[{
                "tool": "aggregate.sql",
                "type": "sql",
                "description": "SUM(val_clean)",
            }],
            output_file=p3 / "datapackage.yaml",
        )

        # Test building graph across the temporary directory
        graph = dm.lineage(search_dirs=[root])
        assert "dataset-raw" in graph.nodes
        assert "dataset-curated" in graph.nodes
        assert "dataset-aggregated" in graph.nodes

        # Query lineage for curated dataset
        curated_lineage = dm.get_lineage("dataset-curated", search_dirs=[root])
        assert curated_lineage["dataset_id"] == "dataset-curated"
        assert "dataset-raw" in curated_lineage["upstream"]
        assert "dataset-aggregated" in curated_lineage["downstream"]
        assert len(curated_lineage["transformations"]) == 1
        assert curated_lineage["transformations"][0]["tool"] == "clean.py"

        # Query lineage for raw dataset
        raw_lineage = dm.get_lineage("dataset-raw", search_dirs=[root])
        assert raw_lineage["upstream"] == []
        assert "dataset-curated" in raw_lineage["downstream"]
        assert "dataset-aggregated" in raw_lineage["downstream"]

        # Query lineage for aggregated dataset
        agg_lineage = dm.get_lineage("dataset-aggregated", search_dirs=[root])
        assert "dataset-curated" in agg_lineage["upstream"]
        assert "dataset-raw" in agg_lineage["upstream"]
        assert agg_lineage["downstream"] == []


def test_markdown_okf_frontmatter_lineage():
    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = Path(tmpdir) / "index.md"
        md_content = """---
type: dataset
title: Censo Población 2024
id: censo-poblacion-2024
dimensions:
  - demografia
lineage:
  source:
    - url: https://ine.gob.bo/raw.csv
      dataset: ine-raw-censo
  transformations:
    - tool: scripts/clean_censo.py
      type: script
      hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
      description: Pipeline ETL INE
  version: 1.0.0
---

# Metodología y Calidad
"""
        md_file.write_text(md_content, encoding="utf-8")

        usecase = DatasetLineageUseCase()
        rec = usecase.extract_from_file(md_file)
        assert rec is not None
        assert rec.dataset_id == "censo-poblacion-2024"
        assert "ine-raw-censo" in rec.was_derived_from
        assert len(rec.transformations) == 1
        assert rec.transformations[0].tool == "scripts/clean_censo.py"


def test_mcp_tool_datamesh_get_lineage():
    req = {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "tools/call",
        "params": {
            "name": "datamesh_get_lineage",
            "arguments": {
                "dataset_id": "test_dataset"
            }
        }
    }
    resp = handle_jsonrpc(req)
    assert resp["id"] == 99
    assert "result" in resp
    content_raw = resp["result"]["content"][0]["text"]
    data = json.loads(content_raw)
    assert data["dataset_id"] == "test_dataset"
    assert "upstream" in data
    assert "downstream" in data
    assert "mermaid" in data
    assert "ascii" in data


def test_go_core_prefix_and_bridge():
    assert hasattr(dm, "_lineage")
    assert hasattr(dm, "_get_lineage")
    assert hasattr(dm, "_discover")
    assert hasattr(dm, "_search")
    assert hasattr(dm, "_get")
    assert hasattr(dm, "_query")
    assert hasattr(dm, "_sql")
    assert hasattr(dm, "_validate")
    assert hasattr(dm, "_publish")

    # Verify execution via _ prefixed functions
    g = dm._lineage(search_dirs=[])
    assert isinstance(g, dm.LineageGraph)
    res = dm._get_lineage("mock-target", search_dirs=[])
    assert res["dataset_id"] == "mock-target"
    assert "upstream" in res
    assert "downstream" in res

