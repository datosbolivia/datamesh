"""Adaptador de almacenamiento S3 / MinIO Aistor para DataMesh SDK.

Soporta buckets, prefijos de repositorio, subida, descarga y operaciones
idempotentes sobre infraestructura compatible con AWS S3 / MinIO.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import subprocess
import urllib.parse
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Set, Union

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def leer_env(nombre: str, default: Optional[str] = None, requerido: bool = True) -> str:
    valor = os.environ.get(nombre, "")
    if valor.strip():
        return valor.strip()
    if default is not None:
        return default
    if requerido:
        raise RuntimeError(f"Falta la variable de entorno {nombre}")
    return ""


def leer_env_alternativa(nombres: List[str], default: Optional[str] = None, requerido: bool = True) -> str:
    for nombre in nombres:
        valor = os.environ.get(nombre, "")
        if valor.strip():
            return valor.strip()
    if default is not None:
        return default
    if requerido:
        raise RuntimeError(
            "Falta una de estas variables de entorno: " + ", ".join(nombres)
        )
    return ""


class S3StorageAdapter:
    """Adaptador de operaciones S3 para Data Lake institucional (Aistor / MinIO)."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        bucket: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: Optional[str] = None,
        client: Optional[Any] = None,
    ):
        self._explicit_endpoint = endpoint_url
        self._explicit_bucket = bucket
        self._explicit_access_key = access_key
        self._explicit_secret_key = secret_key
        self._explicit_region = region
        self._client = client

    def get_config(self, url: Optional[str] = None, bucket: Optional[str] = None) -> Dict[str, str]:
        endpoint = (
            url
            or self._explicit_endpoint
            or leer_env_alternativa(["AISTOR_ENDPOINT", "S3_ENDPOINT", "DATAMESH_S3_ENDPOINT"], default="http://aistor:9000")
        )
        bkt = (
            bucket
            or self._explicit_bucket
            or leer_env_alternativa(["AISTOR_BUCKET", "S3_BUCKET", "DATAMESH_S3_BUCKET"], default="lake")
        )
        acc_key = (
            self._explicit_access_key
            or leer_env_alternativa(["AISTOR_ACCESS_KEY", "S3_ACCESS_KEY", "AWS_ACCESS_KEY_ID", "DATAMESH_S3_ACCESS_KEY"], requerido=False)
        )
        sec_key = (
            self._explicit_secret_key
            or leer_env_alternativa(["AISTOR_SECRET_KEY", "S3_SECRET_KEY", "AWS_SECRET_ACCESS_KEY", "DATAMESH_S3_SECRET_KEY"], requerido=False)
        )
        reg = (
            self._explicit_region
            or leer_env_alternativa(["AISTOR_REGION", "S3_REGION", "AWS_DEFAULT_REGION", "DATAMESH_S3_REGION"], default="us-east-1")
        )
        return {
            "endpoint_url": endpoint,
            "bucket": bkt,
            "access_key": acc_key,
            "secret_key": sec_key,
            "region": reg,
        }

    def get_client(self, config: Optional[Dict[str, str]] = None, url: Optional[str] = None, bucket: Optional[str] = None) -> Any:
        if self._client is not None and not url and not bucket:
            return self._client

        cfg = config or self.get_config(url=url, bucket=bucket)
        if not cfg.get("access_key") or not cfg.get("secret_key"):
            raise RuntimeError(
                "Falta una de estas variables de entorno: AISTOR_ACCESS_KEY, S3_ACCESS_KEY, AWS_ACCESS_KEY_ID"
            )

        return boto3.client(
            "s3",
            endpoint_url=cfg["endpoint_url"],
            aws_access_key_id=cfg["access_key"],
            aws_secret_access_key=cfg["secret_key"],
            region_name=cfg["region"],
            config=Config(signature_version="s3v4"),
        )

    def resolve_target(self, bucket: Optional[str] = None, s3_client: Optional[Any] = None) -> tuple[str, Any]:
        cfg = self.get_config(bucket=bucket)
        bkt = bucket or cfg["bucket"]
        client = s3_client or (self._client if self._client is not None else self.get_client(config=cfg))
        return bkt, client

    @staticmethod
    def repo_desde_git() -> str:
        try:
            resultado = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                text=True,
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except FileNotFoundError:
            return ""
        if resultado.returncode != 0:
            return ""
        path = urllib.parse.urlparse(resultado.stdout.strip()).path
        return path.strip("/").removesuffix(".git")

    def repo_prefix(self, subcarpeta: str = "", repo_name: Optional[str] = None) -> str:
        name = repo_name or leer_env_alternativa(
            ["FORGEJO_REPOSITORY", "GITHUB_REPOSITORY", "REPO_NAME"],
            requerido=False,
        )
        name = name or self.repo_desde_git() or Path.cwd().name
        if not name:
            raise RuntimeError(
                "No se pudo determinar el nombre del repositorio. "
                "Usa repo_name o define REPO_NAME."
            )
        partes = [name.strip("/")]
        if subcarpeta:
            partes.append(subcarpeta.strip("/"))
        return "/".join(p for p in partes if p)

    def listar_objetos(
        self,
        prefix: str = "",
        bucket: Optional[str] = None,
        s3: Optional[Any] = None,
        fecha_desc: bool = False,
    ) -> Iterator[Dict[str, Any]]:
        bkt, client = self.resolve_target(bucket=bucket, s3_client=s3)
        paginator = client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bkt, Prefix=prefix)
        objetos = [
            obj
            for page in pages
            for obj in page.get("Contents", [])
        ]
        if fecha_desc:
            objetos = sorted(
                objetos,
                key=lambda obj: obj["LastModified"],
                reverse=True,
            )
        yield from objetos

    def listar_objetos_recientes(
        self,
        prefix: str = "",
        limite: Optional[int] = 10,
        bucket: Optional[str] = None,
        s3: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        objs = list(self.listar_objetos(prefix=prefix, bucket=bucket, s3=s3, fecha_desc=True))
        if limite is None:
            return objs
        return objs[:limite]

    def ultimo_objeto(
        self,
        prefix: str = "",
        bucket: Optional[str] = None,
        s3: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        recientes = self.listar_objetos_recientes(prefix=prefix, limite=1, bucket=bucket, s3=s3)
        return recientes[0] if recientes else None

    def listar_claves(
        self,
        prefix: str = "",
        bucket: Optional[str] = None,
        s3: Optional[Any] = None,
    ) -> Iterator[str]:
        for obj in self.listar_objetos(prefix=prefix, bucket=bucket, s3=s3):
            yield obj["Key"]

    def listar_nombres(
        self,
        prefix: str = "",
        bucket: Optional[str] = None,
        s3: Optional[Any] = None,
    ) -> Set[str]:
        return {
            PurePosixPath(key).name
            for key in self.listar_claves(prefix=prefix, bucket=bucket, s3=s3)
        }

    def existe_objeto(
        self,
        key: str,
        bucket: Optional[str] = None,
        s3: Optional[Any] = None,
    ) -> bool:
        bkt, client = self.resolve_target(bucket=bucket, s3_client=s3)
        try:
            client.head_object(Bucket=bkt, Key=key)
            return True
        except ClientError as exc:
            codigo = exc.response.get("Error", {}).get("Code")
            if codigo in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def leer_objeto(
        self,
        key: str,
        bucket: Optional[str] = None,
        s3: Optional[Any] = None,
    ) -> bytes:
        bkt, client = self.resolve_target(bucket=bucket, s3_client=s3)
        response = client.get_object(Bucket=bkt, Key=key)
        return response["Body"].read()

    def descargar_objeto(
        self,
        key: str,
        path: Union[str, Path],
        bucket: Optional[str] = None,
        s3: Optional[Any] = None,
    ) -> Path:
        bkt, client = self.resolve_target(bucket=bucket, s3_client=s3)
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(bkt, key, str(target_path))
        return target_path

    def escribir_objeto(
        self,
        key: str,
        body: Union[bytes, str, BinaryIO],
        bucket: Optional[str] = None,
        s3: Optional[Any] = None,
    ) -> str:
        bkt, client = self.resolve_target(bucket=bucket, s3_client=s3)
        client.put_object(Bucket=bkt, Key=key, Body=body)
        return f"s3://{bkt}/{key}"

    def eliminar_objeto(
        self,
        key: str,
        bucket: Optional[str] = None,
        s3: Optional[Any] = None,
    ) -> str:
        bkt, client = self.resolve_target(bucket=bucket, s3_client=s3)
        client.delete_object(Bucket=bkt, Key=key)
        return f"s3://{bkt}/{key}"

    def subir_archivo(
        self,
        path: Union[str, Path],
        key: str,
        bucket: Optional[str] = None,
        s3: Optional[Any] = None,
    ) -> str:
        bkt, client = self.resolve_target(bucket=bucket, s3_client=s3)
        client.upload_file(str(path), bkt, key)
        return f"s3://{bkt}/{key}"
