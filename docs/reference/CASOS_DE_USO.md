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
- **Entrada:** `sql_query` ANSI/DuckDB SQL (ej. `SELECT * FROM 'p2p-bob-exchange:advertiser' LIMIT 25` o `FROM "air_quality:Compilación de datos de calidad del aire de Bolivia"`), `table_mapping` opcional.
- **Comportamiento:**
  1. Extrae referencias de tablas y tríadas canónicas (`catalogo:dataset:resource` o `dataset:resource`).
  2. Resuelve cada tríada contra manifiestos locales `datapackage.{yaml,yml,json}` en `knowledge/nodes/`, proyectos locales en el workspace (`DATAMESH_PROJECTS_DIR`) o catálogos federados HTTP (`llms.txt`).
  3. Soporta normalización transparente de heterogeneidad de formatos (Parquet, CSV, TSV, JSON, JSONL) y extensiones remotas (`httpfs` con normalización a `raw.githubusercontent.com`).
  4. Registra vistas virtuales con alias canónicos y slugificados (`slugify`).
  5. Ejecuta la consulta SQL, normaliza tipos complejos (`Decimal`, fechas, UUIDs) a primitivas serializables en JSON, y retorna columnas, filas y conteo.
  6. Si una tabla no existe o es inalcanzable, genera un error descriptivo y explícito sin fallar con errores crípticos de DuckDB.

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

