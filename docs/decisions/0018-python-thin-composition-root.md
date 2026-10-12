# ADR 0018: Composition Root Delgado y Puente C-ABI Único en el Binding Python

## Estado
Aceptado

## Fecha
2026-10-11

## Contexto
La auditoría de `bindings/python/datamesh/core.py` reveló que la clase `DataMeshRuntime` (1143 líneas) concentraba responsabilidades que no le corresponden como composition root, violando el aislamiento de capas de ADR 0001 y ADR 0008:

1. **ctypes disperso:** el protocolo C-ABI (carga de `libdatamesh.so`, cableado de `argtypes`/`restype`, `DataMeshFreeString`, decodificación JSON y desempaquetado `{success, data}`) se repetía en `core.py` (`discover`, `resolve`, `query`, `validate`, `_go_get_lineage`, `_go_lineage_graph`) y otra vez en `adapters/engine/go_engine.py`.
2. **Lógica de infraestructura en el núcleo:** el parseo de índices federados `llms.txt`, la resolución de tríadas a rutas físicas (caché, proyectos hermanos, manifiestos) y los fallbacks tabulares puros Python (CSV/JSON/JSONL) vivían dentro del runtime.
3. **Acceso a miembros privados:** los adaptadores inbound (`server.py`, `mcp_server.py`) y las pruebas accedían a `dm._runtime.resolver_usecase` y `dm._runtime._duckdb_engine`, acoplando consumidores a la representación interna del singleton.

El resultado era un componente imposible de probar en aislamiento y con múltiples fuentes de verdad para el mismo contrato C-ABI.

## Decisión

### 1. Un único puente ctypes: `adapters/go_bridge.py`
`GoCoreBridge` es el **único** módulo que importa `ctypes`. Carga la biblioteca, cablea todos los símbolos (`DataMeshInit`, `DataMeshDiscoverCatalog`, `DataMeshResolveDataProduct`, `DataMeshQueryResource`, `DataMeshExecuteSQL`, `DataMeshValidate`, `DataMeshGetLineage`, `DataMeshLineageGraph`), aplica el protocolo `call` → `DataMeshFreeString` y expone dos primitivas:
- `call(symbol, *args)`: desempaqueta `{success, data}` (retorna `data` o `None`).
- `call_raw(symbol, *args)`: retorna el sobre completo (usado por `GoCoreQueryEngine` para preservar mensajes de error).

`go_engine.py` deja de importar `ctypes` y delega en el bridge.

### 2. Extracción de infraestructura a adaptadores y casos de uso
- `adapters/catalog/llmstxt_catalog.py` — `LLMSTxtCatalogFetcher` + `parse_llms_txt` (parseo de índices federados).
- `adapters/workspace/local_workspace.py` — `LocalWorkspaceResolver` (tríada → ruta física; caché, proyectos hermanos, manifiestos locales/remotos).
- `adapters/web.py` — `fetch_text`/`safe_urlopen` (lectura uniforme `file://`, http(s) y rutas locales).
- `usecases/discover_catalog.py` — `DiscoverCatalogUseCase` (federación de catálogos).
- `usecases/query_resource.py` — `QueryResourceUseCase` (consulta tabular, Go primero, fallback Python).
- `usecases/validate_resource.py` — `ValidateResourceUseCase`.
- `usecases/resolve_dataproduct.py` — `ResolveDataProductUseCase` (frontmatter de nodos).
- `usecases/datapackage_io.py` — `load_datapackage` / `save_datapackage`.

### 3. `core.py` como composition root delgado
`DataMeshRuntime` solo instancia adaptadores, cablea dependencias y delega en los casos de uso. Su superficie pública no cambia funcionalmente: `discover`, `resolve`, `query`, `sql`, `validate`, `publish`, `align_semantics`, `discover_endpoint`, `harvest_ckan`, `create_datapackage`, `link_concept`, `explain_categories`, `lineage`, `get_lineage`.

### 3b. Fachada pública sin miembros privados
`datamesh/__init__.py` expone `resolve_resource(uri)` y `get_engine(name)`; `server.py`, `mcp_server.py` y las pruebas dejan de acceder a `_runtime._*`.

## Consecuencias
- **Positivo:** un solo punto de verdad para el contrato C-ABI; módulos de infraestructura probables en aislamiento; `core.py` pasa de ~1143 a ~400 líneas, casi todas firmas y docstrings (delegación pura), y queda libre de lógica de negocio; cero accesos a miembros privados del singleton desde adaptadores inbound.
- **Coste:** nuevos módulos y firmas de inyección; se actualizó `server.py`, `mcp_server.py`, `go_engine.py` y `tests/test_duckdb_sql.py`.
- No cambia la superficie pública (`datamesh.__all__`) ni los contratos JSON/CLI/MCP; sólo se **añaden** `resolve_resource` y `get_engine`.

## Referencias
- ADR 0001 (hexagonal), ADR 0006 (motor abstracto), ADR 0008 (Go core dominio / bindings borde).
- `docs/reference/ARQUITECTURA.md` §6 (Principio 6).
