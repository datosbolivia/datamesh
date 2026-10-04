from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Any, Dict, Optional
try:
    import yaml
except ImportError:
    yaml = None

from datamesh.domain.models import PublicationTargetResult
from datamesh.ports.publisher import PublisherPort

class PortalPublisherAdapter(PublisherPort):
    """
    Publishes an ODKF dataset bundle directly into an OKF sovereign portal repository
    (such as catalogo-datamesh or any static Astro portal).
    """

    @property
    def name(self) -> str:
        return "portal"

    def can_publish(self, target: str) -> bool:
        return target.lower() in ("portal", "catalog", "catalogo", "web")

    def publish(
        self,
        dataset_dir_or_manifest: Path,
        manifest_data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> PublicationTargetResult:
        options = options or {}
        # Locate target portal repository: options['portal_dir'] or environment or sibling dir
        portal_dir_raw = options.get("portal_dir") or os.environ.get("DATAMESH_PORTAL_DIR")
        if portal_dir_raw:
            portal_dir = Path(portal_dir_raw).expanduser().resolve()
        else:
            # check sibling catalogo-datamesh
            sibling = Path.cwd().parent / "catalogo-datamesh"
            if sibling.is_dir():
                portal_dir = sibling
            else:
                portal_dir = Path.cwd() / "portal"

        nodes_dir = portal_dir / "knowledge" / "nodes"
        slug = manifest_data.get("slug") or manifest_data.get("name") or "dataset"
        target_node = nodes_dir / slug
        target_node.mkdir(parents=True, exist_ok=True)

        try:
            # 1. datapackage.yaml / yml
            dp_file = target_node / "datapackage.yaml"
            dp_content = {
                "name": slug,
                "title": manifest_data.get("title", slug),
                "description": manifest_data.get("description", ""),
            }
            if "spatial" in manifest_data:
                dp_content["spatial"] = manifest_data["spatial"]
            if "temporal" in manifest_data:
                dp_content["temporal"] = manifest_data["temporal"]
            if "quality" in manifest_data:
                dp_content["quality"] = manifest_data["quality"]
            if "resources" in manifest_data:
                dp_content["resources"] = manifest_data["resources"]

            if yaml is not None:
                with open(dp_file, "w", encoding="utf-8") as f:
                    yaml.dump(dp_content, f, sort_keys=False, allow_unicode=True)

            # 2. index.md
            index_file = target_node / "index.md"
            fm_data = {
                "type": manifest_data.get("type", "dataset"),
                "title": manifest_data.get("title", slug),
                "description": manifest_data.get("description", ""),
                "contracts": [{"type": "datapackage", "path": "./datapackage.yaml"}],
            }
            if "spatial" in manifest_data:
                fm_data["spatial"] = manifest_data["spatial"]
            if "temporal" in manifest_data:
                fm_data["temporal"] = manifest_data["temporal"]

            body = manifest_data.get("body") or f"# {manifest_data.get('title', slug)}\n\n{manifest_data.get('description', '')}\n"

            with open(index_file, "w", encoding="utf-8") as f:
                f.write("---\n")
                if yaml is not None:
                    f.write(yaml.dump(fm_data, sort_keys=False, allow_unicode=True).strip())
                else:
                    for k, v in fm_data.items():
                        f.write(f"{k}: {v}\n")
                f.write("\n---\n\n")
                f.write(body)

            # 3. Concepts if any
            source_dir = dataset_dir_or_manifest if dataset_dir_or_manifest.is_dir() else dataset_dir_or_manifest.parent
            concepts_src = source_dir / "concepts"
            if concepts_src.is_dir():
                concepts_dst = target_node / "concepts"
                concepts_dst.mkdir(parents=True, exist_ok=True)
                for item in concepts_src.glob("*.md"):
                    shutil.copy2(item, concepts_dst / item.name)

            return PublicationTargetResult(
                target="portal",
                success=True,
                destination_uri=str(target_node),
                message=f"Dataset published to portal node {target_node}",
            )
        except Exception as e:
            return PublicationTargetResult(
                target="portal",
                success=False,
                destination_uri=str(target_node),
                error=str(e),
                message=f"Failed to publish to portal: {e}",
            )
