# ADR 0020: Eliminación de Duplicación en Resolución de Datapackage y Determinismo de Salidas en Go

## Estado
Aceptado

## Fecha
2026-10-11

## Contexto
La auditoría posterior a los ADR 0018/0019 detectó dos focos de deuda:

1. **Duplicación Python:** `usecases/resolve_resource.py` (`ResolveAndCacheResourceUseCase`) reimplementaba la búsqueda de manifiestos datapackage (`_find_node_datapackage`, ~90 líneas) y el recorrido de recursos (`_lookup_datapackage_resource`, ~45 líneas) ya presentes en `adapters/workspace/local_workspace.py` (`LocalWorkspaceResolver.find_node_datapackage` / `resolve_triad_to_path`). Ambas copias habían divergido: la del caso de uso soportaba contratos por referencia (`contracts: [{ref: ...}]` en `index.md`) y la del adaptador soportaba normalización de URLs de GitHub y cacheo local. Mantener dos lógicas de "tríada → ruta física" garantiza bugs de inconsistencia (ADR 0018 ya había extraído el resto de infraestructura por esta misma razón).

2. **Bugs y no-determinismo en Go Core:**
   - `domain/ckan_manifest.go`: `r.ID[:8]` provocaba **panic** con identificadores de recurso CKAN de longitud < 8 (o vacíos).
   - `usecases/publish_and_semantic_usecase.go` (`GenerateCaseExpression`): iteraba `mapping.ValueMapping` (un `map`), por lo que el orden de las cláusulas `WHEN` de la expresión SQL `CASE` era aleatorio entre ejecuciones.

## Decisión

### 1. Fuente única de resolución de datapackage (Python)
`ResolveAndCacheResourceUseCase` recibe un `LocalWorkspaceResolver` inyectado (`workspace_resolver`) y **delega** la resolución tríada→ruta en `resolve_triad_to_path`. Se eliminan `_find_node_datapackage` y `_lookup_datapackage_resource`. La capacidad de contratos por referencia de `index.md` se **porta** a `LocalWorkspaceResolver._read_manifest_from_index`, de modo que el adaptador conserva la unión de capacidades (manifiestos locales/remotos + contratos por ref + normalización GitHub + cacheo local). En `core.py` se inyecta `self._workspace` (el mismo resolver ya usado por los motores).

### 2. Robustez y determinismo en Go
- `resourceNameFromID` genera un nombre de recurso estable y libre de panics para IDs cortos/vacíos.
- `GenerateCaseExpression` ordena las claves de `ValueMapping` (`sort.Strings`) antes de emitir las cláusulas `WHEN`, garantizando una salida reproducible.

## Consecuencias
- **Positivo:** una sola implementación de "tríada → ruta física" (DRY) alineada con ADR 0018; sin panics ante metadatos CKAN incompletos; salidas SQL deterministas (relevante para firmas/hashes y tests).
- **Coste:** `ResolveAndCacheResourceUseCase` gana un parámetro opcional `workspace_resolver` (retrocompatible: si se omite, se construye uno por defecto). El comportamiento de resolución es ahora el del adaptador unificado (incluye cacheo local y normalización GitHub), lo que es una mejora, no una regresión.
- Nuevos tests: `domain/ckan_manifest_test.go` (IDs cortos/vacíos y `nil`), determinismo reforzado en `usecases/publish_and_semantic_usecase_test.go`, y `test_hexagonal_storage_and_resolvers.py::test_local_workspace_resolves_contract_ref_from_index`.

## Referencias
- ADR 0008 (bindings como edge adapters), ADR 0018 (composition root delgado), ADR 0019 (determinismo de motores).
- `bindings/python/datamesh/adapters/workspace/local_workspace.py`, `bindings/python/datamesh/usecases/resolve_resource.py`.
