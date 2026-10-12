from __future__ import annotations

from typing import Any, Dict

from datamesh.adapters.go_bridge import GoCoreBridge
from datamesh.adapters.web import fetch_text

try:
    import yaml
except ImportError:
    yaml = None


class ResolveDataProductUseCase:
    """Resolves an ODKF node document and returns its DataProduct metadata.

    Delegates to the Go core via the C-ABI bridge and falls back to reading the
    node markdown (``file://``, http(s) or local path) and parsing its YAML
    frontmatter.
    """

    def __init__(self, bridge: GoCoreBridge):
        self._bridge = bridge

    def execute(self, uri: str) -> Dict[str, Any]:
        go_result = self._bridge.call("DataMeshResolveDataProduct", uri)
        if go_result:
            return go_result

        content = fetch_text(uri, timeout=2)

        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError("No YAML frontmatter found in node markdown")

        frontmatter = parts[1]
        body = parts[2].strip()

        manifest: Dict[str, Any] = {"dimensions": [], "contracts": []}
        try:
            parsed_yaml = yaml.safe_load(frontmatter)
            if isinstance(parsed_yaml, dict):
                manifest.update(parsed_yaml)
                if "dimensions" not in manifest or not manifest["dimensions"]:
                    dom = parsed_yaml.get("domain") or parsed_yaml.get("dominio")
                    manifest["dimensions"] = [dom] if dom else ["core"]
                if "contracts" not in manifest:
                    manifest["contracts"] = []
                if "title" not in manifest and "id" in parsed_yaml:
                    manifest["title"] = str(parsed_yaml["id"])
        except Exception:
            for line in frontmatter.splitlines():
                line_str = line.strip()
                if not line_str or line_str.startswith("#"):
                    continue
                if line_str.startswith("title:"):
                    manifest["title"] = line_str.split(":", 1)[1].strip().strip("\"'")
                elif line_str.startswith("type:"):
                    manifest["type"] = line_str.split(":", 1)[1].strip().strip("\"'")
                elif line_str.startswith("id:") and "title" not in manifest:
                    manifest["title"] = line_str.split(":", 1)[1].strip().strip("\"'")
                elif line_str.startswith("- ") and "dimensions" in manifest:
                    manifest["dimensions"].append(line_str[2:].strip().strip("\"'"))

            if not manifest["dimensions"]:
                manifest["dimensions"] = ["core"]

        return {
            "id": uri,
            "manifest": manifest,
            "description": body,
        }
