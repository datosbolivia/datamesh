from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple
from datamesh.ports.harvester import AuthProviderPort

logger = logging.getLogger("datamesh.auth.keycloak")


class KeycloakAuthAdapter(AuthProviderPort):
    """Auth provider implementing OAuth 2.0 / Keycloak Client Credentials flow.

    Fetches and caches JWT access tokens from Keycloak OpenID Connect token endpoint.
    """

    def __init__(
        self,
        token_endpoint: str,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = None,
        timeout: int = 10,
    ):
        self._token_endpoint = token_endpoint.strip()
        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._scope = scope
        self._timeout = timeout

        self._cached_token: Optional[str] = None
        self._token_expiry_timestamp: float = 0.0

    def get_auth_type(self) -> str:
        return "keycloak"

    def get_auth_headers(self) -> Dict[str, str]:
        token = self._get_access_token()
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def _get_access_token(self) -> Optional[str]:
        now = time.time()
        # Return cached token if valid for at least 30 more seconds
        if self._cached_token and now < (self._token_expiry_timestamp - 30):
            return self._cached_token

        token, expires_in = self._request_token()
        if token:
            self._cached_token = token
            self._token_expiry_timestamp = now + max(60, expires_in)
            return self._cached_token

        return self._cached_token

    def _request_token(self) -> Tuple[Optional[str], int]:
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        if self._scope:
            data["scope"] = self._scope

        payload = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(
            self._token_endpoint,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "datamesh-sdk/0.2.0 (KeycloakAuth)",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    access_token = body.get("access_token")
                    expires_in = int(body.get("expires_in", 300))
                    return access_token, expires_in
                else:
                    logger.error("Keycloak token error HTTP %d", resp.status)
        except Exception as e:
            logger.error("Failed to authenticate against Keycloak at %s: %s", self._token_endpoint, e)

        return None, 0
