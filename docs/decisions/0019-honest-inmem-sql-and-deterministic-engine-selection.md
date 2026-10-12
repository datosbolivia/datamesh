# ADR 0019: Motor SQL Fallback Honesto y Selección Determinista de Motor

## Estado
Aceptado

## Fecha
2026-10-11

## Contexto
La auditoría del motor puro Go (`core-go/adapters/outbound/engine/csv_query_engine.go`, `InMemTabularQueryEngine`) reveló tres problemas de corrección y honestidad en el camino SQL del CLI/MCP de Go Core:

1. **Mentira funcional en `ExecuteSQL`:** el método ignoraba el texto SQL y devolvía *todas* las filas y columnas crudas del recurso, sin aplicar proyección, filtros ni `LIMIT`. Su doc-comment afirmaba "applies column selection". Un cliente que enviara `SELECT departamento, votos_validos ... WHERE departamento = 'La Paz' LIMIT 1` recibía la tabla completa en silencio: resultados incorrectos sin error.
2. **Sobreventa de capacidades:** el texto de ayuda del CLI (`datamesh sql`) y la descripción del tool MCP `datamesh_sql_query` prometían "full ANSI/DuckDB SQL", pero Go Core no embebe DuckDB (`core-go/go.mod` no depende de ningún driver DuckDB). Sólo existe el motor de respaldo en memoria.
3. **Selección de motor no determinista:** `QueryEngineRegistry.SelectEngine` iteraba `r.engines` (un `map`) en los pasos 2–4. En Go el orden de iteración de un `map` es aleatorio, por lo que con más de un motor registrado la elección (y por tanto el comportamiento) no era reproducible.

La especificación `ADR 0003` reserva el SQL ANSI completo (JOINs, agregaciones, funciones de ventana, CTEs) para el motor DuckDB del binding Python; Go Core sólo puede ofrecer un subconjunto de respaldo.

## Decisión

### 1. Subconjunto SQL explícito y honesto (`core-go/domain/sqlsubset.go`)
Se define `SimpleSelect` y `ParseSimpleSelect`, que aceptan exclusivamente:

```
SELECT <* | col[, col...]> FROM <tabla> [WHERE col = valor [AND col = valor ...]] [LIMIT n]
```

- La tabla puede ser una tríada canónica entrecomillada, una URL o una ruta.
- Los valores de `WHERE` deben ser literales (comillas simples/dobles) o numéricos; comparaciones por columna o predicados no igualitarios se rechazan.
- **Cualquier construcción fuera del subconjunto** (agregaciones, funciones, `JOIN`, `GROUP BY`, `ORDER BY`, `HAVING`, `UNION`, `DISTINCT`, `CASE`, subconsultas, paréntesis) produce un **error explícito** que indica usar el motor DuckDB. Nunca se devuelven resultados silenciosamente incorrectos.
- `QueryRequest` gana el campo `Select []string` para transportar la proyección.

### 2. `Execute` aplica proyección real
`InMemTabularQueryEngine.Execute` resuelve `req.Select` contra las cabeceras (case-insensitive) y proyecta las filas; `ExecuteSQL` parsea la consulta, resuelve **una única** tabla y delega en `Execute` con `Select`/`Filters`/`Limit`. `ExecuteSQL` rechaza recursos remotos (sólo lee rutas locales) y consultas multi-tabla.

### 3. Selección determinista de motor
`QueryEngineRegistry` ordena los motores por nombre (`sort.Strings`) antes de aplicar los pasos de preferencia por formato/JOIN cruzado/fallback, garantizando un resultado reproducible e independiente del orden de registro.

### 4. Honestidad en textos de interfaz
- `datamesh sql` (CLI) y el tool MCP `datamesh_sql_query` (Go) describen el subconjunto realmente soportado y remiten a DuckDB para ANSI completo.
- `docs/reference/go-cabi.qmd` (`DataMeshExecuteSQL`) documenta el subconjunto y el rechazo explícito.

## Consecuencias
- **Positivo:** el camino SQL de Go Core nunca miente; los errores son accionables; la elección de motor es determinista y testeable; se alinean código y documentación (ADR 0003).
- **Coste:** los clientes del CLI/MCP Go que enviaban SQL fuera del subconjunto ahora reciben un error en vez de datos incompletos; deben usar el binding Python (DuckDB) para analítica avanzada.
- Nuevos tests: `core-go/domain/sqlsubset_test.go` (parser válido/rechazo) y `core-go/adapters/outbound/engine/csv_query_engine_test.go` (proyección+filtro+límite, rechazo de SQL no soportado, rechazo multi-tabla).

## Referencias
- ADR 0003 (SQL completo con DuckDB y tríadas), ADR 0006 (motor abstracto), ADR 0008 (Go Core dominio / bindings borde), ADR 0018 (composition root delgado).
- `docs/reference/go-cabi.qmd`, `docs/reference/CLI.md` (§1.5, Python CLI con DuckDB).
