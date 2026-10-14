from __future__ import annotations


class DataMeshError(Exception):
    """Base exception for all DataMesh SDK operations."""
    pass


class AuthenticationRequiredError(DataMeshError):
    """Raised when an operation requires authentication that is missing, expired, or rejected (HTTP 401/403 or SSO redirect)."""
    pass


class InvalidContentTypeError(DataMeshError):
    """Raised when an endpoint returns unexpected content type (e.g. HTML when requesting tabular/binary data)."""
    pass


class CatalogConnectionError(DataMeshError):
    """Raised when connection to a catalog fails or returns a server error."""
    pass


class PolicyViolationError(DataMeshError):
    """Raised when access to a resource is restricted or rejected by policy (e.g. zero_microdata or deny)."""
    pass


class GoCoreUnavailableError(DataMeshError):
    """Raised when Go Core native authority is required but libdatamesh.so cannot be loaded."""
    pass
