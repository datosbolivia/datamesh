from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional
from datamesh.domain.models import CacheEntryMetadata, StorageConfig

class StoragePort(ABC):
    """Abstract port for temporal and persistent storage management."""

    @property
    @abstractmethod
    def config(self) -> StorageConfig:
        """Returns the active storage configuration."""
        ...

    @abstractmethod
    def get_cache_dir(self) -> Path:
        """Returns the base cache directory (e.g. ~/datamesh/cache)."""
        ...

    @abstractmethod
    def is_cached(self, key_or_uri: str) -> bool:
        """Checks if a resource is already present and valid in cache."""
        ...

    @abstractmethod
    def get_cached_path(self, key_or_uri: str) -> Optional[Path]:
        """Returns local Path to cached file if exists, else None."""
        ...

    @abstractmethod
    def save(
        self,
        key_or_uri: str,
        content: bytes | str | BinaryIO,
        extension: Optional[str] = None,
        source_service: str = "unknown",
        etag: Optional[str] = None,
    ) -> Path:
        """Saves content into temporal cache atomically and updates metadata."""
        ...

    @abstractmethod
    def store_file(
        self,
        source_path: Path | str,
        key_or_uri: str,
        source_service: str = "unknown",
        move: bool = False,
    ) -> Path:
        """Stores or copies an existing physical file into the cache."""
        ...

    @abstractmethod
    def get_metadata(self, key_or_uri: str) -> Optional[CacheEntryMetadata]:
        """Retrieves recorded metadata for a cached entry."""
        ...

    @abstractmethod
    def evict(self, key_or_uri: str) -> bool:
        """Removes a single item from the cache."""
        ...

    @abstractmethod
    def clear(self, older_than_seconds: Optional[int] = None) -> int:
        """Clears all or expired cache entries. Returns count of files removed."""
        ...
