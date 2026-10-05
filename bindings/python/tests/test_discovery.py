import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import datamesh as dm

def test_discover_mock_content(monkeypatch):
    sample_llms = """# Test Catalog
> Description

## Entries
- [Atlas Electoral](/raw/nodes/elecciones/index.md): Descripcion de elecciones. (Dominio: Demografia. Recursos: r1)
"""
    class MockResponse:
        def read(self):
            return sample_llms.encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req: MockResponse())

    res = dm.discover("https://example.org/llms.txt")
    entries = res.get("entries", [])
    assert len(entries) == 1
    assert entries[0]["title"] == "Atlas Electoral"
    assert entries[0]["domain"] == "Demografia"
    assert entries[0]["resolved_url"] == "https://example.org/raw/nodes/elecciones/index.md"

def test_search_filter(monkeypatch):
    sample_llms = """# Test Catalog
## Entries
- [Atlas Electoral](/raw/nodes/elecciones/index.md): Elecciones bolivianas. (Dominio: Demografia)
- [Cartera de Creditos](/raw/nodes/creditos/index.md): Creditos financieros. (Dominio: Finanzas)
"""
    class MockResponse:
        def read(self):
            return sample_llms.encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req: MockResponse())

    matches = dm.search("creditos", "https://example.org/llms.txt")
    assert len(matches) == 1
    assert matches[0]["title"] == "Cartera de Creditos"


def test_discover_hierarchical_mte_catalog(monkeypatch):
    mte_llms = """# Portal de Datos TMU | Acuerdo FMI - Bolivia
> Catálogo soberano de requerimientos y componentes de datos

### [REQ-01] RIN del programa : Saldo de RIN, RIB, pasivos. (Institución: BCB - Banco Central de Bolivia)
- Dominio Temático: Reservas del Programa
- Especificación Técnica: /raw/knowledge/requirements/REQ-01.md
- Componentes (2):
  * [REQ_01_A] Reservas internacionales brutas (RIB) (Tríada: `mefp:req-01:req_01_a`, Formato: csv, Estado: Con datos): /raw/knowledge/components/req_01_a.md
  * [REQ_01_B] Pasivos de reservas (Tríada: `mefp:req-01:req_01_b`, Formato: csv, Estado: Template): /raw/knowledge/components/req_01_b.md
"""
    class MockResponse:
        def read(self):
            return mte_llms.encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req: MockResponse())

    res = dm.discover("http://localhost:4321/mefp-uie/fmi/llms.txt")
    entries = res.get("entries", [])
    assert len(entries) == 2
    assert entries[0]["title"] == "[REQ-01] Reservas internacionales brutas (RIB)"
    assert entries[0]["domain"] == "Reservas del Programa"
    assert entries[0]["triad"] == "mefp:req-01:req_01_a"
    assert entries[0]["resources"] == ["req_01_a"]
    assert entries[0]["resolved_url"] == "http://localhost:4321/raw/knowledge/components/req_01_a.md"

    # Test search on hierarchical entries
    matches = dm.search("brutas", "http://localhost:4321/mefp-uie/fmi/llms.txt")
    assert len(matches) == 1
    assert matches[0]["title"] == "[REQ-01] Reservas internacionales brutas (RIB)"


def test_resolve_component_node(monkeypatch):
    comp_md = """---
type: component
id: req_01_a
title: Reservas internacionales brutas (RIB)
domain: reservas_programa
path: subpedidos/req_01_a.csv
format: csv
schema_fields:
- TIME_PERIOD
- OBS_VALUE
---
# Reservas internacionales brutas
Documentación del componente técnico.
"""
    class MockResponse:
        def read(self):
            return comp_md.encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req: MockResponse())

    resolved = dm.get("http://localhost:4321/raw/knowledge/components/req_01_a.md")
    assert resolved["manifest"]["title"] == "Reservas internacionales brutas (RIB)"
    assert resolved["manifest"]["type"] == "component"
    assert resolved["manifest"]["format"] == "csv"
    assert resolved["manifest"]["dimensions"] == ["reservas_programa"]
    assert resolved["manifest"]["schema_fields"] == ["TIME_PERIOD", "OBS_VALUE"]

