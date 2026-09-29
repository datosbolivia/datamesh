# Especificación del Servidor Model Context Protocol (MCP) para Agentes de IA

El módulo [`datamesh.mcp_server`](file:///home/andreschirinos/Proyectos/datamesh-sdk/bindings/python/datamesh/mcp_server.py) implementa la especificación **Model Context Protocol (MCP) versión 2024-11-05** mediante transporte JSON-RPC 2.0 sobre `stdio`.

Permite que cualquier agente o asistente de IA descubra, inspeccione y consulte productos de datos abiertos y soberanos sin alucinaciones.

---

## 1. Configuración del Servidor en Agentes

### Configuración en Claude Desktop o Cursor (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "datamesh": {
      "command": "python3",
      "args": ["-m", "datamesh.cli", "mcp-serve"],
      "env": {
        "DATAMESH_CATALOGS": "https://datosbolivia.github.io/llms.txt,https://custom-portal.org/llms.txt"
      }
    }
  }
}
```

---

## 2. Herramientas Expuestas (Tools Catalog)

| Nombre de Herramienta | Parámetros | Descripción |
|---|---|---|
| `datamesh_discover_catalogs` | `catalog_url` *(opcional)* | Descubre y lista Data Products a través de los catálogos soberanos federados o una URL específica. |
| `datamesh_search_catalog` | `keyword` *(requerido)*, `catalog_url` *(opcional)* | Busca Data Products por palabra clave en título, descripción o dominio. |
| `datamesh_get_dataproduct` | `uri` *(requerido)* | Resuelve y devuelve el manifiesto OKF v0.2, dimensiones, contratos y linaje de un nodo. |
| `datamesh_query_resource` | `resource_uri` *(requerido)*, `filters` *(opcional)*, `limit` *(opcional)* | Ejecuta consultas y filtrado tabular en memoria sobre recursos CSV/TSV. |
| `datamesh_sql_query` | `sql_query` *(requerido)* | Ejecuta consultas ANSI SQL completas con DuckDB usando tríadas `"catalogo:dataset:resource"`. Normaliza formatos dispares (CSV, Parquet, JSON) en memoria. |

---

## 3. Guardrails Antialucinación Embebidos

El servidor MCP inyecta instrucciones normativas en el mensaje de inicialización (`initialize`) para forzar al agente a seguir 5 guardrails inquebrantables:

1. **Fundamentación Estricta:** Responder únicamente con los datos contenidos en el campo `rows` o `data` del resultado de la herramienta. Jamás inventar números, fechas o columnas.
2. **Cita Obligatoria de Procedencia:** Citar la tríada canónica (`catalogo:dataset:resource`).
3. **Transparencia ante Nulos:** Si una consulta devuelve 0 filas o `NULL`, declarar explícitamente que no se encontraron registros coincidentes. No generar datos ficticios.
4. **Verificación de Esquema:** Comprobar nombres de columnas con `datamesh_get_dataproduct` o `LIMIT 1` antes de construir consultas complejas.
5. **Separación de Hechos vs. Hipótesis:** Distinguir claramente los datos cuantitativos obtenidos de las interpretaciones subjetivas.

---

## 4. Plantillas de Prompts para Agentes (`prompts`)

El servidor expone prompts preconfigurados para guiar al modelo:

- **`grounded_sql_analysis`**: Exige al agente verificar el esquema antes de ejecutar el SQL y basar su conclusión estrictamente en los registros obtenidos.
- **`dataset_provenance_audit`**: Realiza una auditoría de integridad, contratos sintácticos, dimensiones y presencia de valores nulos.

---

## 5. Ejemplo de Ciclo de Interacción JSON-RPC

### 3.1 Inicialización:
```json
--> {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
<-- {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05", "serverInfo": {"name": "datamesh-mcp-server", "version": "0.2.0"}, "capabilities": {"tools": {}}}}
```

### 3.2 Invocación de Consulta Tabular (`tools/call`):
```json
--> {
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "datamesh_query_resource",
    "arguments": {
      "resource_uri": "https://datosbolivia.github.io/data/elecciones_2020.csv",
      "filters": {
        "departamento": "La Paz"
      },
      "limit": 5
    }
  }
}
```
**Respuesta:**
```json
<-- {
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\n  \"columns\": [\"año\", \"departamento\", \"circunscripcion\", \"partido\", \"votos_validos\"],\n  \"rows\": [[\"2020\", \"La Paz\", \"C-1\", \"MAS\", \"45200\"]],\n  \"row_count\": 1\n}"
      }
    ],
    "isError": false
  }
}
```
