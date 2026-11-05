# Registro de Ingeniería y Arquitectura (DataMesh SDK)

## 2026-11-05
- Sincronización de los bindings Python (`bindings/python/datamesh`) y TypeScript (`bindings/typescript/src/index.ts`) con el Core Go `v0.2.2-rc.1` de `open-knowledge-format`.
- Incorporación del motor de resolución de correspondencias semánticas `ValueLabel -> Concept -> SKOS` (`ValueLabelConceptEntry`, `ConceptNodeSKOS`, `ConceptCorrespondence`, `resolve_concept_correspondences`, `generate_cross_dataset_join_sql`) conectado vía C-ABI (`GoCoreBridge`) con fallback nativo en Python y TypeScript.
- Soporte de direccionamiento DNS Soberano (`<dataset>.<resource>@<catalog>`), esquema `okf://` y preservación de `#fragment` RFC 3986 en `CanonicalURI.parse` y `parseCanonicalUri`.
- Exposición de `diff_bundles` (evolución SemVer 2.0.0) y `attest_computation` (`AttestationVerdict`) en `GoCoreBridge`, `DataMeshRuntime` y fachada pública `datamesh`.
- Actualización de `docs/reference/CASOS_DE_USO.md` (CU-31 y CU-32), `docs/reference/ARQUITECTURA.md` y suite de pruebas de integridad referencial (`test_reference_integrity.py`, `test_publishing_and_semantics.py`).
