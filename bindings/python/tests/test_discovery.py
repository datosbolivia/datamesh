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
