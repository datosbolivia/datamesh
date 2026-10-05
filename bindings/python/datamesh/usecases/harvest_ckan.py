from __future__ import annotations

import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional
try:
    import yaml
except ImportError:
    yaml = None

from datamesh.domain.models import CKANPackage, CKANHarvestResult
from datamesh.ports.harvester import CKANClientPort, AuthProviderPort

import unicodedata

logger = logging.getLogger("datamesh.usecases.harvest_ckan")


def slugify(text: str) -> str:
    norm = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    cleaned = re.sub(r'[^a-zA-Z0-9]+', '_', norm.strip().lower())
    return cleaned.strip('_') or 'dataset'


class HarvestCKANUseCase:
    """Orchestrates harvesting CKAN datasets and reconstructing OKF v0.2 knowledge bundles."""

    def __init__(self, client: CKANClientPort):
        self._client = client

    def execute(
        self,
        base_url: str,
        query: str = "",
        limit: int = 100,
        offset: int = 0,
        auth_provider: Optional[AuthProviderPort] = None,
        output_dir: Optional[str | Path] = None,
        probe_datastore_schema: bool = True,
    ) -> CKANHarvestResult:
        start_time = time.time()
        packages, total_count = self._client.search_packages(
            base_url=base_url,
            query=query,
            offset=offset,
            limit=limit,
            auth_provider=auth_provider,
        )

        reconstructed_manifests: List[Dict[str, Any]] = []

        target_path = Path(output_dir).resolve() if output_dir else None
        if target_path:
            target_path.mkdir(parents=True, exist_ok=True)

        for pkg in packages:
            manifest_dict, index_md = self.reconstruct_okf_bundle(
                pkg=pkg,
                base_url=base_url,
                auth_provider=auth_provider,
                probe_datastore_schema=probe_datastore_schema,
            )
            reconstructed_manifests.append(manifest_dict)

            if target_path:
                pkg_dir = target_path / manifest_dict["name"]
                pkg_dir.mkdir(parents=True, exist_ok=True)

                # Write datapackage.yaml / datapackage.json
                dp_file = pkg_dir / "datapackage.yaml"
                if yaml:
                    with open(dp_file, "w", encoding="utf-8") as f:
                        yaml.dump(manifest_dict, f, allow_unicode=True, sort_keys=False)
                else:
                    dp_file = pkg_dir / "datapackage.json"
                    with open(dp_file, "w", encoding="utf-8") as f:
                        json.dump(manifest_dict, f, indent=2, ensure_ascii=False)

                # Write index.md
                idx_file = pkg_dir / "index.md"
                with open(idx_file, "w", encoding="utf-8") as f:
                    f.write(index_md)

        exec_ms = int((time.time() - start_time) * 1000)
        return CKANHarvestResult(
            catalog_url=base_url,
            total_discovered=total_count,
            harvested_packages=tuple(reconstructed_manifests),
            output_directory=str(target_path) if target_path else None,
            execution_time_ms=exec_ms,
        )

    def reconstruct_okf_bundle(
        self,
        pkg: CKANPackage,
        base_url: str = "",
        auth_provider: Optional[AuthProviderPort] = None,
        probe_datastore_schema: bool = True,
    ) -> tuple[Dict[str, Any], str]:
        """Transforms a CKAN package into OKF datapackage dict and index.md string."""
        pkg_slug = slugify(pkg.name) or slugify(pkg.title)
        title = pkg.title or pkg.name
        description = pkg.notes or f"Conjunto de datos extraído del portal CKAN {base_url}"

        # 1. Resources
        resources_list: List[Dict[str, Any]] = []
        for r in pkg.resources:
            r_slug = slugify(r.name)
            fields: List[Dict[str, str]] = []
            if r.datastore_active and probe_datastore_schema and base_url:
                try:
                    fields = self._client.get_datastore_schema(base_url, r.id, auth_provider)
                except Exception as e:
                    logger.debug("Failed to probe datastore schema for resource %s: %s", r.id, e)

            res_entry: Dict[str, Any] = {
                "name": r_slug,
                "title": r.name,
                "path": r.url,
                "format": r.format,
                "scheme": "http" if r.url.startswith("http") else "file",
            }
            if r.description:
                res_entry["description"] = r.description
            if r.size:
                res_entry["bytes"] = r.size
            if r.mimetype:
                res_entry["mediatype"] = r.mimetype
            if fields:
                res_entry["schema"] = {"fields": fields}

            resources_list.append(res_entry)

        # 2. Spatial & Temporal extras
        spatial_cov = self._extract_spatial(pkg.extras)
        temporal_cov = self._extract_temporal(pkg.extras)

        # 3. Assemble datapackage
        dp_dict: Dict[str, Any] = {
            "name": pkg_slug,
            "title": title,
            "description": description,
            "resources": resources_list,
        }
        if pkg.version:
            dp_dict["version"] = pkg.version
        if spatial_cov:
            dp_dict["spatial"] = spatial_cov
        if temporal_cov:
            dp_dict["temporal"] = temporal_cov
        if pkg.tags:
            dp_dict["keywords"] = list(pkg.tags)

        # Quality estimation
        dp_dict["quality"] = {
            "status": "curated",
            "completeness": 0.95 if resources_list else 0.50,
        }

        # 4. Generate index.md with frontmatter
        index_md = self._render_index_markdown(pkg_slug, title, description, pkg, dp_dict)

        return dp_dict, index_md

    def _extract_spatial(self, extras: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for key in ("spatial", "spatial-coverage", "spatial_coverage", "coverage_spatial"):
            val = extras.get(key)
            if not val:
                continue
            if isinstance(val, str) and val.strip().startswith("{"):
                try:
                    geo = json.loads(val)
                    if "bbox" in geo:
                        return {"bbox": geo["bbox"], "granularity": "geojson"}
                except Exception:
                    pass
            elif isinstance(val, str) and "," in val:
                parts = [p.strip() for p in val.split(",")]
                if len(parts) == 4:
                    try:
                        bbox = [float(p) for p in parts]
                        return {"bbox": bbox, "granularity": "bbox"}
                    except ValueError:
                        pass
            return {"country": str(val)}
        return None

    def _extract_temporal(self, extras: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        out: Dict[str, Any] = {}
        for k in ("temporal_start", "temporal_start_date", "start_date"):
            if k in extras and extras[k]:
                out["start"] = str(extras[k])
                break
        for k in ("temporal_end", "temporal_end_date", "end_date"):
            if k in extras and extras[k]:
                out["end"] = str(extras[k])
                break
        for k in ("frequency", "accrualperiodicity", "periodicity"):
            if k in extras and extras[k]:
                out["frequency"] = str(extras[k])
                break

        return out if out else None

    def _render_index_markdown(
        self,
        slug: str,
        title: str,
        description: str,
        pkg: CKANPackage,
        dp_dict: Dict[str, Any]
    ) -> str:
        fm_lines = [
            "---",
            "type: dataset",
            f"title: \"{title}\"",
            f"description: \"{description[:180].replace(chr(10), ' ')}\"",
        ]
        if "spatial" in dp_dict:
            sp = dp_dict["spatial"]
            fm_lines.append("spatial:")
            if "country" in sp:
                fm_lines.append(f"  country: {sp['country']}")
            if "bbox" in sp:
                fm_lines.append(f"  bbox: {sp['bbox']}")
        if "temporal" in dp_dict:
            tp = dp_dict["temporal"]
            fm_lines.append("temporal:")
            if "start" in tp:
                fm_lines.append(f"  start: {tp['start']}")
            if "end" in tp:
                fm_lines.append(f"  end: {tp['end']}")

        fm_lines.extend([
            "contracts:",
            "  - type: datapackage",
            "    path: ./datapackage.yaml",
        ])
        if pkg.organization_title:
            fm_lines.extend([
                "lineage:",
                "  source:",
                f"    - name: \"{pkg.organization_title}\"",
            ])
            if pkg.url:
                fm_lines.append(f"      url: {pkg.url}")

        if pkg.tags:
            fm_lines.append(f"tags: [{', '.join(pkg.tags[:10])}]")

        fm_lines.append("---\n")

        body_lines = [
            f"# {title}\n",
            f"{description}\n",
            "## Recursos Disponibles\n",
        ]
        for r in pkg.resources:
            body_lines.append(f"- **{r.name}** (`{r.format}`): [{r.url}]({r.url})")
            if r.description:
                body_lines.append(f"  - *Descripción*: {r.description}")

        body_lines.append("\n## Origen e Integración OKF")
        body_lines.append("Reconstruido automáticamente desde portal CKAN hacia especificación soberana OKF / ODKF v0.2.")

        return "\n".join(fm_lines) + "\n" + "\n".join(body_lines) + "\n"
