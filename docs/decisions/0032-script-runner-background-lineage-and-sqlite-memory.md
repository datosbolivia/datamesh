# ADR 0032: Ejecutor de Scripts/Funciones, Cálculo de Linaje en Segundo Plano y Memoria Operacional en SQLite para Publicación Asistida por Agentes

## Estado
Aceptado

## Fecha
2026-10-22

## Contexto y Planteamiento del Problema
El linaje de datos en entornos científicos y analíticos sufre de dos problemas crónicos:
1. **La Fricción de la Documentación Manual:** Los desarrolladores y científicos de datos raramente documentan paso a paso en archivos YAML los inputs, transformaciones y outputs de sus scripts. Esto genera desfase entre los datos reales y el linaje declarado en los manifiestos.
2. **Carencia de Memoria Operacional Ligera:** Sin un motor de persistencia embebido, la inspección de procedencia exige escanear recursivamente y re-parsear archivos en cada consulta, ralentizando las herramientas de agentes IA.

Se requiere un mecanismo no invasivo que permita ejecutar scripts (desde terminal o envolviendo funciones en Python) capturando el linaje en segundo plano y almacenándolo en una base de datos local SQLite de cero configuración.

## Decisión Arquitectónica Adoptada

### 1. Interfaz de Ejecución Dual
Se proveen dos vías canónicas de captura de procedencia:
- **Terminal / CLI (`datamesh run` / `okf run`):**
  Ejecuta scripts externos (`.py`, `.sh`, `.sql`) midiendo tiempos, capturando código fuente (hash SHA-256), inputs y outputs.
- **Envoltorio de Funciones / SDK (`@dm.track_lineage`):**
  Decorador de funciones en Python que intercepta la ejecución, captura los argumentos, mide latencias y asocia los artefactos generados al identificador del dataset destino.

### 2. Memoria Operacional Embebida en SQLite (`lineage.db`)
Se implementa el puerto `LineageStorePort` y el adaptador `SQLiteLineageStore` utilizando la biblioteca estándar de Python `sqlite3`:
- Ubicación por defecto: `.datamesh/lineage.db` (en el espacio de trabajo local).
- Tablas canónicas: `executions`, `lineage_sources`, `lineage_transformations`, `artifacts`.
- Principio KISS/YAGNI: Cero servicios de bases de datos externos, cero dependencias pesadas adicionales.

### 3. Sinergia con Agentes IA y Publicación Asistida
Los registros persistidos en SQLite actúan como la memoria episódica operacional del agente:
- El agente consulta el historial de ejecuciones y transformaciones mediante herramientas MCP (`datamesh_get_lineage`).
- A partir de los registros verificados en SQLite, el agente puede sintetizar automáticamente la sección `lineage:` en `datapackage.yaml` y proponer la publicación hacia catálogos soberanos (`dm.publish`).

## Consecuencias y Compensaciones (Trade-offs)

### Positivas
- Cero fricción: el linaje se computa automáticamente al ejecutar el código.
- Memoria persistente local ultrarrápida: consultas analíticas instantáneas sobre la procedencia de datos sin re-escanear archivos.
- Trazabilidad científica reproducible (código fuente hasheado con SHA-256).
- Habilita al agente de IA para actuar como auditor informado antes de autorizar publicaciones.

### Negativas / Coste
- Requiere permisos de escritura local para crear el archivo `.datamesh/lineage.db`.
- Los scripts ejecutados en terminal deben ser deterministas para que los hashes de entrada y salida coincidan en ejecuciones repetidas.
