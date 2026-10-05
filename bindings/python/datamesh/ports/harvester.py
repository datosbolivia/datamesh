from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from datamesh.domain.models import WellKnownDiscovery, CKANPackage, CKANHarvestResult


class AuthProviderPort(ABC):
    """Outbound port for generating HTTP headers for authenticated requests."""

    @abstractmethod
    def get_auth_headers(self) -> Dict[str, str]:
        """Returns header dictionary to inject into outgoing requests."""
        raise NotImplementedError

    @abstractmethod
    def get_auth_type(self) -> str:
        """Returns the auth type identifier."""
        raise NotImplementedError


class WellKnownResolverPort(ABC):
    """Outbound port for fetching and parsing /.well-known/datamesh.json discovery documents."""

    @abstractmethod
    def fetch_well_known(self, target_url: str) -> Optional[WellKnownDiscovery]:
        """Attempts to fetch and parse /.well-known/datamesh.json or /.well-known/okf.json."""
        raise NotImplementedError


class CKANClientPort(ABC):
    """Outbound port for querying CKAN Action API v3."""

    @abstractmethod
    def search_packages(
        self,
        base_url: str,
        query: str = "",
        offset: int = 0,
        limit: int = 100,
        auth_provider: Optional[AuthProviderPort] = None
    ) -> Tuple[List[CKANPackage], int]:
        """Searches packages in CKAN, returning package list and total count."""
        raise NotImplementedError

    @abstractmethod
    def get_package(
        self,
        base_url: str,
        package_id: str,
        auth_provider: Optional[AuthProviderPort] = None
    ) -> Optional[CKANPackage]:
        """Fetches a single package by id or slug."""
        raise NotImplementedError

    @abstractmethod
    def get_datastore_schema(
        self,
        base_url: str,
        resource_id: str,
        auth_provider: Optional[AuthProviderPort] = None
    ) -> List[Dict[str, str]]:
        """Queries datastore_search limit=1 to inspect field names and types."""
        raise NotImplementedError
