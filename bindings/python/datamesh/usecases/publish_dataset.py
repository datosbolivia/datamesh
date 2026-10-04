from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
try:
    import yaml
except ImportError:
    yaml = None

from datamesh.domain.models import PublicationTargetResult
from datamesh.ports.publisher import PublisherPort

class PublishDatasetUseCase:
    """Orchestrates validation, metadata enrichment, and multi-target publishing of ODKF datasets."""

    def __init__(self, publishers: Optional[List[PublisherPort]] = None):
        self._publishers = publishers or []

    def register_publisher(self, publisher: PublisherPort) -> None:
        self._publishers.append(publisher)

    def load_manifest(self, path: Path) -> Dict[str, Any]:
        """Loads manifest from datapackage.yaml/json or directory."""
        if path.is_dir():
            candidates = [
                path / "datapackage.yaml",
                path / "datapackage.yml",
                path / "datapackage.json",
                path / "index.md",
            ]
            for c in candidates:
                if c.is_file():
                    return self.load_manifest(c)
            return {"slug": path.name, "title": path.name}

        content = path.read_text(encoding="utf-8")
        if path.name == "index.md" or path.suffix == ".md":
            # Extract frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm_text = parts[1]
                    body = parts[2].strip()
                    fm = yaml.safe_load(fm_text) if yaml is not None else {}
                    fm["body"] = body
                    return fm
            return {"title": path.stem, "body": content}

        if path.suffix in (".yaml", ".yml") and yaml is not None:
            return yaml.safe_load(content) or {}
        elif path.suffix == ".json":
            return json.loads(content)
        return {}

    def execute(
        self,
        dataset_path: str | Path,
        targets: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> List[PublicationTargetResult]:
        p = Path(dataset_path).expanduser().resolve()
        manifest = self.load_manifest(p)
        options = options or {}

        targets_to_run = targets or ["local"]
        results: List[PublicationTargetResult] = []

        for target in targets_to_run:
            matched = False
            for pub in self._publishers:
                if pub.can_publish(target):
                    matched = True
                    res = pub.publish(p, manifest, options=options)
                    results.append(res)
                    break
            if not matched:
                results.append(PublicationTargetResult(
                    target=target,
                    success=False,
                    error=f"No publisher adapter registered for target '{target}'",
                ))

        return results
