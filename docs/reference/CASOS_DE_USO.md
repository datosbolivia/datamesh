# Casos de Uso del Core DataMesh SDK

## CU-01: Descubrimiento y Federación Multicatálogo (`DiscoverCatalogUseCase`)
- **Actor:** Usuario final, script Python, o cliente web en TypeScript / Agente MCP.
- **Entrada:** `catalogURL` opcional (si es omitido, descubre concurrentemente todos los catálogos en `Config.Base.CatalogURLs`).
- **Comportamiento:**
  1. Descarga concurrentemente los archivos `llms.txt` de todas las fuentes federadas.
  2. Parsea las secciones Markdown, extrayendo cada Data Product con título, URI relativa, descripción, dominio temático y recursos asociados.
  3. Resuelve URLs relativas contra la raíz de cada catálogo y etiqueta el origen en `catalog_source`.
  4. Deduplica entradas y retorna el agregado inmutable `domain.Catalog`.

## CU-02: Búsqueda Semántica/Palabra Clave (`Search`)
- **Actor:** Usuario final o agente de IA.
- **Entrada:** `keyword`, `catalogURL` opcional.
- **Comportamiento:**
  1. Ejecuta CU-01.
  2. Filtra entradas coincidentes en título, descripción o dominio a través de todos los catálogos federados.
  3. Retorna lista de `domain.CatalogEntry`.

## CU-03: Resolución y Validación de Data Product (`ResolveDataProductUseCase`)
- **Actor:** Consumidor de datos o agente MCP.
- **Entrada:** URI o URL del nodo (ej. `https://datosbolivia.github.io/raw/nodes/elecciones-bolivia/index.md`).
- **Comportamiento:**
  1. Obtiene el contenido Markdown del nodo.
  2. Extrae y parsea el frontmatter YAML según especificación OKF / ODKF v0.2.
  3. Valida invariantes de dominio (tipo válido, dimensiones presentes, título no vacío).
  4. Construye y retorna la entidad `domain.DataProduct`.

## CU-04: Carga y Fusión de Configuración (`ConfigUseCase`)
- **Actor:** Inicializador del SDK.
- **Entrada:** Ruta opcional de archivo o variables de entorno del sistema.
- **Comportamiento:**
  1. Carga valores por defecto de la especificación.
  2. Aplica configuraciones del archivo `datamesh.json` o `datamesh.yaml` si existen (incluyendo lista `catalogs`).
  3. Aplica variables `DATAMESH_{{BASE_VAR}}` y `DATAMESH__{{ADAPTADOR}}_{{VAR}}`.
  4. Valida invariantes y expone la configuración activa.

## CU-05: Consulta Tabular en Memoria (`QueryDataProductUseCase`)
- **Actor:** Consumidor de datos, analista o Agente MCP.
- **Entrada:** `resource_uri`, `filters` clave-valor opcionales, `limit` entero opcional.
- **Comportamiento:**
  1. Carga los bytes del recurso desde caché local, archivo o HTTP.
  2. Determina el formato tabular (CSV o TSV).
  3. Ejecuta proyecciones y filtros de igualdad sobre las columnas especificadas.
  4. Retorna el resultado estructurado `domain.QueryResult` con columnas, filas y métricas de tiempo de ejecución.

## CU-06: Ejecución SQL ANSI/DuckDB con Resolución de Tríadas y Heterogeneidad (`DuckDBSQLQueryUseCase`)
- **Actor:** Consumidor de datos, analista, agente LLM (vía MCP `datamesh_sql_query`) o CLI (`datamesh sql`).
- **Entrada:** `sql_query` ANSI/DuckDB SQL (ej. `SELECT * FROM 'p2p-bob-exchange:advertiser' LIMIT 25`, `FROM "catalogo/dataset/recurso"`, o `FROM "https://datosbolivia.github.io/datasets/cartera-creditos/creditos.csv"`), `table_mapping` opcional.
- **Comportamiento:**
  1. Extrae referencias de tablas: tríadas con dos puntos (`catalogo:dataset:resource`), rutas con barras (`catalogo/dataset/recurso` o `dataset/recurso`), o URLs directas (`https://.../datasets/<dataset>/<resource.ext>`).
  2. Resuelve cada referencia contra manifiestos locales `datapackage.{yaml,yml,json}` en `knowledge/nodes/`, proyectos locales en el workspace (`DATAMESH_PROJECTS_DIR`) o catálogos federados HTTP (`llms.txt`).
  3. Soporta normalización transparente de heterogeneidad de formatos (Parquet, CSV, TSV, JSON, JSONL) y extensiones remotas (`httpfs` con normalización a `raw.githubusercontent.com`).
  4. Si DuckDB falla al registrar una vista remota por errores SSL de CA gubernamental o IO de red, descarga automáticamente el recurso a la caché temporal local con contexto SSL no verificado (`ssl.CERT_NONE`) y recrea la vista apuntando al archivo local.
  5. Registra vistas virtuales con alias canónicos y slugificados (`slugify`).
  6. Ejecuta la consulta SQL, normaliza tipos complejos (`Decimal`, fechas, UUIDs) a primitivas serializables en JSON, y retorna columnas, filas y conteo.
  7. Si una tabla no existe o es inalcanzable, genera un error descriptivo y explícito sin fallar con errores crípticos de DuckDB.

## CU-07: Fachada Unificada de 5 Métodos en Bindings (`UnifiedClientFacade`)
- **Actor:** Desarrolladores e integradores en Python (`import datamesh as dm`) y TypeScript (`import { datamesh, discover, search, get, query, sql } from '@datosbolivia/datamesh-client'`).
- **Entrada:** Llamadas de una sola línea a cualquiera de los 5 métodos canónicos unificados:
  1. `discover([catalog_url])`: Catálogo federado completo o inspección de un endpoint específico.
  2. `search(keyword, [catalog_url])`: Búsqueda de productos de datos por palabra clave en título, descripción o dominio.
  3. `get(uri_or_url)`: Recuperación y validación de manifest y descripción de un producto de datos OKF v0.2.
  4. `query(resource_uri | QueryRequest)`: Consulta tabular simple en memoria con filtros y paginación.
  5. `sql(sql_query, [table_mapping / options])`: Ejecución SQL ANSI/DuckDB con soporte para tríadas y URLs.
- **Comportamiento:**
  1. Elimina duplicidad entre bindings y el core asegurando paridad estricta de nombres, contratos y firmas.
  2. Expone las mismas 5 herramientas estándar en los servidores MCP tanto en Go (`core-go/adapters/inbound/cli/serve.go`) como en Python (`datamesh/server.py` y `datamesh/mcp_server.py`).

## CU-07: Gestión de Almacenamiento Temporal y Caché (`ManageStorageUseCase`)
- **Actor:** Motor analítico DuckDB, script de mantenimiento, o usuario final vía SDK (`datamesh.storage`).
- **Entrada:** Llave o URI de recurso, stream o bytes de datos, extensión de formato opcional, TTL o expiración.
- **Comportamiento:**
  1. Administra el directorio genérico `~/datamesh/` y la caché local `~/datamesh/cache/`.
  2. Registra y verifica la presencia en caché (`is_cached`) mediante hash SHA-256 de la URI.
  3. Realiza escrituras seguras y atómicas a disco previniendo descargas corruptas o truncadas.
  4. Mantiene el índice `metadata.json` con tamaño, checksum SHA-256, timestamps UTC, ETag y servicio origen.
  5. Permite desalojo selectivo (`evict`) o purga total/por antigüedad (`clear`).

## CU-08: Descarga y Resolución Adaptativa Multiproveedor (`ResolveAndCacheResourceUseCase`)
- **Actor:** Adaptador `DuckDBQueryEngine` o consumidor del SDK.
- **Entrada:** URI del recurso, URL remota o referencia de tríada `dataset:resource`.
- **Comportamiento:**
  1. Verifica si el recurso ya reside en la caché temporal `~/datamesh/cache`. Si existe, lo retorna de inmediato sin consultar la red.
  2. Si no está en caché, consulta los adaptadores de servicio en orden de precedencia:
     - `LocalFileAdapter`: Archivos directos del filesystem o repositorios locales en el workspace del usuario.
     - `GitHubAdapter`: Descarga y normaliza URLs a `raw.githubusercontent.com`.
     - `KaggleAdapter`: Descarga mediante API oficial de Kaggle (`~/.kaggle/kaggle.json`) o recupera copias locales consolidadas.
     - `HttpAdapter`: Streaming directo de endpoints web y exportaciones tabulares (Google Sheets).
  3. Almacena el recurso en `~/datamesh/cache/` con su formato inferido.
  4. Retorna el objeto `ResolvedResource` con la ruta física local para su escaneo directo por DuckDB.

## CU-09: Selección y Ejecución Polimórfica de Motor de Consultas (`ExecuteQueryEngineUseCase`)
- **Actor:** Usuario final vía SDK (`datamesh.sql(..., engine=...)`), CLI (`datamesh sql --engine ...`), o Agente IA.
- **Entrada:** Sentencia SQL estándar, mapeo opcional de tablas y nombre del motor objetivo (`duckdb`, `inmem`, `go`).
- **Comportamiento:**
  1. Valida el motor especificado contra el registro polimórfico (`QueryEnginePort`).
  2. Si se selecciona `duckdb`: aprovecha el motor OLAP columnar en memoria con joins multi-tabla y soporte para Parquet/CSV/JSON/TSV.
  3. Si se selecciona `inmem`: ejecuta proyección de columnas, filtros de igualdad y límites en Python/Go puro sin dependencias nativas externas.
  4. Si se selecciona `go`: delega la ejecución al núcleo canónico de Go (`core-go/`) mediante la interfaz C-ABI (`DataMeshExecuteSQL`).
  5. Retorna el resultado uniforme estructurado con `columns`, `rows` y `row_count`.

## CU-10: Lectura y Resolución Unificada de Manifiestos Heterogéneos (`UnifiedManifestReaderUseCase`)
- **Actor:** Núcleo canónico Go (`core-go/`), resolvedores de nodo/catálogo, bindings C-ABI y WebAssembly.
- **Entrada:** Ruta o URI a nodo o catálogo (`node_path`, `index.md`, `llms.txt`, `datapackage.{json,yaml,yml}`).
- **Comportamiento:**
  1. Abstrae el análisis de manifiestos mediante `ManifestParserPort`, desacoplando la especificación Frictionless de futuros estándares (DCAT, RO-Crate, CKAN).
  2. Implementa parsers modulares y sin dependencias externas:
     - `DataPackageJSONParser`: Procesa esquemas de metadatos Frictionless en `datapackage.json`.
     - `DataPackageYAMLParser`: Scanner nativo en Go puro para `datapackage.yaml` y `datapackage.yml`.
     - `OKFMarkdownParser`: Extrae frontmatter YAML y cuerpo markdown de `index.md` (norma OKF/ODKF v0.2).
     - `LLMsTxtParser`: Parsea índices federados `llms.txt`, `llm.txt` y `llms-full.txt`.
  3. `UnifiedMetadataReader` escanea el directorio objetivo detectando automáticamente el formato presente y retornando un `PackageManifest` unificado.
  4. Resuelve nombres y recursos con `FindResource(nameOrSlug)` soportando nombres exactos, case-insensitive y slugificados (`slugify`).
  5. Facilita la resolución canónica de tríadas `[catalogo:dataset:resource]` en C-ABI y WASM con rutas normalizadas a recursos físicos.

## CU-11: Publicación Estandarizada Multi-Plataforma (`PublishDatasetUseCase`)
- **Actor:** Publicador de datos, analista, CLI (`datamesh publish`), o script ETL Python (`dm.publish()`).
- **Entrada:** `dataset_path` (directorio de bundle o archivo `datapackage.yaml`), lista de destinos `targets` (`local`, `portal`, `kaggle`), opciones adicionales (`destination`, `portal_dir`, `owner`).
- **Comportamiento:**
  1. Analiza y valida el contrato ODKF / Frictionless extrayendo esquema, metadatos espaciales (`SpatialCoverage`), temporales (`TemporalCoverage`), de calidad (`QualityProfile`) y recursos tabulares.
  2. Ejecuta los adaptadores de destino registrados concurrentemente o en secuencia:
     - `LocalBundlePublisherAdapter`: Genera o empaqueta el bundle OKF completo (`datapackage.yaml`, `index.md` con frontmatter conforme, carpeta de conceptos `concepts/`).
     - `PortalPublisherAdapter`: Publica directamente en el repositorio local o remoto de un catálogo soberano (`knowledge/nodes/<slug>/`).
     - `KagglePublisherAdapter`: Genera `dataset-metadata.json` con enriquecimiento de cobertura espacio-temporal y opcionalmente publica mediante Kaggle API.
  3. Retorna un informe estructurado con el estado de cada plataforma (`PublicationTargetResult`).

## CU-12: Mapeo y Normalización Semántica de Categorías (`SemanticAlignmentUseCase`)
- **Actor:** Analista de datos, motor de consultas DuckDB, Agente IA o CLI (`datamesh align`).
- **Entrada:** `datapackage_or_schema` con definiciones de columnas que enlazan a conceptos (`concept`) o diccionarios valor-concepto (`value_mapping`).
- **Comportamiento:**
  1. Extrae los mapeos ontológicos de cada columna declarados en el contrato sintáctico.
  2. Genera expresiones SQL estándar (`CASE WHEN raw = 'val' THEN 'concept:...' ELSE raw END`).
  3. Permite que DuckDB ejecute joins y agregaciones sobre columnas heterogéneas (ej. `"LP"`, `"02"`, `"La Paz"`) unificándolas bajo el mismo concepto canónico sin alterar los archivos de microdatos crudos.

## CU-13: Ingesta y Reconstrucción de Catálogos CKAN a OKF v0.2 (`HarvestCKANUseCase`)
- **Actor:** Administrador de catálogo, script de recolección (harvester), Agente IA o CLI (`datamesh harvest-ckan`, `dm.harvest_ckan()`).
- **Entrada:** `ckan_url` (URL del portal CKAN o endpoint de la Action API v3), `query`, `limit`, `offset`, credenciales de autenticación (`token`, `client_id`, `client_secret`), y directorio de salida opcional (`output_dir`).
- **Comportamiento:**
  1. Consulta la API de CKAN (`/api/3/action/package_search`, `/package_show`) con soporte de paginación e inyección de encabezados de autenticación (`AuthProviderPort`).
  2. Para cada dataset descubierto, extrae:
     - Recursos tabulares y binarios, sondeando esquemas de columnas en DataStore (`datastore_search`) cuando se encuentre activo.
     - Cobertura espacial (GeoJSON o BBox extraído de los campos `extras`: `spatial`, `spatial-coverage`).
     - Cobertura temporal (`temporal_start`, `temporal_end`, `frequency`).
     - Metadatos institucionales y etiquetas de clasificación.
  3. Reconstruye el paquete de datos OKF Frictionless (`datapackage.yaml` o `datapackage.json`).
  4. Genera el documento de conocimiento `index.md` con frontmatter estructurado OKF v0.2 y diccionario de recursos.
  5. Escribe los bundles en el directorio local de destino si fue especificado y retorna el resumen de ejecución `CKANHarvestResult`.

## CU-14: Descubrimiento Federado mediante Well-Known y Autenticación Unificada (`DiscoverWellKnownUseCase`)
- **Actor:** Cliente DataMesh, Agente IA o CLI (`datamesh discover`, `dm.discover_endpoint()`).
- **Entrada:** `target_url` (URL de un portal o dominio soberano, ej. `https://datos.gob.bo`).
- **Comportamiento:**
  1. Sondea la presencia del documento normativo `/.well-known/datamesh.json` o `/.well-known/okf.json`.
  2. Si el endpoint está disponible, parsea la configuración del catálogo, tipo de backend (`ckan`, `okf`, `dcat`), capacidades y requerimientos de autenticación (`keycloak`, `oauth2`, `api_key`, `none`).
  3. Si no existe well-known publicado, ejecuta un sondeo heurístico activo contra el endpoint de estado de CKAN (`/api/3/action/status_show`), deduciendo automáticamente las capacidades del portal.
  4. Inicializa transparentemente el proveedor de autenticación adecuado (`KeycloakAuthAdapter` para client credentials con token cache, `APIKeyAuthAdapter` para tokens de encabezado, o `NoAuthAdapter` para acceso público).



