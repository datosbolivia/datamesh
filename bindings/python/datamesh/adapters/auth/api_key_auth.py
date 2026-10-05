from __future__ import annotations

from typing import Dict, Optional
from datamesh.ports.harvester import AuthProviderPort


class NoAuthAdapter(AuthProviderPort):
    """Null auth provider for publicly open catalogs."""

    def get_auth_headers(self) -> Dict[str, str]:
        return {}

    def get_auth_type(self) -> str:
        return "none"


class APIKeyAuthAdapter(AuthProviderPort):
    """Auth provider using static tokens, API keys, or pre-shared bearer tokens."""

    def __init__(
        self,
        token: str,
        header_name: str = "X-CKAN-API-Key",
        prefix: str = ""
    ):
        self._token = token.strip()
        self._header_name = header_name.strip()
        self._prefix = prefix.strip()

    def get_auth_headers(self) -> Dict[str, str]:
        if not self._token:
            return {}
        val = f"{self._prefix} {self._token}".strip() if self._prefix else self._token
        return {self._header_name: val}

    def get_auth_type(self) -> str:
        return "api_key"


class BearerTokenAuthAdapter(AuthProviderPort):
    """Auth provider injecting Authorization: Bearer <token>."""

    def __init__(self, token: str):
        self._token = token.strip()

    def get_auth_headers(self) -> Dict[str, str]:
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token}"}

    def get_auth_type(self) -> str:
        return "bearer"
