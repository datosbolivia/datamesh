from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datamesh.domain.models import ResolvedResource
from datamesh.ports.storage import StoragePort

class ResourceAdapterPort(ABC):
    """Abstract port for service-specific resource resolution and downloading (Local, Kaggle, Git, HTTP)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the adapter (e.g. 'local', 'github', 'kaggle', 'http')."""
        ...

    @abstractmethod
    def can_handle(self, uri_or_path: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Determines if this adapter can resolve or download the specified URI or path."""
        ...

    @abstractmethod
    def resolve_and_fetch(
        self,
        uri_or_path: str,
        storage: StoragePort,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ResolvedResource]:
        """
        Resolves metadata and fetches the resource into temporal cache if necessary.
        Returns ResolvedResource with local path for DuckDB execution.
        """
        ...

class ConfigPort(ABC):
    """Abstract port for reading and writing configuration in generic ~/datamesh/config.yaml."""

    @abstractmethod
    def load_config(self) -> Dict[str, Any]:
        """Loads configuration from file merged with environment variables."""
        ...

    @abstractmethod
    def save_config(self, config_data: Dict[str, Any]) -> None:
        """Saves configuration back to disk."""
        ...
