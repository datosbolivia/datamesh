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
    assert len(ctx_payload["services"]) == 1
    assert ctx_payload["services"][0]["title"] == "Servicio de Riesgo Municipal"
    assert len(ctx_payload["cli_tools"]) == 1
    assert ctx_payload["cli_tools"][0]["title"] == "okf-geo enrich-municipio"
    assert len(ctx_payload["concepts"]) >= 1
    assert "geo-municipio:tabla_municipios" in ctx_payload["context_markdown"]

    # 4. Inspect Knowledge Graph v2 via MCP datamesh_get_knowledge_graph
    resp_kg = handle_jsonrpc({
        "jsonrpc": "2.0",
        "id": 13,
        "method": "tools/call",
        "params": {
            "name": "datamesh_get_knowledge_graph",
            "arguments": {},
        },
    })
    assert resp_kg is not None
    kg_payload = json.loads(resp_kg["result"]["content"][0]["text"])
    geo_dataset_nodes = [n for n in kg_payload["nodes"] if n["type"] == "dataset" and n.get("slug") == "geo-municipio"]
    assert len(geo_dataset_nodes) == 1
    service_nodes = [n for n in kg_payload["nodes"] if n["type"] == "service" and "geo-municipio" in n["id"]]
    assert len(service_nodes) == 1
    assert service_nodes[0]["title"] == "Servicio de Riesgo Municipal"
    edge_tuples = {(e["source"], e["target"], e["relation"]) for e in kg_payload["edges"]}
    assert ("service:geo-municipio:./openapi.yaml", "wd:Q15284", "ACCEPTS_CONCEPT") in edge_tuples
    assert ("service:geo-municipio:./openapi.yaml", "wd:Q7944", "RETURNS_CONCEPT") in edge_tuples
    assert ("cli:geo-municipio:okf-geo enrich-municipio", "wd:Q15284", "ACCEPTS_CONCEPT") in edge_tuples
    assert ("cli:geo-municipio:okf-geo enrich-municipio", "wd:Q186588", "RETURNS_CONCEPT") in edge_tuples


def test_external_owl_cli_contract_and_openapi_array_response(tmp_path: Path):
    bundle_dir = tmp_path / "ext-cli-bundle"
    bundle_dir.mkdir(parents=True)

    (bundle_dir / "index.md").write_text(
        """---
type: dataset
title: Bundle con CLI Externo
contracts:
  - type: owl-cli
    path: ./owl-cli.yaml
  - type: datapackage
    path: ./datapackage.yaml
  - type: openapi
    path: ./openapi.yaml
---
# Bundle con CLI Externo
""",
        encoding="utf-8",
    )

    (bundle_dir / "owl-cli.yaml").write_text(
        """binary: okf-spatial
subcommand: intersect
arguments:
  - name: cod_ine
    flag: --municipio
    type: string
    required: true
    concept: wd:Q15284
    description: Código INE municipal
output:
  format: geojson
  concept: wd:Q186588
  description: Geometría resultante
""",
        encoding="utf-8",
    )

    (bundle_dir / "datapackage.yaml").write_text(
        """name: ext-cli-bundle
resources:
  - name: cobertura
    path: data/cobertura.csv
    format: csv
    schema:
      fields:
        - name: cod_ine
          type: string
          concept: wd:Q15284
""",
        encoding="utf-8",
    )

    (bundle_dir / "openapi.yaml").write_text(
        """openapi: 3.1.0
info:
  title: API de Cobertura
  version: 1.0.0
paths:
  /v1/cobertura:
    get:
      summary: Lista cobertura
      responses:
        "200":
          description: OK
          x-okf-concept: wd:Q15284
          content:
            application/json:
              schema:
                type: array
                items:
                  type: object
                  properties:
                    cod_ine:
                      type: string
                      x-okf-concept: wd:Q15284
                    porcentaje:
                      type: number
                      x-okf-concept: wd:Q7944
""",
        encoding="utf-8",
    )

    dp = dm.get(str(bundle_dir))
    assert dp is not None
    resources = dp.resources if hasattr(dp, "resources") else dp.get("resources", [])
    description = dp.description if hasattr(dp, "description") else dp.get("description", "")
    assert len(resources) == 1
    res_name = resources[0].name if hasattr(resources[0], "name") else resources[0]["name"]
    assert res_name == "cobertura"
    assert "okf-spatial intersect" in description
    assert "`--municipio`" in description
    assert "wd:Q186588" in description
    assert "wd:Q7944" in description


def test_explain_categories_curie_filename_and_okf_validation(tmp_path: Path):
    bundle_dir = tmp_path / "curie-bundle"
    data_dir = bundle_dir / "data"
    data_dir.mkdir(parents=True)

    csv_file = data_dir / "ventas.csv"
    csv_file.write_text("cod_ine,departamento,monto\n020101,La Paz,100.5\n070101,Santa Cruz,250.0\n", encoding="utf-8")

    (bundle_dir / "index.md").write_text(
        """---
type: dataset
title: Ventas por Departamento
dimensions:
  - departamento
contracts:
  - type: datapackage
    path: ./datapackage.yaml
---
# Ventas por Departamento
""",
        encoding="utf-8",
    )

    pkg_path = bundle_dir / "datapackage.yaml"
    pkg = dm.create_datapackage(
        name="curie-bundle",
        title="Ventas por Departamento",
        files=[csv_file],
        output_file=pkg_path,
    )
    assert pkg.name == "curie-bundle"

    dm.link_concept(
        datapackage_path_or_dict=pkg_path,
        resource_name="ventas",
        column_name="departamento",
        concept_ref="wd:Q250050",
        value_mappings={
            "La Paz": {"label": "Departamento de La Paz"},
            "Santa Cruz": {"label": "Departamento de Santa Cruz"},
        },
        save_to_path=pkg_path,
    )
    docs = dm.explain_categories(pkg_path, output_concepts_dir=bundle_dir / "concepts")
    assert len(docs) == 1

    concept_path = bundle_dir / "concepts" / "departamento.md"
    assert concept_path.exists()
    content = concept_path.read_text(encoding="utf-8")
    assert "skos:" in content
    assert "exact_match:" in content
    assert "wd:Q250050" in content

    val_report = dm.validate(str(bundle_dir / "index.md"))
    assert val_report["valid"] is True
    assert val_report["total_errors"] == 0


def test_server_well_known_and_mcp_202(monkeypatch):
    import threading
    import urllib.request
    from datamesh.server import DataMeshServerHandler, ReusableHTTPServer

    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")

    srv = ReusableHTTPServer(("127.0.0.1", 0), DataMeshServerHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base_url = f"http://127.0.0.1:{port}"
        disc = dm.discover_endpoint(base_url)
        assert disc is not None
        schema_ver = disc.schema_version if hasattr(disc, "schema_version") else disc.get("schema_version")
        caps = disc.capabilities if hasattr(disc, "capabilities") else disc.get("capabilities", {})
        assert schema_ver.startswith("0.2")
        assert caps.get("mcp") is True

        req = urllib.request.Request(
            f"{base_url}/mcp",
            data=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            assert resp.status == 202
            assert resp.read() == b""
    finally:
        srv.shutdown()
        srv.server_close()

