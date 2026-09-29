# Casos de Uso del Core DataMesh SDK

## CU-01: Descubrimiento de Catálogo Soberano (`DiscoverCatalogUseCase`)
- **Actor:** Usuario final, script Python, o cliente web en TypeScript.
- **Entrada:** `catalogURL` opcional (si es omitido, utiliza `Config.Base.CatalogURL`).
- **Comportamiento:**
  1. Descarga el archivo de catálogo formateado en `llms.txt`.
  2. Parsea las secciones Markdown, extrayendo cada Data Product con título, URI relativa, descripción, dominio temático y recursos asociados.
  3. Resuelve las URLs relativas con base en el endpoint de origen.
  4. Retorna el agregado inmutable `domain.Catalog`.

## CU-02: Búsqueda Semántica/Palabra Clave (`Search`)
- **Actor:** Usuario final o agente de IA.
- **Entrada:** `keyword`, `catalogURL` opcional.
- **Comportamiento:**
  1. Ejecuta CU-01.
  2. Filtra entradas coincidentes en título, descripción o dominio.
  3. Retorna lista de `domain.CatalogEntry`.

## CU-03: Resolución y Validación de Data Product (`ResolveDataProductUseCase`)
- **Actor:** Consumidor de datos.
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
  2. Aplica configuraciones del archivo `datamesh.json` o `datamesh.yaml` si existen.
  3. Aplica variables `DATAMESH_{{BASE_VAR}}` y `DATAMESH__{{ADAPTADOR}}_{{VAR}}`.
  4. Valida invariantes y expone la configuración activa.
