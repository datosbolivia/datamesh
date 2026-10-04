from __future__ import annotations

import json
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

class LocalBundlePublisherAdapter(PublisherPort):
    """Publishes or exports a dataset bundle into a standard OKF/ODKF local directory."""

    @property
    def name(self) -> str:
        return "local"

    def can_publish(self, target: str) -> bool:
        return target.lower() in ("local", "directory", "dir", "file", "bundle") or target.startswith((".", "/", "~"))

    def publish(
        self,
        dataset_dir_or_manifest: Path,
        manifest_data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> PublicationTargetResult:
        options = options or {}
        output_dir = Path(options.get("destination", options.get("output_dir", "./dist_bundle"))).expanduser().resolve()
        slug = manifest_data.get("slug") or manifest_data.get("name") or dataset_dir_or_manifest.name.replace(".yaml", "").replace(".yml", "").replace(".json", "")

        target_node_dir = output_dir / slug if output_dir.name != slug else output_dir
        target_node_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. datapackage.yaml / .json
            dp_file = target_node_dir / "datapackage.yaml"
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
            else:
                dp_json = target_node_dir / "datapackage.json"
                with open(dp_json, "w", encoding="utf-8") as f:
                    json.dump(dp_content, f, indent=2, ensure_ascii=False)

            # 2. index.md with OKF frontmatter
            index_file = target_node_dir / "index.md"
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
                        f.write(f"{k}: {json.dumps(v, ensure_ascii=False)}\n")
                f.write("\n---\n\n")
                f.write(body)

            # 3. Concepts folder if present in source
            source_dir = dataset_dir_or_manifest if dataset_dir_or_manifest.is_dir() else dataset_dir_or_manifest.parent
            concepts_src = source_dir / "concepts"
            if concepts_src.is_dir():
                concepts_dst = target_node_dir / "concepts"
                concepts_dst.mkdir(parents=True, exist_ok=True)
                for item in concepts_src.glob("*.md"):
                    shutil.copy2(item, concepts_dst / item.name)

            return PublicationTargetResult(
                target="local",
                success=True,
                destination_uri=str(target_node_dir),
                message=f"Bundle successfully created at {target_node_dir}",
            )
        except Exception as e:
            return PublicationTargetResult(
                target="local",
                success=False,
                destination_uri=str(target_node_dir),
                error=str(e),
                message=f"Failed to publish local bundle: {e}",
            )
