# ADR 0021: Entorno de Pruebas Hermético y Override Exclusivo de Workspace

## Estado
Aceptado

## Fecha
2026-10-11

## Contexto
La suite de pruebas del binding Python ejecutaba consultas canónicas (`dm.sql`) que resolvían tríadas a archivos físicos a través de:
- el directorio de proyectos del usuario (`~/Proyectos`, con cientos de repos hermanos),
- el caché temporal (`~/datamesh/cache`),
- un checkout hermano de `catalogo-datamesh` (rutas relativas hardcodeadas `../catalogo-datamesh/...`).

Consecuencia: tres pruebas (`test_mcp_sql_tool`, `test_user_reported_queries`, `test_user_join_query_with_decimal_json_serializable`) pasaban o fallaban según lo que hubiera en la máquina del desarrollador, no según el código. En un entorno "limpio" resolvían a un CSV de Kaggle con 4 estaciones (esperando 14) o a un dataset electoral ajeno, y además descargaban red (lento, no reproducible en CI). Además, los directorios `DEFAULT_CACHE_DIR`/`DEFAULT_DATAMESH_HOME` se calculaban en el import de `constants.py`, por lo que `DATAMESH_HOME`/`DATAMESH_CACHE_DIR` no surtían efecto en la resolución de tríadas.

## Decisión
1. **Override exclusivo de workspace:** `get_workspace_search_dirs()` trata `DATAMESH_PROJECTS_DIR`/`DATAMESH_WORKSPACE_DIR` como la **única** raíz cuando se define (en lugar de añadirla a `~/Projects`, `~/Proyectos`, `~/workspace`, `~/src` y al directorio padre del CWD). Sin la variable, el comportamiento por defecto no cambia.
2. **Rutas dinámicas y conscientes del entorno:** `local_workspace.py`, `duckdb_engine.py`, `inmem_engine.py` y `zip_extractor.py` resuelven home/caché vía `get_datamesh_home()`/`get_cache_dir()` en tiempo de ejecución, en vez de las constantes congeladas `DEFAULT_*` capturadas en el import.
3. **Eliminación de candidatos absolutos-relativos ocultos:** se retiran de `find_node_datapackage` los candidatos `../catalogo-datamesh/...` y `../../catalogo-datamesh/...`, que evadían el override. El caso por defecto sigue cubierto porque `get_workspace_search_dirs()` incluye el directorio padre del CWD y se añade `{ws}/catalogo-datamesh/knowledge/nodes/{ds}`.
4. **Workspace de fixtures + `conftest.py` hermético:** `bindings/python/tests/conftest.py` fija, antes de importar `datamesh`, `DATAMESH_HOME`/`DATAMESH_CACHE_DIR` a un directorio temporal y `DATAMESH_PROJECTS_DIR`/`DATAMESH_WORKSPACE_DIR` a `tests/fixtures/`. El workspace de fixtures contiene nodos mínimos (`air_quality`, `p2p-bob-exchange`, `elecciones`, `presupuesto`) con recursos locales, de modo que las consultas resuelven datos deterministas offline.

## Consecuencias
- **Positivo:** suite hermética y reproducible (0 red en los tests de consulta: 77 tests en ~4 s); los 3 fallos ambientales desaparecen sin debilitar las aserciones; resolución de tríadas respeta `DATAMESH_HOME`/`DATAMESH_CACHE_DIR`/`DATAMESH_PROJECTS_DIR`.
- **Coste / cambio de comportamiento:** quien defina `DATAMESH_PROJECTS_DIR`/`DATAMESH_WORKSPACE_DIR` obtendrá *solo* esa raíz (semántica de override explícito, coherente con el nombre de la variable). Para restaurar el escaneo amplio basta con no definir la variable.
- **Fixtures versionados:** se agrega `bindings/python/tests/fixtures/` (manifiestos + CSV/Parquet mínimos). `mock_data_elecciones.csv` y `mock_data_presupuesto.parquet` son copias de `core-go/testdata/` para mantener la resolución local y sin CWD-dependencia.

## Referencias
- ADR 0018 (composition root delgado), ADR 0020 (resolución única de datapackage).
- `bindings/python/datamesh/constants.py`, `bindings/python/datamesh/adapters/workspace/local_workspace.py`, `bindings/python/tests/conftest.py`, `bindings/python/tests/fixtures/`.
