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
