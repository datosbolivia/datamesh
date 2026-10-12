# ADR 0017: Autoridad Única del Dominio y Erradicación de Acoplamientos Laterales en Go Core

## Estado
Aceptado

## Fecha
2026-10-11

## Contexto
La auditoría de arquitectura de `core-go/` detectó tres violaciones del patrón Ports & Adapters y del principio "Go Core como autoridad de dominio" (ADR 0008):

1. **Adaptador → Adaptador:** `adapters/outbound/resolvers/node_resolver.go` importaba e instanciaba directamente el adaptador `adapters/outbound/manifests` (`NewUnifiedMetadataReader`). Un adaptador outbound no debe conocer ni construir a otro; solo debe depender de puertos.
2. **Caso de uso → Caso de uso (detalle privado):** `usecases/ingest_as_is.go` dependía del tipo concreto `*HarvestCKANUseCase` y accedía a su campo **no exportado** `harvester.ckanClient`, acoplando un caso de uso a la representación interna de otro. La lógica de reconstrucción CKAN→ODKF vivía dentro del caso de uso de harvest, aunque es una transformación pura (sin E/S).
3. **Validación fuera del dominio:** el paquete `core-go/validator` contenía reglas normativas OKF/ODKF (PE1-PE5, formato de tríadas, SHA-256, anclas SKOS, contratos) — es decir, **invariantes de dominio** — aislado en un paquete hermano del dominio.

Estas violaciones impedían sustituir adaptadores, probar casos de uso con dobles simples y garantizar una única fuente de verdad para las reglas OKF.

## Decisión

### 1. El resolver depende de un puerto, no de un adaptador
`NodeDataProductResolver` recibe un `outbound.UnifiedMetadataReaderPort` en su constructor (`NewNodeDataProductResolver(reader)`) y delega `ReadNode`. El composition root (`cli/main.go`, `cshared/exports.go`, `wasm/main_wasm.go`) construye el `UnifiedMetadataReader` concreto y lo inyecta. Ningún adaptador outbound importa a otro.

### 2. La reconstrucción CKAN→ODKF se eleva al dominio
`domain.ReconstructManifestFromCKAN(pkg *CKANPackage) (*PackageManifest, error)` (en `core-go/domain/ckan_manifest.go`) es la única implementación de la transformación, sin E/S ni contexto. `HarvestCKANUseCase.ReconstructOKF` (contrato del puerto inbound) pasa a ser un delegado de una línea. `AsIsIngestUseCase` depende ahora de `outbound.CKANClientPort` y del dominio, **no** del otro caso de uso ni de sus campos privados.

### 3. `validator` se fusiona con `domain`
`core-go/validator/validator.go` se mueve a `core-go/domain/validator.go` (`package domain`). `ValidateUseCase` consume `domain.ValidateConceptContent/ValidateBundle/ValidateTriad/ValidationReport`. El paquete `validator` desaparece.

## Consecuencias
- **Positivas:** reglas OKF y reconstrucción CKAN con una única fuente de verdad en el dominio; adaptadores intercambiables; casos de uso testeables con fakes de puertos; se eliminan aristas prohibidas adap→adapt y UC→UC.
- **Coste:** firmas de constructores actualizadas (`NewNodeDataProductResolver`, `NewAsIsIngestUseCase`); pruebas ajustadas a los nuevos dobles.
- No cambia la superficie de la API pública ni los contratos JSON/CLI/MCP.

## Referencias
- ADR 0001 (hexagonal), ADR 0008 (Go core dominio / bindings borde), ADR 0013 (ingesta as-is).
- `docs/reference/ARQUITECTURA.md` §6 (Principios Rectores).
