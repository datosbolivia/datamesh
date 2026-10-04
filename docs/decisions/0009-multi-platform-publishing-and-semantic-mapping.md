# ADR 0009: Publicación Multi-Plataforma, Metadatos Espacio-Temporales y Mapeo Semántico

- **Estado:** Aceptado
- **Fecha:** 2026-10-04
- **Contexto:**
  La publicación de datos en el ecosistema DataMesh requería un mecanismo desacoplado para transformar y publicar datasets y bundles ODKF v0.2 hacia múltiples plataformas simultáneamente (directorios locales, repositorios de catálogos soberanos Astro/OKF, y plataformas externas como Kaggle Datasets).
  Asimismo, era imperativo estandarizar los metadatos de cobertura espacial (ISO 19115 / W3C DCAT v3 / GeoJSON) y temporal (ISO 8601 / W3C Time), así como proveer una solución de alineación semántica para columnas de datos sin alterar los archivos de microdatos crudos ni duplicar el almacenamiento.

- **Decisión:**
  1. Se definieron los Value Objects inmutables `SpatialCoverage`, `TemporalCoverage`, `QualityProfile` y `SemanticFieldMapping` en `datamesh.domain.models` y sus interfaces equivalentes en TypeScript.
  2. Se diseñó el puerto hexagonal `PublisherPort` y su caso de uso orquestador `PublishDatasetUseCase`, implementando adaptadores para `LocalBundlePublisherAdapter`, `PortalPublisherAdapter` y `KagglePublisherAdapter`.
  3. Se desacopló el mapeo semántico mediante `SemanticAlignmentUseCase`: las columnas en `datapackage.yaml` declaran enlaces a conceptos de la base de conocimiento local (`concept: "concepts/..."`) y tablas de equivalencia de valores (`value_mapping`). Los SKOS formales (Wikidata, ontologías W3C) residen en los documentos de concepto ODKF correspondientes, manteniendo limpio el contrato tabular.
  4. DuckDB y el motor analítico consumen expresiones generadas automáticamente (`CASE WHEN ... END`) para normalizar identificadores y permitir joins y agregaciones multi-tabla sin scripts de limpieza ad-hoc.
  5. Se actualizaron los bindings de Python y TypeScript, el CLI (`datamesh publish`, `datamesh align`), y el portal web (`catalogo-datamesh`) para renderizar badges de cobertura espacio-temporal y calidad.

- **Consecuencias:**
  - **Positivas:**
    - Cero código huérfano y cumplimiento normativo estricto con OKF/ODKF v0.2.
    - Publicación con un solo comando o llamada SDK hacia múltiples destinos.
    - Joins federados entre fuentes con nomenclaturas heterogéneas sin intervención manual.
  - **Compensaciones:**
    - Los publicadores deben definir explícitamente sus diccionarios `value_mapping` si desean alineación automática para columnas de códigos o abreviaturas no estandarizadas.
