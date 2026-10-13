# ADR 0024: Abstracción de mefp-datos, Adaptador S3/Aistor y CKAN Unificado

## Estado
Aceptado

## Fecha
2026-10-12

## Contexto
El ecosistema del Data Lake del Ministerio de Economía y Finanzas Públicas (MEFP) utilizaba la librería `mefp_datos` para interactuar con dos piezas de infraestructura centrales:
1. Almacenamiento de objetos S3 / MinIO (`Aistor`): gestión de buckets, prefijos de repositorio, subida y descarga de archivos de microdatos y dumps crudos (`dump_raw`).
2. Catálogo soberano de datos (`CKAN`): búsqueda, inspección, descarga de recursos tabulares y sincronización/publicación de datasets conforme al esquema institucional (`datapackage.json` -> CKAN API).
3. Vistas de análisis en memoria (`aliases`): helpers para transformar respuestas de CKAN y archivos tabulares en DataFrames de `pandas`.
4. Ciclo de vida y scaffolding de repositorios (`repo`): plantillas para nuevos proyectos ETL en Forgejo con pipelines y git credentials.

Sin embargo, el DataMesh SDK (`datamesh-sdk`) ya implementa un núcleo hexagonal soberano para descubrimiento federado, resolución adaptativa de recursos, ejecución analítica SQL sobre DuckDB y normalización OKF/ODKF v0.2. Mantener la lógica de ingesta, resolución de objetos S3 y publicación desacoplada en `mefp_datos` generaba duplicidad de código, divergencia en contratos de metadatos y limitaba la capacidad de DuckDB para resolver tríadas institucionales `mefp:dataset:recurso` o URLs directas `s3://...` / `aistor://...`.

## Decisión
`datamesh-sdk` asume plenamente los procesos de obtención, resolución y publicación de información del Data Lake MEFP mediante adaptadores hexagonales:

1. **Adaptador de Almacenamiento S3 / Aistor (`S3StorageAdapter` / `AistorStorageAdapter`):**
   - Implementa operaciones de cliente S3 sobre MinIO / AWS S3 usando `boto3`.
   - Soporta resolución automática de configuración por variables de entorno (`AISTOR_ENDPOINT`, `S3_ENDPOINT`, `AISTOR_BUCKET`, `S3_BUCKET`, etc.).
   - Administra prefijos de repositorio (`repo_prefix`), subida (`upload_file`, `put_object`), descarga, streaming y listado de objetos por fecha.

2. **Resolvedor de Recursos S3 / Aistor (`S3Adapter`):**
   - Implementa `ResourceAdapterPort`.
   - Resuelve URIs `s3://bucket/key`, `aistor://bucket/key` y tríadas `mefp:dataset:resource` / `lake:dataset:resource` descargando a la caché temporal de DataMesh con validación SHA-256.
   - Permite que `dm.sql("SELECT * FROM 's3://lake/path/file.csv'")` o `dm.sql("SELECT * FROM 'mefp:dataset:resource'")` funcionen transparentemente en DuckDB.

3. **Resolvedor y Publicador CKAN Enriquecido (`CKANAdapter` & `CKANPublisherAdapter`):**
   - Implementa `PublisherPort` para publicar y sincronizar paquetes Frictionless / OKF v0.2 directamente en portales CKAN (`dm.publish(path, targets=['ckan'])`), preservando metadatos extendidos del MEFP (ADR 0012).
   - Extrae exhaustivamente todos los metadatos institucionales (esquema de campos, tipos Frictionless/CKAN, cobertura espacial/temporal, políticas `x-policy`, metadatos dimensionales `filas`, `columnas`, `frecuencia_actualizacion_dias`, y especificaciones Lakequery) para reconstruir el bundle OKF y el `index.md` con frontmatter estructurado.

4. **Fachada de Aliases Pandas (`datamesh.to_df`, `datamesh.aliases`):**
   - Expone funciones de lectura tabular directa a `pandas.DataFrame` para queries, datasets y recursos de CKAN o S3.

5. **Rol de `mefp_datos` como Librería Alias:**
   - `mefp_datos` se refactoriza para convertirse en una capa alias y de retrocompatibilidad sobre `datamesh`.
   - Sus módulos (`mefp_datos.aistor`, `mefp_datos.ckan`, `mefp_datos.aliases`, `mefp_datos.repo`) delegan sus llamadas en los adaptadores y use cases canónicos de `datamesh-sdk`.
   - Los contratos de API preexistentes y los tests unitarios de `mefp_datos` se preservan al 100%.

## Consecuencias
- **Positivas:**
  - Unificación de toda la pila de datos (S3, MinIO, CKAN, Kaggle, GitHub, Local) bajo el mismo modelo de dominio y motor de ejecución DuckDB.
  - Soporte de tríadas `mefp:dataset:recurso` y consultas directas a recursos sueltos `s3://...` o CKAN.
  - Generación automática de documentación Markdown con cabeceras YAML conformes a OKF / ODKF v0.2 para cualquier dataset proveniente de CKAN.
  - Retrocompatibilidad asegurada para todos los repositorios existentes del ministerio que importan `mefp_datos`.
- **Compensaciones:**
  - `boto3` y `ckanapi` / `urllib` se integran como dependencias estándar en el runtime de DataMesh.
