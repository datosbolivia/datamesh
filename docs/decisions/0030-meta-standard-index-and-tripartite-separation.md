# ADR 0030: Arquitectura de Meta-Estándar, Resolución por Referencia (`ref:`) y Separación Epistemológica (Metadato, Paradato y Dato)

## Estado
Aceptado

## Fecha
2026-10-22

## Contexto y Planteamiento del Problema
Los formatos de datos abiertos y conocimiento actuales adolecen de dos extremos viciosos:
1. **Sobre-ingeniería monolítica (RDF/OWL):** Forzar a que todo el ecosistema de datos se convierta a grafos semánticos complejos, resultando ilegible para humanos, ineficiente para motores analíticos y con una curva de adopción prohibitiva.
2. **Inconsistencia y duplicidad (JSON/CSV planos):** Duplicar metadatos descriptivos en múltiples archivos de configuración, provocando divergencia (*drift*) y desincronización con los catálogos oficiales (DCAT, Frictionless Data Packages, OpenAPI).

El proyecto concibe el estándar **Open Knowledge Format (OKF / ODKF v0.2)** no como un nuevo formato que compite con los existentes, sino como un **Meta-Estándar e Índice de Índices (*Index of Indexes*)** construido como un superset de Google OKF.

## Decisión Arquitectónica Adoptada

### 1. OKF como Meta-Estándar Universal
El formato OKF actúa como la capa unificadora, ligera y legible (Markdown + Frontmatter YAML) que sirve de índice soberano para catálogos heterogéneos. En lugar de forzar a las organizaciones a migrar sus repositorios o redefinir esquemas, OKF los cataloga, orquesta y valida mediante una fachada interoperable.

### 2. Resolución por Referencia (`ref:`) contra la Duplicidad (SSOT)
Se formaliza el soporte normativo de la cláusula `ref:` (o `path:`) en contratos sintácticos, linajes y fuentes:
- Los conceptos pueden apuntar directamente a especificaciones existentes en sus estándares nativos:
  - **Frictionless Data Package:** `ref: "https://datos.gob.bo/datapackage.json"`
  - **W3C DCAT v3:** `ref: "https://datos.gob.bo/catalog.ttl#dist-aire"`
  - **OpenAPI 3.1:** `ref: "https://api.clima.bo/openapi.yaml"`
  - **Common Workflow Language (CWL) / W3C PROV:** `ref: "https://repo.org/pipeline.cwl"`
- **Principio Single Source of Truth (SSOT):** El motor no duplica esquemas; el adaptador resuelve y cachea la referencia remota o local, garantizando consistencia absoluta.

### 3. Separación Epistemológica Tripartita
El modelo conceptual delimita tres planos ontológicos independientes:
1. **Metadato (Metadata):** Descriptivo de la naturaleza del dato (qué representa, campos, tipos, anchors semánticos SKOS, dimensiones).
2. **Paradato (Paradata):** Descriptivo del *proceso metodológico* y del contexto de captura (cómo se capturó, quién o qué agente lo generó [`generated.by`], con qué receta o pipeline [`generated.recipe`], cómo se verificó [`verified[]`], cuál es su cadencia de frescura [`freshness.cadence`] y su linaje criptográfico [`lineage.transformations`]).
3. **Dato (Data):** El cuerpo o matriz de información propiamente dicho (valores, registros, tensores, particiones parquet).

### 4. Taxonomía Operativa de Recursos
Los recursos subyacentes se clasifican en una matriz ortogonal de dos dimensiones:
- **Por Dinamismo:**
  - *Estáticos:* Inmutables, versionados, direccionables por hash criptográfico (archivos CSV, Parquet, GeoJSON, SQLite, DuckDB, archivos ZIP anidados con Range Requests).
  - *Dinámicos:* Computables o en flujo continuo (endpoints REST OpenAPI, GraphQL, Apache Arrow Flight SQL streams, vistas SQL federadas).
- **Por Localidad:**
  - *Locales:* Almacenados en el nodo o sistema de archivos del agente.
  - *Remotos:* Hospedados en Internet/Intranet (HTTP/HTTPS, buckets S3/MinIO, repositorios Git, nodos P2P IPFS/Kademlia).

### 5. Arquitectura Extensible de Plugins / Conectores
El motor Go y el SDK Python desacoplan la especificación del transporte mediante puertos abstractos (`StoragePort`, `CatalogResolverPort`, `FormatTranslatorPort`), permitiendo la incorporación de plugins independientes para cosechar (*harvesting*), consultar y transformar entre estándares sin modificar el núcleo de dominio.

## Consecuencias y Compensaciones

### Consecuencias Positivas
- **Cero Redundancia:** Las instituciones reutilizan sus esquemas DCAT, Frictionless o CKAN preexistentes simplemente referenciándolos con `ref:`.
- **Claridad Conceptual:** Separar paradatos de metadatos permite a los agentes de IA auditar la veracidad metodológica sin contaminar los esquemas sintácticos de consulta analítica.
- **Interoperabilidad Universal:** El formato puede ser consumido por humanos (Markdown), máquinas analíticas (DuckDB / Arrow) y agentes de IA (llms.txt / OKF).

### Compensaciones y Mitigaciones
- *Dependencia de red para referencias remotas:* Mitigado mediante políticas de resolución local-first, almacenamiento en caché criptográfico y verificación por hash SHA-256 (`PE5`).
