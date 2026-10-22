# ADR 0029: Reubicación de Core Go en open-knowledge-format como Expresión Canónica de Domain-Driven Design

## Estado
Aceptado

## Fecha
2026-10-22

## Contexto
En el diseño arquitectónico de la tesis de grado *"Diseño e Implementación del Formato de Conocimiento Abierto Orientado a Datos"* (UDABOL, Ingeniería de Sistemas), el software se estructura bajo dos pilares:
1. **Especificación Normativa y Dominio Puro (`open-knowledge-format`):** Fuente única de verdad normativa para el contenedor, ontologías semánticas (W3C DCAT v3, SKOS, PROV-O), gramática EBNF de direccionamiento soberano (`dataset.recurso@catalogo`) y reglas de invariantes formales (PE1-PE5, OE1-OE5).
2. **Runtime y Bindings de Ciencia de Datos (`datamesh-sdk`):** Entorno de ejecución física, motor analítico embebido DuckDB zero-copy, cliente Model Context Protocol (MCP) para agentes de IA y bindings de alto nivel en Python.

Históricamente, el paquete `core-go` (que implementa el modelo de dominio DDD, las entidades, value objects inmutables, la verificación de firmas OpenSSH RFC 4253 y los puertos abstractos) residía dentro de `datamesh-sdk`. Esta disposición generaba una ambigüedad arquitectónica: la expresión formal del dominio en código tipado y compilado estaba alojada en el repositorio del SDK downstream en lugar del repositorio del estándar normativo upstream.

## Decisión

### 1. Migración de Core Go a `open-knowledge-format`
Se reubica el código base de `core-go` al repositorio normativo:
- **Ruta Primaria de Autoridad:** `/home/andreschirinos/Proyectos/open-knowledge-format/src/`
- **Módulo Canónico Go:** `github.com/datosbolivia/open-knowledge-format/src`
- **Responsabilidad:** Constituye la implementación de referencia canónica compilada (Single Source of Code Truth) del estándar OKF v0.2, libre de dependencias de frameworks externos, con empaquetado para C-ABI (`cshared/exports.go`) y WebAssembly (`wasm/`).

### 2. Rol Downstream de `datamesh-sdk`
`datamesh-sdk` opera como consumidor downstream de la autoridad normativa:
- Enlaza el artefacto binario C-ABI (`libdatamesh.so` / `libdatamesh.dylib` / `datamesh.dll`) mediante `ctypes` (`GoCoreBridge`).
- Mantiene una réplica sincronizada de `core-go` o enlace local para desarrollo y compilación hermética de artefactos nativos.
- Se concentra en la experiencia de usuario (DX): API de una línea estilo DuckDB/Pandas (`dm.read`, `dm.sql`), integración con el ecosistema de IA (servidor MCP) y adaptadores de alto nivel (Kaggle, S3, CKAN, HTTP Range).

## Consecuencias

### Positivas
- **Alineación Ontológica y DDD Estricta:** El estándar (`open-knowledge-format`) no es únicamente un documento en texto plano, sino que ofrece una biblioteca canónica en Go con el modelo de dominio puro listo para ser reutilizado por implementaciones de terceros en cualquier lenguaje.
- **Independencia Tecnológica:** Cualquier organización puede implementar un cliente OKF en Rust, C++ o TypeScript consumiendo directamente `open-knowledge-format/src` vía C-ABI sin depender del SDK de Python.
- **Rigor Metodológico para la Tesis (UDABOL):** En el Capítulo IV (Ingeniería del Proyecto), la separación queda perfectamente cristalizada:
  - *Subcapítulo IV.1:* Especificación formal y Modelo de Dominio Go (`open-knowledge-format`).
  - *Subcapítulo IV.2:* Plataforma de consumo analítico, DuckDB y Agentes IA (`datamesh-sdk`).

### Negativas / Mitigaciones
- **Mantenimiento en Doble Repositorio:** Cambios al dominio Go requieren comitearse en `open-knowledge-format` antes de actualizarse en `datamesh-sdk`.
  - *Mitigación:* Se ejecutan las suites de pruebas automatizadas (`go test ./...` y `pytest tests/test_reference_integrity.py`) para certificar que la interfaz C-ABI y las firmas de funciones se mantengan 100% compatibles.
