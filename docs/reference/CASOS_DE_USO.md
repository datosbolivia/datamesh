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
