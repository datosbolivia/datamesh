from __future__ import annotations

import ctypes
import json
import os
import urllib.request
import re
from typing import Any, Dict, List, Optional

class DataMeshRuntime:
    """Python ctypes bridge to Go Core libdatamesh.so with pure Python HTTP fallback."""

    def __init__(self, lib_path: Optional[str] = None):
        self._lib = None
        target_path = lib_path or os.environ.get("DATAMESH_LIB_PATH", "libdatamesh.so")
        if os.path.exists(target_path):
            try:
                self._lib = ctypes.CDLL(target_path)
                self._lib.DataMeshInit.argtypes = [ctypes.c_char_p]
                self._lib.DataMeshInit.restype = ctypes.c_char_p
                self._lib.DataMeshDiscoverCatalog.argtypes = [ctypes.c_char_p]
                self._lib.DataMeshDiscoverCatalog.restype = ctypes.c_char_p
                self._lib.DataMeshResolveDataProduct.argtypes = [ctypes.c_char_p]
                self._lib.DataMeshResolveDataProduct.restype = ctypes.c_char_p
                self._lib.DataMeshFreeString.argtypes = [ctypes.c_char_p]
                self._lib.DataMeshFreeString.restype = None
                self._lib.DataMeshInit(None)
            except Exception:
                self._lib = None

    def discover(self, catalog_url: Optional[str] = None) -> Dict[str, Any]:
        url = catalog_url or os.environ.get("DATAMESH_CATALOG_URL", "https://datosbolivia.github.io/llms.txt")
        if self._lib:
            c_url = ctypes.c_char_p(url.encode("utf-8"))
            raw_ptr = self._lib.DataMeshDiscoverCatalog(c_url)
            raw_json = ctypes.string_at(raw_ptr).decode("utf-8")
            self._lib.DataMeshFreeString(raw_ptr)
            res = json.loads(raw_json)
            if not res.get("success"):
                raise RuntimeError(res.get("error", "Unknown discovery error"))
            return res.get("data", {})

        # Python fallback mirror
        req = urllib.request.Request(url, headers={"User-Agent": "datamesh-sdk/0.2 (Python-Fallback)"})
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
        return self._parse_llms_txt(content, url)

    def _parse_llms_txt(self, content: str, source_url: str) -> Dict[str, Any]:
        entries = []
        entry_pattern = re.compile(r"^-\s*\[(.*?)\]\((.*?)\)(?::\s*(.*))?$")
        domain_pattern = re.compile(r"\(Dominio:\s*([^)]*?)(?:\.|\)|Recursos:)")
        
        for line in content.splitlines():
            m = entry_pattern.match(line.strip())
            if m:
                title, raw_uri, desc = m.group(1), m.group(2), m.group(3) or ""
                resolved = urllib.parse.urljoin(source_url, raw_uri)
                dm = domain_pattern.search(desc)
                domain = dm.group(1).strip() if dm else ""
                clean_desc = desc.split("(Dominio:")[0].strip()
                entries.append({
                    "title": title,
                    "uri": raw_uri,
                    "resolved_url": resolved,
                    "description": clean_desc,
                    "domain": domain,
                })
        return {"source_url": source_url, "entries": entries}
