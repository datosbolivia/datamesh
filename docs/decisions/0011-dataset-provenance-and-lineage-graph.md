# ADR 0011: Proveniencia de Datos, Trazabilidad Criptográfica y Grafo DAG de Derivación (Lineage)

- **Estado:** Aceptado
- **Fecha:** 2026-10-07
- **Contexto:**
  En ecosistemas de datos federados y mallas de datos (DataMesh), los conjuntos de datos no existen aislados; con frecuencia son el resultado de procesos de ingesta, limpieza, normalización o agregación computacional aplicados sobre otros datasets (upstream).
  Los consumidores, auditores y agentes de IA necesitan determinar con precisión:
  1. ¿De qué fuentes o datasets proviene un producto de datos específico? (linaje aguas arriba / *upstream*).
  2. ¿Qué datasets o reportes son el resultado o derivación directa de un dataset dado? (linaje aguas abajo / *downstream*).
  3. ¿Cuáles herramientas, scripts o consultas SQL intermedias transformaron los datos y cuál es su firma/hash de integridad criptográfica SHA-256? (cumplimiento normativo de PE3 y PE5 de OKF/ODKF v0.2 y el estándar W3C PROV-O).

- **Decisión:**
  1. **Go Core como Autoridad Central de Dominio (`core-go/domain/lineage.go` & `core-go/usecases/lineage_usecase.go`):**
     - La lógica de negocio, traversal transitivo del DAG (`Upstream`, `Downstream`), entidades (`LineageSource`, `LineageTransformation`, `LineageInfo`, `LineageNode`, `LineageEdge`, `LineageGraph`) y renderizadores (`ToMermaid`, `ToASCII`) residen primordialmente en Go Core.
     - Se implementó `LineageServicePort` en `core-go/ports/inbound/services.go` y el caso de uso `LineageUseCase`.
     - Se añadieron exports C-ABI en `core-go/adapters/inbound/cshared/exports.go`: `DataMeshGetLineage` y `DataMeshLineageGraph`, con liberación de memoria segura (`DataMeshFreeString`).
     - Se añadió soporte nativo en el CLI de Go (`core-go/adapters/inbound/cli/main.go`) mediante el subcomando `datamesh lineage [target] [--format ascii|mermaid|json]`.
  2. **Bindings y Convención de Prefijo `_`:**
     - Siguiendo la convención arquitectónica del SDK, los métodos del core Go se encuentran disponibles en los bindings con el prefijo `_` (`_lineage`, `_get_lineage`, `_discover`, `_search`, etc.).
     - La fachada de alto nivel delega al C-ABI (`_lib.DataMeshGetLineage`) si la biblioteca compilada está presente, o ejecuta el fallback autónomo en el lenguaje host (`DatasetLineageUseCase` en Python).
  3. **Dos Versiones del Core (Full vs. Headless/Minimal):**
     - *Core con Adaptadores (Full Batteries-Included):* Incluye motores de query nativos (DuckDB/InMem), adaptadores de red (HTTP/GitHub/Kaggle), y resolvedores de catálogo para CLI y servidores embebidos.
     - *Core Minimal / Headless (Sin Adaptadores):* Ofrece únicamente los agregados de dominio y puertos abstractos, permitiendo que cada binding (Python con DuckDB columnar en memoria, TypeScript con WASM y Virtual File System de navegador, R con drivers nativos) conecte adaptadores ligeros o específicos del runtime sin cargar dependencias pesadas innecesarias.
  4. **Modelos de Dominio en Python (`bindings/python/datamesh/domain/models.py`):**
     - Dataclasses inmutables (`frozen=True`) homólogas a Go Core para paridad cross-language.
  5. **Persistencia y Creación de Paquetes (`CreateDataPackageUseCase`):**
     - Parámetros `sources`, `transformations` y `lineage` en `dm.create_datapackage(...)`.
  6. **CLI y Servidor MCP:**
     - Python CLI: `datamesh lineage [target] [--format ascii|mermaid|json] [--dir DIR]`.
     - Herramienta MCP: `datamesh_get_lineage` bajo guardrails estrictos de no-alucinación.

- **Consecuencias:**
  - **Positivas:**
    - Cero duplicidad lógica: Go Core gobierna la semántica de proveniencia mientras los bindings consumen la API C-ABI directamente o mediante adaptadores optimizados.
    - Soporte completo del estándar OKF v0.2 (PE3/PE5) y W3C PROV-O en Go, Python y CLI.
    - Flexibilidad de distribución: opción de compilar un binario/so ligero sin adaptadores o uno autocontenido.
  - **Compensaciones:**
    - Los bindings deben mantener sincronizadas las definiciones de structs/dataclasses y wrappers de serialización JSON entre Go y los lenguajes cliente.

