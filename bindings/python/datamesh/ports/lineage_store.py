from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class LineageStorePort(ABC):
    """Outbound port defining persistence of operational execution lineage and artifacts."""

    @abstractmethod
    def record_execution(self, record: Dict[str, Any]) -> str:
        """Persists a new script or function execution event and returns its ID."""
        pass

    @abstractmethod
    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves execution record by ID with attached sources, transformations, and artifacts."""
        pass

    @abstractmethod
    def list_executions(self, target: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists execution events optionally filtered by target triad/dataset."""
        pass

    @abstractmethod
    def record_artifact(self, execution_id: str, artifact_path: str, format_name: Optional[str] = None) -> Dict[str, Any]:
        """Computes hash and stores produced artifact metadata linked to execution."""
        pass

    @abstractmethod
    def get_artifacts_for_execution(self, execution_id: str) -> List[Dict[str, Any]]:
        """Retrieves list of output artifacts for a given execution ID."""
        pass

    @abstractmethod
    def get_lineage_for_target(self, target: str) -> Dict[str, Any]:
        """Reconstructs synthesized W3C PROV-O lineage dictionary for a target dataset."""
        pass
    @abstractmethod
    def find_executions_for_cache_key(self, cache_key: str) -> List[Dict[str, Any]]:
        """Finds executions that produced or consumed the given cached entry key."""
        pass

