# ADR 0013: Autoridad Canónica en Go, Ingesta As-Is y ODKF como Hub de Exportación

## Estado
Aceptado

## Fecha
2026-10-11

## Contexto
El ecosistema OKF/ODKF v0.2 debe interoperar con catálogos que *no siguen* la convención del documento normativo `/.well-known/datamesh.json`. Hasta ahora el SDK solo soporta la vía de descubrimiento "conformante": `DiscoverWellKnownUseCase` (CU-14) resuelve el tipo de backend (`ckan`, `okf`, `dcat`, `git`) y `HarvestCKANUseCase` (CU-13) ingiere portales CKAN convencionales.

Dos problemas estructurales quedaban sin resolver:

1. **Autoridad distribuida del dominio.** Desde ADR 0008 el núcleo de dominio es Go, pero la lógica de reconstrucción cultural y mapeo de metadatos vive reproducida en Python (`bindings/python/datamesh/usecases/harvest_ckan.py`). Sin una norma explícita, cada binding tiende a re-implementar reglas de negocio en su propio idioma, reintroduciendo duplicidad.
2. **Puerto genérico de ingesta "as-is".** El core Go ya tiene un lector heterogéneo (`UnifiedMetadataReaderPort` con cadena de parsers extensible vía `RegisterParser`) y exportadores de publicación (ADR 0009), pero no expone un caso de uso que: (a) encuentre metadatos *tal y como están publicados* (llms.txt, `datapackage.json`/`datapackage.yaml`, `index.md` OKF, `package_show` de CKAN, DCAT) y los convierta al modelo canónico ODKF; y (b) convierta desde ODKF hacia otros estándares (CKAN/Frictionless DataPackage, W3C DCAT).

## Decisión

1. **Go es la única autoridad de dominio.** El lenguaje Go (`core-go/`) es la fuente única de verdad para: agregados de dominio (`DataProduct`, `PackageManifest`, `WellKnownDiscovery`, `Catalog`), invariantes de validación, reglas de reconstrucción y conversión de formatos. Ningún binding re-implementa reglas de negocio; los bindings (Python, TypeScript, R) aportan únicamente **adaptadores idiomáticos que implementan los puertos Go** (`WellKnownResolverPort`, `CKANClientPort`, `UnifiedMetadataReaderPort`, `AuthProviderPort`, `ResourceAdapterPort`, `StoragePort`, `QueryEnginePort`, `PublisherPort`).
2. **Dos vías de descubrimiento.** La herramienta debe encontrar metadatos de dos maneras:
   - **Conformante:** viaja por `WellKnownDiscovery` (CU-14) y usa el adapter idiomático apropiado. Queda permitida para portales que se adaptan a la herramienta.
   - **As-Is:** sondeo heurístico sobre la información *como está publicada* (sin well-known). El motor sondea `llms.txt`, `datapackage.json`/`.yaml`/`.yml`, `index.md` OKF y `package_show`/`status_show` de CKAN en ese orden, y **convierte lo que encuentra al modelo ODKF canónico**.
3. **ODKF como modelo hub.** Todo formato externo se importa normalizándolo a `DataProduct` (ODKF). Todo `DataProduct` ODKF puede exportarse a formatos externos mediante convertidores puros en `core-go/domain` (`knowledge_export.go`): CKAN/Frictionless DataPackage JSON y W3C DCAT JSON (extensibles a RO-Crate, etc.).
4. **Nuevo caso de uso:** `AsIsIngestUseCase` (interoperabilidad) orquesta la cadena de sondeo y expone la exportación, siguiendo la pila epistemológica de ADR 0014 (datos - información - conocimiento): los parsers entregan *información* (manifiestos), y `NewDataProduct` eleva a *conocimiento* ODKF validando invariantes (título, tipo, dimensiones).

## Consecuencias

### Positivas
- Una sola implementación de reconstrucción CKAN-ODKF y conversión ODKF-a-otros en Go; los bindings delegan.
- Extensibilidad declarativa: un formato nuevo = un nuevo `ManifestParserPort` registrado + un convertidor de exportación; sin tocar los casos de uso ni el dominio.
- Interoperabilidad real con catálogos que no emiten well-known; el mismo motor lee un OKF y un CKAN como objetos ODKF idénticos.
- Rellena el hueco de numeración 0012-0014 del registro de ADRs.

### Negativas
- Requiere que los adaptadores de red de los bindings sigan exponiendo los puertos Go con la misma *forma* de los datos Go (tipos JSON estables).
- El sondeo as-is puede interpretar mal recursos ambiguos (p.ej. un `llms.txt` con múltiples catálogos); se mitiga normalizando siempre a `DataProduct` y reportando el formato de origen detectado en `metadata["source_format"]`.
- Durabilidad: mientras no exista el puente C-ABI de ADR 0015 (prefijo `_`), los adaptadores Python que hoy cumplen estos puertos son concesión transitoria y deben migrar a llamadas al core Go.

### Compatibilidad
- Compatible con ADR 0008 (Go núcleo, bindings edge adapters), ADR 0010 (CKAN + well-known), ADR 0012 (endpoints unificados `datapackage_show`), ADR 0014 (pila epistemológica) y ADR 0015 (bindings delgados vía C-ABI).
- La vía conformante permanece intacta; el sondeo as-is es aditivo.
