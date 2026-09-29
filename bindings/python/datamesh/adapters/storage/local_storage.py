from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, BinaryIO, Dict, Optional

from datamesh.domain.models import CacheEntryMetadata, StorageConfig
from datamesh.ports.storage import StoragePort

class LocalStorageManager(StoragePort):
    """
    Implements StoragePort managing the generic configuration directory ~/datamesh/
    and temporal cache storage directory ~/datamesh/cache/.
    """

    def __init__(self, config: Optional[StorageConfig] = None):
        self._config = config or StorageConfig.default()
        self._ensure_directories()
        self._metadata_path = self._config.cache_dir / "metadata.json"
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._load_metadata()

    @property
    def config(self) -> StorageConfig:
        return self._config

    def _ensure_directories(self) -> None:
        """Creates ~/datamesh and ~/datamesh/cache if they do not exist."""
        try:
            self._config.home_dir.mkdir(parents=True, exist_ok=True)
            self._config.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            # If filesystem is read-only in sandbox or test, fallback to /tmp/datamesh
            fallback_home = Path("/tmp/datamesh")
            self._config = StorageConfig(
                home_dir=fallback_home,
                cache_dir=fallback_home / "cache",
                config_file=fallback_home / "config.yaml",
            )
            self._config.home_dir.mkdir(parents=True, exist_ok=True)
            self._config.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_dir(self) -> Path:
        return self._config.cache_dir

    def _hash_key(self, key_or_uri: str) -> str:
        return hashlib.sha256(key_or_uri.encode("utf-8")).hexdigest()[:24]

    def _load_metadata(self) -> None:
        if self._metadata_path.exists():
            try:
                with open(self._metadata_path, "r", encoding="utf-8") as f:
                    self._metadata_cache = json.load(f)
            except Exception:
                self._metadata_cache = {}
        else:
            self._metadata_cache = {}

    def _save_metadata(self) -> None:
        try:
            temp_file = tempfile.NamedTemporaryFile("w", dir=self._config.cache_dir, delete=False, encoding="utf-8")
            json.dump(self._metadata_cache, temp_file, indent=2, ensure_ascii=False)
            temp_file.flush()
            temp_file.close()
            os.replace(temp_file.name, self._metadata_path)
        except Exception:
            pass

    def is_cached(self, key_or_uri: str) -> bool:
        k = self._hash_key(key_or_uri)
        if k in self._metadata_cache:
            entry = self._metadata_cache[k]
            p = Path(entry.get("local_path", ""))
            return p.exists() and p.is_file() and p.stat().st_size > 0
        return False

    def get_cached_path(self, key_or_uri: str) -> Optional[Path]:
        k = self._hash_key(key_or_uri)
        if k in self._metadata_cache:
            entry = self._metadata_cache[k]
            p = Path(entry.get("local_path", ""))
            if p.exists() and p.is_file() and p.stat().st_size > 0:
                return p
        return None

    def save(
        self,
        key_or_uri: str,
        content: bytes | str | BinaryIO,
        extension: Optional[str] = None,
        source_service: str = "unknown",
        etag: Optional[str] = None,
    ) -> Path:
        k = self._hash_key(key_or_uri)
        ext = extension or ".bin"
        if not ext.startswith("."):
            ext = f".{ext}"
        
        target_path = self._config.cache_dir / f"{k}{ext}"
        sha = hashlib.sha256()

        temp_file = tempfile.NamedTemporaryFile("wb", dir=self._config.cache_dir, delete=False)
        try:
            if isinstance(content, str):
                data = content.encode("utf-8")
                temp_file.write(data)
                sha.update(data)
            elif isinstance(content, bytes):
                temp_file.write(content)
                sha.update(content)
            else:
                # Binary stream
                while chunk := content.read(65536):
                    temp_file.write(chunk)
                    sha.update(chunk)
            temp_file.flush()
            temp_file.close()
            os.replace(temp_file.name, target_path)
        except Exception:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)
            raise

        size = target_path.stat().st_size
        fmt = ext.lstrip(".").lower()
        meta = CacheEntryMetadata(
            key=k,
            original_uri=key_or_uri,
            local_path=str(target_path.resolve()),
            format=fmt,
            size_bytes=size,
            cached_at=datetime.now(timezone.utc).isoformat(),
            etag=etag,
            sha256=sha.hexdigest(),
            source_service=source_service,
        )
        self._metadata_cache[k] = meta.to_dict()
        self._save_metadata()
        return target_path

    def store_file(
        self,
        source_path: Path | str,
        key_or_uri: str,
        source_service: str = "unknown",
        move: bool = False,
    ) -> Path:
        src = Path(source_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Source file {src} does not exist")

        k = self._hash_key(key_or_uri)
        ext = src.suffix or ".bin"
        target_path = self._config.cache_dir / f"{k}{ext}"

        if move:
            shutil.move(src, target_path)
        else:
            shutil.copy2(src, target_path)

        sha = hashlib.sha256()
        with open(target_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)

        meta = CacheEntryMetadata(
            key=k,
            original_uri=key_or_uri,
            local_path=str(target_path.resolve()),
            format=ext.lstrip(".").lower(),
            size_bytes=target_path.stat().st_size,
            cached_at=datetime.now(timezone.utc).isoformat(),
            sha256=sha.hexdigest(),
            source_service=source_service,
        )
        self._metadata_cache[k] = meta.to_dict()
        self._save_metadata()
        return target_path

    def get_metadata(self, key_or_uri: str) -> Optional[CacheEntryMetadata]:
        k = self._hash_key(key_or_uri)
        data = self._metadata_cache.get(k)
        if data:
            return CacheEntryMetadata.from_dict(data)
        return None

    def evict(self, key_or_uri: str) -> bool:
        k = self._hash_key(key_or_uri)
        if k in self._metadata_cache:
            entry = self._metadata_cache.pop(k)
            p = Path(entry.get("local_path", ""))
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
            self._save_metadata()
            return True
        return False

    def clear(self, older_than_seconds: Optional[int] = None) -> int:
        now = datetime.now(timezone.utc).timestamp()
        removed = 0
        keys_to_remove = []

        for k, entry in list(self._metadata_cache.items()):
            should_remove = False
            if older_than_seconds is not None:
                cached_time_str = entry.get("cached_at")
                if cached_time_str:
                    try:
                        cached_time = datetime.fromisoformat(cached_time_str).timestamp()
                        if (now - cached_time) > older_than_seconds:
                            should_remove = True
                    except Exception:
                        should_remove = True
            else:
                should_remove = True

            if should_remove:
                keys_to_remove.append(k)
                p = Path(entry.get("local_path", ""))
                if p.exists():
                    try:
                        p.unlink()
                        removed += 1
                    except Exception:
                        pass

        for k in keys_to_remove:
            self._metadata_cache.pop(k, None)

        self._save_metadata()
        return removed
