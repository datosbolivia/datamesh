from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
import urllib.request
import urllib.error

from datamesh.domain.models import PublicationTargetResult
from datamesh.ports.publisher import PublisherPort

class KagglePublisherAdapter(PublisherPort):
    """Generates dataset-metadata.json and publishes or prepares a dataset for Kaggle Datasets API."""

    @property
    def name(self) -> str:
        return "kaggle"

    def can_publish(self, target: str) -> bool:
        return target.lower() in ("kaggle", "kaggle.com") or target.startswith("kaggle://")

    def publish(
        self,
        dataset_dir_or_manifest: Path,
        manifest_data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> PublicationTargetResult:
        options = options or {}
        output_dir = Path(options.get("destination", dataset_dir_or_manifest if dataset_dir_or_manifest.is_dir() else dataset_dir_or_manifest.parent)).expanduser().resolve()
        
        slug = manifest_data.get("slug") or manifest_data.get("name") or "dataset"
        owner = options.get("owner") or os.environ.get("KAGGLE_USERNAME", "datosbolivia")
        kaggle_id = f"{owner}/{slug}"

        # Generate dataset-metadata.json
        metadata = {
            "title": manifest_data.get("title", slug),
            "id": kaggle_id,
            "licenses": [{"name": manifest_data.get("license", "CC-BY-4.0")}],
            "description": manifest_data.get("description", ""),
        }
        
        # Spatial/temporal description enrichment for Kaggle
        extras = []
        if "spatial" in manifest_data:
            sp = manifest_data["spatial"]
            extras.append(f"Spatial Coverage: {sp.get('country', '')} {sp.get('regions', '')}".strip())
        if "temporal" in manifest_data:
            tp = manifest_data["temporal"]
            extras.append(f"Temporal Coverage: {tp.get('start', '')} to {tp.get('end', '')} ({tp.get('frequency', '')})".strip())
        
        if extras:
            metadata["description"] += "\n\n" + "\n".join(extras)

        metadata_file = output_dir / "dataset-metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Check if Kaggle CLI / library is available for actual upload
        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
            api = KaggleApi()
            api.authenticate()
            api.dataset_create_new(folder=str(output_dir), dir_mode="zip", quiet=False)
            return PublicationTargetResult(
                target="kaggle",
                success=True,
                destination_uri=f"https://www.kaggle.com/datasets/{kaggle_id}",
                message=f"Kaggle dataset created/updated at https://www.kaggle.com/datasets/{kaggle_id}",
            )
        except ImportError:
            return PublicationTargetResult(
                target="kaggle",
                success=True,
                destination_uri=str(metadata_file),
                message=f"Prepared Kaggle metadata at {metadata_file}. Run 'kaggle datasets create -p {output_dir}' to upload.",
            )
        except Exception as e:
            return PublicationTargetResult(
                target="kaggle",
                success=False,
                destination_uri=str(metadata_file),
                error=str(e),
                message=f"Kaggle metadata generated at {metadata_file}, but API upload failed: {e}",
            )
