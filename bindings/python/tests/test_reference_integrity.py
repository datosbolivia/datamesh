"""Reference integrity checks: the documented DataMesh SDK API must exist.

Covers AGENTS.md section 1: no orphan code, no phantom API. The exported
surface of `datamesh` and its CLI subcommands are normative; a documented
symbol that no longer resolves is a contract break for users.

Run: python3 -m pytest -q bindings/python/tests/test_reference_integrity.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

from datamesh import __all__ as DATAMESH_ALL

DOCUMENTED_API = [
    "discover",
    "discover_endpoint",
    "search",
    "get",
    "query",
    "sql",
    "resolve_resource",
    "get_engine",
    "validate",
    "publish",
    "align_semantics",
    "harvest_ckan",
    "lineage",
    "get_lineage",
    "create_datapackage",
    "link_concept",
    "explain_categories",
    "storage",
    "config",
    "run_server",
    "DataMeshRuntime",
    "StoragePort",
    "ResourceAdapterPort",
    "ConfigPort",
    "QueryEnginePort",
    "PublisherPort",
    "AuthProviderPort",
    "WellKnownResolverPort",
    "CKANClientPort",
    "LocalStorageManager",
    "FileConfigAdapter",
    "LocalFileAdapter",
    "GitHubAdapter",
    "KaggleAdapter",
    "HttpAdapter",
    "NoAuthAdapter",
    "APIKeyAuthAdapter",
    "BearerTokenAuthAdapter",
    "KeycloakAuthAdapter",
    "WellKnownResolverAdapter",
    "CKANClientAdapter",
    "DuckDBQueryEngine",
    "InMemTabularQueryEngine",
    "GoCoreQueryEngine",
    "ResolveAndCacheResourceUseCase",
    "DiscoverWellKnownUseCase",
    "HarvestCKANUseCase",
    "DatasetLineageUseCase",
]

DOCUMENTED_CLI_COMMANDS = [
    "catalog",
    "search",
    "get",
    "query",
    "sql",
    "publish",
    "align",
    "discover",
    "harvest-ckan",
    "package-create",
    "package-link",
    "package-explain",
    "lineage",
    "mcp-serve",
    "serve",
]


def test_all_exported_symbols_resolve() -> None:
    import datamesh as dm

    broken = [name for name in DATAMESH_ALL if not hasattr(dm, name)]
    assert broken == []


def test_reference_documented_api_is_exported() -> None:
    import datamesh as dm

    missing = [name for name in DOCUMENTED_API if not hasattr(dm, name)]
    assert missing == []


def test_documented_api_is_covered_by_all() -> None:
    missing = [name for name in DOCUMENTED_API if name not in set(DATAMESH_ALL)]
    assert missing == []


def test_reference_cli_subcommands_are_available() -> None:
    python_dir = pathlib.Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "datamesh.cli"],
        cwd=python_dir,
        capture_output=True,
        text=True,
    )
    usage = result.stderr + result.stdout
    assert result.returncode in (0, 1, 2), f"datamesh.cli crashed: {usage}"
    missing = [cmd for cmd in DOCUMENTED_CLI_COMMANDS if cmd not in usage]
    assert missing == []