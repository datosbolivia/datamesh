"""Adaptador para publicar y sincronizar paquetes Frictionless y OKF en portales CKAN."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

try:
    from ckanapi import CKANAPIError, NotAuthorized, NotFound, RemoteCKAN
    from requests.exceptions import RequestException
    _CKAN_AVAILABLE = True
except ImportError:
    CKANAPIError = Exception  # type: ignore
    NotAuthorized = Exception  # type: ignore
    NotFound = Exception  # type: ignore
    RemoteCKAN = Any  # type: ignore
    RequestException = Exception  # type: ignore
    _CKAN_AVAILABLE = False

from datamesh.domain.models import PublicationTargetResult
from datamesh.ports.publisher import PublisherPort

logger = logging.getLogger("datamesh.publishers.ckan")

DOWNLOAD_CHUNK_SIZE = 1024 * 1024


def tipo_campo_ckan(tipo: str) -> str:
    tipos = {
        "string": "text",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "datetime": "timestamp",
        "year": "int",
        "object": "json",
        "array": "json",
    }
    return tipos.get(tipo.lower(), tipo)


def campos_ckan(resource: Dict[str, Any]) -> List[Dict[str, Any]]:
    campos = []
    schema = resource.get("schema") or {}
    for field in schema.get("fields", []):
        campo: Dict[str, Any] = {
            "id": field["name"],
            "type": tipo_campo_ckan(field.get("type", "text")),
        }
        info: Dict[str, Any] = {}
        if field.get("title"):
            info["label"] = field["title"]
        if field.get("description"):
            info["notes"] = field["description"]
        if info:
            campo["info"] = info
        campos.append(campo)
    return campos


def normalizar_fecha(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, str):
        valor = valor.strip()
        if not valor:
            return None
        try:
            return datetime.fromisoformat(valor).isoformat()
        except ValueError:
            pass
        for patron in ("%Y-%m-%d", "%Y-%m", "%Y/%m/%d"):
            try:
                return datetime.strptime(valor, patron).date().isoformat()
            except ValueError:
                pass
        return valor
    return None


def estadisticas_archivo(path: Union[str, Path]) -> Dict[str, Any]:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha256.update(chunk)

    stat = os.stat(path)
    return {
        "size": stat.st_size,
        "hash": sha256.hexdigest(),
        "last_modified": int(stat.st_mtime),
    }


class CKANPublisherAdapter(PublisherPort):
    """
    Publishes and synchronizes DataPackages (datapackage.json/yaml) to CKAN portals.
    Preserves and synchronizes MEFP / Lakequery extended metadata (ADR 0012).
    """

    @property
    def name(self) -> str:
        return "ckan"

    def can_publish(self, target: str) -> bool:
        t = str(target).lower().strip()
        return t in ("ckan", "portal_ckan") or t.startswith(("ckan://", "http://", "https://"))

    def get_ckan_client(self, options: Optional[Dict[str, Any]] = None) -> RemoteCKAN:
        if not _CKAN_AVAILABLE:
            raise RuntimeError("ckanapi is required for CKAN publishing. Install with: pip install ckanapi requests")
        options = options or {}
        url = options.get("url") or options.get("ckan_url") or os.environ.get("CKAN_URL", "").strip()
        if not url:
            raise RuntimeError("Falta la URL de CKAN. Especifica options['url'] o CKAN_URL.")
        api_key = options.get("api_key") or options.get("token") or os.environ.get("CKAN_ACCESS_KEY", "").strip()
        return RemoteCKAN(url, apikey=api_key or None)

    def publish(
        self,
        dataset_dir_or_manifest: Path,
        manifest_data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> PublicationTargetResult:
        options = options or {}
        base_dir = dataset_dir_or_manifest if dataset_dir_or_manifest.is_dir() else dataset_dir_or_manifest.parent

        try:
            ckan = self.get_ckan_client(options)
            owner_org = options.get("owner_org") or manifest_data.get("owner_org") or os.environ.get("CKAN_OWNER_ORG", "")

            # 1. Leer README o index.md si existe
            readme_text = ""
            for rname in ("README.md", "index.md", "AYUDA.md"):
                rpath = base_dir / rname
                if rpath.is_file():
                    with open(rpath, "r", encoding="utf-8") as rf:
                        readme_text = rf.read().strip()
                    break

            pkg_metadata: Dict[str, Any] = {
                "name": manifest_data.get("name", "dataset"),
                "title": manifest_data.get("title", manifest_data.get("name", "dataset")),
                "notes": readme_text or manifest_data.get("description", ""),
                "version": manifest_data.get("version", ""),
            }
            if owner_org:
                pkg_metadata["owner_org"] = owner_org
            if manifest_data.get("homepage"):
                pkg_metadata["url"] = manifest_data["homepage"]
            if manifest_data.get("keywords"):
                pkg_metadata["tags"] = [{"name": tag} for tag in manifest_data["keywords"]]

            # Inject lineage into CKAN package extras
            extras = []
            if manifest_data.get("lineage"):
                lin = manifest_data["lineage"]
                extras.append({"key": "lineage", "value": json.dumps(lin) if isinstance(lin, (dict, list)) else str(lin)})
            if manifest_data.get("was_derived_from"):
                wdf = manifest_data["was_derived_from"]
                extras.append({"key": "was_derived_from", "value": json.dumps(wdf) if isinstance(wdf, (dict, list)) else str(wdf)})
            if manifest_data.get("sources"):
                srcs = manifest_data["sources"]
                extras.append({"key": "sources", "value": json.dumps(srcs) if isinstance(srcs, (dict, list)) else str(srcs)})
            if extras:
                pkg_metadata["extras"] = extras

            # 2. Crear o actualizar paquete en CKAN
            try:
                existing_pkg = ckan.action.package_show(id=pkg_metadata["name"])
                pkg_metadata["id"] = existing_pkg["id"]
                package = ckan.action.package_patch(**pkg_metadata)
            except (NotFound, Exception) as exc:
                if isinstance(exc, NotFound) or "not found" in str(exc).lower():
                    if not pkg_metadata.get("owner_org"):
                        raise RuntimeError("Falta owner_org para crear el paquete en CKAN. Defínelo en datapackage o CKAN_OWNER_ORG.")
                    package = ckan.action.package_create(**pkg_metadata)
                else:
                    raise

            # 3. Recursos existentes
            existentes = {r["name"]: r for r in package.get("resources", [])}
            archivos_map = options.get("files") or {}

            # 4. Sincronizar cada recurso declarado
            for res in manifest_data.get("resources", []):
                r_name = res.get("name", "")
                r_path_str = res.get("path", "")
                
                # Buscar archivo físico local
                archivo_fisico = None
                if r_name in archivos_map:
                    archivo_fisico = Path(archivos_map[r_name])
                elif (base_dir / r_path_str).is_file():
                    archivo_fisico = base_dir / r_path_str
                elif Path(r_path_str).is_file():
                    archivo_fisico = Path(r_path_str)

                meta_res: Dict[str, Any] = {
                    "package_id": package["id"],
                    "name": r_name,
                    "description": res.get("description", ""),
                    "format": res.get("format", "").upper() if res.get("format") else (archivo_fisico.suffix.lstrip(".").upper() if archivo_fisico else "CSV"),
                }

                # Metadatos MEFP
                for k in ("filas", "columnas", "resource_family_id", "frecuencia_actualizacion_dias"):
                    if res.get(k) is not None:
                        meta_res[k] = res[k]
                for k in ("fecha_minima", "fecha_maxima"):
                    val_fecha = normalizar_fecha(res.get(k))
                    if val_fecha:
                        meta_res[k] = val_fecha

                meta_res["x-policy"] = res.get("x-policy") or res.get("policy") or "allow_all"
                if res.get("lakequery"):
                    meta_res["lakequery"] = res["lakequery"]
                if res.get("schema"):
                    meta_res["schema"] = res["schema"]
                    if not meta_res.get("columnas") and "fields" in res["schema"]:
                        meta_res["columnas"] = len(res["schema"]["fields"])

                # Inject lineage / dependencies metadata into CKAN resource
                if res.get("lineage"):
                    meta_res["lineage"] = json.dumps(res["lineage"]) if isinstance(res["lineage"], (dict, list)) else str(res["lineage"])
                if res.get("was_derived_from"):
                    meta_res["was_derived_from"] = json.dumps(res["was_derived_from"]) if isinstance(res["was_derived_from"], (dict, list)) else str(res["was_derived_from"])
                if res.get("transformation"):
                    meta_res["transformation"] = res["transformation"]
                elif res.get("transformations"):
                    meta_res["transformation"] = json.dumps(res["transformations"]) if isinstance(res["transformations"], (dict, list)) else str(res["transformations"])
                if res.get("sources"):
                    meta_res["sources"] = json.dumps(res["sources"]) if isinstance(res["sources"], (dict, list)) else str(res["sources"])

                if archivo_fisico and archivo_fisico.is_file():
                    stats = estadisticas_archivo(archivo_fisico)
                    meta_res["size"] = stats["size"]
                    meta_res["hash"] = stats["hash"]

                # Patch o Create recurso
                if r_name in existentes:
                    meta_res["id"] = existentes[r_name]["id"]
                    if archivo_fisico and archivo_fisico.is_file():
                        with open(archivo_fisico, "rb") as upload_f:
                            ckan.action.resource_patch(upload={"upload": upload_f}, **meta_res)
                    else:
                        ckan.action.resource_patch(**meta_res)
                else:
                    if archivo_fisico and archivo_fisico.is_file():
                        with open(archivo_fisico, "rb") as upload_f:
                            ckan.action.resource_create(upload={"upload": upload_f}, **meta_res)
                    else:
                        meta_res["url"] = res.get("path", "")
                        ckan.action.resource_create(**meta_res)

            ckan_url_base = options.get("url") or os.environ.get("CKAN_URL", "")
            dataset_web_url = f"{ckan_url_base.rstrip('/')}/dataset/{package.get('name')}"

            return PublicationTargetResult(
                target="ckan",
                success=True,
                destination_uri=dataset_web_url,
                message=f"Paquete '{package.get('name')}' sincronizado exitosamente en CKAN con metadatos extendidos.",
            )

        except Exception as e:
            logger.error("Error al publicar en CKAN: %s", e)
            return PublicationTargetResult(
                target="ckan",
                success=False,
                destination_uri="",
                error=str(e),
                message=f"Fallo al publicar paquete en CKAN: {e}",
            )
