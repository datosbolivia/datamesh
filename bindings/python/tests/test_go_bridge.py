import ctypes

from datamesh.adapters.go_bridge import GoCoreBridge


def test_c_abi_returns_preserve_raw_pointer():
    # Regression: declaring the C-ABI returns as c_char_p makes ctypes copy the
    # Go-allocated buffer into a Python ``bytes``; DataMeshFreeString would then
    # free a foreign address and corrupt the heap (``munmap_chunk(): invalid
    # pointer``). Returns must be c_void_p so the original pointer is decoded
    # with ``string_at`` and freed as-is.
    for name, (_, restype) in GoCoreBridge._SIGNATURES.items():
        assert restype is ctypes.c_void_p, f"{name} must return c_void_p, got {restype}"
