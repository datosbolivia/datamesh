# ADR 0001: Arquitectura Hexagonal y Core en Go para DataMesh SDK

## Estado
Aceptado

## Contexto
El SDK de DataMesh requiere un núcleo de alto rendimiento, estricto en tipos y portátil para compilar tanto a binario nativo / librería compartida C (`.so`), ejecutable CLI, y WebAssembly (`.wasm`) para ejecución ligera en cliente web/navegador. Los clientes en Python (consola/librería) y TypeScript (navegador/frontend) consumen las mismas invariantes de dominio y validaciones OKF v0.2.

Además, el sistema debe ser capaz de descubrir catálogos federados basados en el estándar `llms.txt` (ej. `https://datosbolivia.github.io/llms.txt`) y ser completamente configurable mediante:
1. Archivos `datamesh.json` o `datamesh.yaml`.
2. Variables de entorno base: `DATAMESH_{{BASE_VAR}}`.
3. Variables de entorno por adaptador: `DATAMESH__{{ADAPTADOR}}_{{VAR}}`.

## Decisión
1. **Core en Go (`core-go`)**:
   - **Dominio**: Entidades puras y agregados inmutables (`DataProduct`, `Manifest`, `Catalog`, `Config`). Cero dependencias externas.
   - **Puertos de Entrada**: `CatalogServicePort`, `DataProductServicePort`, `ConfigServicePort`.
   - **Puertos de Salida**: `CatalogResolverPort`, `DataProductResolverPort`, `StoragePort`, `ConfigLoaderPort`.
   - **Casos de Uso**: `DiscoverCatalogUseCase`, `ResolveDataProductUseCase`, `ConfigUseCase`.
   - **Adaptadores de Salida**: `LLMSTxtCatalogResolver`, `NodeDataProductResolver`, `FileStorage`, `FileAndEnvConfigLoader`.
   - **Adaptadores de Entrada**:
     - `cli`: Interfaz de consola nativa.
     - `cshared`: Export Cgo para puente FFI/ctypes en Python.
     - `wasm`: Export `syscall/js` para entorno navegador.

2. **Puertos en Lenguajes de Consumo**:
   - **Python**: Fachada unificada (`import datamesh as dm`) consumiendo `libdatamesh.so` vía `ctypes` con fallback nativo HTTP.
   - **TypeScript**: Cliente ligero asíncrono para navegadores web y WASM.

## Consecuencias
- Núcleo desacoplado de frameworks e infraestructura.
- Portabilidad a WebAssembly sin runtime de Node.js en cliente.
- Jerarquía de configuración flexible y determinista (Env > File > Defaults).
