from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Optional
from datamesh.domain.models import (
    WellKnownDiscovery,
    CatalogMetadata,
    AuthConfiguration,
    KeycloakAuth,
    APIKeyAuth,
)
from datamesh.ports.harvester import WellKnownResolverPort

logger = logging.getLogger("datamesh.discovery.well_known")


class WellKnownResolverAdapter(WellKnownResolverPort):
    """Discovers catalog endpoints and auth requirements via /.well-known/datamesh.json or active probing."""

    def __init__(self, timeout: int = 5):
        self._timeout = timeout

    def fetch_well_known(self, target_url: str) -> Optional[WellKnownDiscovery]:
        parsed = urllib.parse.urlparse(target_url.strip())
        origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else target_url.strip().rstrip("/")
        base_path = parsed.path.rstrip("/")

        candidate_urls = [
            f"{origin}/.well-known/datamesh.json",
            f"{origin}/.well-known/okf.json",
        ]
        if base_path and base_path != "/":
            candidate_urls.insert(0, f"{origin}{base_path}/.well-known/datamesh.json")

        headers = {
            "Accept": "application/json",
            "User-Agent": "datamesh-sdk/0.2.0 (WellKnownDiscovery)",
        }

        # 1. Try explicit well-known URLs
        for url in candidate_urls:
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        if isinstance(data, dict) and ("catalog" in data or "schema_version" in data):
                            logger.info("Found standardized well-known discovery at %s", url)
                            return WellKnownDiscovery.from_dict(data)
            except Exception as e:
                logger.debug("Well-known probe failed at %s: %s", url, e)

        # 2. Heuristic probe for CKAN API status if no well-known document is published
        ckan_disc = self._probe_ckan_fallback(origin, base_path, headers)
        if ckan_disc is not None:
            return ckan_disc

        # 3. Heuristic probe for OKF / llms.txt sovereign catalog
        return self._probe_llmstxt_fallback(origin, base_path, headers)

    def _probe_llmstxt_fallback(
        self,
        origin: str,
        base_path: str,
        headers: dict,
    ) -> Optional[WellKnownDiscovery]:
        llms_candidates = []
        if base_path and base_path != "/":
            if base_path.endswith("/llms.txt") or base_path.endswith("/llm.txt") or base_path.endswith("/llms-full.txt"):
                llms_candidates.append(f"{origin}{base_path}")
            else:
                llms_candidates.append(f"{origin}{base_path}/llms.txt")
        llms_candidates.extend([
            f"{origin}/llms.txt",
            f"{origin}/llms-full.txt",
        ])

        text_headers = {
            "Accept": "text/plain, text/markdown, */*",
            "User-Agent": headers.get("User-Agent", "datamesh-sdk/0.2.2 (WellKnownDiscovery)"),
        }

        for probe_url in llms_candidates:
            req = urllib.request.Request(probe_url, headers=text_headers)
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    if resp.status == 200:
                        raw_text = resp.read().decode("utf-8", errors="replace")
                        if "# " in raw_text and ("- [" in raw_text or "* [" in raw_text):
                            site_title = origin
                            site_desc = "Discovered via OKF / llms.txt sovereign catalog probe"
                            for line in raw_text.splitlines():
                                ls = line.strip()
                                if ls.startswith("# ") and site_title == origin:
                                    site_title = ls[2:].strip()
                                elif ls.startswith("> ") and site_desc.startswith("Discovered via"):
                                    site_desc = ls[2:].strip()
                            parsed_origin = urllib.parse.urlparse(origin)
                            slug_name = (parsed_origin.netloc or site_title).lower().replace(".", "_").replace(" ", "_")
                            return WellKnownDiscovery(
                                schema_version="0.2.2",
                                catalog=CatalogMetadata(
                                    name=slug_name,
                                    title=site_title,
                                    catalog_url=probe_url,
                                    catalog_type="okf",
                                    api_endpoint=probe_url,
                                    description=site_desc,
                                ),
                                auth=AuthConfiguration(
                                    auth_type="none",
                                    required=False,
                                ),
                                capabilities={
                                    "search": True,
                                    "sql_query": True,
                                    "knowledge_graph": True,
                                    "harvesting": True,
                                },
                            )
            except Exception:
                pass
        return None

    def _probe_ckan_fallback(
        self,
        origin: str,
        base_path: str,
        headers: dict
    ) -> Optional[WellKnownDiscovery]:
        ckan_candidates = [
            f"{origin}{base_path}/api/3/action/status_show",
            f"{origin}/api/3/action/status_show",
            f"{origin}{base_path}/status_show",
        ]

        for probe_url in ckan_candidates:
            req = urllib.request.Request(probe_url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    if resp.status == 200:
                        body = json.loads(resp.read().decode("utf-8"))
                        if isinstance(body, dict) and body.get("success"):
                            site_title = body.get("result", {}).get("site_title", origin)
                            api_endpoint = probe_url.rsplit("/status_show", 1)[0]
                            catalog_url = origin if not base_path or base_path.startswith("/api") else f"{origin}{base_path}"
                            logger.info("Discovered legacy CKAN portal at %s", api_endpoint)

                            # Probe Keycloak / OIDC redirect
                            keycloak_auth = self._probe_keycloak_redirect(origin, headers)
                            auth_type = "keycloak" if keycloak_auth else "none"
                            auth_required = bool(keycloak_auth)

                            return WellKnownDiscovery(
                                schema_version="0.2.0",
                                catalog=CatalogMetadata(
                                    name=site_title.lower().replace(" ", "_"),
                                    title=site_title,
                                    catalog_url=catalog_url,
                                    catalog_type="ckan",
                                    api_endpoint=api_endpoint,
                                    description="Discovered via CKAN Action API probe",
                                ),
                                auth=AuthConfiguration(
                                    auth_type=auth_type,
                                    required=auth_required,
                                    keycloak=keycloak_auth,
                                    api_key=APIKeyAuth(header_name="X-CKAN-API-Key"),
                                ),
                                capabilities={
                                    "search": True,
                                    "sql_query": True,
                                    "datastore": True,
                                    "harvesting": True,
                                },
                            )
            except Exception:
                pass

        return None

    def _probe_keycloak_redirect(self, origin: str, headers: dict) -> Optional[KeycloakAuth]:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        for path in ("/oidc/login?came_from=/", "/user/login"):
            url = f"{origin}{path}"
            req = urllib.request.Request(url, headers=headers)
            try:
                opener.open(req, timeout=self._timeout)
            except urllib.error.HTTPError as he:
                redirect_url = he.headers.get("Location")
                if redirect_url and ("protocol/openid-connect" in redirect_url or "realms/" in redirect_url):
                    parsed = urllib.parse.urlparse(redirect_url)
                    query = urllib.parse.parse_qs(parsed.query)
                    client_id = query.get("client_id", [None])[0]
                    raw_scopes = query.get("scope", ["openid profile"])[0]
                    scopes = [s.strip() for s in raw_scopes.replace("+", " ").split()]

                    base_realm = redirect_url.split("/protocol/openid-connect")[0]
                    logger.info("Auto-discovered Keycloak realm at %s (client_id: %s)", base_realm, client_id)
                    return KeycloakAuth(
                        realm_url=base_realm,
                        token_endpoint=f"{base_realm}/protocol/openid-connect/token",
                        authorization_endpoint=f"{base_realm}/protocol/openid-connect/auth",
                        client_id=client_id,
                        scopes_supported=tuple(scopes),
                    )
            except Exception:
                pass
        return None
