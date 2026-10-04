# ADR 0008: Arquitectura Hexagonal Canónica — Go Core como Dominio y Bindings como Adaptadores de Borde

## Estado
Aceptado

## Contexto
El ecosistema DataMesh SDK proporciona capacidades analíticas y de federación en múltiples plataformas y lenguajes:
1. **Go Core (`core-go/`)**: El núcleo fundacional de alto rendimiento, compilable como binario estático CLI, biblioteca compartida C-ABI (`libdatamesh.so` para C/C++, Rust, Python) y WebAssembly (`main_wasm.go` para ejecución cliente en el navegador).
2. **Python Bindings (`bindings/python/`)**: Fachada estilo Pandas / DuckDB (`import datamesh as dm`) para científicos de datos, analistas y agentes de IA con integración MCP.
3. **TypeScript Bindings (`bindings/typescript/`)**: Cliente isomórfico para portales estáticos (Astro), paneles analíticos y navegadores web (`@datosbolivia/datamesh-client`).

Anteriormente, existía riesgo de divergencia lógica y duplicación funcional:
- Lógica de resolución de esquemas y heurísticas de búsqueda que podían bifurcarse entre Python, TypeScript y Go.
- Nombres de métodos y herramientas divergentes (`executeSQL` vs `datamesh_sql_query`, herramientas MCP dispares entre servidores).
- Tratamiento inconsistente de URIs canónicas, URLs directas (`https://.../datasets/<ds>/<res>.csv`) y sintaxis con barras (`catalogo/dataset/recurso`).

Conforme al skill rector `hexagonal-architecture` y las directrices de `keep-it-simple` y `python-code-style`, la arquitectura debe establecer inequívocamente:
- **Go Core** define y gobierna el Dominio Ubicuo, las Entidades, los Puertos Inbound/Outbound y la Orquestación de Casos de Uso.
- **Bindings** actúan como Adaptadores de Borde (Inbound Drivers o Outbound Driven Adapters) adaptando los contratos canónicos a las ergonomías idiomáticas de cada lenguaje sin duplicar la lógica de negocio ni las reglas de dominio.

## Decisión

### 1. Invariantes de Dominio y Puertos Canónicos en Go Core
Go Core define la única fuente de verdad normativa para el modelo de dominio:
- **Dominio (`core-go/domain/`)**:
  - `ResourceTriad`: Representación canónica `[catalog:]dataset:resource`. Métodos `ParseTriad`, `ExtractTriadsFromSQL` y parser universal soportando:
    - Tríadas con dos puntos: `catalogo:dataset:resource` y `dataset:resource`.
    - Tríadas con barras: `catalogo/dataset/recurso` y `dataset/recurso`.
    - Esquemas sovereign: `datamesh://[catalog/]dataset/resource`.
    - URLs directas: `https://datosbolivia.github.io/datasets/cartera-creditos/creditos.csv`.
  - `DataProduct`: Aggregate Root OKF / ODKF v0.2 con `Validate()`.
  - `Catalog` y `CatalogEntry`: Modelo federado multicatálogo.
  - `PackageManifest`: Abstracción agnóstica de metadatos (Frictionless, OKF Markdown, LLMs.txt).
  - `QueryRequest`, `SQLQueryRequest` y `QueryResult`: DTOs inmutables de consulta tabular y SQL.

- **Puertos de Entrada / Inbound (`core-go/ports/inbound/`)**:
  - `CatalogServicePort`: `DiscoverAll`, `Discover`, `Search`.
  - `DataProductServicePort`: `Resolve`, `Validate`.
  - `QueryServicePort`: `Query`, `ExecuteSQL`.
  - `ConfigServicePort`: `GetConfig`.

- **Puertos de Salida / Outbound (`core-go/ports/outbound/`)**:
  - `CatalogResolverPort`, `DataProductResolverPort`, `StoragePort`, `QueryEnginePort`, `ManifestParserPort`, `UnifiedMetadataReaderPort`, `TriadResolverPort`, `ConfigLoaderPort`.

### 2. Fachada Unificada de 5 Operaciones en Todos los Bindings
Tanto los bindings de alto nivel como los adaptadores de borde exponen exactamente las mismas 5 operaciones canónicas:
1. `discover(catalog_url?)`: Descubrimiento y federación multicatálogo.
2. `search(keyword, catalog_url?)`: Búsqueda federada por palabra clave en título, descripción o dominio.
3. `get(uri_or_url)`: Resolución y validación de manifest y descripción de Data Product OKF v0.2.
4. `query(resource_uri, filters?, limit?)`: Proyección y filtrado tabular en memoria.
5. `sql(sql_query, options?)`: Motor ANSI SQL sobre tríadas canónicas y URLs directas con normalización columnar.

### 3. Protocolo MCP Idéntico entre Lenguajes
Los adaptadores de protocolo MCP (JSON-RPC 2.0) en Go Core (`core-go/adapters/inbound/cli/serve.go`) y Python (`bindings/python/datamesh/server.py` / `mcp_server.py`) exponen el mismo conjunto de 5 herramientas estandarizadas:
- `datamesh_discover_catalogs`
- `datamesh_search_catalog`
- `datamesh_get_dataproduct`
- `datamesh_query_resource`
- `datamesh_sql_query`

### 4. Adaptadores de Infraestructura Especializados por Lenguaje
Cada binding aporta implementaciones de los puertos outbound según su ecosistema:
- **Python**:
  - `DuckDBQueryEngine`: Motor columnar OLAP ANSI SQL que implementa `QueryEnginePort`. Incluye fallback resiliente: si la creación de una vista DuckDB remota falla por error de certificado SSL gubernamental, descarga automáticamente el archivo mediante `HttpAdapter` a la caché temporal local con `ssl.CERT_NONE` y registra la vista apuntando a la copia local.
  - `LocalStorageManager`: Implementación de `StoragePort` sobre `~/.datamesh/cache`.
  - `GitHubAdapter`, `KaggleAdapter`, `LocalFileAdapter`, `HttpAdapter`: Adaptadores de resolución multiproveedor.
- **TypeScript / Web**:
  - `DuckDBBrowserEngine`: Implementación en WebAssembly sobre DuckDB-WASM para el navegador.
  - `InMemTabularQueryEngine`: Motor de proyección CSV en memoria para entornos cliente ligeros.
  - `CORSProxy`: Formateo y retransmisión de solicitudes web con `formatProxiedUrl`.

## Consecuencias
- **Cero divergencia conceptual**: Las reglas de parsing de tríadas, validación de Data Products y contratos sintácticos emanan del dominio en Go Core.
- **Ergonomía idiomática preservada**: En Python se usa `import datamesh as dm; df = dm.sql(...)`; en TypeScript `import { datamesh, sql } from '@datosbolivia/datamesh-client'`; en Go `datamesh sql "..."`.
- **Mantenibilidad y testabilidad**: Casos de uso desacoplados de detalles de red o almacenamiento; se testean con mocks/fakes en memoria.
