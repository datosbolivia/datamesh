# ADR 0002: Catálogos Soberanos Descentralizados, Motor de Consulta Tabular y Servidor MCP

## Estado
Aceptado

## Contexto
El Formato de Conocimiento Abierto Federado (OKF/ODKF v0.2) exige un modelo descentralizado donde múltiples catálogos institucionales (municipios, ministerios, universidades, observatorios) puedan federarse sin depender de un único punto central de falla. Si bien `https://datosbolivia.github.io/llms.txt` funge como catálogo soberano por defecto, el SDK debe permitir agregar múltiples endpoints soberanos concurrentemente.

Asimismo, los agentes de IA requieren una vía estándar para interactuar con los datos sin alucinaciones, lo que demanda un servidor Model Context Protocol (MCP) nativo montado sobre la CLI y un motor de consultas tabulares en memoria para filtrar datos antes de pasarlos al contexto de los modelos.

## Decisión
1. **Catálogos Descentralizados Múltiples**:
   - `BaseConfig.CatalogURLs`: Lista de URLs de catálogos configurables mediante JSON/YAML (`catalogs: [...]`) o variables de entorno (`DATAMESH_CATALOGS=url1,url2`).
   - `DiscoverCatalogUseCase.DiscoverAll`: Recupera concurrentemente los catálogos con tolerancia a fallos, combinando y deduplicando entradas e inyectando la propiedad `catalog_source`.

2. **Motor de Consultas Tabulares en Memoria (`QueryEnginePort`)**:
   - Soporte para ejecutar consultas con filtros de igualdad por columna (`filters`) y límites de filas (`limit`) sobre recursos CSV/TSV locales o remotos sin requerir un servidor SQL externo.

3. **Servidor MCP Estándar (`bindings/python/datamesh/mcp_server.py`)**:
   - Protocolo JSON-RPC 2.0 sobre `stdio`.
   - Herramientas: `datamesh_discover_catalogs`, `datamesh_search_catalog`, `datamesh_get_dataproduct`, `datamesh_query_resource`.

## Consecuencias
- Descentralización total: los usuarios pueden federar catálogos privados y públicos simultáneamente.
- Agentes de IA pueden usar directamente las herramientas vía MCP sin wrappers adicionales.
- Consultas eficientes y ligeras en memoria para clientes y scripts.
