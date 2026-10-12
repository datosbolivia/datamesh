# ADR 0012: Modelo Unificado de Metadatos MEFP, CKAN, Lakequery y Frictionless DataPackage (OKF v0.2)

- **Estado:** Aceptado
- **Fecha:** 2026-10-07
- **Contexto:**
  El ecosistema de datos del Ministerio de Economía y Finanzas Públicas (MEFP) integra múltiples componentes soberanos:
  1. `datamesh-sdk`: Núcleo analítico federado, motor DuckDB, ingesta y resolución de tríadas (`catalog:dataset:resource`).
  2. `ckanext-lakequery`: Motor de consultas analíticas directas sobre MinIO/S3 usando DuckDB, firmado de exportaciones y especificaciones de query.
  3. `ckanext-metadata`: Motor de gestión enriquecida de metadatos, calidad de datos y auditoría/historial de cambios (diffs snapshot).
  4. `ckanext-mefp`: Tema y portal visual de CKAN alineado al diseño institucional.

  Anteriormente existía divergencia en los modelos de metadatos: CKAN utilizaba campos sueltos (`extras`, `filas`, `columnas`, `esquema`), Lakequery utilizaba un esquema interno para describir columnas Parquet, y DataMesh SDK esperaba especificaciones estándar Frictionless DataPackage / OKF v0.2. Se requería que todos los componentes hablaran el **mismo idioma canónico de metadatos** y pudieran interoperar sin fricción ni transformaciones ad-hoc.

- **Decisión:**
  1. **Dialecto Universal de Tipos de Columna:**
     - Se estandarizan los tipos de campo conforme a Frictionless Table Schema / OKF v0.2: `string`, `number`, `integer`, `boolean`, `date`, `datetime`, `object`, `array`.
     - Cada campo incluye opcionalmente: `name`, `type`, `title`, `description`, `unit`, `label`, `filterable`, `sortable`.
  2. **Contrato Canónico de Recurso (Frictionless Resource + MEFP Lake Extensions):**
     - Metadatos dimensionales y operativos: `row_count` / `filas`, `columnas`, `fecha_minima`, `fecha_maxima`, `frecuencia_actualizacion_dias`, `resource_family_id`.
     - Políticas de gobernanza soberana: `x-policy` (`zero_microdata`, `allow_all`, `deny`).
     - Especificación de ejecución distribuida: `lakequery` con `enabled`, `storage` (`backend`, `bucket`, `key`), `queryable`.
     - Definición de esquema tabular: `schema: { fields: [...] }` compatible con `table_schema`, `esquema` y DataStore.
  3. **Exposición Unificada de DataPackage en CKAN:**
     - Endpoint canónico en `ckanext-lakequery`: Action API `lakequery_datapackage_show`.
     - Endpoint canónico en `ckanext-metadata`: Action API `metadata_datapackage_show`, con rutas HTTP directas:
       - `GET /dataset/<id>/datapackage.json` (mimetype: `application/json`)
       - `GET /dataset/<id>/datapackage.yaml` (mimetype: `application/x-yaml`)
     - Enlace de descarga e interoperabilidad integrado en las plantillas visuales de `ckanext-mefp` (`package/read.html`).
  4. **Alineación del Núcleo `datamesh-sdk`:**
     - `CKANResource` en el dominio extiende atributos de primera clase para `schema`, `filas`, `columnas`, `fecha_minima`, `fecha_maxima`, `frecuencia_actualizacion_dias`, `resource_family_id`, `x_policy` y `lakequery`.
     - `CKANClientAdapter` y `HarvestCKANUseCase` mapean estos atributos preservando el esquema enriquecido y generando bundles OKF v0.2 completos sin pérdida de fidelidad.

- **Consecuencias:**
  - **Positivas:**
    - Cero divergencia semántica entre CKAN, Lakequery, MEFP Metadata y DataMesh SDK.
    - Los agentes de IA y herramientas analíticas pueden consultar o ingerir cualquier conjunto de datos directamente con `dm.harvest_ckan(...)` o consumiendo `/datapackage.json` / `/datapackage.yaml`.
    - Cumplimiento pleno de las directrices OKF v0.2, PE1-PE5 y Frictionless Standards.
  - **Compensaciones:**
    - Recursos Parquet sin esquema explícito deben introspeccionarse mediante DuckDB (`describe_parquet`).
