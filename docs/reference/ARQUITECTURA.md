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

**Motor fallback puro Go (`InMemTabularQueryEngine`):** cuando no hay DuckDB (CLI/MCP de Go Core), el camino SQL sólo soporta el subconjunto honesto `SELECT <cols|*> FROM <tabla> [WHERE col = valor [AND ...]] [LIMIT n]` sobre **una única** tabla local CSV/TSV. Las construcciones fuera de ese subconjunto (agregaciones, funciones, `JOIN`, `GROUP BY`, `ORDER BY`, subconsultas) se **rechazan con un error explícito** en lugar de devolver resultados parciales o incorrectos (`core-go/domain/sqlsubset.go`). La selección entre motores registrados (`QueryEngineRegistry.SelectEngine`) es determinista (orden por nombre), no dependiente del orden de iteración del `map`. Autoridad normativa: **ADR 0019**.

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
│   │   ├── local_storage.py # LocalStorageManager (~/datamesh/cache/, escrituras atómicas, metadata.json)
│   │   └── zip_extractor.py # extract_zip_tabular_resource (desempaquetado selectivo de microdatos tabulares en ZIP)
│   ├── config/
│   │   └── file_config.py   # FileConfigAdapter (~/datamesh/config.yaml)
│   ├── resolvers/           # Adaptadores multiproveedor
│   │   ├── local_file.py    # LocalFileAdapter (archivos locales, proyectos hermanos)
│   │   ├── github.py        # GitHubAdapter (streaming CDN raw.githubusercontent.com)
│   │   ├── kaggle.py        # KaggleAdapter (API oficial Kaggle ~/.kaggle/kaggle.json)
│   │   └── http.py          # HttpAdapter (endpoints web y Google Sheets)
│   ├── engine/
│   │   ├── duckdb_engine.py # DuckDBQueryEngine (motor OLAP columnar sobre caché local y zips extraídos)
│   │   ├── inmem_engine.py  # InMemTabularQueryEngine (motor en memoria puro sin binarios nativos)
│   │   └── go_engine.py     # GoCoreQueryEngine (delegación C-ABI hacia libdatamesh.so)
│   ├── catalog/
│   │   └── llmstxt_catalog.py # LLMSTxtCatalogFetcher (parseo de índices federados llms.txt)
│   ├── workspace/
│   │   └── local_workspace.py # LocalWorkspaceResolver (tríada -> ruta física: caché y proyectos hermanos)
│   ├── go_bridge.py         # GoCoreBridge (único puente ctypes/C-ABI hacia libdatamesh.so)
│   └── web.py               # fetch_text / safe_urlopen (lectura file://, http(s) y local)
├── usecases/                # Orquestación de aplicación
│   ├── resolve_resource.py  # ResolveAndCacheResourceUseCase (caché + adaptadores; lookup de datapackage delegado a LocalWorkspaceResolver)
│   ├── discover_catalog.py  # DiscoverCatalogUseCase (federación de catálogos llms.txt)
│   ├── query_resource.py    # QueryResourceUseCase (consulta tabular CSV/JSON, fallback puro Python)
│   ├── validate_resource.py # ValidateResourceUseCase (validación OKF/ODKF, fallback Python)
│   ├── resolve_dataproduct.py # ResolveDataProductUseCase (frontmatter de nodos, fallback Python)
│   └── datapackage_io.py     # load_datapackage / save_datapackage (YAML/JSON)
├── core.py                  # Composition Root delgado (cablea dependencias; sin lógica de negocio)
├── cli.py                   # Inbound Adapter: CLI
├── server.py                # Inbound Adapter: Sovereign HTTP Server (REST + Proxy + MCP)
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
2. **Fachada Unificada**:
   - `discover(catalog_url?)`
   - `discover_endpoint(target_url)`
   - `search(keyword, catalog_url?)`
   - `get(uri_or_url)`
   - `query(resource_uri, filters?, limit?)`
   - `sql(sql_query, options?)`
   - `publish(dataset_path, targets?, options?)`
    - `align_semantics(datapackage_or_schema)`
    - `harvest_ckan(ckan_url, ...)`
    - `create_datapackage(name, title?, files?, resources?, output_file?, sources?, transformations?, lineage?)`
    - `link_concept(datapackage, resource, column, concept_ref?, value_mappings?)`
    - `explain_categories(datapackage, output_concepts_dir)`
    - `lineage(target?, search_dirs?, catalog_url?)`
    - `get_lineage(dataset_id_or_path, search_dirs?, catalog_url?)`
3. **Paridad de Herramientas MCP**: Servidores MCP exponen herramientas canónicas (`datamesh_discover_catalogs`, `datamesh_search_catalog`, `datamesh_get_dataproduct`, `datamesh_query_resource`, `datamesh_sql_query`, `datamesh_discover_endpoint`, `datamesh_harvest_ckan`, `datamesh_get_lineage`) con idénticos contratos JSON-RPC 2.0.

4. **Resiliencia de Infraestructura en Adaptadores de Borde**:
   - Fallos de certificados SSL de portales de gobierno son absorbidos a nivel de adaptador (`DuckDBQueryEngine` -> `HttpAdapter` con `ssl.CERT_NONE` hacia temporal cache) sin contaminar los casos de uso ni la capa de dominio.

5. **Aislamiento Estricto de Capas (ADR 0017)**:
   - **Dominio**: concentra toda regla de negocio. Las reglas normativas OKF/ODKF (`ValidateConceptContent`, `ValidateBundle`, `ValidateTriad`, SHA-256, SKOS) y la reconstrucción `CKANPackage -> PackageManifest` (`ReconstructManifestFromCKAN`) residen en `core-go/domain/`.
   - **Puertos:** los adaptadores outbound dependen exclusivamente de puertos (`UnifiedMetadataReaderPort`, `CKANClientPort`), nunca de otro adaptador. Los casos de uso no acceden a detalles privados de otros casos de uso; dependen de puertos y del dominio.
   - El composition root (`cli/main.go`, `cshared/exports.go`, `wasm/main_wasm.go`) es el único lugar que conoce e inyecta adaptadores concretos.

6. **Composition Root Delgado en Python (ADR 0018)**:
   - `datamesh/core.py` (`DataMeshRuntime`) se limita a instanciar y cablear dependencias; no contiene lógica de ctypes, parseo de catálogos, resolución de workspace ni fallbacks tabulares.
   - El **único** puente ctypes/C-ABI es `datamesh/adapters/go_bridge.py` (`GoCoreBridge`): carga `libdatamesh.so`, cablea símbolos y aplica el protocolo `call`/`free`/`decode`.
   - La lógica extraída vive en adaptadores (`llmstxt_catalog.py`, `local_workspace.py`, `web.py`) y casos de uso (`discover_catalog.py`, `query_resource.py`, `validate_resource.py`, `resolve_dataproduct.py`, `datapackage_io.py`).
   - La fachada pública expone `resolve_resource()` y `get_engine()`; ningún consumidor accede a miembros privados de `_runtime`.


## 7. Ingesta de Catálogos CKAN, Autenticación (Keycloak/OAuth2/APIKey) y Descubrimiento Well-Known

```text
+-----------------------------------------------------------------------------------------------+
|                                      INGESTA & HARVESTING                                     |
|  [CLI: harvest-ckan, discover]      [dm.harvest_ckan()]       [dm.discover_endpoint()]        |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                                        INBOUND PORTS                                          |
|  - HarvesterServicePort (DiscoverWellKnown, HarvestCKAN, ReconstructOKF)                      |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                                          USE CASES                                            |
|  - DiscoverWellKnownUseCase (Sondeo /.well-known/datamesh.json y fallback CKAN status_show)   |
|  - HarvestCKANUseCase (Ingesta Action API v3, reconstrucción datapackage.yaml e index.md)    |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                                     DOMAIN VALUE OBJECTS                                      |
|  - WellKnownDiscovery (SchemaVersion, CatalogMetadata, AuthConfiguration, Capabilities)       |
|  - CKANPackage, CKANResource, CKANDataStoreField, CKANHarvestResult                          |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                                        OUTBOUND PORTS                                         |
|  - WellKnownResolverPort (FetchWellKnown)                                                     |
|  - CKANClientPort (SearchPackages, GetPackage, GetDataStoreSchema)                            |
|  - AuthProviderPort (GetAuthHeaders, GetAuthType)                                             |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                                     OUTBOUND ADAPTERS                                         |
|  - WellKnownResolverAdapter (HTTP / JSON resolver con fallback heurístico)                    |
|  - CKANClientAdapter (Action API v3 client)                                                   |
|  - KeycloakAuthAdapter (OAuth2 Client Credentials con JWT in-memory cache)                    |
|  - APIKeyAuthAdapter / BearerTokenAuthAdapter (Static token headers)                          |
+-----------------------------------------------------------------------------------------------+
```

## 8. Construcción de Manifiestos e Interoperabilidad Semántica (`CreateDataPackage` & `LinkKnowledgeConcepts`)

```text
+-----------------------------------------------------------------------------------------------+
|                                   MANIFIESTOS Y SEMÁNTICA                                     |
|  [CLI: package-create, link, explain]    [dm.create_datapackage()]   [dm.explain_categories()] |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                                          USE CASES                                            |
|  - CreateDataPackageUseCase: Inferencia DuckDB/CSV/Parquet de esquemas e inspección de ZIPs. |
|  - LinkKnowledgeConceptsUseCase: Enlace de columnas y categorías a conceptos SKOS / OKF v0.2. |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                                     DOMAIN VALUE OBJECTS                                      |
|  - KnowledgeConceptDoc, CategoryConceptMapping, DataPackageBuildResult                        |
+-----------------------------------------------------------------------------------------------+
```

## 9. Trazabilidad Criptográfica, Grafo de Proveniencia y Linaje (`DatasetLineageUseCase`)

```text
+-----------------------------------------------------------------------------------------------+
|                                    PROVENIENCIA Y LINAJE                                      |
|  [CLI: datamesh lineage]       [dm.lineage()]       [dm.get_lineage()]       [MCP Tool]       |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                                          USE CASES                                            |
|  - DatasetLineageUseCase: Escaneo de manifiestos, construcción de grafo DAG,                |
|    resolución recursiva upstream/downstream y generación Mermaid / ASCII / JSON.              |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                                     DOMAIN VALUE OBJECTS                                      |
|  - LineageSource (Name, Dataset, Resource, URL, Hash)                                         |
|  - LineageTransformation (Tool, Type, Hash, Description, Query)                               |
|  - LineageInfo (DatasetID, Version, Sources, Transformations, WasDerivedFrom)                 |
|  - LineageNode, LineageEdge, LineageGraph (Upstream, Downstream, to_mermaid, to_ascii)         |
+-----------------------------------------------------------------------------------------------+
```

## 10. Interoperabilidad Soberana de Metadatos (MEFP + Lakequery + CKAN + DataPackage)

```text
+-----------------------------------------------------------------------------------------------+
|                                    CKAN / PORTAL MEFP                                         |
|  [ckanext-mefp Web UI]   [ckanext-metadata Audit/Quality]   [ckanext-lakequery DuckDB S3]     |
+-----------------------------------------------------------------------------------------------+
       |                                      |                                      |
       | (/dataset/<id>/datapackage.{json,yaml})| (/api/action/metadata_datapackage_show)    |
       v                                      v                                      v
+-----------------------------------------------------------------------------------------------+
|                       CANONICAL FRICTIONLESS DATAPACKAGE / OKF v0.2                           |
|  - Dialecto Unificado: string, integer, number, boolean, date, datetime, object, array       |
|  - Dimensiones: row_count/filas, columnas, fecha_minima, fecha_maxima, frecuencia_dias        |
|  - Gobernanza: x-policy (zero_microdata, allow_all, deny)                                     |
|  - Ejecución Distribuida: lakequery spec { enabled, storage: {backend, bucket, key} }        |
|  - Esquema Tabular: schema: { fields: [{name, type, title, description, unit}] }              |
+-----------------------------------------------------------------------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------------------+
|                                     DATAMESH-SDK CORE                                         |
|  - CKANClientAdapter / HarvestCKANUseCase: Ingesta enriquecida sin pérdida semántica.        |
|  - DuckDB Query Engine: Ejecución analítica federada sobre URLs, S3, o archivos locales.     |
+-----------------------------------------------------------------------------------------------+
```

## 11. Pila Ontológica, Contratos Distribuidos y Gobernanza Epistémica (ADR 0014 & ADR 0015)

```text
+-----------------------------------------------------------------------------------------------+
|                    CAPA 4: INTELIGENCIA (Agentes Model Context Protocol - MCP)                |
|  [Razonamiento cruzado]  [Consultas analíticas sin alucinación]  [Falsabilidad Popperiana]    |
+-----------------------------------------------------------------------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------------------+
|                    CAPA 3: CONOCIMIENTO (Epistemología, Paradatos y Validación)               |
|  - Roles Epistémicos: emitter (productor + firma digital) y attester (validador + dictamen)  |
|  - Paradatos Narrativos: Metodología, supuestos de medición, sesgos y limitaciones en Body    |
|  - Falsabilidad Algorítmica: status (draft, stable, verified, refuted), supersedes: <uri>     |
+-----------------------------------------------------------------------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------------------+
|                    CAPA 2: INFORMACIÓN (Metadatos y Contratos Sintácticos)                    |
|  - Pluralidad: Contratos Inline vs By-Reference (contracts: [{type, ref: ./datapackage.yaml}])|
|  - Semántica Ontológica: skos (Wikidata, Schema.org), dimensiones analíticas                  |
+-----------------------------------------------------------------------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------------------+
|                    CAPA 1: DATOS (La Evidencia Bruta / Zero-Microdata)                        |
|  - Microdatos Distribuidos: Parquet, CSV, S3, Lakehouses, APIs REST, CKAN Datastore           |
|  - Direccionamiento Canónico: odkf://<namespace>/<catalog>/<dataset>[:<version>]               |
|  - Adaptadores Desacoplados: LocalFileAdapter, HttpAdapter, GitHubAdapter, KaggleAdapter      |
+-----------------------------------------------------------------------------------------------+
```


## 12. Ingesta As-Is y ODKF como Hub de Exportación (ADR 0013)

El motor debe encontrar metadatos *tal y como están publicados* (sin depender del well-known) y convertirlos al modelo ODKF canónico, y desde ODKF exportar a otros estándares. Autoridad normativa: **ADR 0013**.

- **Vía conformante:** `/.well-known/datamesh.json` (ver §7) resuelve el tipo de backend y se delega en el puerto idiomático (`ckan`, `okf`, `git`, `dcat`).
- **Vía as-is:** si no hay well-known, `AsIsIngestUseCase` recorre la cadena de sondeo (ADR 0013): `llms.txt`/`llms-full.txt`, `datapackage.json`/`.yaml`/`.yml` (parsers registrados en `UnifiedMetadataReaderPort`), `index.md` OKF y, en fallback, `package_show`/`status_show` de CKAN via capa anticorrupción (`HarvestCKANUseCase.ReconstructOKF`).
- **Elevación a ODKF:** cada manifiesto intermedio (Capa 2 Información) se normaliza a `DataProduct` canónico (Capa 3 Conocimiento) con invariantes (título, tipo, dimensiones) en el límite del dominio.
- **Exportación hub (dominio puro):** `core-go/domain/knowledge_export.go` serializa `DataProduct` a:
  - CKAN/Frictionless DataPackage JSON (`ToCKANDataPackageJSON`, punta a puente `/dataset/<id>/datapackage.json` de ADR 0012).
  - W3C DCAT-AP JSON-LD (`ToDCATJSON`, catalog de tipo `dcat`).
  - Nuevos destinos = nuevo convertidor en dominio + (opcionalmente) nuevo `ManifestParserPort` para su re-ingesta.
- **Puerto:** `Inbound.InteroperabilityServicePort` (ingestar, exportar CKAN, exportar DCAT); caso de uso de referencia: **CU-20** en `docs/reference/CASOS_DE_USO.md`.

## 13. Perímetro de Seguridad (ADR 0016)

Autoridad normativa: **ADR 0016**. La capa de entrada (HTTP REST, proxy CORS y MCP, en Python y Go) opera bajo una política **default-deny** para SSRF, TLS y lectura local:

| Superficie | Política | Aplica en |
| --- | --- | --- |
| Destinos de reenvío (`/proxy`, `read_resource`, fetch de `query_resource`) | Solo `http(s)`; se bloquean hosts que resuelven a loopback, RFC 1918, link-local, multicast, reservados o no especificados | `datamesh/net.py` (Python), `core-go/adapters/inbound/cli/security.go` (Go) |
| Verificación TLS | Estricta por defecto; fallback `CERT_NONE` solo con `DATAMESH_INSECURE_TLS=1` y solo ante errores de certificado | `datamesh.net.open_url` |
| Referencias de recursos en MCP | Solo `http(s)` o tríadas canónicas; se rechazan rutas absolutas, `file://`, `..`, unidades Windows y UNC | `mcp_server.py`, `serve.go` |
| SQL con datos del operador | Literales e identificadores escapados (`sql_string_literal`, `sql_identifier`) | `sql_utils.py` en `usecases/query_resource.py`, `server.py`, `mcp_server.py` |
| Serialización de configuración | `Config.Sanitized()` enmascara `token`, `secret`, `password`, `passwd`, `credential`, `api_key`, `apikey`, `client_secret` | `main.go` (`datamesh config`), `cshared/exports.go` (`DataMeshInit`) |
| Bind del servidor | `127.0.0.1` por defecto (Python y Go); `0.0.0.0` explícito | `server.run_server`, `datamesh serve --host` |

**Variables de entorno de configuración (todas opt-in):**

- `DATAMESH_INSECURE_TLS=1` — degrada la verificación de certificado ante errores TLS.
- `DATAMESH_PROXY_ALLOWED_HOSTS=host1,host2` — allowlist SSRF; si está definida, solo esos hosts.
- `DATAMESH_PROXY_ALLOW_PRIVATE=1` — restaura destinos privados (federaciones de intranet).
- `DATAMESH_CORS_ORIGIN=...` — origen CORS permitido (default `*`).
