from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
try:
    import yaml
except ImportError:
    yaml = None

from datamesh.domain.models import (
    SemanticFieldMapping,
    ValueLabelConceptEntry,
    ConceptNodeSKOS,
    ConceptCorrespondence,
)


class SemanticAlignmentUseCase:
    """
    Extracts semantic concept mappings from ODKF schemas, resolves ValueLabel -> Concept -> SKOS
    correspondences across heterogeneous datasets, and builds deterministic SQL CASE / JOIN expressions.
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
                unit = f.get("unit")
                agg_behavior = f.get("aggregation_behavior")
                value_map = f.get("value_mapping") or f.get("categories") or {}
                raw_vls = f.get("value_labels") or []
                vls: List[ValueLabelConceptEntry] = []
                for vl in raw_vls:
                    if isinstance(vl, dict):
                        vls.append(ValueLabelConceptEntry.from_dict(vl))
                    elif isinstance(vl, ValueLabelConceptEntry):
                        vls.append(vl)

                if concept or value_map or vls or unit or agg_behavior:
                    clean_vmap: Dict[str, str] = {}
                    if isinstance(value_map, dict):
                        clean_vmap = {str(k): str(v) for k, v in value_map.items()}
                    elif isinstance(value_map, list):
                        for item in value_map:
                            if isinstance(item, dict) and "value" in item:
                                c_id = item.get("concept") or item.get("id") or concept
                                if c_id:
                                    clean_vmap[str(item["value"])] = str(c_id)
                    mappings.append(SemanticFieldMapping(
                        field_name=f.get("name", ""),
                        concept_ref=concept,
                        unit=unit,
                        aggregation_behavior=agg_behavior,
                        value_mapping=clean_vmap,
                        value_labels=tuple(vls),
                    ))
        return mappings

    @classmethod
    def generate_case_expression(cls, mapping: SemanticFieldMapping, table_prefix: str = "") -> str:
        """Generates a deterministic SQL CASE expression mapping raw ValueLabels to canonical concept IDs."""
        col = f"{table_prefix}.{mapping.field_name}" if table_prefix else mapping.field_name
        merged: Dict[str, str] = dict(mapping.value_mapping)
        for vl in mapping.value_labels:
            if vl.raw_value and vl.concept_id:
                merged[vl.raw_value] = vl.concept_id
            for alt in vl.alt_labels:
                if alt and vl.concept_id:
                    merged[alt] = vl.concept_id

        if not merged:
            return col

        when_clauses = []
        for raw_val in sorted(merged.keys()):
            concept_id = merged[raw_val]
            escaped_val = raw_val.replace("'", "''")
            escaped_concept = concept_id.replace("'", "''")
            when_clauses.append(f"WHEN {col} = '{escaped_val}' THEN '{escaped_concept}'")

        fallback = f"ELSE {col}"
        return f"(CASE {' '.join(when_clauses)} {fallback} END)"

    @classmethod
    def resolve_concept_correspondences(
        cls,
        source_mapping: SemanticFieldMapping | Dict[str, Any],
        target_mapping: SemanticFieldMapping | Dict[str, Any],
        concept_catalog: Optional[Dict[str, ConceptNodeSKOS | Dict[str, Any]]] = None,
        bridge: Optional[Any] = None,
    ) -> List[ConceptCorrespondence]:
        """Resolves ValueLabel -> Concept -> SKOS correspondences (Go Core first, Python fallback)."""
        src_obj = SemanticFieldMapping.from_dict(source_mapping) if isinstance(source_mapping, dict) else source_mapping
        tgt_obj = SemanticFieldMapping.from_dict(target_mapping) if isinstance(target_mapping, dict) else target_mapping
        cat_dict: Dict[str, Dict[str, Any]] = {}
        for k, v in (concept_catalog or {}).items():
            cat_dict[k] = v.to_dict() if isinstance(v, ConceptNodeSKOS) else dict(v)

        if bridge is not None and getattr(bridge, "available", False):
            go_res = bridge.resolve_concept_correspondences(src_obj.to_dict(), tgt_obj.to_dict(), cat_dict)
            if isinstance(go_res, list):
                return [
                    ConceptCorrespondence(
                        source_value=c["source_value"],
                        source_concept_id=c["source_concept_id"],
                        target_value=c["target_value"],
                        target_concept_id=c["target_concept_id"],
                        shared_anchor_uri=c["shared_anchor_uri"],
                        match_predicate=c["match_predicate"],
                    )
                    for c in go_res
                ]

        # Pure-Python fallback matching Go Core's ValueLabel -> Concept -> SKOS resolution
        nodes: Dict[str, ConceptNodeSKOS] = {
            k: ConceptNodeSKOS.from_dict(v) for k, v in cat_dict.items()
        }

        def expand_entries(m: SemanticFieldMapping) -> List[ValueLabelConceptEntry]:
            out = list(m.value_labels)
            seen = {vl.raw_value for vl in out}
            for k in sorted(m.value_mapping.keys()):
                if k not in seen:
                    out.append(ValueLabelConceptEntry(raw_value=k, concept_id=m.value_mapping[k]))
            for vl in out:
                cid = vl.concept_id.strip()
                if not cid:
                    continue
                ex = nodes.get(cid, ConceptNodeSKOS(concept_id=cid))
                nodes[cid] = ConceptNodeSKOS(
                    concept_id=cid,
                    pref_label=ex.pref_label or vl.pref_label,
                    notation=ex.notation or vl.notation,
                    alt_labels=tuple(dict.fromkeys([*ex.alt_labels, *vl.alt_labels])),
                    skos=ex.skos,
                    exact_match=tuple(dict.fromkeys([*ex.exact_match, *vl.exact_match])),
                    close_match=tuple(dict.fromkeys([*ex.close_match, *vl.close_match])),
                    broader=tuple(dict.fromkeys([*ex.broader, *vl.broader])),
                )
            return out

        src_entries = expand_entries(src_obj)
        tgt_entries = expand_entries(tgt_obj)

        def match_nodes(a: ConceptNodeSKOS, b: ConceptNodeSKOS) -> Optional[tuple[str, str]]:
            if a.concept_id and a.concept_id == b.concept_id:
                return a.concept_id, "direct_concept_ref"
            if b.concept_id in a.exact_match or b.concept_id in a.skos:
                return b.concept_id, "direct_concept_ref"
            if a.concept_id in b.exact_match or a.concept_id in b.skos:
                return a.concept_id, "direct_concept_ref"
            if b.concept_id in a.close_match:
                return b.concept_id, "skos:closeMatch"
            if a.concept_id in b.close_match:
                return a.concept_id, "skos:closeMatch"
            for u in [*a.exact_match, *a.skos]:
                if u in b.exact_match or (u in a.exact_match and u in b.skos):
                    return u, "skos:exactMatch"
            for u in a.skos:
                if u in b.skos:
                    return u, "skos_anchor"
            all_b = set([*b.exact_match, *b.skos, *b.close_match])
            for u in [*a.exact_match, *a.skos, *a.close_match]:
                if u in all_b:
                    return u, "skos:closeMatch"
            return None

        corrs: List[ConceptCorrespondence] = []
        for s_vl in src_entries:
            s_cid = s_vl.concept_id.strip()
            if not s_cid:
                continue
            s_node = nodes[s_cid]
            for t_vl in tgt_entries:
                t_cid = t_vl.concept_id.strip()
                if not t_cid:
                    continue
                t_node = nodes[t_cid]
                res = match_nodes(s_node, t_node)
                if res:
                    corrs.append(ConceptCorrespondence(
                        source_value=s_vl.raw_value,
                        source_concept_id=s_cid,
                        target_value=t_vl.raw_value,
                        target_concept_id=t_cid,
                        shared_anchor_uri=res[0],
                        match_predicate=res[1],
                    ))
        corrs.sort(key=lambda c: (c.source_value, c.target_value))
        return corrs

    @classmethod
    def generate_cross_dataset_join_sql(
        cls,
        source_mapping: SemanticFieldMapping | Dict[str, Any],
        source_alias: str,
        target_mapping: SemanticFieldMapping | Dict[str, Any],
        target_alias: str,
        concept_catalog: Optional[Dict[str, ConceptNodeSKOS | Dict[str, Any]]] = None,
        bridge: Optional[Any] = None,
    ) -> str:
        """Generates a deterministic ANSI SQL join predicate bridging two datasets via SKOS correspondences."""
        src_obj = SemanticFieldMapping.from_dict(source_mapping) if isinstance(source_mapping, dict) else source_mapping
        tgt_obj = SemanticFieldMapping.from_dict(target_mapping) if isinstance(target_mapping, dict) else target_mapping
        cat_dict: Dict[str, Dict[str, Any]] = {}
        for k, v in (concept_catalog or {}).items():
            cat_dict[k] = v.to_dict() if isinstance(v, ConceptNodeSKOS) else dict(v)

        if bridge is not None and getattr(bridge, "available", False):
            go_sql = bridge.generate_cross_dataset_join_sql(
                src_obj.to_dict(), source_alias, tgt_obj.to_dict(), target_alias, cat_dict
            )
            if go_sql:
                return go_sql

        corrs = cls.resolve_concept_correspondences(src_obj, tgt_obj, concept_catalog, bridge=None)
        src_proj = SemanticFieldMapping(
            field_name=src_obj.field_name,
            value_mapping={c.source_value: c.shared_anchor_uri for c in corrs},
        )
        tgt_proj = SemanticFieldMapping(
            field_name=tgt_obj.field_name,
            value_mapping={c.target_value: c.shared_anchor_uri for c in corrs},
        )
        left_sql = cls.generate_case_expression(src_proj, source_alias)
        right_sql = cls.generate_case_expression(tgt_proj, target_alias)
        return f"{left_sql} = {right_sql}"
