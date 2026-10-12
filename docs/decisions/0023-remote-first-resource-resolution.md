# ADR 0023: Resolución de Recursos Remotos "Remoto-Primero"

## Estado
Aceptado

## Fecha
2026-10-12

## Contexto
Al probar el SDK contra un caso real (`monitor-economico` consultando
`p2p-bob-exchange:advice`) la resolución devolvía datos del **2025-11-27** aunque
el dataset publicado en Kaggle ya estaba actualizado al **2026-10-12**.

El origen no era Kaggle, sino la precedencia de los adaptadores:

- `KaggleAdapter._find_local_sibling_file` y `GitHubAdapter._find_in_local_clone`
  buscaban **primero** una copia en cualquier proyecto hermano del workspace
  (`~/Proyectos/...`) y la devolvían sin descargar. Una copia local obsoleta
  (`p2p-bob-exchange/data/advice.parquet`, sin versionar ni actualizar)
  **ensombrecía** la fuente canónica declarada por el nodo.
- `HttpAdapter`/`GitHubAdapter`/`KaggleAdapter` devolvían la entrada de caché sin
  revalidar, de modo que nunca se veía una versión nueva aunque existiera.

Resultado: comportamiento no determinista y datos silenciosamente desactualizados,
en contradicción con el principio "googlear antes de reutilizar" y con el mandato
de trazabilidad/linaje (ADR 0009, ADR 0013).

## Decisión
Los adaptadores de recursos **remotos** (`kaggle`, `github`, `http`) establecen:

1. **Remoto-primero:** siempre se intenta descargar la última versión publicada y
   se refresca la caché temporal (`storage.save`/`storage.store_file`).
2. **Detección de cambio:** se compara el `sha256` nuevo con el almacenado en la
   metadata; si cambió se registra (`logging.info`). Así el sistema de linaje puede
   validar si la fuente mutó entre resoluciones.
3. **Fallback degradado con aviso:** si la descarga falla (offline, sin
   credenciales, error de red) se recurre, en este orden, a (a) la copia en caché y
   (b) una copia local hermana/clon, **siempre** emitiendo `logging.warning` que
   advierte de que la copia puede estar desactualizada. Si nada existe, se propaga
   el error.
4. **Frecuencia de actualización en metadata:** `CacheEntryMetadata.update_frequency`
   registra la periodicidad declarada por el nodo (`temporal.frequency` en el
   `datapackage`/OKF), inyectada por `ResolveAndCacheResourceUseCase` desde
   `LocalWorkspaceResolver.node_update_frequency()`.

El fallback local se desterró de la ruta feliz: ya no es una optimización
silenciosa de cero copias, sino un modo degradado explícito y observable.

## Consecuencias
- **Positivo:** los datos están siempre al día; el resultado es determinista y no
  depende de copias accidentales en proyectos hermanos; las desviaciones son
  auditables (warning + linaje/`sha256` + frecuencia).
- **Coste:** cada resolución remota implica una descarga/validación (latencia,
  cuota de red/Kaggle). El modo offline depende de la caché y emite warnings. La
  resolución en entornos sin red es más lenta por el intento fallido previo al
  fallback.

## Referencias
- ADR 0016 (endurecimiento de red), ADR 0020 (deduplicación de resolución), ADR 0022 (propiedad C-ABI y PyYAML).
- `bindings/python/datamesh/adapters/resolvers/{kaggle,github,http}.py`,
  `bindings/python/datamesh/adapters/workspace/local_workspace.py`,
  `bindings/python/datamesh/usecases/resolve_resource.py`,
  `bindings/python/datamesh/domain/models.py` (`CacheEntryMetadata`).
