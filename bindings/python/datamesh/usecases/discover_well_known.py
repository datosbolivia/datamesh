from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from datamesh.domain.models import WellKnownDiscovery
from datamesh.ports.harvester import WellKnownResolverPort, AuthProviderPort
from datamesh.adapters.auth.api_key_auth import NoAuthAdapter, APIKeyAuthAdapter, BearerTokenAuthAdapter
from datamesh.adapters.auth.keycloak_auth import KeycloakAuthAdapter

logger = logging.getLogger("datamesh.usecases.discover_well_known")


class DiscoverWellKnownUseCase:
    """Use case for discovering catalog capabilities, metadata, and authentication specifications."""

    def __init__(self, resolver: WellKnownResolverPort):
        self._resolver = resolver

    def execute(self, target_url: str) -> Optional[WellKnownDiscovery]:
        if not target_url.startswith(("http://", "https://")):
            target_url = f"https://{target_url}"
        return self._resolver.fetch_well_known(target_url)

    def create_auth_provider(
        self,
        discovery: Optional[WellKnownDiscovery],
        token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> AuthProviderPort:
        """Selects and instantiates the optimal AuthProvider based on discovery document and credentials."""
        if not discovery:
            if token:
                return APIKeyAuthAdapter(token)
            return NoAuthAdapter()

        auth_cfg = discovery.auth

        # 1. Keycloak / OAuth2 Client Credentials
        if auth_cfg.auth_type == "keycloak" and auth_cfg.keycloak:
            kc = auth_cfg.keycloak
            cid = client_id or kc.client_id
            if cid and client_secret:
                return KeycloakAuthAdapter(
                    token_endpoint=kc.token_endpoint,
                    client_id=cid,
                    client_secret=client_secret,
                    scope=scope or (kc.scopes_supported[0] if kc.scopes_supported else None),
                )
            elif token:
                return BearerTokenAuthAdapter(token)

        # 2. API Key / Token Header
        if token:
            header_name = "X-CKAN-API-Key"
            prefix = ""
            if auth_cfg.api_key:
                header_name = auth_cfg.api_key.header_name or header_name
                prefix = auth_cfg.api_key.prefix or prefix
            elif auth_cfg.auth_type == "bearer":
                header_name = "Authorization"
                prefix = "Bearer"

            return APIKeyAuthAdapter(token=token, header_name=header_name, prefix=prefix)

        return NoAuthAdapter()
