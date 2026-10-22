# ADR 0028: Dependencia Normativa Upstream del Formato de Conocimiento Abierto (OKF/ODKF v0.2) y Arquitectura Hexagonal de Conectores

## Estado
Aceptado

## Fecha
2026-10-21

## Contexto
Durante el proceso de investigación y desarrollo de la tesis de grado *"Diseño e Implementación del Formato de Conocimiento Abierto Orientado a Datos"* (UDABOL, Ingeniería de Sistemas), se identificó la necesidad de delimitar formalmente la frontera entre el estándar normativo de especificación y el software ejecutable:
1. **Riesgo de Acoplamiento y Ambigüedad de Dominio:** Sin una demarcación formal, la lógica de validación semántica, los contratos ontológicos (W3C DCAT v3, SKOS, PROV-O) y la gramática de direccionamiento soberano (`dataset.recurso@catalogo`) corrían el riesgo de acoplarse indebidamente a las particularidades de implementación técnica de Python, DuckDB o Go Core.
2. **Jerarquía Epistemológica y Estándar Universal:** El repositorio `/home/andreschirinos/Proyectos/open-knowledge-format` constituye la fuente única de verdad (Single Source of Truth) normativa, definiendo el contenedor universal de datos y metadatos, su meta-índice de estándares y las reglas de conformidad PE1-PE5 y OE1-OE5.
3. **Rol de DataMesh SDK como Runtime Downstream:** `datamesh-sdk` debe operar exclusivamente como la implementación técnica de referencia (*downstream reference client and execution engine*), encargada de materializar los puertos abstractos del estándar mediante adaptadores de infraestructura de alto rendimiento (DuckDB in-memory, Apache Arrow, C-ABI bindings, cliente P2P).
4. **Validación Crítica de Literatura (NotebookLM):** La investigación bibliográfica evidenció que el 63.64% de las fallas en metadatos distribuidos derivan de inconsistencias en la resolución de operaciones concurrentes (*USENIX 2025 Horcrux*). Para mitigar esto, el estándar exige inmutabilidad estricta por direccionamiento de contenido (CID SHA-256), mientras que el SDK implementa la caché verificada y los adaptadores de transporte.

## Decisión

### 1. Declaración de Dependencia Upstream Normativa
Se establece formalmente que:
- **`open-knowledge-format` es la autoridad normativa upstream:** Cualquier cambio a las estructuras de manifiestos, vocabulario ubicuo, invariantes de conformidad, protocolos de red P2P o esquemas conceptuales debe definirse y aprobarse primero en `open-knowledge-format/SPEC.md`.
- **`datamesh-sdk` es downstream:** La biblioteca Python, el CLI y el núcleo Go Core implementan los puertos definidos en el estándar. Cualquier divergencia entre el comportamiento del SDK y la especificación de `open-knowledge-format` se clasifica como defecto crítico de implementación.

### 2. Mapeo Hexagonal de Puertos Abstractos a Adaptadores Concretos
El SDK alinea su estructura de puertos y adaptadores con la Sección 16 de `open-knowledge-format/SPEC.md`:

| Puerto Abstracto (OKF v0.2) | Adaptador Concreto (DataMesh SDK) | Responsabilidad Técnica |
| :--- | :--- | :--- |
| **`StoragePort`** | `LocalFileAdapter`, `HttpRangeAdapter`, `S3StorageAdapter` | Acceso a almacenamiento local, lectura selectiva por rangos RFC 7233 y buckets S3/MinIO. |
| **`StoragePort` (Archivos Compuestos)** | `ZipExtractorAdapter` (`extract_zip_tabular_resource`) | Extracción y lectura selectiva de subarchivos dentro de paquetes ZIP/TAR mediante fragment identifiers RFC 3986. |
| **`CatalogResolverPort`** | `GitStaticCatalogAdapter`, `LocalDirCatalogAdapter`, `CKANCatalogAdapter`, `KademliaDHTAdapter` | Resolución concurrente de catálogos estáticos (`llms.txt`), directorios locales, APIs CKAN y enrutamiento P2P XOR. |
| **`DataProductResolverPort`** | `ResolveDataProductUseCase`, `UnifiedMetadataReader` | Normalización de Frontmatter YAML, JSON Schema y Frictionless Data Packages. |
| **`QueryEnginePort`** | `DuckDBQueryEngine`, `ArrowFlightSQLEngine` | Ejecución ANSI SQL zero-copy en memoria y streaming analítico distribuido. |
| **`TrustVerifierPort`** | `SSHKeyTrustAdapter`, `GitHubDIDVerifier`, `HashlibChecksumAdapter` | Verificación de firmas Ed25519, contraste contra `github.com/<user>.keys` y verificación de integridad SHA-256. |

### 3. Bundles de Prueba FAIR para el Contexto Boliviano
Se incorporan 4 bundles canónicos de validación en `examples/bundles/` reflejando los escenarios normativos:
1. `air_quality_bolivia`: Recurso estático tabular con anclaje ontológico SKOS/Wikidata.
2. `cndc_despacho_electrico`: Recurso dinámico `dcat:DataService` con linaje PROV-O y consulta analítica SQL.
3. `censo_2024_cartografia`: Recurso compuesto ZIP con fragment identifiers RFC 3986 y soporte para HTTP Range Requests.
4. `udabol_salud_syndicated`: Sindicación multicatálogo Many-to-Many con co-referencia `owl:sameAs` y resolución de DNS Soberano.

## Consecuencias

### Positivas
- **Desacoplamiento Limpio:** El estándar `open-knowledge-format` permanece puro, agnóstico de lenguaje de programación y directamente citable en publicaciones académicas y tesis universitarias.
- **Trazabilidad Metodológica:** Alineación directa con la metodología DSRM (*Design Science Research Methodology*), donde el estándar representa el modelo/constructo formal y el SDK representa la instanciación de software.
- **Robustez y Rendimiento:** El SDK se enfoca en optimizaciones de ejecución física (DuckDB zero-copy, lectura parcial de ZIPs, paralelismo en Go) sin desvirtuar la semántica del dominio.
- **Interoperabilidad Internacional:** Coherencia estricta con W3C DCAT v3, Frictionless Data Package, Apache Arrow y W3C PROV-O.

### Negativas / Mitigaciones
- **Sobrecarga de Sincronización:** Cualquier ajuste en el formato requiere actualizar la especificación antes de modificar el código del SDK. *Mitigación:* Se implementan suites de pruebas de integridad de referencia (`test_reference_integrity.py`) que validan la coherencia entre documentación y código.
