# Referencia Técnica de Interfaces CLI: DataMesh SDK

DataMesh SDK cuenta con dos interfaces de línea de comandos equivalentes y sincronizadas con la arquitectura hexagonal:

1. **Go Core CLI (`datamesh` compilado desde `core-go/adapters/inbound/cli/main.go`)**: Rendimiento nativo, cero dependencias, ideal para contenedores y sistemas sin Python.
2. **Python CLI (`python -m datamesh.cli` o `datamesh`)**: Orientado a pipelines de datos, entornos de ciencia de datos y servidores de agentes IA vía MCP.

---

## 1. Comandos Disponibles

### 1.1 `catalog [url]`
Descubre y parsea catálogos soberanos federados en formato `llms.txt`.
- **Sin argumento:** Descubre de forma descentralizada y concurrente todos los catálogos configurados en `catalogs` / `DATAMESH_CATALOGS` (por defecto `https://datosbolivia.github.io/llms.txt`).
- **Con argumento `url`:** Consulta únicamente el catálogo especificado.

```bash
# Go CLI
datamesh catalog
datamesh catalog https://datosbolivia.github.io/llms.txt

# Python CLI
python3 -m datamesh.cli catalog
python3 -m datamesh.cli catalog https://datosbolivia.github.io/llms.txt
```

**Salida (JSON):**
```json
{
  "title": "DataMesh Federated Catalog",
  "source_catalogs": [
    "https://datosbolivia.github.io/llms.txt"
  ],
  "entries": [
    {
      "title": "Atlas Electoral y Elecciones Generales de Bolivia (1979-2025)",
      "uri": "/raw/nodes/elecciones-bolivia/index.md",
      "resolved_url": "https://datosbolivia.github.io/raw/nodes/elecciones-bolivia/index.md",
      "description": "Conjunto de datos estructurados sobre la historia democrática...",
      "domain": "Demografía, Censos y Sociedad",
      "resources": ["elecciones_generales_2020"],
      "catalog_source": "https://datosbolivia.github.io/llms.txt"
    }
  ]
}
```

---

### 1.2 `search <keyword> [url]`
Busca Data Products a través de los catálogos soberanos coincidentes en título, descripción o dominio.

```bash
# Go CLI
datamesh search elecciones
datamesh search creditos https://datosbolivia.github.io/llms.txt

# Python CLI
python3 -m datamesh.cli search elecciones
```

---

### 1.3 `get <uri_or_url>`
Resuelve y valida un Data Product OKF v0.2 a partir de su URI o URL HTTP directa a su `index.md`.

```bash
# Go CLI
datamesh get https://datosbolivia.github.io/raw/nodes/elecciones-bolivia/index.md

# Python CLI
python3 -m datamesh.cli get https://datosbolivia.github.io/raw/nodes/elecciones-bolivia/index.md
```

**Salida (JSON):**
```json
{
  "id": "https://datosbolivia.github.io/raw/nodes/elecciones-bolivia/index.md",
  "manifest": {
    "type": "dataset",
    "title": "Atlas Electoral y Elecciones Generales de Bolivia (1979-2025)",
    "dimensions": ["año", "departamento", "circunscripcion", "partido"],
    "contracts": [
      {
        "type": "datapackage",
        "path": "./datapackage.yaml"
      }
    ],
    "lineage": {
      "sources": ["https://github.com/datosbolivia/elecciones2025"],
      "version": "1.0.0",
      "updated_at": "2026-09-11T00:00:00Z"
    }
  },
  "description": "# Atlas Electoral y Elecciones Generales de Bolivia..."
}
```

---

### 1.4 `query <resource_uri> [--filter key=value] [--limit N]`
Ejecuta consultas tabulares en memoria sobre recursos CSV/TSV locales o remotos, aplicando filtros de columna y límites.

```bash
# Go CLI
datamesh query ./data.csv --filter departamento="La Paz" --limit 10

# Python CLI
python3 -m datamesh.cli query ./data.csv --filter departamento="La Paz" --limit 10
python3 -m datamesh.cli query https://example.org/sample.csv --filter partido="MAS"
```

**Salida (JSON):**
```json
{
  "columns": ["año", "departamento", "circunscripcion", "partido", "votos_validos"],
  "rows": [
    ["2020", "La Paz", "C-1", "MAS", "45200"],
    ["2020", "La Paz", "C-1", "CC", "32100"]
  ],
  "row_count": 2
}
```

---

### 1.5 `config`
Imprime la configuración activa resultante de la fusión de valores por defecto, archivos `datamesh.json` / `datamesh.yaml` y variables de entorno `DATAMESH_*`.

```bash
datamesh config
```

---

### 1.6 `mcp-serve` (Python CLI)
Inicia el servidor Model Context Protocol (MCP) estándar sobre entrada/salida estándar (`stdio`). Permite a agentes de IA (Claude Desktop, Cursor, Antigravity, cline, etc.) ejecutar herramientas de descubrimiento y consulta directamente.

```bash
python3 -m datamesh.cli mcp-serve
```
