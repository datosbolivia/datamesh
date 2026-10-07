from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

try:
    import yaml
except ImportError:
    yaml = None

from datamesh.domain.models import (
    LineageEdge,
    LineageGraph,
    LineageInfo,
    LineageNode,
    LineageSource,
    LineageTransformation,
)
from datamesh.constants import get_workspace_search_dirs


class DatasetLineageUseCase:
    """
    Orchestrates dataset provenance, dependency extraction, and lineage graph analysis
    conforming to OKF / ODKF v0.2 and W3C PROV-O standards.
    """

    def __init__(
        self,
        search_dirs_fn: Optional[Callable[[], List[Path]]] = None,
        catalog_discovery_fn: Optional[Callable[[Optional[str]], Dict[str, Any]]] = None,
    ):
        self._search_dirs_fn = search_dirs_fn or get_workspace_search_dirs
        self._catalog_discovery_fn = catalog_discovery_fn

    def extract_from_dict(self, data: Dict[str, Any], default_id: str = "") -> LineageInfo:
        """Constructs a LineageInfo model from a manifest dictionary."""
        return LineageInfo.from_dict(data, dataset_id=default_id)

    def extract_from_file(self, file_path: Union[str, Path]) -> Optional[LineageInfo]:
        """Extracts LineageInfo from a datapackage.yaml/json or OKF markdown file."""
        path_obj = Path(file_path)
        if not path_obj.exists() or not path_obj.is_file():
            return None

        # Derive dataset id from parent directory or file name
        fname = path_obj.name.lower()
        parent_name = path_obj.parent.name

        if fname.endswith((".yaml", ".yml", ".json")):
            try:
                content = path_obj.read_text(encoding="utf-8")
                data = yaml.safe_load(content) if yaml and fname.endswith((".yaml", ".yml")) else json.loads(content)
                if isinstance(data, dict):
                    ds_id = str(data.get("name") or data.get("id") or parent_name)
                    return self.extract_from_dict(data, default_id=ds_id)
            except Exception:
                return None

        elif fname.endswith(".md"):
            try:
                content = path_obj.read_text(encoding="utf-8")
                return self.extract_from_markdown(content, default_id=parent_name)
            except Exception:
                return None

        return None

    def extract_from_markdown(self, markdown_text: str, default_id: str = "") -> Optional[LineageInfo]:
        """Extracts frontmatter YAML and constructs LineageInfo from markdown text."""
        lines = markdown_text.splitlines()
        if not lines or lines[0].strip() != "---":
            return None

        end_idx = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break

        if end_idx == -1:
            return None

        frontmatter_str = "\n".join(lines[1:end_idx])
        if yaml:
            try:
                fm = yaml.safe_load(frontmatter_str)
                if isinstance(fm, dict):
                    ds_id = str(fm.get("id") or fm.get("name") or default_id or "unnamed_node")
                    return self.extract_from_dict(fm, default_id=ds_id)
            except Exception:
                pass
        return None

    def scan_directory(self, dir_path: Union[str, Path]) -> List[LineageInfo]:
        """Scans a directory tree for DataPackages and OKF index.md files with lineage."""
        root = Path(dir_path)
        if not root.exists():
            return []

        records: List[LineageInfo] = []
        seen_ids: Set[str] = set()

        # Find manifests
        manifest_names = ("datapackage.yaml", "datapackage.yml", "datapackage.json", "index.md")
        for mname in manifest_names:
            for p in root.rglob(mname):
                # Avoid hidden or cache directories
                if any(part.startswith((".", "node_modules", "venv", "__pycache__")) for part in p.parts):
                    continue
                rec = self.extract_from_file(p)
                if rec and rec.dataset_id and rec.dataset_id not in seen_ids:
                    records.append(rec)
                    seen_ids.add(rec.dataset_id)

        return records

    def build_graph(
        self,
        records: Optional[List[LineageInfo]] = None,
        search_dirs: Optional[List[Union[str, Path]]] = None,
        catalog_url: Optional[str] = None,
    ) -> LineageGraph:
        """
        Builds a comprehensive Lineage DAG graph combining explicit records,
        scanned workspace packages, and discovered federated catalogs.
        """
        collected: Dict[str, LineageInfo] = {}

        # 1. Add explicit records
        if records:
            for r in records:
                collected[r.dataset_id] = r

        # 2. Scan workspace directories if none provided or to complement
        dirs_to_scan = search_dirs if search_dirs is not None else self._search_dirs_fn()
        for d in dirs_to_scan:
            scanned = self.scan_directory(d)
            for s in scanned:
                if s.dataset_id not in collected:
                    collected[s.dataset_id] = s

        # 3. Incorporate federated catalog if discovery function is available
        if self._catalog_discovery_fn:
            try:
                cat = self._catalog_discovery_fn(catalog_url)
                for entry in cat.get("entries", []):
                    entry_title = entry.get("title", "")
                    entry_url = entry.get("resolved_url") or entry.get("url") or ""
                    # If entry has lineage field or name
                    entry_id = entry.get("name") or entry.get("id") or entry_title
                    if entry_id and entry_id not in collected and entry.get("lineage"):
                        rec = self.extract_from_dict(entry, default_id=entry_id)
                        collected[entry_id] = rec
            except Exception:
                pass

        # Build nodes and edges
        nodes: Dict[str, LineageNode] = {}
        edges: List[LineageEdge] = []

        # Add all known datasets as nodes
        for ds_id, rec in collected.items():
            nodes[ds_id] = LineageNode(
                id=ds_id,
                title=rec.title or ds_id,
                type="dataset",
            )

        # Build edges based on was_derived_from, sources, and transformations
        for ds_id, rec in collected.items():
            # Derive edges from sources
            parents: Set[str] = set()

            for src in rec.sources:
                p_name = src.dataset or src.name
                if p_name and p_name != ds_id:
                    parents.add(p_name)
                    # If parent node doesn't exist yet, register it as external source or dataset
                    if p_name not in nodes:
                        is_url = p_name.startswith(("http://", "https://", "file://"))
                        node_type = "external_source" if is_url else "dataset"
                        nodes[p_name] = LineageNode(
                            id=p_name,
                            title=src.name or p_name,
                            type=node_type,
                        )

            for p in rec.was_derived_from:
                if p != ds_id:
                    parents.add(p)
                    if p not in nodes:
                        nodes[p] = LineageNode(id=p, title=p, type="dataset")

            # Associate edge labels with transformations if available
            label = None
            first_trans = rec.transformations[0] if rec.transformations else None
            if first_trans:
                label = first_trans.description or first_trans.tool

            for p in parents:
                edges.append(LineageEdge(
                    source=p,
                    target=ds_id,
                    label=label,
                    transformation=first_trans,
                ))

        return LineageGraph(
            nodes=nodes,
            edges=tuple(edges),
            records=collected,
        )

    def get_lineage(
        self,
        dataset_id_or_path: str,
        search_dirs: Optional[List[Union[str, Path]]] = None,
        catalog_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculates full lineage details for a given dataset, showing what it was produced from (upstream)
        and what datasets are the result of it (downstream).
        """
        # If dataset_id_or_path is a path to an existing file, extract it first
        file_rec: Optional[LineageInfo] = None
        target_id = dataset_id_or_path
        if os.path.exists(dataset_id_or_path):
            file_rec = self.extract_from_file(dataset_id_or_path)
            if file_rec:
                target_id = file_rec.dataset_id

        # Build graph
        explicit_records = [file_rec] if file_rec else []
        graph = self.build_graph(
            records=explicit_records,
            search_dirs=search_dirs,
            catalog_url=catalog_url,
        )

        # If not found directly, check case-insensitive or partial match
        if target_id not in graph.nodes:
            clean_tgt = target_id.lower().strip()
            for nid in graph.nodes:
                if nid.lower().strip() == clean_tgt:
                    target_id = nid
                    break

        upstream_ids = graph.upstream(target_id)
        downstream_ids = graph.downstream(target_id)
        record = graph.records.get(target_id)

        node = graph.nodes.get(target_id)
        title = record.title if record and record.title else (node.title if node else target_id)

        return {
            "dataset_id": target_id,
            "title": title,
            "version": record.version if record else None,
            "updated_at": record.updated_at if record else None,
            "upstream": upstream_ids,
            "downstream": downstream_ids,
            "sources": [s.to_dict() for s in record.sources] if record else [],
            "transformations": [t.to_dict() for t in record.transformations] if record else [],
            "mermaid": graph.to_mermaid(highlight_id=target_id),
            "ascii": graph.to_ascii(root_id=target_id),
            "graph": graph.to_dict(),
        }
