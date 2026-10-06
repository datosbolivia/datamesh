from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import yaml
except ImportError:
    yaml = None

from datamesh.domain.models import CategoryConceptMapping, KnowledgeConceptDoc, DataPackageBuildResult


class LinkKnowledgeConceptsUseCase:
    """
    Connects columns and categorical column values in Frictionless / OKF v0.2 DataPackages
    to knowledge concept definitions (concepts/*.md), and generates SKOS concept files.
    """

    @classmethod
    def link_column_concept(
        cls,
        datapackage_data: Dict[str, Any],
        resource_name_or_index: Union[str, int],
        column_name: str,
        concept_ref: str,
    ) -> Dict[str, Any]:
        """
        Links a specific column to a knowledge concept path or URI (e.g. 'concepts/sexo.md' or 'https://...').
        """
        pkg = dict(datapackage_data)
        resources = pkg.get("resources", [])
        target_res = cls._find_resource(resources, resource_name_or_index)
        if not target_res:
            raise ValueError(f"Resource '{resource_name_or_index}' not found in datapackage.")

        schema = target_res.setdefault("schema", {})
        fields = schema.setdefault("fields", [])
        found_field = False
        for f in fields:
            if isinstance(f, dict) and f.get("name") == column_name:
                f["concept"] = concept_ref
                found_field = True
                break

        if not found_field:
            # Field doesn't exist yet, create minimal definition
            fields.append({
                "name": column_name,
                "type": "string",
                "concept": concept_ref,
            })

        return pkg

    @classmethod
    def link_categories(
        cls,
        datapackage_data: Dict[str, Any],
        resource_name_or_index: Union[str, int],
        column_name: str,
        value_mappings: Dict[str, Union[str, Dict[str, str]]],
    ) -> Dict[str, Any]:
        """
        Links categorical values to labels and concepts in field.valueLabels or field.categories / field.value_mapping.
        value_mappings can be:
        { "1": "Hombre", "2": "Mujer" }
        or
        { "1": {"label": "Hombre", "concept": "concepts/genero_masculino.md"}, ... }
        """
        pkg = dict(datapackage_data)
        resources = pkg.get("resources", [])
        target_res = cls._find_resource(resources, resource_name_or_index)
        if not target_res:
            raise ValueError(f"Resource '{resource_name_or_index}' not found in datapackage.")

        schema = target_res.setdefault("schema", {})
        fields = schema.setdefault("fields", [])
        for f in fields:
            if isinstance(f, dict) and f.get("name") == column_name:
                # Update valueLabels and value_mapping / categories
                v_labels = dict(f.get("valueLabels", {}))
                v_map = dict(f.get("value_mapping", {}))
                for val_k, val_info in value_mappings.items():
                    k_str = str(val_k)
                    if isinstance(val_info, dict):
                        lbl = val_info.get("label", k_str)
                        c_ref = val_info.get("concept")
                        v_labels[k_str] = lbl
                        if c_ref:
                            v_map[k_str] = c_ref
                    else:
                        v_labels[k_str] = str(val_info)
                f["valueLabels"] = v_labels
                if v_map:
                    f["value_mapping"] = v_map
                break
        return pkg

    @classmethod
    def create_concept_doc(
        cls,
        concept_id: str,
        title: str,
        pref_label: Optional[str] = None,
        description: Optional[str] = None,
        alt_labels: Optional[List[str]] = None,
        exact_match: Optional[str] = None,
        broader: Optional[str] = None,
        related: Optional[List[str]] = None,
        body_markdown: str = "",
        categories: Optional[List[Union[CategoryConceptMapping, Dict[str, Any]]]] = None,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> KnowledgeConceptDoc:
        """
        Creates an OKF / SKOS concept document, and optionally saves it to <output_dir>/<concept_id>.md.
        """
        clean_categories: List[CategoryConceptMapping] = []
        if categories:
            for c in categories:
                if isinstance(c, CategoryConceptMapping):
                    clean_categories.append(c)
                elif isinstance(c, dict):
                    clean_categories.append(CategoryConceptMapping(
                        value=str(c.get("value", "")),
                        label=str(c.get("label", "")),
                        concept=c.get("concept"),
                        description=c.get("description"),
                    ))

        doc = KnowledgeConceptDoc(
            id=concept_id,
            title=title,
            pref_label=pref_label or title,
            description=description,
            alt_labels=tuple(alt_labels or []),
            exact_match=exact_match,
            broader=broader,
            related=tuple(related or []),
            body_markdown=body_markdown,
            categories=tuple(clean_categories),
        )

        if output_dir:
            out_p = Path(output_dir)
            out_p.mkdir(parents=True, exist_ok=True)
            fname = f"{concept_id}.md" if not concept_id.endswith(".md") else concept_id
            target_path = out_p / fname
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(doc.to_markdown())

        return doc

    @classmethod
    def generate_concepts_from_field_categories(
        cls,
        datapackage_data: Dict[str, Any],
        output_concepts_dir: Union[str, Path],
    ) -> List[KnowledgeConceptDoc]:
        """
        Scans all fields in all resources that have valueLabels or value_mapping,
        and generates an explanatory OKF concept document for any field lacking one.
        """
        out_p = Path(output_concepts_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        generated_docs: List[KnowledgeConceptDoc] = []

        for res in datapackage_data.get("resources", []):
            # check inner zip resources if present
            sub_res_list = [res]
            if res.get("mediatype") == "zip" and "resources" in res:
                sub_res_list = res.get("resources", [])

            for sub in sub_res_list:
                schema = sub.get("schema") or {}
                fields = schema.get("fields", [])
                for f in fields:
                    if not isinstance(f, dict):
                        continue
                    v_labels = f.get("valueLabels")
                    v_map = f.get("value_mapping") or {}
                    if v_labels and isinstance(v_labels, dict):
                        field_name = f.get("name", "campo")
                        title = f.get("title") or f"Variable {field_name}"
                        desc = f.get("description") or f"Diccionario y clasificación de valores para {field_name}."
                        
                        # Prepare categories
                        cats: List[CategoryConceptMapping] = []
                        for val_k, val_lbl in v_labels.items():
                            val_str = str(val_k)
                            linked_concept = v_map.get(val_str)
                            cats.append(CategoryConceptMapping(
                                value=val_str,
                                label=str(val_lbl),
                                concept=linked_concept,
                            ))

                        concept_id = f.get("concept") or f"concepts/{field_name.lower()}.md"
                        clean_id = concept_id.split("/")[-1].replace(".md", "")
                        doc = cls.create_concept_doc(
                            concept_id=clean_id,
                            title=title,
                            pref_label=title,
                            description=desc,
                            categories=cats,
                            output_dir=out_p,
                        )
                        generated_docs.append(doc)
        return generated_docs

    @staticmethod
    def _find_resource(resources: List[Dict[str, Any]], target: Union[str, int]) -> Optional[Dict[str, Any]]:
        """Finds a resource by index or name/path (including nested zip resources)."""
        if isinstance(target, int):
            if 0 <= target < len(resources):
                return resources[target]
            return None

        for r in resources:
            if r.get("name") == target or r.get("path") == target:
                return r
            if r.get("mediatype") == "zip" and "resources" in r:
                for sub in r.get("resources", []):
                    if sub.get("name") == target or sub.get("path") == target:
                        return sub
        return None
