# Guía de Inicio Rápido (Quickstart) — DataMesh SDK

Bienvenido a **DataMesh SDK**, la infraestructura abierta y soberana para consultar, federar y analizar datos abiertos (OKF / ODKF v0.2) con soporte para múltiples catálogos descentralizados, motor SQL en memoria (DuckDB) y servidor MCP (Model Context Protocol) para agentes de Inteligencia Artificial.

Repositorio oficial: [https://github.com/datosbolivia/datamesh.git](https://github.com/datosbolivia/datamesh.git)

---

## 1. Instalación

### 1.1 Clonar el Repositorio
```bash
git clone https://github.com/datosbolivia/datamesh.git
cd datamesh
git checkout core-go-sdk
```

### 1.2 Opción A: Python SDK y CLI (Recomendado para Ciencia de Datos y MCP)
Requiere Python 3.9+:

```bash
# Instalación en modo desarrollo
pip install -e bindings/python

# O instalación directa desde Git
pip install git+https://github.com/datosbolivia/datamesh.git#subdirectory=bindings/python
```

Verificar la instalación:
```bash
datamesh --help
```

### 1.3 Opción B: Go Core CLI (Binario Nativo Ultraligero)
Requiere Go 1.22+:

```bash
cd core-go
go build -o ../datamesh adapters/inbound/cli/main.go
cd ..
./datamesh --help
```

### 1.4 Opción C: TypeScript / Navegador Web
Para entornos frontend o dashboards sin backend:

```bash
cd bindings/typescript
npm install
npm run build
```

---

## 2. Configuración

El SDK no requiere configuración obligatoria para empezar; utiliza por defecto el catálogo soberano de Bolivia: `https://datosbolivia.github.io/llms.txt`.

### 2.1 Variables de Entorno
```bash
# Catálogo único
export DATAMESH_CATALOG_URL="https://datosbolivia.github.io/llms.txt"

# O múltiples catálogos federados (Descentralizado)
export DATAMESH_CATALOGS="https://datosbolivia.github.io/llms.txt,https://custom-dataspace.org/llms.txt"

# Parámetros base
export DATAMESH_STORAGE_PATH="./.datamesh/cache"
export DATAMESH_TIMEOUT="30"
export DATAMESH_LOG_LEVEL="info"

# Configuración específica de adaptadores: DATAMESH__{ADAPTADOR}_{VARIABLE}
export DATAMESH__KAGGLE_KEY="tu_clave_api"
export DATAMESH__GITHUB_TOKEN="ghp_tu_token"
```

### 2.2 Archivo de Configuración (`datamesh.json` o `datamesh.yaml`)
Crea un archivo `datamesh.yaml` en la raíz de tu proyecto:

```yaml
# Catálogo base por defecto
catalog_url: https://datosbolivia.github.io/llms.txt

# Catálogos federados descentralizados
catalogs:
  - https://datosbolivia.github.io/llms.txt
  - https://custom-dataspace.org/llms.txt

storage_path: .datamesh/cache
timeout: 30
log_level: info

adapters:
  kaggle:
    key: tu_clave_kaggle
  github:
    token: tu_token_github
```

---

## 3. Uso desde la Línea de Comandos (CLI)

### 3.1 Descubrir Catálogos Soberanos
Descarga y parsea de forma concurrente todos los catálogos configurados (`llms.txt`):

```bash
# Descubrir todos los catálogos federados
datamesh catalog

# Descubrir un catálogo específico
datamesh catalog https://datosbolivia.github.io/llms.txt
```

### 3.2 Buscar Productos de Datos
Filtra por palabra clave en título, descripción o dominio temático:

```bash
datamesh search elecciones
datamesh search "calidad del aire"
```

### 3.3 Inspeccionar un Data Product (OKF v0.2)
Obtén y valida el manifiesto, dimensiones, contratos y linaje de un nodo:

```bash
datamesh get https://datosbolivia.github.io/raw/nodes/elecciones-bolivia/index.md
```

### 3.4 Consultas Tabulares Simples
Filtra recursos CSV/TSV locales o remotos:

```bash
datamesh query ./core-go/testdata/mock_data_elecciones.csv --filter departamento="La Paz" --limit 5
```

### 3.5 Consultas SQL Completas con DuckDB y Tríadas Canónicas
Ejecuta consultas **ANSI SQL completas** referenciando tablas mediante la tríada `"catalogo:dataset:resource"`. El motor normaliza sobre la marcha la heterogeneidad de formatos (CSV, TSV, Parquet, JSON):

```bash
# Agregación SQL
datamesh sql "
SELECT departamento, SUM(votos_validos) as total_votos
FROM 'core-go/testdata/mock_data_elecciones.csv'
GROUP BY departamento
ORDER BY total_votos DESC"

# JOIN cruzado entre formatos distintos (CSV + Parquet)
datamesh sql "
SELECT 
    e.departamento,
    SUM(e.votos_validos) as votos_totales,
    p.presupuesto,
    p.sector
FROM 'bolivia:elecciones:votos' e
JOIN 'municipal:presupuesto:ejecucion' p ON e.departamento = p.municipio
GROUP BY e.departamento, p.presupuesto, p.sector
ORDER BY votos_totales DESC"
```

---

## 4. Uso como Librería Python (Fachada de 1 Línea)

```python
import datamesh as dm

# 1. Descubrimiento federado
catalogo = dm.discover()
print(f"Catálogos conectados: {catalogo.get('source_catalogs')}")
print(f"Total datasets encontrados: {len(catalogo.get('entries', []))}")

# 2. Búsqueda semántica / por palabra clave
resultados = dm.search("elecciones")
for r in resultados:
    print(f"- {r['title']} ({r['domain']}) -> {r['resolved_url']}")

# 3. Inspección de metadatos OKF
nodo = dm.get("https://datosbolivia.github.io/raw/nodes/elecciones-bolivia/index.md")
print(f"Tipo: {nodo['manifest']['type']}, Dimensiones: {nodo['manifest']['dimensions']}")

# 4. Consulta ANSI SQL con DuckDB y Tríadas Canónicas
query_sql = """
SELECT departamento, SUM(votos_validos) as total_votos
FROM 'bolivia:elecciones:votos'
GROUP BY departamento
ORDER BY total_votos DESC
"""
resultado = dm.sql(query_sql, table_mapping={
    "bolivia:elecciones:votos": "core-go/testdata/mock_data_elecciones.csv"
})
print("Columnas:", resultado["columns"])
print("Filas:", resultado["rows"])
```

---

## 5. Configurar el Servidor MCP para Agentes de IA

DataMesh incluye un servidor **Model Context Protocol (MCP)** nativo sobre `stdio`, permitiendo a herramientas como **Claude Desktop**, **Cursor**, **Antigravity**, **Cline** u otros agentes interactuar con datos federados y ejecutar consultas SQL.

### 5.1 Iniciar el Servidor Manualmente
```bash
datamesh mcp-serve
```

### 5.2 Configuración en Claude Desktop o Cursor
Agrega el servidor en tu archivo `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "datamesh": {
      "command": "datamesh",
      "args": ["mcp-serve"],
      "env": {
        "DATAMESH_CATALOGS": "https://datosbolivia.github.io/llms.txt"
      }
    }
  }
}
```

### 5.3 Herramientas Disponibles en el Agente

| Herramienta MCP | Descripción |
|---|---|
| `datamesh_discover_catalogs` | Descubre datasets en catálogos soberanos federados o específicos. |
| `datamesh_search_catalog` | Busca por palabra clave en título, descripción o dominio. |
| `datamesh_get_dataproduct` | Lee manifiesto, dimensiones y linaje de un nodo OKF v0.2. |
| `datamesh_query_resource` | Filtra datos tabulares simples (CSV/TSV). |
| `datamesh_sql_query` | Ejecuta consultas ANSI SQL completas con DuckDB usando tríadas `"catalogo:dataset:resource"`. |

---

## 6. Documentación Adicional

- [Arquitectura Hexagonal y Puertos](file:///home/andreschirinos/Proyectos/datamesh-sdk/docs/reference/ARQUITECTURA.md)
- [Casos de Uso Formales](file:///home/andreschirinos/Proyectos/datamesh-sdk/docs/reference/CASOS_DE_USO.md)
- [Referencia Completa de Comandos CLI](file:///home/andreschirinos/Proyectos/datamesh-sdk/docs/reference/CLI.md)
- [Especificación Técnica del Servidor MCP](file:///home/andreschirinos/Proyectos/datamesh-sdk/docs/reference/MCP_SERVER.md)
- [ADRs de Decisiones de Diseño](file:///home/andreschirinos/Proyectos/datamesh-sdk/docs/decisions/)
