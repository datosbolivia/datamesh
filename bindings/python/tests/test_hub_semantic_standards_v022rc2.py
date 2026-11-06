from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import datamesh as dm
from datamesh.adapters.catalog.llmstxt_catalog import parse_llms_txt
from datamesh.adapters.catalog.well_known import WellKnownResolverAdapter
from datamesh.mcp_server import handle_jsonrpc


def test_mcp_jsonrpc_strict_notifications_return_none():
    # Standard notifications/initialized
    assert handle_jsonrpc({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    # Short initialized notification
    assert handle_jsonrpc({"jsonrpc": "2.0", "method": "initialized"}) is None
    # Cancelled notification without id
    assert handle_jsonrpc({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}}) is None
    # Any notification missing id or with id=None
    assert handle_jsonrpc({"jsonrpc": "2.0", "method": "custom/event"}) is None
    assert handle_jsonrpc({"jsonrpc": "2.0", "id": None, "method": "custom/event"}) is None

    # Normal request with id still returns valid JSON-RPC response
    ping_resp = handle_jsonrpc({"jsonrpc": "2.0", "id": 42, "method": "ping"})
    assert ping_resp is not None
    assert ping_resp["id"] == 42
    assert ping_resp["result"] == {}


def test_parse_llms_txt_multi_link_line_preserves_target_uri():
    raw = """# Catálogo Soberano
> Índice de prueba

- [Créditos ASFI](/raw/nodes/asfi-creditos/index.md): Cartera de créditos bancarios. (Dominio: Finanzas. Recursos: cartera_2025)
- [Índice de Calidad del Aire (ICA)](./concepts/air_quality_index.md) - [Q2364111](https://www.wikidata.org/wiki/Q2364111)
"""
    parsed = parse_llms_txt(raw, "https://datosbolivia.github.io/raw/nodes/air_quality/index.md")
    entries = parsed["entries"]
    assert len(entries) == 2
    assert entries[1]["uri"] == "./concepts/air_quality_index.md"
    assert entries[1]["resolved_url"] == "https://datosbolivia.github.io/raw/nodes/air_quality/concepts/air_quality_index.md"


def test_search_accent_insensitive_and_multi_token(monkeypatch):
    fake_catalog = {
        "title": "Catálogo Test",
        "entries": [
            {
                "title": "Créditos Bancarios por Municipio",
                "uri": "/raw/nodes/asfi-creditos/index.md",
                "resolved_url": "https://datosbolivia.github.io/raw/nodes/asfi-creditos/index.md",
                "description": "Estadísticas de colocación crediticia.",
                "domain": "Economía y Finanzas",
                "resources": ["cartera_municipal"],
            },
            {
                "title": "Calidad del Aire",
                "uri": "/raw/nodes/air_quality/index.md",
                "resolved_url": "https://datosbolivia.github.io/raw/nodes/air_quality/index.md",
                "description": "Mediciones de material particulado PM2.5.",
                "domain": "Medio Ambiente",
                "resources": ["mediciones"],
            },
        ],
    }
    monkeypatch.setattr(dm, "discover", lambda catalog_url=None: fake_catalog)

    # Search without accents ("creditos") matches "Créditos"
    res1 = dm.search("creditos")
    assert len(res1) == 1
    assert res1[0]["title"] == "Créditos Bancarios por Municipio"

    # Search multi-token ("economia municipio")
    res2 = dm.search("economia municipio")
    assert len(res2) == 1
    assert res2[0]["title"] == "Créditos Bancarios por Municipio"

    # Search by resource name ("cartera_municipal")
    res3 = dm.search("cartera_municipal")
    assert len(res3) == 1


def test_well_known_llmstxt_fallback_probe():
    adapter = WellKnownResolverAdapter(timeout=2)

    fake_llms = b"# Datos Bolivia\n> Portal Soberano OKF\n\n- [BCB Semanal](/raw/nodes/bcb-semanal/index.md): Reservas\n"

    def fake_urlopen(req, timeout=2):
        url = req.full_url
        if url.endswith("/llms.txt"):
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = fake_llms
            mock_resp.__enter__.return_value = mock_resp
            return mock_resp
        raise OSError("404 Not Found")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        disc = adapter.fetch_well_known("https://datosbolivia.github.io")
        assert disc is not None
        assert disc.catalog.catalog_type == "okf"
        assert disc.catalog.catalog_url == "https://datosbolivia.github.io/llms.txt"
        assert disc.capabilities.get("sql_query") is True
        assert disc.capabilities.get("knowledge_graph") is True


def test_markdown_contract_synthesis_and_mcp_tools(tmp_path: Path, monkeypatch):
    bundle_dir = tmp_path / "geo-municipio"
    concepts_dir = bundle_dir / "concepts"
    concepts_dir.mkdir(parents=True)

    (bundle_dir / "index.md").write_text(
        """---
type: dataset
title: Hub Territorial de Municipios
dimensions:
  - municipio
contracts:
  - type: datapackage
    path: ./datapackage.yaml
  - type: openapi
    path: ./openapi.yaml
  - type: owl-cli
    binary: okf-geo
    subcommand: enrich-municipio
    inputs:
      - name: codigo_ine
        flag: --cod-ine
        type: string
        concept: wd:Q15284
        required: true
        description: Código INE de 6 dígitos
    outputs:
      format: json
      concept: wd:Q186588
      description: Polígono GeoJSON del municipio
---
# Hub Territorial de Municipios

Documentación narrativa para el agente.

```ojs
viewof filtro = Inputs.select(["La Paz", "Santa Cruz"])
```
""",
        encoding="utf-8",
    )

    (bundle_dir / "datapackage.yaml").write_text(
        """name: geo-municipio
resources:
  - name: tabla_municipios
    path: data/municipios.parquet
    format: parquet
    schema:
      fields:
        - name: cod_ine
          type: string
          title: Código INE Municipal
          concept: wd:Q15284
        - name: departamento
          type: string
          title: Departamento
          categories:
            - La Paz
            - Santa Cruz
            - Cochabamba
""",
        encoding="utf-8",
    )

    (bundle_dir / "openapi.yaml").write_text(
        """openapi: 3.1.0
info:
  title: Servicio de Riesgo Municipal
  version: 1.0.0
servers:
  - url: https://api.datosbolivia.org
paths:
  /v1/riesgo/municipio:
    get:
      summary: Obtiene indicador de riesgo por municipio
      parameters:
        - name: cod_ine
          in: query
          required: true
          x-okf-concept: wd:Q15284
          schema:
            type: string
          description: Código INE de 6 dígitos
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  indice_riesgo:
                    type: number
                    x-okf-concept: wd:Q7944
                    description: Índice de riesgo climático
""",
        encoding="utf-8",
    )

    concept_file = concepts_dir / "cod_ine.md"
    concept_file.write_text(
        """---
type: concept
title: Código INE Municipal
skos:
  - https://www.wikidata.org/wiki/Q15284
---
# Código INE Municipal

Código único de 6 dígitos asignado por el INE a cada municipio de Bolivia.
""",
        encoding="utf-8",
    )

    # 1. Inspect via MCP datamesh_get_dataproduct
    resp_dp = handle_jsonrpc({
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "datamesh_get_dataproduct",
            "arguments": {"uri": str(bundle_dir)},
        },
    })
    assert resp_dp is not None
    dp_payload = json.loads(resp_dp["result"]["content"][0]["text"])
    assert "raw_content" not in dp_payload
    assert dp_payload["title"] == "Hub Territorial de Municipios"
    assert len(dp_payload["resources"]) == 1
    assert dp_payload["resources"][0]["name"] == "tabla_municipios"
    desc = dp_payload["description"]
    assert "```ojs" not in desc
    assert "## Contrato de Datos y Esquema Semántico (Sintetizado)" in desc
    assert "`cod_ine`" in desc
    assert "GET /v1/riesgo/municipio" in desc
    assert "okf-geo enrich-municipio" in desc

    # 2. Inspect specific concept file via MCP datamesh_read_concept_body
    resp_concept = handle_jsonrpc({
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {
            "name": "datamesh_read_concept_body",
            "arguments": {"uri": str(concept_file)},
        },
    })
    assert resp_concept is not None
    c_payload = json.loads(resp_concept["result"]["content"][0]["text"])
    assert c_payload["title"] == "Código INE Municipal"
    assert "Código único de 6 dígitos" in c_payload["markdown_body"]

    # 3. Inspect Semantic Context Map via MCP datamesh_resolve_context
    fake_cat = {
        "title": "Catálogo Territorial",
        "entries": [
            {
                "title": "Hub Territorial de Municipios",
                "uri": "/raw/nodes/geo-municipio/index.md",
                "resolved_url": str(bundle_dir / "index.md"),
                "description": "Datos de municipios con [Código INE](./concepts/cod_ine.md).",
                "domain": "Geografía",
                "resources": ["tabla_municipios"],
            }
        ],
    }
    monkeypatch.setattr(dm, "discover", lambda catalog_url=None: fake_cat)
    resp_ctx = handle_jsonrpc({
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {
            "name": "datamesh_resolve_context",
            "arguments": {"query": "municipios"},
        },
    })
    assert resp_ctx is not None
    ctx_payload = json.loads(resp_ctx["result"]["content"][0]["text"])
    assert ctx_payload["total_datasets"] == 1
    assert "geo-municipio:tabla_municipios" in ctx_payload["context_markdown"]
