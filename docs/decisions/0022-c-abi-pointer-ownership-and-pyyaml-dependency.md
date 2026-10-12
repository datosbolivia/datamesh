# ADR 0022: Propiedad de Punteros en el C-ABI y Dependencia YAML

## Estado
Aceptado

## Fecha
2026-10-12

## Contexto
Al ejercitar las nuevas implementaciones (ADRs 0016-0021) contra un caso real
(`monitor-economico`, que consulta `p2p-bob-exchange:advice` vía `dm.sql`)
aparecieron dos defectos que la propia suite del SDK no podía detectar:

1. **Corrupción de heap en el puente C-ABI (`go_bridge.py`):** las funciones del
   núcleo Go (`DataMeshExecuteSQL`, etc.) devuelven `*C.char` asignado con
   `C.CString` y se liberan con `DataMeshFreeString` (`C.free`). El puente
   declaraba `restype = ctypes.c_char_p`, con lo que ctypes **copia** el buffer a
   un `bytes` de Python y pierde el puntero original. Al llamar a
   `DataMeshFreeString(raw)` se pasaba la dirección de un buffer de Python (no del
   montón Go) → `munmap_chunk(): invalid pointer` y cierre abrupto del proceso.
   La suite no lo detectaba porque no compila `libdatamesh.so`: sin biblioteca, el
   motor Go nunca ejecutaba la ruta C-ABI.

2. **Dependencia YAML no declarada:** los manifiestos de nodo (`datapackage.yml`,
   frontmatter de `index.md`) se leen con PyYAML, pero `pyproject.toml` solo
   declaraba `duckdb`. En un entorno limpio (p. ej. el `.venv` de
   `monitor-economico`) `import yaml` falla, la lectura de manifiestos YAML
   devuelve `None` silenciosamente y la resolución de tríadas cae al catálogo
   remoto (Kaggle) o falla.

## Decisión
1. **Propiedad de punteros C-ABI:** todas las firmas de `GoCoreBridge._SIGNATURES`
   se declaran con `restype = ctypes.c_void_p` y `DataMeshFreeString` con
   `argtypes = [ctypes.c_void_p]`. El puntero original se decodifica con
   `ctypes.string_at` y se libera tal cual. El resultado de `DataMeshInit` también
   se libera tras el cableado.
2. **Guard de regresión:** `bindings/python/tests/test_go_bridge.py` verifica que
   ningún símbolo del C-ABI se declare con `c_char_p`.
3. **PyYAML como dependencia de núcleo:** se añade `PyYAML>=6.0` a las
   dependencias de `bindings/python/pyproject.toml`, ya que el formato OKF/ODKF
   usa metadatos YAML de forma central.

## Consecuencias
- **Positivo:** el motor Go es usable desde Python sin corromper la memoria; la
  resolución local de nodos YAML funciona en instalaciones limpias; sin descargas
  implícitas de Kaggle.
- **Coste:** PyYAML pasa a ser una dependencia obligatoria (antes opcional de
  facto). Las firmas `c_void_p` obligan a decodificar manualmente con
  `string_at` (ya implementado en `call`/`call_raw`).

## Referencias
- ADR 0018 (puente C-ABI único), ADR 0019 (subconjunto SQL honesto en Go), ADR 0021 (workspace hermético).
- `bindings/python/datamesh/adapters/go_bridge.py`, `bindings/python/pyproject.toml`, `bindings/python/tests/test_go_bridge.py`.
