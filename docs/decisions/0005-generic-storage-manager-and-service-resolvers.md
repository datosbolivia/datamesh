# ADR 0005: Gestor de Storage Temporal ~/datamesh/cache y Adaptadores Hexagonales de Servicios (Local, Kaggle, GitHub, HTTP)

## Estado
Aceptado

## Contexto
El análisis OLAP con DuckDB sobre catálogos federados exige disponibilidad física de los recursos de datos. Sin embargo, en un entorno heterogéneo y distribuido:
1. Los recursos se alojan en plataformas diversas con protocolos y mecanismos de autenticación dispares (archivos locales, repositorios de GitHub con URLs raw/blob, datasets de Kaggle protegidos por credenciales API, endpoints HTTP/Google Sheets).
2. Consultar recursos remotos directamente vía red en cada ejecución SQL produce latencias elevadas, cuellos de botella de ancho de banda y fallas en entornos con conectividad intermitente o restricciones de red (sandboxes).
3. DuckDB opera con máxima velocidad analítica (I/O mapeado en memoria, escaneo columnar paralelo de Parquet/CSV) cuando los archivos residen físicamente en el almacenamiento local.

Se requiere un gestor de almacenamiento temporal estandarizado en el entorno del usuario (`~/datamesh/cache/`), gobernado por un archivo de configuración genérico (`~/datamesh/config.yaml`), desacoplado del motor analítico mediante Puertos y Adaptadores hexagonales.

## Decisión
1. **Configuración Genérica en `~/datamesh/`**:
   - Se establece `~/datamesh/` como directorio raíz de configuración y estado local del usuario (prioritario, con fallback a `~/.datamesh/` o configurable mediante `DATAMESH_HOME`).
   - Se crea y gestiona `~/datamesh/config.yaml` definiendo catálogos federados por defecto, rutas de almacenamiento y habilitación de adaptadores.

2. **Puerto de Almacenamiento Temporal (`StoragePort`) y Adaptador (`LocalStorageManager`)**:
   - `StoragePort` define el contrato para verificar caché (`is_cached`), obtener rutas locales (`get_cached_path`), guardar streams de datos atómicamente (`save`), persistir archivos (`store_file`), consultar metadatos (`get_metadata`) y desalojar entradas (`evict`, `clear`).
   - `LocalStorageManager` implementa el puerto gestionando el directorio `~/datamesh/cache/`, garantizando escrituras seguras con archivos temporales y atomicidad mediante `os.replace`, indexando entradas en `metadata.json` con hash SHA-256, tamaño, ETag y fecha de expiración.

3. **Adaptadores de Servicios Desacoplados (`ResourceAdapterPort`)**:
   - `LocalFileAdapter`: Detecta rutas locales absolutas, relativas y proyectos clonados en el workspace del usuario o `DATAMESH_PROJECTS_DIR`, permitiendo acceso de cero-copia.
   - `GitHubAdapter`: Normaliza URLs de `github.com` a endpoints CDN de `raw.githubusercontent.com`, realiza streaming HTTP con ETag y persiste en temporal storage.
   - `KaggleAdapter`: Parsea referencias `kaggle.com/datasets/<owner>/<dataset>/<file>`, descarga archivos mediante la API oficial de Kaggle (`~/.kaggle/kaggle.json`) y provee fallback inteligente a proyectos locales consolidados.
   - `HttpAdapter`: Procesa URLs genéricas `http://` y `https://` (ej. exportaciones CSV de Google Sheets), infiriendo extensiones y tipos de contenido para su descarga en caché.

4. **Caso de Uso de Orquestación (`ResolveAndCacheResourceUseCase`)**:
   - Orquesta la resolución de tríadas (`catalogo:dataset:resource`), inspección de manifiestos `datapackage.{yaml,yml,json}` y selección del adaptador idóneo.
   - Verifica primeramente la presencia en `StoragePort`. Si existe en caché local, evita descargas redundantes; si es nuevo, coordina la descarga y retorna la ruta local al motor DuckDB.

5. **Integración con `DuckDBQueryEngine`**:
   - DuckDB recibe el caso de uso inyectado y crea vistas virtuales directamente sobre los archivos físicos alojados en `~/datamesh/cache/`.

## Consecuencias
- Velocidad máxima de ejecución SQL con DuckDB sobre archivos locales temporales.
- Resiliencia offline total una vez descargada la información en caché.
- Aislamiento arquitectónico estricto: añadir un nuevo proveedor (ej. HuggingFace, S3, MinIO) solo requiere implementar `ResourceAdapterPort` sin modificar el motor analítico ni el dominio.
