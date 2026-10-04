# R Binding — Sovereign DataMesh SDK (`datamesh`)

Paquete oficial de R para consumir el ecosistema federado DataMesh (OKF / ODKF v0.2).

## Características

- **Arquitectura Hexagonal**: Se conecta directamente al núcleo canónico de Go (`core-go/`) mediante la interfaz C-ABI (`libdatamesh.so` / `libdatamesh.dylib` / `datamesh.dll`), manteniendo un fallback puro en R para entornos sin binarios nativos.
- **Fachada Unificada de 5 Métodos**:
  1. `datamesh_discover()` / `dm_discover()`: Descubrimiento y federación multicatálogo.
  2. `datamesh_search()` / `dm_search()`: Búsqueda por palabra clave en título, descripción o dominio.
  3. `datamesh_get()` / `dm_get()`: Resolución y validación de Data Products OKF v0.2.
  4. `datamesh_query()` / `dm_query()`: Consulta y filtrado tabular con límites.
  5. `datamesh_sql()` / `dm_sql()`: Ejecución SQL ANSI/DuckDB sobre tríadas canónicas y URLs.

## Instalación

```r
# Vía devtools o remotes desde el repositorio local o GitHub
devtools::install("bindings/r")
```

## Uso Rápido

```r
library(datamesh)

# 1. Descubrir catálogos federados
cat <- dm_discover()
print(cat$entries)

# 2. Búsqueda por palabra clave
elecciones <- dm_search("elecciones")

# 3. Obtener metadatos de un Data Product OKF v0.2
dp <- dm_get("https://datosbolivia.github.io/raw/nodes/elecciones-bolivia/index.md")
print(dp$manifest$title)

# 4. Consulta tabular con filtros
df <- dm_query(
  "https://datosbolivia.github.io/datasets/cartera-creditos/creditos.csv",
  filters = list(departamento = "La Paz"),
  limit = 100
)

# 5. Ejecutar SQL con DuckDB sobre tríadas
mapping <- list(
  "bolivia:elecciones:votos" = "path/to/votos.csv"
)
res <- dm_sql(
  "SELECT departamento, SUM(votos_validos) as total FROM 'bolivia:elecciones:votos' GROUP BY departamento",
  table_mapping = mapping
)
head(res)
```
