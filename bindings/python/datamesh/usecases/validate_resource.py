from __future__ import annotations

import os
import re
from typing import Any, Dict

from datamesh.adapters.go_bridge import GoCoreBridge


class ValidateResourceUseCase:
    """Validates an OKF/ODKF concept, bundle directory or canonical triad.

    Delegates to the Go core via the C-ABI bridge, then falls back to the
    reference-agent Python validator and, finally, a permissive structural check.
    """

    def __init__(self, bridge: GoCoreBridge):
        self._bridge = bridge

    def execute(self, target: str) -> Dict[str, Any]:
        go_result = self._bridge.call("DataMeshValidate", target)
        if go_result:
            return go_result

        try:
            from reference_agent.bundle.validator import validate_concept_content, validate_bundle, validate_triad
            if os.path.isdir(target):
                return validate_bundle(target).to_dict()
            if os.path.isfile(target):
                with open(target, "r", encoding="utf-8") as f:
                    return validate_concept_content(f.read(), file_path=target).to_dict()
            if ":" in target or "/" in target:
                return validate_triad(target).to_dict()
        except ImportError:
            pass

        clean = target.strip().strip("\"'")
        is_triad = bool(re.match(r"^[a-zA-Z0-9_\-\.]+[:/][a-zA-Z0-9_\-\. ]+([:/][a-zA-Z0-9_\-\. ]+)?$", clean))
        valid = is_triad or os.path.exists(target)
        return {
            "valid": valid,
            "target": target,
            "total_errors": 0 if valid else 1,
            "total_warnings": 0,
            "issues": [] if valid else [{"code": "VALIDATION-FAILED", "severity": "ERROR", "message": f"Could not validate target '{target}'"}],
        }
