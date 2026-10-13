"""Adaptador para resolver y descargar recursos desde S3/MinIO/Aistor a la caché local."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, Optional

from datamesh.adapters.storage.s3_storage import S3StorageAdapter
from datamesh.domain.models import ResolvedResource, ResourceDescriptor
from datamesh.ports.resolver import ResourceAdapterPort
from datamesh.ports.storage import StoragePort

logger = logging.getLogger("datamesh.resolvers.s3")


class S3Adapter(ResourceAdapterPort):
    """
    Adapter for discovering, downloading, and caching resources from S3 / MinIO / Aistor.
    
    Supports:
    - s3://<bucket>/<key>
    - aistor://<bucket>/<key>
    - Contextual resolution for triad [mefp:]<dataset>:<resource> or [lake:]<dataset>:<resource>
    """

    def __init__(self, s3_storage: Optional[S3StorageAdapter] = None):
        self._s3 = s3_storage or S3StorageAdapter()

    @property
    def name(self) -> str:
        return "s3"

    def can_handle(self, uri_or_path: str, context: Optional[Dict[str, Any]] = None) -> bool:
        lower = str(uri_or_path).lower().strip()
        if lower.startswith(("s3://", "aistor://")):
            return True
        if context:
            source = str(context.get("source", "")).lower()
            catalog = str(context.get("catalog", "")).lower()
            if source in ("s3", "aistor", "minio") or catalog in ("mefp", "lake", "aistor"):
                return True
        return False

    def parse_s3_uri(self, uri: str) -> tuple[str, str]:
        """Extrae (bucket, key) desde s3://bucket/key o aistor://bucket/key."""
        clean = uri.strip()
        for scheme in ("s3://", "aistor://"):
            if clean.startswith(scheme):
                clean = clean[len(scheme):]
                break
        parts = clean.split("/", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        elif len(parts) == 1:
            cfg = self._s3.get_config()
            return cfg["bucket"], parts[0]
        return "", ""

    def resolve_and_fetch(
        self,
        uri_or_path: str,
        storage: StoragePort,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ResolvedResource]:
        context = context or {}
        bucket, key = self.parse_s3_uri(uri_or_path)

        if not key and context.get("dataset") and context.get("resource"):
            # Construct key from dataset/resource
            cfg = self._s3.get_config()
            bucket = cfg["bucket"]
            ds = str(context["dataset"])
            res = str(context["resource"])
            key = f"{ds}/{res}"

        if not bucket or not key:
            return None

        canonical_ref = f"s3://{bucket}/{key}"
        fmt = Path(key).suffix.lstrip(".").lower() or "csv"

        # Check if S3 object exists and fetch
        try:
            content_bytes = self._s3.leer_objeto(key=key, bucket=bucket)
        except Exception as exc:
            logger.warning("No se pudo obtener el objeto S3 %s: %s", canonical_ref, exc)
            # Offline or error fallback: return cached if exists
            if storage.is_cached(canonical_ref):
                cp = storage.get_cached_path(canonical_ref)
                if cp and cp.exists():
                    return ResolvedResource(
                        descriptor=ResourceDescriptor(
                            raw_reference=canonical_ref,
                            dataset=context.get("dataset"),
                            resource=context.get("resource"),
                            format=fmt,
                            source_service="s3",
                        ),
                        local_path=cp,
                        format=fmt,
                        is_cached=True,
                    )
            return None

        # Store atomically in local datamesh cache
        cached_path = storage.save(
            key_or_uri=canonical_ref,
            content=content_bytes,
            extension=f".{fmt}",
            source_service="s3",
        )

        return ResolvedResource(
            descriptor=ResourceDescriptor(
                raw_reference=canonical_ref,
                dataset=context.get("dataset"),
                resource=context.get("resource"),
                format=fmt,
                source_service="s3",
            ),
            local_path=cached_path,
            format=fmt,
            is_cached=True,
        )
