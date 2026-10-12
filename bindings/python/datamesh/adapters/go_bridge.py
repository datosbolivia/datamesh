from __future__ import annotations

import ctypes
import json
import os
from typing import Any, Dict, Optional


class GoCoreBridge:
    """Single ctypes bridge to the compiled Go core (``libdatamesh.so``).

    Owns everything related to the C-ABI: library loading, symbol wiring, the
    safe call/free/decode protocol and the ``{"success": bool, "data": ...}``
    envelope. No other module touches ``ctypes`` or the ABI contract directly.
    """

    _SIGNATURES: Dict[str, tuple] = {
        "DataMeshInit": ([ctypes.c_char_p], ctypes.c_char_p),
        "DataMeshDiscoverCatalog": ([ctypes.c_char_p], ctypes.c_char_p),
        "DataMeshSearchCatalog": ([ctypes.c_char_p, ctypes.c_char_p], ctypes.c_char_p),
        "DataMeshResolveDataProduct": ([ctypes.c_char_p], ctypes.c_char_p),
        "DataMeshQueryResource": ([ctypes.c_char_p, ctypes.c_char_p], ctypes.c_char_p),
        "DataMeshExecuteSQL": ([ctypes.c_char_p, ctypes.c_char_p], ctypes.c_char_p),
        "DataMeshValidate": ([ctypes.c_char_p], ctypes.c_char_p),
        "DataMeshGetLineage": ([ctypes.c_char_p, ctypes.c_char_p], ctypes.c_char_p),
        "DataMeshLineageGraph": ([ctypes.c_char_p], ctypes.c_char_p),
    }

    def __init__(self, lib_path: Optional[str] = None, lib_handle: Optional[Any] = None):
        self._lib = lib_handle
        if self._lib is None:
            target_path = lib_path or os.environ.get("DATAMESH_LIB_PATH", "libdatamesh.so")
            if os.path.exists(target_path):
                try:
                    self._lib = ctypes.CDLL(target_path)
                except OSError:
                    self._lib = None
        if self._lib is not None:
            self._wire_symbols()

    def _wire_symbols(self) -> None:
        try:
            for name, (argtypes, restype) in self._SIGNATURES.items():
                fn = getattr(self._lib, name, None)
                if fn is not None:
                    fn.argtypes = argtypes
                    fn.restype = restype
            free = getattr(self._lib, "DataMeshFreeString", None)
            if free is not None:
                free.argtypes = [ctypes.c_char_p]
                free.restype = None
            init = getattr(self._lib, "DataMeshInit", None)
            if init is not None:
                init(None)
        except Exception:
            self._lib = None

    @property
    def available(self) -> bool:
        return self._lib is not None

    @property
    def handle(self) -> Optional[Any]:
        return self._lib

    def supports(self, symbol: str) -> bool:
        return self._lib is not None and hasattr(self._lib, symbol)

    def call(self, symbol: str, *args: Any) -> Optional[Any]:
        """Invokes a Go symbol, frees the C string and unwraps ``data`` on success.

        Returns ``None`` when the bridge is unavailable, the symbol is missing, the
        Go call failed, or the response envelope is not a successful payload.
        """
        if not self.supports(symbol):
            return None
        try:
            fn = getattr(self._lib, symbol)
            c_args = [a.encode("utf-8") if isinstance(a, str) else a for a in args]
            raw = fn(*c_args)
            if not raw:
                return None
            try:
                resp = json.loads(ctypes.string_at(raw).decode("utf-8"))
            finally:
                free = getattr(self._lib, "DataMeshFreeString", None)
                if free is not None:
                    free(raw)
            if isinstance(resp, dict) and resp.get("success") and resp.get("data"):
                return resp["data"]
        except Exception:
            pass
        return None

    def call_with_options(self, symbol: str, options: Optional[Dict[str, Any]], *prefix: Any) -> Optional[Any]:
        """Calls a symbol whose last argument is a JSON-encoded options object."""
        return self.call(symbol, *prefix, json.dumps(options or {}))

    def call_raw(self, symbol: str, *args: Any) -> Optional[Dict[str, Any]]:
        """Returns the full decoded envelope without unwrapping, or ``None``."""
        if not self.supports(symbol):
            return None
        try:
            fn = getattr(self._lib, symbol)
            c_args = [a.encode("utf-8") if isinstance(a, str) else a for a in args]
            raw = fn(*c_args)
            if not raw:
                return None
            try:
                return json.loads(ctypes.string_at(raw).decode("utf-8"))
            finally:
                free = getattr(self._lib, "DataMeshFreeString", None)
                if free is not None:
                    free(raw)
        except Exception:
            return None
