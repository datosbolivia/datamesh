from __future__ import annotations

import os
import tempfile
from pathlib import Path
import pytest
import yaml

import datamesh as dm
from datamesh.usecases.create_datapackage import CreateDataPackageUseCase
from datamesh.usecases.link_knowledge_concepts import LinkKnowledgeConceptsUseCase
from datamesh.domain.models import KnowledgeConceptDoc, CategoryConceptMapping


def test_create_datapackage_from_csv():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "sample_data.csv"
        csv_path.write_text(
            "id,departamento,poblacion,activo\n"
            "1,La Paz,3000000,true\n"
            "2,Santa Cruz,3300000,true\n"
            "3,Cochabamba,2000000,false\n",
            encoding="utf-8"
        )
        out_pkg = Path(tmpdir) / "datapackage.yaml"
        res = dm.create_datapackage(
            name="test-census",
            title="Test Census Package",
            description="A test package description",
            files=[csv_path],
            output_file=out_pkg,
        )

        assert res.name == "test-census"
        assert res.title == "Test Census Package"
        assert out_pkg.exists()

        loaded = yaml.safe_load(out_pkg.read_text(encoding="utf-8"))
        assert len(loaded["resources"]) == 1
        res0 = loaded["resources"][0]
        assert res0["name"] == "sample_data"
        assert res0["format"] == "csv"
        fields = res0["schema"]["fields"]
        field_names = [f["name"] for f in fields]
        assert "id" in field_names
        assert "departamento" in field_names
        assert "poblacion" in field_names
        assert "activo" in field_names


def test_link_column_and_categories():
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_file = Path(tmpdir) / "datapackage.yaml"
        initial_pkg = {
            "name": "censo-sample",
            "resources": [
                {
                    "name": "personas",
                    "path": "personas.csv",
                    "schema": {
                        "fields": [
                            {"name": "P21_SEXO", "type": "string"},
                            {"name": "EDAD", "type": "integer"},
                        ]
                    }
                }
            ]
        }
        pkg_file.write_text(yaml.dump(initial_pkg), encoding="utf-8")

        # 1. Link column to concept
        dm.link_concept(
            datapackage_path_or_dict=pkg_file,
            resource_name="personas",
            column_name="P21_SEXO",
            concept_ref="concepts/sexo.md",
            value_mappings={
                "1": {"label": "Hombre", "concept": "concepts/genero_masculino.md"},
                "2": {"label": "Mujer", "concept": "concepts/genero_femenino.md"},
            },
            save_to_path=pkg_file,
        )

        updated = yaml.safe_load(pkg_file.read_text(encoding="utf-8"))
        f0 = updated["resources"][0]["schema"]["fields"][0]
        assert f0["concept"] == "concepts/sexo.md"
        assert f0["valueLabels"] == {"1": "Hombre", "2": "Mujer"}
        assert f0["value_mapping"] == {
            "1": "concepts/genero_masculino.md",
            "2": "concepts/genero_femenino.md",
        }


def test_explain_categories_generates_concept_docs():
    with tempfile.TemporaryDirectory() as tmpdir:
        concepts_dir = Path(tmpdir) / "concepts"
        sample_pkg = {
            "name": "censo-sample",
            "resources": [
                {
                    "name": "personas",
                    "path": "personas.csv",
                    "schema": {
                        "fields": [
                            {
                                "name": "P21_SEXO",
                                "title": "Sexo de la persona",
                                "description": "Variable demográfica de sexo registrado",
                                "concept": "concepts/sexo.md",
                                "valueLabels": {"1": "Hombre", "2": "Mujer"},
                                "value_mapping": {"1": "concepts/genero_masculino.md"},
                            }
                        ]
                    }
                }
            ]
        }

        docs = dm.explain_categories(sample_pkg, output_concepts_dir=concepts_dir)
        assert len(docs) == 1
        doc = docs[0]
        assert doc.id == "sexo"
        assert doc.title == "Sexo de la persona"
        assert len(doc.categories) == 2

        doc_file = concepts_dir / "sexo.md"
        assert doc_file.exists()
        content = doc_file.read_text(encoding="utf-8")
        assert "type: concept" in content
        assert "Sexo de la persona" in content
        assert "Hombre" in content
        assert "Mujer" in content
        assert "concepts/genero_masculino.md" in content
