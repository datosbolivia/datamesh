# ADR 0007: Unificación de Formatos de Lectura y Abstracción de Manifiestos de Datos en Go Core

## Estado
Aceptado

## Contexto
El estándar Open Knowledge Format (OKF / ODKF v0.2) y los nodos federados de DataMesh pueden estructurar sus metadatos utilizando una diversidad de especificaciones y extensiones:
1. Manifiestos Frictionless DataPackage que en la práctica coexisten como `datapackage.json`, `datapackage.yaml` o `datapackage.yml`.
2. Documentos de conocimiento semántico estructurados en Markdown con frontmatter YAML (`index.md`) de acuerdo con la especificación OKF v0.2 (PE1-PE5, OE1-OE5).
3. Índices federados para agentes de lenguaje e inferencia basados en `llms.txt`, `llm.txt` y `llms-full.txt`.
4. Nuevos y futuros formatos de metadatos abiertos como DCAT-AP, W3C CSVW, RO-Crate o catálogos CKAN que no deben requerir reescrituras de la lógica del núcleo ni acoplarse rígidamente al estándar Frictionless.

Hasta este punto, partes del sistema asumían rutas fijas a `datapackage.json` o realizaban lecturas ad-hoc. Para garantizar la interoperabilidad universal, zero-dependencies en Go Core, y la consistencia en todas las interfaces (C-ABI `libdatamesh.so`, WebAssembly para el navegador, Python ctypes y TypeScript SDK), era necesario desacoplar la lectura de manifiestos a través de un puerto de análisis abstracto y un resolvedor unificado de directorios.

## Decisión

1. **Abstracción de Dominio y Modelo de Manifiesto (`core-go/domain/package.go`)**:
   - `PackageFormat`: Enumeración de tipos de paquete soportados (`PackageFormatDataPackageJSON`, `PackageFormatDataPackageYAML`, `PackageFormatOKFMarkdown`, `PackageFormatLLMsTxt`, `PackageFormatGeneric`).
   - `PackageManifest`: Estructura unificada e inmutable conteniendo `Name`, `Title`, `Description`, `Format`, `Resources` (`PackageResource`), `Keywords`, `Licenses` y `Sources`.
   - `Slugify(name string) string` y `FindResource(nameOrSlug string) *PackageResource`: Capacidad de búsqueda tolerante a mayúsculas/minúsculas, espacios, guiones y alias normalizados para resolución determinista de tríadas (`catalogo:dataset:resource`).

2. **Puertos Hexagonales de Lectura (`core-go/ports/outbound/package_reader.go`)**:
   - `ManifestParserPort`: Interfaz polimórfica que define `Format() domain.PackageFormat`, `CanParse(filename string) bool`, `ParseBytes(data []byte, basePath string) (*domain.PackageManifest, error)` y `ParseFile(filePath string) (*domain.PackageManifest, error)`.
   - `UnifiedMetadataReaderPort`: Interfaz de alto nivel que escanea un directorio de nodo o catálogo (`ReadNodeDir`), analiza archivos arbitrarios (`ReadFile`), busca manifiestos de dataset (`FindDatasetManifest`) y resuelve tríadas canónicas (`TriadResolverPort`).

3. **Adaptadores Concretos sin Dependencias Externas (`core-go/adapters/outbound/manifests/`)**:
   - `DataPackageJSONParser`: Analizador del estándar JSON de Frictionless.
   - `DataPackageYAMLParser`: Analizador de `datapackage.yaml` y `datapackage.yml` implementado con un scanner nativo en Go estándar (sin dependencias CGO ni paquetes externos de terceros).
   - `OKFMarkdownParser`: Parser de `index.md` que separa frontmatter YAML de las secciones semánticas en markdown.
   - `LLMsTxtParser`: Parser de catálogos e índices LLM (`llms.txt`, `llms-full.txt`).
   - `UnifiedMetadataReader`: Adaptador unificado que implementa `UnifiedMetadataReaderPort` y `TriadResolverPort`, manteniendo un registro extensible (`RegisterParser`) e inspeccionando directorios en orden de precedencia (`datapackage.json`, `datapackage.yaml`, `datapackage.yml`, `index.md`).

4. **Integración con C-ABI y WebAssembly**:
   - `core-go/adapters/inbound/cshared/exports.go` y `core-go/adapters/inbound/wasm/main_wasm.go` emplean directamente el `UnifiedMetadataReader` para resolver cualquier referencia física antes de la delegación de consultas.

## Consecuencias
- Desacoplamiento total entre los casos de uso analíticos y las representaciones físicas de los manifiestos.
- Soporte transparente para datasets con `datapackage.yaml`, `datapackage.yml` o `datapackage.json` indistintamente.
- Extensibilidad directa: nuevos estándares como DCAT o RO-Crate pueden agregarse simplemente implementando `ManifestParserPort` y registrándolos en `UnifiedMetadataReader`.
- Cero dependencias añadidas a `go.mod`, preservando compilación estática instantánea y compatibilidad con WASM en navegadores web.
