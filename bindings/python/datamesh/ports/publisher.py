from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
from datamesh.domain.models import PublicationTargetResult

class PublisherPort(ABC):
    """Abstract port for publishing datasets and ODKF bundles to different target platforms."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the publication target (e.g. 'portal', 'local', 'kaggle', 'github')."""
        ...

    @abstractmethod
    def can_publish(self, target: str) -> bool:
        """Determines if this publisher handles the given target name or URI scheme."""
        ...

    @abstractmethod
    def publish(
        self,
        dataset_dir_or_manifest: Path,
        manifest_data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> PublicationTargetResult:
        """Publishes the dataset bundle to the target platform."""
        ...
