# ADR 0006: Abstracción Hexagonal del Motor de Consultas y Portabilidad Cross-Language (Go Core, DuckDB, In-Memory)

## Estado
Aceptado

## Contexto
El Formato de Conocimiento Abierto Federado (OKF / ODKF v0.2) requiere capacidades analíticas sobre conjuntos de datos heterogéneos (CSV, TSV, Parquet, JSON, JSONL).
Originalmente, la ejecución SQL estaba acoplada a la librería DuckDB en Python. Sin embargo:
1. El núcleo de lógica de dominio y protocolos de red de DataMesh SDK reside canónicamente en Go (`core-go/`), y debe ser compartido de forma idéntica entre múltiples bindings (Python ctypes/C-ABI, TypeScript WASM para navegadores, CLI nativo).
2. No todos los entornos de ejecución disponen de DuckDB o de compiladores de extensiones nativas C++ (por ejemplo, entornos serverless mínimos, navegadores sin WASM multithreading complejo o contenedores de bajo recurso).
3. Diferentes motores analíticos tienen compensaciones distintas: DuckDB sobresale en joins complejos y agregaciones OLAP masivas; motores tabulares puros en memoria destacan en arranque instantáneo, cero dependencias nativas y portabilidad universal; el núcleo en Go provee la base unificada de compilación y C-ABI.

Por tanto, se requiere un puerto abstracto de motor de consultas (`QueryEnginePort`) implementable tanto en Go (`core-go/ports/outbound/query.go`) como en los diferentes lenguajes cliente (`datamesh.ports.engine.QueryEnginePort`), permitiendo alternar motores sin modificar el código de los casos de uso ni la API de usuario (`datamesh.sql(...)`).

## Decisión

1. **Puerto de Motor de Consultas en Go Core (`outbound.QueryEnginePort`)**:
   - Define el contrato unificado: `Name() string`, `SupportsFormat(format string) bool`, `SupportsCrossFormatJoin() bool`, `Execute(...)`, `ExecuteSQL(...)`, `RegisterTable(...)`.
   - `QueryEngineRegistryPort`: Permite registrar motores (`RegisterEngine`) y seleccionar el motor óptimo según los formatos involucrados (`SelectEngine`).
   - Implementación de motor de referencia en Go: `InMemTabularQueryEngine` (`adapters/outbound/engine/csv_query_engine.go`), capaz de procesar proyecciones, filtros y límites sobre CSV/TSV/JSON.
   - Caso de uso ampliado: `QueryDataProductUseCase.ExecuteSQLWithOptions(...)` que acepta `QueryOptions` con mapeo de tablas explícito y selección de motor.

2. **Exposición Cross-Language en Go Core (C-Shared ABI y WebAssembly)**:
   - C-Shared (`core-go/adapters/inbound/cshared/exports.go`): Exporta `DataMeshExecuteSQL(sqlQuery *C.char, optionsJSON *C.char) *C.char` para consumo por `ctypes` en Python o `ffi` en Node.js.
   - WASM (`core-go/adapters/inbound/wasm/main_wasm.go`): Exporta `DataMesh.executeSQL(sqlQuery, optionsJSON)` devolviendo una Promesa de JavaScript para portales web (ej. `catalogo-datamesh`).

3. **Puerto y Adaptadores en Python (`datamesh.ports.engine` y `datamesh.adapters.engine`)**:
   - `QueryEnginePort`: Clase base abstracta (`ABC`) que estandariza `name`, `supports_format`, `supports_cross_format_join`, `execute_sql` y `register_table`.
   - `DuckDBQueryEngine`: Motor principal OLAP analítico con soporte para DuckDB nativo, virtual views y escaneo columnar paralelo de Parquet/CSV.
   - `InMemTabularQueryEngine`: Motor en memoria en Python puro para escaneos, proyecciones, filtros de igualdad y límites sin requerir binarios nativos externos.
   - `GoCoreQueryEngine`: Adaptador que delega la ejecución de consultas a la biblioteca compilada del núcleo de Go (`libdatamesh.so`) a través de la C-ABI.

4. **Fachada Unificada y Selección de Motor**:
   - La API de alto nivel `datamesh.sql(query_str, table_mapping=None, engine=None)` y el CLI `datamesh sql "..." --engine [duckdb|inmem|go]` permiten al usuario o agente seleccionar el motor deseado o confiar en el default analítico (`duckdb`).

## Consecuencias
- Desacoplamiento total entre la lógica de resolución de catálogos/tríadas y los motores de ejecución analítica.
- Go Core consolida su rol de fuente canónica de verdad y puente de portabilidad compartida.
- Ejecución garantizada en cualquier entorno: alta velocidad con DuckDB cuando está disponible, o fallback universal in-memory sin dependencias nativas.
