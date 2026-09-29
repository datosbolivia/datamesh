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
       |  - ConfigLoaderPort                                                      |
       +--------------------------------------------------------------------------+
                                            |
                                            v
       +--------------------------------------------------------------------------+
       |                            DRIVEN / OUTBOUND                             |
       |  [LLMSTxtResolver]  [NodeResolver]  [FileStorage]  [QueryEngine]  [Loader]
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

