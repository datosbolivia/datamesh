from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
try:
    import yaml
except ImportError:
    yaml = None

from datamesh.domain.models import SemanticFieldMapping

class SemanticAlignmentUseCase:
    """
    Extracts semantic concept mappings from ODKF schemas and builds DuckDB SQL mapping expressions.
    Enables joining tables across raw datasets by normalizing raw abbreviations/codes to ODKF concept IDs.
    """

    @classmethod
    def extract_mappings(cls, datapackage_or_schema: Dict[str, Any]) -> List[SemanticFieldMapping]:
        mappings: List[SemanticFieldMapping] = []
        resources = datapackage_or_schema.get("resources", [])
        if not resources and "fields" in datapackage_or_schema:
            resources = [{"schema": datapackage_or_schema}]

        for res in resources:
            schema = res.get("schema") or {}
            fields = schema.get("fields", [])
            for f in fields:
                if not isinstance(f, dict):
                    continue
                concept = f.get("concept") or f.get("concept_ref")
                value_map = f.get("value_mapping") or f.get("categories") or {}
                if concept or value_map:
                    clean_vmap: Dict[str, str] = {}
                    if isinstance(value_map, dict):
                        clean_vmap = {str(k): str(v) for k, v in value_map.items()}
                    elif isinstance(value_map, list):
                        # List of category dicts: [{'value': 'LPZ', 'concept': 'concept:...'}, ...]
                        for item in value_map:
                            if isinstance(item, dict) and "value" in item:
                                c_id = item.get("concept") or item.get("id") or concept
                                if c_id:
                                    clean_vmap[str(item["value"])] = str(c_id)
                    mappings.append(SemanticFieldMapping(
                        field_name=f.get("name", ""),
                        concept_ref=concept,
                        value_mapping=clean_vmap,
                    ))
        return mappings

    @classmethod
    def generate_case_expression(cls, mapping: SemanticFieldMapping, table_prefix: str = "") -> str:
        """Generates a SQL CASE expression mapping raw codes to canonical concept IDs."""
        col = f"{table_prefix}.{mapping.field_name}" if table_prefix else mapping.field_name
        if not mapping.value_mapping:
            return col
        
        when_clauses = []
        for raw_val, concept_id in mapping.value_mapping.items():
            escaped_val = raw_val.replace("'", "''")
            escaped_concept = concept_id.replace("'", "''")
            when_clauses.append(f"WHEN {col} = '{escaped_val}' THEN '{escaped_concept}'")
        
        fallback = f"ELSE {col}"
        return f"(CASE {' '.join(when_clauses)} {fallback} END)"
