# ADR 0014: Jerarquía Epistemológica y Pila Ontológica (Datos → Información → Conocimiento → Inteligencia)

## Estado
Aceptado

## Contexto
El ecosistema descentralizado impulsado por Open Knowledge Format (OKF) y su extensión para redes federadas Open Data Knowledge Format (ODKF) no busca ser un simple repositorio estático de documentos ni un buscador sintáctico tradicional. Para alimentar de manera rigurosa a agentes de IA mediante el Model Context Protocol (MCP), permitir transacciones B2B/B2G confiables y servir al público general, el sistema requiere una arquitectura conceptual estricta que ordene cómo se transforman los activos digitales brutos en capacidad de razonamiento verificable.

Validamos y formalizamos la visión ascendente: para tener **Inteligencia** se requiere **Conocimiento**; para tener **Conocimiento** se requiere **Información**; y para tener **Información** se requiere **Datos**.

## Decisión

Adoptamos la **Pila Ontológica y Epistemológica de 4 Capas** como la directriz fundamental de diseño para el motor (`core-go/`), los adaptadores de borde y las herramientas para agentes MCP:

$$\text{Datos} \xrightarrow{\text{Estructuración \& Contexto}} \text{Información} \xrightarrow{\text{Epistemología \& Validación}} \text{Conocimiento} \xrightarrow{\text{Cruce \& Razonamiento}} \text{Inteligencia}$$

### Definición de las Capas del Stack

#### Capa 1: Datos (La Sustancia / Evidencia Bruta)
- **Naturaleza:** Hechos brutos, telemetría, registros de sensores, filas tabulares, blobs binarios o fragmentos sin procesar.
- **Principio:** **Zero-Microdata**. Los datos físicos residen de forma distribuida (S3, Parquet, APIs REST, CKAN DataStore, bases relacionales) y están sujetos a restricciones de propiedad intelectual y seguridad corporativa (B2B).
- **Adaptadores:** `DataAccessAdapterPort`, `LocalStorageManager`, `HttpAdapter`, `CKANClientAdapter`.

#### Capa 2: Información (Metadatos y Estructura Sintáctica)
- **Naturaleza:** Datos dotados de sintaxis y contexto organizativo básico (esquemas Frictionless DataPackage, W3C DCAT, tipos de datos, restricciones, vocabularios ontológicos W3C SKOS/Wikidata).
- **Principio:** Permite que los sistemas informáticos entiendan el "continente" sin necesariamente interpretar aún la validez de su contenido.
- **Contratos:** Bloque `contracts` (Frictionless, DCAT, OpenAPI, CWL), resoluble tanto *inline* como *by-reference* (`ref: ./datapackage.yaml`).

#### Capa 3: Conocimiento (Paradatos, Epistemología y Validación Científica)
- **Naturaleza:** Información validada, proveniencia auditable, roles epistémicos (`emitter`, `attester`), linaje computacional (DAG) y marcos metodológicos explicados en Paradatos Narrativos.
- **Principio:** Es el núcleo soberano de ODKF (ficheros `.md` + Bundles). Aquí se establece si un activo es "conocimiento probado", "consenso científico" o "reporte preliminar", aplicando criterios popperianos de falsabilidad (`status: verified | refuted | stable | draft`, `supersedes: <uri>`).
- **Artefactos:** Documentos de concepto (`*.md`) con YAML frontmatter y cuerpo narrativo.

#### Capa 4: Inteligencia (Agentes MCP y Razonamiento Cruzado)
- **Naturaleza:** Capacidad de los agentes de IA (vía Model Context Protocol) para cruzar, correlacionar, traducir y accionar sobre el Conocimiento validado.
- **Principio:** La inteligencia emerge únicamente cuando los agentes consumen conocimiento con trazabilidad garantizada, erradicando alucinaciones mediante citas obligatorias de tríadas soberanas (`[catalogo:dataset:recurso]`).

## Consecuencias

### Positivas
- Estructura limpia que previene la confusión entre el almacenamiento físico (datos), los contratos (información), la gobernanza científica (conocimiento) y la ejecución autónoma de agentes (inteligencia).
- Facilita la auditoría algorítmica y la explicabilidad en entornos B2B y gubernamentales.
- Permite la interoperabilidad entre información estructurada (tablas), semiestructurada (APIs JSON) y no estructurada (textos, modelos).

### Negativas
- Exige a los adaptadores de ingestión realizar un esfuerzo explícito de transformación y etiquetado epistemológico antes de exponer los activos a la red MCP.
