# Arquitectura de Referencia: DataMesh Core SDK (Go + Python + TypeScript)

## 1. Diagrama Hexagonal

```text
       +--------------------------------------------------------------------------+
       |                            DRIVING / INBOUND                             |
       |  [CLI Adapter]      [C-Shared / ctypes]    [WASM Adapter]    [MCP Server] |
       +--------------------------------------------------------------------------+
                                            |
                                            v
       +--------------------------------------------------------------------------+
       |                              INBOUND PORTS                               |
       |  - CatalogServicePort (DiscoverAll, Discover, Search)                    |
       |  - DataProductServicePort (Resolve, Validate)                            |
       |  - QueryServicePort (Query)                                              |
       |  - ConfigServicePort (GetConfig)                                         |
       +--------------------------------------------------------------------------+
                                            |
                                            v
       +--------------------------------------------------------------------------+
       |                               USE CASES                                  |
       |  - DiscoverCatalogUseCase (Multi-catalog concurrent federation)          |
       |  - ResolveDataProductUseCase (OKF v0.2 frontmatter parser)               |
       |  - QueryDataProductUseCase (In-memory projection & filtering)            |
       |  - ConfigUseCase (Hierarchical loader)                                   |
       +--------------------------------------------------------------------------+
                                            |
                                            v
       +--------------------------------------------------------------------------+
       |                                 DOMAIN                                   |
       |  - DataProduct (Aggregate Root), Manifest, Resource, Contract, Lineage   |
       |  - Catalog, CatalogEntry (with CatalogSource attribution)                |
       |  - QueryRequest, QueryResult                                             |
       |  - Config, BaseConfig (CatalogURLs list, Adapter options)                 |
       +--------------------------------------------------------------------------+
                                            |
                                            v
       +--------------------------------------------------------------------------+
       |                             OUTBOUND PORTS                               |
       |  - CatalogResolverPort                                                   |
       |  - DataProductResolverPort                                               |
       |  - StoragePort                                                           |
       |  - QueryEnginePort                                                       |
       |  - ManifestParserPort                                                    |
       |  - UnifiedMetadataReaderPort                                             |
       |  - ConfigLoaderPort                                                      |
       +--------------------------------------------------------------------------+
                                            |
                                            v
       +--------------------------------------------------------------------------+
       |                            DRIVEN / OUTBOUND                             |
       |  [UnifiedMetadataReader] (DataPackage JSON/YAML/YML, OKF Markdown, LLMs) |
       |  [FileStorage]  [InMemQueryEngine]  [ConfigLoader]                       |
       +--------------------------------------------------------------------------+
```

## 2. Esquema de Configuración

El SDK implementa una cascada de configuración estricta:

1. **Variables de Entorno (Máxima prioridad)**:
   - Base: `DATAMESH_{{BASE_VAR}}` (ej. `DATAMESH_CATALOG_URL`, `DATAMESH_STORAGE_PATH`, `DATAMESH_TIMEOUT`, `DATAMESH_LOG_LEVEL`)
   - Adaptadores: `DATAMESH__{{ADAPTADOR}}_{{VAR}}` (ej. `DATAMESH__KAGGLE_KEY`, `DATAMESH__GITHUB_TOKEN`)
2. **Archivos de Configuración**:
   - `datamesh.json` o `datamesh.yaml` / `datamesh.yml`
3. **Valores por Defecto (Fallback)**:
   - `catalog_url`: `https://datosbolivia.github.io/llms.txt`
   - `storage_path`: `.datamesh/cache`
   - `timeout`: `30s`
   - `log_level`: `info`

## 3. Motor SQL DuckDB y Normalización de Heterogeneidad

El adaptador `DuckDBQueryEngine` proporciona capacidades completas de analítica OLAP ANSI SQL sobre recursos federados:
- **Resolución Canónica:** Soporta sintaxis de 2 partes (`dataset:resource`) y 3 partes (`catalogo:dataset:resource`), así como nombres slugificados generados en gráficos.
- **Descubrimiento de Manifiestos Datapackage:** Localiza y analiza archivos `datapackage.yaml`, `datapackage.yml` y `datapackage.json` en nodos locales (`knowledge/nodes/`) o vía HTTP federado.
- **Acceso Híbrido Cero-Latencia / Streaming:** Prioriza copias locales en repositorios de trabajo y caché (`~/datamesh/cache`), recurriendo de manera transparente a URLs remotas con `httpfs` (normalizando URLs de GitHub a `raw.githubusercontent.com`).
- **Compatibilidad JSON:** Normalización recursiva de tipos de DuckDB (`Decimal`, `datetime`, `UUID`) para garantizar salida serializable limpia en JSON a través de CLI y MCP.

## 4. Módulos Hexagonales en Python (`bindings/python/datamesh/`)

El runtime de Python implementa Arquitectura Hexagonal estricta con inversión de dependencias hacia el dominio:

```text
datamesh/
├── domain/                  # Entidades y Value Objects puros (inmutables, sin frameworks)
│   └── models.py            # StorageConfig, ResourceDescriptor, ResolvedResource, CacheEntryMetadata
├── ports/                   # Contratos e Interfaces abstractas
│   ├── storage.py           # StoragePort (operaciones de caché temporal y persistente)
│   ├── resolver.py          # ResourceAdapterPort, ConfigPort
│   └── engine.py            # QueryEnginePort (abstracción agnóstica de motor de consultas)
├── adapters/                # Implementaciones tecnológicas
│   ├── storage/
│   │   └── local_storage.py # LocalStorageManager (~/datamesh/cache/, escrituras atómicas, metadata.json)
│   ├── config/
│   │   └── file_config.py   # FileConfigAdapter (~/datamesh/config.yaml)
│   ├── resolvers/           # Adaptadores multiproveedor
│   │   ├── local_file.py    # LocalFileAdapter (archivos locales, proyectos hermanos)
│   │   ├── github.py        # GitHubAdapter (streaming CDN raw.githubusercontent.com)
│   │   ├── kaggle.py        # KaggleAdapter (API oficial Kaggle ~/.kaggle/kaggle.json)
│   │   └── http.py          # HttpAdapter (endpoints web y Google Sheets)
│   └── engine/
│       ├── duckdb_engine.py # DuckDBQueryEngine (motor OLAP columnar sobre caché local)
│       ├── inmem_engine.py  # InMemTabularQueryEngine (motor en memoria puro sin binarios nativos)
│       └── go_engine.py     # GoCoreQueryEngine (delegación C-ABI hacia libdatamesh.so)
├── usecases/                # Orquestación de aplicación
│   └── resolve_resource.py  # ResolveAndCacheResourceUseCase
├── core.py                  # Composition Root (instancia adaptadores y cablea dependencias)
├── cli.py                   # Inbound Adapter: CLI
└── mcp_server.py            # Inbound Adapter: Protocolo MCP JSON-RPC
```

## 5. Unificación de Manifiestos y Formatos de Lectura en Go Core (`core-go/`)

Para desacoplar el núcleo de formatos específicos y garantizar cero dependencias de terceros en CGO y WASM:

- **Dominio (`core-go/domain/package.go`):** Entidad `PackageManifest` y tipos `PackageResource`, que normalizan cualquier especificación de metadatos abierta a una representación estándar en memoria, soportando resolución tolerante a fallos mediante `FindResource` y normalización fonética / slugificada (`Slugify`).
- **Puerto de Parser Abstracto (`core-go/ports/outbound/package_reader.go`):** Interfaz `ManifestParserPort` que desacopla la lectura física de archivos del análisis sintáctico. Permite incorporar nuevos estándares (DCAT-AP, RO-Crate, CKAN) simplemente registrando nuevos parsers sin modificar los casos de uso.
- **Lector Unificado (`core-go/adapters/outbound/manifests/unified_reader.go`):** Implementa `UnifiedMetadataReaderPort` e inspecciona directorios de nodos y catálogos en orden de precedencia:
  1. `datapackage.json` (Frictionless JSON vía `DataPackageJSONParser`)
  2. `datapackage.yaml` y `datapackage.yml` (Frictionless YAML vía `DataPackageYAMLParser` nativo sin librerías externas)
  3. `index.md` (Open Knowledge Format v0.2 vía `OKFMarkdownParser`)
  4. `llms.txt` y `llms-full.txt` (Índices federados vía `LLMsTxtParser`)
- **Resolución Determinista de Tríadas (`TriadResolverPort`):** Vincula las tríadas canónicas `[catalogo:dataset:resource]` directamente al recurso físico subyacente tanto en C-ABI (`libdatamesh.so`) como en WebAssembly para navegadores web.

## 6. Separación Canónica: Go Core como Autoridad de Dominio y Bindings como Adaptadores de Borde

En cumplimiento del patrón Ports & Adapters y las directrices de `hexagonal-architecture`:

```text
+---------------------------------------------------------------------------------------------------------+
|                                      GO CORE (DOMAIN & USE CASES)                                       |
|  - Domain: ResourceTriad (Colon/Slash/URL syntax), DataProduct, PackageManifest                         |
|  - Inbound Ports: CatalogServicePort, DataProductServicePort, QueryServicePort                           |
|  - Outbound Ports: TriadResolverPort, QueryEnginePort, StoragePort, ManifestParser                       |
|  - Use Cases: DiscoverCatalog, ResolveDataProduct, QueryDataProduct, Config                              |
+---------------------------------------------------------------------------------------------------------+
                                                     |
               +-------------------------------------+-------------------------------------+
               |                                     |                                     |
               v                                     v                                     v
+-----------------------------+       +-------------------------------+       +-----------------------------+
|     PYTHON ADAPTER LAYER    |       |    TYPESCRIPT / WASM ADAPTER  |       |       R ADAPTER LAYER       |
| - Inbound: Python Facade dm |       | - Inbound: TS Client / Hooks  |       | - Inbound: R Facade dm_*    |
| - Outbound: DuckDBEngine    |       | - Outbound: DuckDBBrowser     |       | - Outbound: Go C-ABI dynload|
|   (with unverified SSL      |       |   (WebAssembly Engine)        |       | - Outbound: DuckDB R driver |
|    government fallback)     |       | - Outbound: InMemTabular      |       | - Pure R HTTP Fallback      |
| - Outbound: LocalStorageMgr |       | - Composition: useDataMesh()  |       | - Composition: .onLoad()    |
| - Composition: core.py      |       |   (isomorphic web/Node)       |       |   (CRAN-compliant package)  |
+-----------------------------+       +-------------------------------+       +-----------------------------+
```

### Principios Rectores:
1. **Autoridad de Dominio en Go Core**: Ningún binding redefine reglas de negocio ni heurísticas de validación de esquemas OKF v0.2. Las tríadas canónicas (`cat:ds:res`), sintaxis de rutas con barras (`cat/ds/res`) y URLs de datasets (`https://.../datasets/ds/res.ext`) son procesadas uniformemente.
2. **Fachada Unificada de 5 Métodos**:
   - `discover(catalog_url?)`
   - `search(keyword, catalog_url?)`
   - `get(uri_or_url)`
   - `query(resource_uri, filters?, limit?)`
   - `sql(sql_query, options?)`
3. **Paridad de Herramientas MCP**: Tanto el servidor MCP de Go (`datamesh serve`) como el de Python (`datamesh.mcp_server`) exponen las mismas 5 herramientas con idénticos contratos de entrada y salida JSON-RPC 2.0.
4. **Resiliencia de Infraestructura en Adaptadores de Borde**:
   - Fallos de certificados SSL de portales de gobierno son absorbidos a nivel de adaptador (`DuckDBQueryEngine` -> `HttpAdapter` con `ssl.CERT_NONE` hacia temporal cache) sin contaminar los casos de uso ni la capa de dominio.



