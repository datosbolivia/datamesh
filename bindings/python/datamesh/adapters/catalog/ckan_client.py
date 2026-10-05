from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from datamesh.domain.models import CKANPackage, CKANResource
from datamesh.ports.harvester import CKANClientPort, AuthProviderPort

logger = logging.getLogger("datamesh.catalog.ckan_client")


class CKANClientAdapter(CKANClientPort):
    """Client for CKAN Action API v3 with authentication support."""

    def __init__(self, timeout: int = 15):
        self._timeout = timeout

    def _normalize_endpoint(self, base_url: str) -> str:
        url = base_url.strip().rstrip("/")
        if not url.endswith("/api/3/action"):
            if "/api/3" in url:
                url = url.split("/api/3")[0] + "/api/3/action"
            else:
                url = f"{url}/api/3/action"
        return url

    def _make_request(
        self,
        url: str,
        auth_provider: Optional[AuthProviderPort] = None,
        data: Optional[Dict[str, Any]] = None,
        method: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "datamesh-sdk/0.2.0 (CKANClient)",
        }
        if auth_provider:
            headers.update(auth_provider.get_auth_headers())

        body_bytes = None
        if data is not None:
            headers["Content-Type"] = "application/json"
            body_bytes = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8"))
                    if isinstance(payload, dict) and payload.get("success"):
                        return payload.get("result")
                    else:
                        logger.warning("CKAN API returned success=false from %s: %s", url, payload.get("error"))
        except urllib.error.HTTPError as he:
            # If POST failed with 400/405, and GET hasn't been tried, attempt fallback
            if method != "GET" and data is not None and he.code in (400, 404, 405):
                params_str = urllib.parse.urlencode(data)
                fallback_url = f"{url}?{params_str}" if "?" not in url else f"{url}&{params_str}"
                return self._make_request(fallback_url, auth_provider, data=None, method="GET")
            logger.error("CKAN request failed for %s (HTTP %d): %s", url, he.code, he)
        except Exception as e:
            logger.error("CKAN request failed for %s: %s", url, e)
        return None

    def search_packages(
        self,
        base_url: str,
        query: str = "",
        offset: int = 0,
        limit: int = 100,
        auth_provider: Optional[AuthProviderPort] = None
    ) -> Tuple[List[CKANPackage], int]:
        endpoint = self._normalize_endpoint(base_url)
        params = {"rows": limit, "start": offset}
        if query:
            params["q"] = query

        url = f"{endpoint}/package_search"
        # CKAN 2.11+ requires POST for JSON Action API; older CKANs accept GET
        result = self._make_request(url, auth_provider, data=params, method="POST")
        if not result:
            return [], 0

        count = int(result.get("count", 0))
        results = result.get("results", [])

        packages = [self._parse_package(pkg) for pkg in results if isinstance(pkg, dict)]
        return packages, count

    def get_package(
        self,
        base_url: str,
        package_id: str,
        auth_provider: Optional[AuthProviderPort] = None
    ) -> Optional[CKANPackage]:
        endpoint = self._normalize_endpoint(base_url)
        url = f"{endpoint}/package_show"
        result = self._make_request(url, auth_provider, data={"id": package_id}, method="POST")
        if not result or not isinstance(result, dict):
            return None
        return self._parse_package(result)

    def get_datastore_schema(
        self,
        base_url: str,
        resource_id: str,
        auth_provider: Optional[AuthProviderPort] = None
    ) -> List[Dict[str, str]]:
        endpoint = self._normalize_endpoint(base_url)
        url = f"{endpoint}/datastore_search"
        result = self._make_request(url, auth_provider, data={"resource_id": resource_id, "limit": 1}, method="POST")
        if not result or not isinstance(result, dict):
            return []

        fields = result.get("fields", [])
        out = []
        for f in fields:
            if isinstance(f, dict) and "id" in f:
                field_id = f["id"]
                if field_id == "_id":
                    continue
                out.append({"name": field_id, "type": self._map_ckan_type(f.get("type", "text"))})
        return out

    def _parse_package(self, data: Dict[str, Any]) -> CKANPackage:
        pkg_id = data.get("id", "")
        name = data.get("name", "")
        title = data.get("title") or name
        notes = data.get("notes")
        url = data.get("url")
        version = data.get("version")

        org = data.get("organization")
        org_title = org.get("title") if isinstance(org, dict) else None

        tags = tuple(t.get("name") for t in data.get("tags", []) if isinstance(t, dict) and "name" in t)

        extras_dict: Dict[str, Any] = {}
        for ex in data.get("extras", []):
            if isinstance(ex, dict) and "key" in ex and "value" in ex:
                extras_dict[ex["key"]] = ex["value"]

        resources_list = []
        for r in data.get("resources", []):
            if isinstance(r, dict):
                r_id = r.get("id", "")
                r_name = r.get("name") or r.get("description") or f"resource_{r_id[:8]}"
                r_url = r.get("url", "")
                r_fmt = (r.get("format") or "csv").strip().lower()
                r_desc = r.get("description")
                r_mime = r.get("mimetype")
                r_size = r.get("size")
                r_datastore = bool(r.get("datastore_active", False))

                resources_list.append(
                    CKANResource(
                        id=r_id,
                        name=r_name,
                        url=r_url,
                        format=r_fmt,
                        description=r_desc,
                        mimetype=r_mime,
                        size=int(r_size) if r_size is not None and str(r_size).isdigit() else None,
                        datastore_active=r_datastore,
                    )
                )

        return CKANPackage(
            id=pkg_id,
            name=name,
            title=title,
            notes=notes,
            url=url,
            version=version,
            organization_title=org_title,
            tags=tags,
            extras=extras_dict,
            resources=tuple(resources_list),
        )

    def _map_ckan_type(self, ckan_type: str) -> str:
        t = ckan_type.lower()
        if t in ("int", "int4", "int8", "integer"):
            return "integer"
        elif t in ("float", "numeric", "real", "double precision", "money"):
            return "number"
        elif t in ("bool", "boolean"):
            return "boolean"
        elif t in ("date",):
            return "date"
        elif t in ("timestamp", "timestamptz"):
            return "datetime"
        return "string"
