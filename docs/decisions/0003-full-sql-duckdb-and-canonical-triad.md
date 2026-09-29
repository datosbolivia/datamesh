# ADR 0003: Motor SQL Completo con DuckDB, Tríada Canónica y Normalización de Heterogeneidad

## Estado
Aceptado

## Contexto
Los consumidores de datos abiertos federados y los agentes de IA necesitan realizar análisis expresivos con sintaxis ANSI SQL completa (JOINs, agregaciones, funciones de ventana, CTEs, ordenamientos) en lugar de filtros tabulares simples.

Además, los recursos en el DataMesh sufren de dos retos fundamentales:
1. **Identificación Canónica Descentralizada**: En un catálogo federado, cada recurso requiere un direccionamiento universal que no dependa de URLs rígidas.
2. **Heterogeneidad de Formatos**: Los proveedores exponen recursos en CSV, TSV, Parquet, JSON, o JSON Lines, lo cual dificulta que un usuario o agente realice cruces de datos entre múltiples dominios.

## Decisión
1. **Notación de Tríada Canónica (`catalogo:dataset:resource`)**:
   - Cada tabla en las consultas SQL se referencia mediante la tríada `catalogo:dataset:resource` (ej. `"bolivia:elecciones:votos_2020"`).
   - El preprocesador del motor extrae automáticamente las tríadas referenciadas en las cláusulas `FROM` y `JOIN`.
   - Se resuelve cada componente contra el catálogo soberano correspondiente (`llms.txt`), su manifiesto OKF v0.2 y sus contratos de recursos.

2. **Normalización de Heterogeneidad con DuckDB**:
   - DuckDB se utiliza como motor analítico columnar embebido en memoria (cero infraestructura externa).
   - Para cada tríada resuelta, el motor registra una vista virtual (`CREATE VIEW "<catalogo:dataset:resource>" AS SELECT * FROM ...`) seleccionando automáticamente la función columnar óptima:
     * Parquet: `read_parquet(...)`
     * CSV/TSV: `read_csv_auto(...)`
     * JSON/JSON Lines: `read_json_auto(...)`
   - Los datos heterogéneos se unifican transparentemente en vectores columnares en memoria, permitiendo JOINs cruzados directos entre formatos distintos (ej. JOIN entre un CSV de elecciones y un Parquet de presupuesto municipal).

3. **Exposición en CLI y Servidor MCP**:
   - CLI: Comando `datamesh sql "<QUERY_SQL>"`.
   - Servidor MCP: Herramienta `datamesh_sql_query(sql_query)` para que agentes de IA ejecuten consultas analíticas avanzadas sin alucinaciones.

## Consecuencias
- Consultas analíticas ilimitadas con estándar ANSI SQL.
- Interoperabilidad total entre formatos tabulares dispares sin requerir pipelines de ETL previos.
- Agentes de IA pueden responder preguntas complejas ejecutando JOINs y agregaciones en una sola llamada de herramienta.
