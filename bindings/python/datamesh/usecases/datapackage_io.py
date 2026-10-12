from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

try:
    import yaml
except ImportError:
    yaml = None


def load_datapackage(
    datapackage_path_or_dict: Union[str, Path, Dict[str, Any]],
) -> Tuple[Dict[str, Any], Optional[Path]]:
    """Loads a DataPackage from a path (YAML/JSON by suffix) or copies a dict."""
    if isinstance(datapackage_path_or_dict, (str, Path)):
        source_path = Path(datapackage_path_or_dict)
        with open(source_path, "r", encoding="utf-8") as f:
            if yaml is not None and source_path.suffix in (".yaml", ".yml"):
                data = yaml.safe_load(f) or {}
            else:
                data = json.load(f)
        return data, source_path
    return dict(datapackage_path_or_dict), None


def save_datapackage(data: Dict[str, Any], path: Path) -> None:
    """Writes a DataPackage to disk (YAML for .yaml/.yml, JSON otherwise)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if yaml is not None and path.suffix in (".yaml", ".yml"):
            yaml.dump(data, f, sort_keys=False, allow_unicode=True)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)
