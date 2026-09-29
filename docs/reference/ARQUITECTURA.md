# Arquitectura de Referencia: DataMesh Core SDK (Go + Python + TypeScript)

## 1. Diagrama Hexagonal

```text
       +-----------------------------------------------------------+
       |                     DRIVING / INBOUND                     |
       |  [CLI Adapter]      [C-Shared / ctypes]    [WASM Adapter] |
       +-----------------------------------------------------------+
                                   |
                                   v
       +-----------------------------------------------------------+
       |                       INBOUND PORTS                       |
       |  - CatalogServicePort                                     |
       |  - DataProductServicePort                                 |
       |  - ConfigServicePort                                      |
       +-----------------------------------------------------------+
                                   |
                                   v
       +-----------------------------------------------------------+
       |                        USE CASES                          |
       |  - DiscoverCatalogUseCase                                 |
       |  - ResolveDataProductUseCase                              |
       |  - ConfigUseCase                                          |
       +-----------------------------------------------------------+
                                   |
                                   v
       +-----------------------------------------------------------+
       |                          DOMAIN                           |
       |  - DataProduct (Aggregate Root)                           |
       |  - Catalog, CatalogEntry                                  |
       |  - Manifest, Resource, Contract, Lineage                  |
       |  - Config, BaseConfig                                     |
       +-----------------------------------------------------------+
                                   |
                                   v
       +-----------------------------------------------------------+
       |                      OUTBOUND PORTS                       |
       |  - CatalogResolverPort                                    |
       |  - DataProductResolverPort                                |
       |  - StoragePort                                            |
       |  - ConfigLoaderPort                                       |
       +-----------------------------------------------------------+
                                   |
                                   v
       +-----------------------------------------------------------+
       |                    DRIVEN / OUTBOUND                      |
       |  [LLMSTxtResolver]  [NodeResolver]  [FileStorage] [Loader]|
       +-----------------------------------------------------------+
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
