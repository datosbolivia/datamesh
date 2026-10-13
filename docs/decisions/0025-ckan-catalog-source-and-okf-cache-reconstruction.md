# ADR 0025: Integración de CKAN como Catálogo Federado y Reconstrucción Automática OKF en Caché

## Estado
Aceptado

## Fecha
2026-10-12

## Contexto
El Formato de Conocimiento Abierto Federado (OKF / ODKF v0.2) y el DataMesh SDK utilizan tríadas canónicas `[catalogo:]dataset:resource` para identificar y consultar productos de datos sovereign mediante DuckDB.

Sin embargo, en entornos corporativos y de gobierno abierto como el Ministerio de Economía y Finanzas Públicas (MEFP), datasets enteros residen en portales CKAN autenticados (`https://ckan.datos.gob.bo/`). Cuando un usuario o agente consulta una tríada institucional (p. ej. `'indicadores_macro_fmi:req_13_a'`) o una URL directa de recurso en CKAN:
1. El portal CKAN puede no contar de antemano con un archivo `datapackage.yaml` físico pre-cosechado en el repositorio local.
2. DuckDB intentaba registrar vistas virtuales directamente sobre la URL remota mediante `read_csv_auto('http://...')`, lo cual fallaba con `HTTP 0 / 401 UNAUTHORIZED` debido a que el motor HTTP interno de DuckDB no inyecta cabeceras `Authorization` arbitrarias.
3. Se requería que CKAN opere como una fuente de catálogo federado de primer orden, de modo que cualquier consulta sobre un dataset en CKAN lo convierta automáticamente en un paquete OKF completo (`datapackage.yaml` + `index.md`) en la caché soberana local (`<cache_dir>/nodes/<dataset>/`), y resuelva sus recursos tabulares hacia copias locales validadas criptográficamente.

## Decisión
Se implementa la integración nativa de CKAN como catálogo federado y la reconstrucción transparente de nodos OKF en caché:

1. **Auto-Carga de Perfiles de Entorno (`load_environment`):**
   - `datamesh.constants` detecta y carga automáticamente archivos `datamesh.env` y `.env` en el directorio de trabajo o sus directorios superiores, inyectando `CKAN_URL`, `CKAN_ACCESS_KEY` y variables de almacenamiento sin sobreescribir variables existentes.
   - Corrige expansiones de ruta herméticas (`PROJECT_ROOT`, `DATAMESH_HOME`, `DATAMESH_CACHE_DIR`).

2. **CKAN como Fuente en el Descubrimiento Federado (`DiscoverCatalogUseCase`):**
   - `get_catalog_urls()` reconoce `CKAN_URL` / `CKAN_BASE_URL` como una fuente de catálogo activa.
   - `DiscoverCatalogUseCase` detecta endpoints CKAN y utiliza `CKANClientAdapter.search_packages()` para mapear los datasets de CKAN como entradas del catálogo federado (`dm.discover()`).

3. **Reconstrucción Automática OKF en Caché (`LocalWorkspaceResolver._read_manifest_from_ckan`):**
   - Cuando un dataset (p. ej. `indicadores_macro_fmi`) no existe en el workspace local (`knowledge/nodes/`), el resolvedor consulta el portal CKAN vía `package_show`.
   - Si existe, `HarvestCKANUseCase.reconstruct_okf_bundle()` ensambla el manifiesto OKF v0.2 enriquecido (`datapackage.yaml`) y el documento de conocimiento (`index.md`) con frontmatter YAML (dimensiones, contratos, linaje, tags, políticas `x-policy`).
   - Los archivos se almacenan inmediatamente en `<cache_dir>/nodes/<dataset>/`. Consultas posteriores son servidas localmente sin latencia de red.

4. **Pre-Descarga y Resolución Autenticada para DuckDB (`register_table_aliases` y `HttpAdapter`):**
   - Cuando DuckDB registra vistas para URLs remotas protegidas (`is_remote` con tokens de autorización `CKAN_ACCESS_KEY` / `DATAMESH_AUTH_TOKEN`), el motor invoca `HttpAdapter.resolve_and_fetch()` antes de intentar la creación de vista directa.
   - `HttpAdapter` descarga el recurso usando streaming autenticado y sigue redirecciones hacia buckets S3/filestore, almacenándolo en caché local con hash SHA-256.
   - DuckDB crea la vista apuntando al archivo local en caché, garantizando cero errores de red o autenticación.

## Consecuencias
- **Positivas:**
  - Resolución transparente y de 1 línea: `dm.sql("SELECT * FROM 'indicadores_macro_fmi:req_13_a'")` y `dm.sql("SELECT * FROM '<URL>'")` funcionan out-of-the-box.
  - Conformidad OKF v0.2: Cualquier paquete en CKAN se transforma automáticamente en un nodo de conocimiento navegable en caché con metadatos completos y linaje institucional.
  - Soporte offline y reanudable: Una vez cosechado en caché, los queries se ejecutan a velocidad local en DuckDB sin depender del estado del servidor CKAN.
- **Compensaciones:**
  - El primer query a un dataset no cosechado incurre en latencia de red para consultar la API de CKAN y descargar el archivo inicial a la caché.
