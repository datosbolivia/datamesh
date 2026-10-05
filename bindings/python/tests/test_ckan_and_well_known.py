from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

import datamesh as dm
from datamesh.domain.models import (
    WellKnownDiscovery,
    CatalogMetadata,
    AuthConfiguration,
    KeycloakAuth,
    APIKeyAuth,
    CKANPackage,
    CKANResource,
)
from datamesh.adapters.auth import (
    NoAuthAdapter,
    APIKeyAuthAdapter,
    BearerTokenAuthAdapter,
    KeycloakAuthAdapter,
)
from datamesh.adapters.catalog.well_known import WellKnownResolverAdapter
from datamesh.adapters.catalog.ckan_client import CKANClientAdapter
from datamesh.usecases.discover_well_known import DiscoverWellKnownUseCase
from datamesh.usecases.harvest_ckan import HarvestCKANUseCase


SAMPLE_WELL_KNOWN_DATA = {
    "schema_version": "0.2.0",
    "catalog": {
        "name": "datos-gob-bo",
        "title": "Portal de Datos Abiertos de Bolivia",
        "type": "ckan",
        "catalog_url": "https://datos.gob.bo",
        "api_endpoint": "https://datos.gob.bo/api/3/action",
        "description": "Catálogo oficial de datos de Bolivia",
        "version": "2.10",
    },
    "auth": {
        "type": "keycloak",
        "required": False,
        "keycloak": {
            "realm_url": "https://auth.datos.gob.bo/realms/datamesh",
            "token_endpoint": "https://auth.datos.gob.bo/realms/datamesh/protocol/openid-connect/token",
            "client_id": "datamesh-client",
            "scopes_supported": ["openid", "data:read"],
        },
        "api_key": {
            "header_name": "X-CKAN-API-Key",
        },
    },
    "capabilities": {
        "search": True,
        "sql_query": True,
        "datastore": True,
        "harvesting": True,
    },
}

SAMPLE_CKAN_PACKAGE_RAW = {
    "id": "c1f7a2d4-1234-5678-90ab-cdef12345678",
    "name": "censo-poblacion-2024",
    "title": "Censo de Población y Vivienda 2024 - Bolivia",
    "notes": "Microdatos anonimizados del Censo de Población y Vivienda 2024 levantado por el INE.",
    "version": "1.0.0",
    "organization": {
        "name": "ine",
        "title": "Instituto Nacional de Estadística (INE)",
    },
    "tags": [{"name": "demografia"}, {"name": "censo"}, {"name": "hogares"}],
    "extras": [
        {"key": "spatial", "value": "-69.64,-22.90,-57.45,-9.67"},
        {"key": "temporal_start", "value": "2024-03-23T00:00:00Z"},
        {"key": "temporal_end", "value": "2024-03-25T23:59:59Z"},
        {"key": "frequency", "value": "decennial"},
    ],
    "resources": [
        {
            "id": "res-001",
            "name": "Población por Departamento y Municipio",
            "description": "Distribución poblacional agregada a nivel municipal",
            "url": "https://datos.gob.bo/dataset/censo2024/poblacion.csv",
            "format": "CSV",
            "size": 5242880,
            "mimetype": "text/csv",
            "datastore_active": True,
        }
    ],
}


def test_auth_adapters():
    # 1. NoAuth
    no_auth = NoAuthAdapter()
    assert no_auth.get_auth_headers() == {}
    assert no_auth.get_auth_type() == "none"

    # 2. APIKey
    api_auth = APIKeyAuthAdapter(token="secret-key-123", header_name="X-Custom-Key")
    assert api_auth.get_auth_headers() == {"X-Custom-Key": "secret-key-123"}
    assert api_auth.get_auth_type() == "api_key"

    # 3. BearerToken
    bearer = BearerTokenAuthAdapter(token="jwt.token.abc")
    assert bearer.get_auth_headers() == {"Authorization": "Bearer jwt.token.abc"}
    assert bearer.get_auth_type() == "bearer"


def test_keycloak_auth_adapter_flow():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "access_token": "keycloak_jwt_token_xyz",
            "expires_in": 300,
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        kc = KeycloakAuthAdapter(
            token_endpoint="https://auth.example.com/token",
            client_id="my-client",
            client_secret="my-secret",
        )
        headers = kc.get_auth_headers()
        assert headers == {"Authorization": "Bearer keycloak_jwt_token_xyz"}

        # Second call should use cached token without additional network request
        mock_urlopen.reset_mock()
        headers2 = kc.get_auth_headers()
        assert headers2 == {"Authorization": "Bearer keycloak_jwt_token_xyz"}
        assert mock_urlopen.call_count == 0


def test_well_known_resolver_adapter_success():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(SAMPLE_WELL_KNOWN_DATA).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        resolver = WellKnownResolverAdapter()
        disc = resolver.fetch_well_known("https://datos.gob.bo")

        assert disc is not None
        assert disc.schema_version == "0.2.0"
        assert disc.catalog.name == "datos-gob-bo"
        assert disc.catalog.catalog_type == "ckan"
        assert disc.auth.auth_type == "keycloak"
        assert disc.auth.keycloak.client_id == "datamesh-client"
        assert disc.capabilities["harvesting"] is True


def test_well_known_resolver_ckan_fallback_probe():
    with patch("urllib.request.urlopen") as mock_urlopen:
        # First calls to .well-known fail with 404
        # Fallback call to /api/3/action/status_show succeeds
        def side_effect(req, timeout=5):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "status_show" in url:
                resp = MagicMock()
                resp.status = 200
                resp.read.return_value = json.dumps({
                    "success": True,
                    "result": {"site_title": "Portal de Datos Bolivia Legacy"}
                }).encode("utf-8")
                ctx = MagicMock()
                ctx.__enter__.return_value = resp
                return ctx
            raise Exception("404 Not Found")

        mock_urlopen.side_effect = side_effect

        resolver = WellKnownResolverAdapter()
        disc = resolver.fetch_well_known("https://legacy-ckan.bo")

        assert disc is not None
        assert disc.catalog.catalog_type == "ckan"
        assert disc.catalog.title == "Portal de Datos Bolivia Legacy"
        assert "status_show" not in disc.catalog.api_endpoint


def test_discover_well_known_usecase_auth_selection():
    resolver = MagicMock()
    resolver.fetch_well_known.return_value = WellKnownDiscovery.from_dict(SAMPLE_WELL_KNOWN_DATA)

    uc = DiscoverWellKnownUseCase(resolver)
    disc = uc.execute("https://datos.gob.bo")
    assert disc is not None

    # Keycloak client credentials configured
    auth_kc = uc.create_auth_provider(disc, client_secret="my_kc_secret")
    assert isinstance(auth_kc, KeycloakAuthAdapter)

    # Token for Keycloak catalog produces Bearer token
    auth_bearer = uc.create_auth_provider(disc, token="token_123")
    assert isinstance(auth_bearer, BearerTokenAuthAdapter)
    assert auth_bearer.get_auth_headers() == {"Authorization": "Bearer token_123"}

    # Discovery with explicit API Key auth type
    disc_apikey = WellKnownDiscovery.from_dict({
        **SAMPLE_WELL_KNOWN_DATA,
        "auth": {"type": "api_key", "api_key": {"header_name": "X-CKAN-API-Key"}},
    })
    auth_key = uc.create_auth_provider(disc_apikey, token="token_123")
    assert isinstance(auth_key, APIKeyAuthAdapter)
    assert auth_key.get_auth_headers() == {"X-CKAN-API-Key": "token_123"}

    # No credentials provided
    auth_none = uc.create_auth_provider(disc)
    assert isinstance(auth_none, NoAuthAdapter)


def test_harvest_ckan_usecase_reconstruction(tmp_path: Path):
    mock_client = MagicMock()
    pkg = CKANClientAdapter()._parse_package(SAMPLE_CKAN_PACKAGE_RAW)
    mock_client.search_packages.return_value = ([pkg], 1)
    mock_client.get_datastore_schema.return_value = [
        {"name": "departamento", "type": "string"},
        {"name": "municipio", "type": "string"},
        {"name": "total_habitantes", "type": "integer"},
    ]

    uc = HarvestCKANUseCase(mock_client)
    res = uc.execute(
        base_url="https://datos.gob.bo/api/3/action",
        output_dir=tmp_path,
        probe_datastore_schema=True,
    )

    assert res.total_discovered == 1
    assert len(res.harvested_packages) == 1

    manifest = res.harvested_packages[0]
    assert manifest["name"] == "censo_poblacion_2024"
    assert manifest["title"] == "Censo de Población y Vivienda 2024 - Bolivia"
    assert "spatial" in manifest
    assert manifest["spatial"]["bbox"] == [-69.64, -22.90, -57.45, -9.67]
    assert manifest["temporal"]["start"] == "2024-03-23T00:00:00Z"
    assert manifest["temporal"]["end"] == "2024-03-25T23:59:59Z"

    resource = manifest["resources"][0]
    assert resource["name"] == "poblacion_por_departamento_y_municipio"
    assert resource["format"] == "csv"
    assert "schema" in resource
    assert len(resource["schema"]["fields"]) == 3
    assert resource["schema"]["fields"][2]["type"] == "integer"

    # Verify generated bundle directory
    pkg_dir = tmp_path / "censo_poblacion_2024"
    assert pkg_dir.exists()
    assert (pkg_dir / "index.md").exists()
    assert (pkg_dir / "datapackage.yaml").exists() or (pkg_dir / "datapackage.json").exists()

    index_text = (pkg_dir / "index.md").read_text(encoding="utf-8")
    assert "type: dataset" in index_text
    assert "Instituto Nacional de Estadística (INE)" in index_text
    assert "Recursos Disponibles" in index_text


def test_datamesh_facade_discover_and_harvest(tmp_path: Path):
    with patch("datamesh.core.DataMeshRuntime.discover_endpoint") as mock_disc:
        with patch("datamesh.core.DataMeshRuntime.harvest_ckan") as mock_harv:
            mock_disc.return_value = WellKnownDiscovery.from_dict(SAMPLE_WELL_KNOWN_DATA)
            mock_harv.return_value = dm.CKANHarvestResult(
                catalog_url="https://datos.gob.bo",
                total_discovered=5,
                harvested_packages=({"name": "censo_2024"}, {"name": "inflacion_ine"}),
                output_directory=str(tmp_path),
            )

            # 1. dm.discover_endpoint
            d = dm.discover_endpoint("https://datos.gob.bo")
            assert d is not None
            assert d.catalog.name == "datos-gob-bo"

            # 2. dm.harvest_ckan
            h = dm.harvest_ckan("https://datos.gob.bo", limit=2, output_dir=tmp_path)
            assert h.total_discovered == 5
            assert len(h.harvested_packages) == 2


def test_cli_discover_and_harvest(capsys):
    from datamesh.cli import main
    import sys

    # 1. Test CLI discover
    with patch("datamesh.discover_endpoint") as mock_disc:
        mock_disc.return_value = WellKnownDiscovery.from_dict(SAMPLE_WELL_KNOWN_DATA)
        with patch.object(sys, "argv", ["datamesh", "discover", "https://datos.gob.bo"]):
            main()
            captured = capsys.readouterr()
            data = json.loads(captured.out)
            assert data["schema_version"] == "0.2.0"
            assert data["catalog"]["type"] == "ckan"
            assert data["auth"]["type"] == "keycloak"

    # 2. Test CLI harvest-ckan
    with patch("datamesh.harvest_ckan") as mock_harv:
        mock_harv.return_value = dm.CKANHarvestResult(
            catalog_url="https://datos.gob.bo",
            total_discovered=1,
            harvested_packages=({"name": "censo_2024"},),
            output_directory="/tmp/harvest",
            execution_time_ms=120,
        )
        with patch.object(sys, "argv", ["datamesh", "harvest-ckan", "https://datos.gob.bo", "--limit", "1"]):
            main()
            captured = capsys.readouterr()
            data = json.loads(captured.out)
            assert data["catalog_url"] == "https://datos.gob.bo"
            assert data["harvested_count"] == 1
            assert "censo_2024" in data["packages"]

