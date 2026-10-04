from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class StorageConfig:
    """Configuration parameters for generic ~/.datamesh and ~/datamesh storage."""
    home_dir: Path
    cache_dir: Path
    config_file: Path
    max_cache_size_bytes: int = 10 * 1024 * 1024 * 1024  # 10 GB
    default_ttl_seconds: int = 86400 * 7  # 7 days

    @classmethod
    def default(cls) -> StorageConfig:
        from datamesh.constants import get_datamesh_home, get_cache_dir
        home = get_datamesh_home()
        cache = get_cache_dir()
        config_path = home / "config.yaml"
        return cls(
            home_dir=home,
            cache_dir=cache,
            config_file=config_path,
        )

@dataclass(frozen=True)
class CanonicalURI:
    """Represents a standardized sovereign URI '[catalog:]dataset:resource' or 'datamesh://...'."""
    dataset: str
    resource: str
    catalog: Optional[str] = None

    @classmethod
    def parse(cls, raw: str) -> Optional[CanonicalURI]:
        trimmed = raw.strip().strip("'\"`")
        if not trimmed:
            return None
        # 1. datamesh:// or odkf:// scheme
        if trimmed.startswith(("datamesh://", "odkf://")):
            clean = trimmed.split("://", 1)[1]
            parts = [p.strip() for p in clean.split("/") if p.strip()]
            if len(parts) >= 3:
                return cls(catalog=parts[0], dataset=parts[1], resource=parts[2])
            elif len(parts) == 2:
                return cls(catalog=None, dataset=parts[0], resource=parts[1])
            return None

        # 2. HTTP/HTTPS or file URLs containing /datasets/<dataset>/<resource> or /nodes/<dataset>/<resource>
        if trimmed.startswith(("http://", "https://", "file://")):
            # Match e.g. .../datasets/cartera-creditos/creditos.csv or .../nodes/elecciones/votos.parquet
            match = re.search(r'/(?:datasets|nodes)/([^/]+)/([^/?#]+)', trimmed)
            if match:
                ds = match.group(1).strip()
                res_raw = match.group(2).strip()
                res = res_raw.rsplit(".", 1)[0] if "." in res_raw else res_raw
                return cls(catalog=None, dataset=ds, resource=res)
            # Match generic URL ending with /<dataset>/<resource.ext>
            parsed_path = trimmed.split("?")[0].split("#")[0].rstrip("/")
            path_parts = [p for p in parsed_path.split("/") if p]
            if len(path_parts) >= 2:
                ds = path_parts[-2]
                res_raw = path_parts[-1]
                res = res_raw.rsplit(".", 1)[0] if "." in res_raw else res_raw
                return cls(catalog=None, dataset=ds, resource=res)

        # 3. Colon-separated format ('cat:ds:res' or 'ds:res')
        if ":" in trimmed:
            parts = trimmed.split(":")
            if len(parts) == 3:
                return cls(catalog=parts[0].strip(), dataset=parts[1].strip(), resource=parts[2].strip())
            elif len(parts) == 2:
                return cls(catalog=None, dataset=parts[0].strip(), resource=parts[1].strip())

        # 4. Slash-separated format ('cat/ds/res' or 'ds/res')
        if "/" in trimmed:
            parts = [p.strip() for p in trimmed.split("/") if p.strip()]
            if len(parts) == 3:
                return cls(catalog=parts[0], dataset=parts[1], resource=parts[2])
            elif len(parts) == 2:
                return cls(catalog=None, dataset=parts[0], resource=parts[1])

        return None

    @property
    def triad(self) -> str:
        if self.catalog:
            return f"{self.catalog}:{self.dataset}:{self.resource}"
        return f"{self.dataset}:{self.resource}"

    @property
    def full_uri(self) -> str:
        if self.catalog:
            return f"datamesh://{self.catalog}/{self.dataset}/{self.resource}"
        return f"datamesh://{self.dataset}/{self.resource}"

@dataclass(frozen=True)
class ResourceDescriptor:
    """Value object describing a target resource to resolve."""
    raw_reference: str
    dataset: Optional[str] = None
    resource: Optional[str] = None
    format: Optional[str] = None  # parquet, csv, tsv, json, jsonl
    source_service: str = "unknown"  # local, github, kaggle, http, git

@dataclass(frozen=True)
class CacheEntryMetadata:
    """Metadata recorded for every cached resource."""
    key: str
    original_uri: str
    local_path: str
    format: str
    size_bytes: int
    cached_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    etag: Optional[str] = None
    sha256: Optional[str] = None
    source_service: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "original_uri": self.original_uri,
            "local_path": self.local_path,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "cached_at": self.cached_at,
            "etag": self.etag,
            "sha256": self.sha256,
            "source_service": self.source_service,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CacheEntryMetadata:
        return cls(
            key=data["key"],
            original_uri=data["original_uri"],
            local_path=data["local_path"],
            format=data.get("format", "csv"),
            size_bytes=data.get("size_bytes", 0),
            cached_at=data.get("cached_at", datetime.now(timezone.utc).isoformat()),
            etag=data.get("etag"),
            sha256=data.get("sha256"),
            source_service=data.get("source_service", "unknown"),
        )

@dataclass(frozen=True)
class ResolvedResource:
    """Represents a resolved and downloaded physical resource ready for DuckDB execution."""
    descriptor: ResourceDescriptor
    local_path: Path
    format: str  # parquet, csv, tsv, json, jsonl
    is_cached: bool = False
    metadata: Optional[CacheEntryMetadata] = None
