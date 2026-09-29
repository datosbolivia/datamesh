from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional
try:
    import yaml
except ImportError:
    yaml = None
import json

from datamesh.domain.models import StorageConfig
from datamesh.ports.resolver import ConfigPort

class FileConfigAdapter(ConfigPort):
    """
    Manages loading and saving configuration for DataMesh SDK in ~/datamesh/config.yaml.
    Merges configuration file with environment variables.
    """

    def __init__(self, config_file: Optional[Path] = None):
        if config_file:
            self.config_path = config_file
        else:
            storage_conf = StorageConfig.default()
            self.config_path = storage_conf.config_file
        self._ensure_config_exists()

    def _ensure_config_exists(self) -> None:
        if not self.config_path.exists():
            default_config = {
                "base": {
                    "catalog_url": "https://datosbolivia.github.io/llms.txt",
                    "catalog_urls": [
                        "https://datosbolivia.github.io/llms.txt"
                    ],
                    "storage_path": str(self.config_path.parent / "cache"),
                    "timeout": 30,
                    "log_level": "info",
                },
                "adapters": {
                    "local": {"enabled": True},
                    "github": {"enabled": True},
                    "kaggle": {"enabled": True},
                    "http": {"enabled": True},
                }
            }
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                self.save_config(default_config)
            except Exception:
                pass

    def load_config(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    if self.config_path.suffix in [".yaml", ".yml"] and yaml:
                        data = yaml.safe_load(f) or {}
                    else:
                        data = json.load(f) or {}
            except Exception:
                data = {}

        # Merge environment overrides
        base = data.setdefault("base", {})
        if "DATAMESH_CATALOG_URL" in os.environ:
            base["catalog_url"] = os.environ["DATAMESH_CATALOG_URL"]
        if "DATAMESH_CATALOGS" in os.environ or "DATAMESH_CATALOG_URLS" in os.environ:
            raw = os.environ.get("DATAMESH_CATALOGS") or os.environ.get("DATAMESH_CATALOG_URLS") or ""
            base["catalog_urls"] = [c.strip() for c in raw.split(",") if c.strip()]
        if "DATAMESH_STORAGE_PATH" in os.environ:
            base["storage_path"] = os.environ["DATAMESH_STORAGE_PATH"]
        if "DATAMESH_TIMEOUT" in os.environ:
            try:
                base["timeout"] = int(os.environ["DATAMESH_TIMEOUT"])
            except ValueError:
                pass
        return data

    def save_config(self, config_data: Dict[str, Any]) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                if self.config_path.suffix in [".yaml", ".yml"] and yaml:
                    yaml.safe_dump(config_data, f, default_flow_style=False, sort_keys=False)
                else:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
