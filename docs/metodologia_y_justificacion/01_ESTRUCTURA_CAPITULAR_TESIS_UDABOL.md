# ESTRUCTURA CAPITULAR DE PROYECTO DE GRADO
## Carrera de Ingeniería de Sistemas — Universidad de Aquino Bolivia (UDABOL)

**Título del Proyecto de Grado:**  
# "Diseño e Implementación del Formato de Conocimiento Abierto Orientado a Datos"
*(Subtítulo / Mención Técnica: Arquitectura Hexagonal, Gobernanza Federada y Estándares Semánticos para Ecosistemas Descentralizados de Datos)*

**Modalidad:** Proyecto de Grado  
**Grado Académico al que se Postula:** Licenciatura en Ingeniería de Sistemas  
**Área de Especialidad:** Arquitectura de Software Distribuido, Formatos Abiertos y Web Semántica  
**Postulante:** Andres Humberto Chirinos Lizondo  
**Articulación Tecnológica:**
- **Especificación Normativa y Estándar Agnóstico:** [`open-knowledge-format`](file:///home/andreschirinos/Proyectos/open-knowledge-format) (Especificación agnóstica de dominios, esquemas JSON y manifiestos del formato).
- **Instanciación del SDK y Motor de Ejecución:** [`datamesh-sdk`](file:///home/andreschirinos/Proyectos/datamesh-sdk) (Arquitectura hexagonal, fachada de 1 línea, motor embebido DuckDB y CLI).

---

### PRESENTACIÓN INSTITUCIONAL Y PRELIMINARES
- **Portada Oficial UDABOL:** Logotipo institucional, Facultad de Ciencia y Tecnología, Carrera de Ingeniería de Sistemas, Título del Proyecto de Grado, Autor, Tutor/Relator Metodológico, La Paz - Bolivia.
- **Páginas Preliminares:**
  - Acta de Aprobación de Perfil y Defensa.
  - Dedicatoria y Agradecimientos.
  - Resumen Ejecutivo (Español) y Abstract (Inglés) con Palabras Clave / Keywords.
  - Índice General Paginado.
  - Índice de Figuras y Diagramas de Arquitectura.
  - Índice de Tablas y Cuadros Técnicos.
  - Glosario de Siglas y Lenguaje Ubicuo (DDD).

---

### CAPÍTULO I: MARCO INTRODUCTORIO Y DE REFERENCIA
*Este capítulo establece el contexto del problema en el entorno nacional e internacional, formula el problema central de ingeniería, y delimita los alcances y justificaciones.*

- **1.1 Introducción**
  - Contextualización de la transición desde repositorios centralizados y formatos cerrados hacia formatos abiertos universales y soberanía de datos (*Data as a Product* y *Open Knowledge Format*).
  - Breve descripción del Formato de Conocimiento Abierto Orientado a Datos como estándar agnóstico y del SDK como su implementación operativa.
- **1.2 Antecedentes**
  - *1.2.1 Antecedentes Internacionales:* Evolución del paradigma Data Mesh (ThoughtWorks, Zhamak Dehghani), espacios europeos de datos (Gaia-X, IDSA), iniciativas de catálogos semánticos y abiertos (Our World in Data, Frictionless Data, Wikidata).
  - *1.2.2 Antecedentes Nacionales (Bolivia):* Situación de los silos de datos públicos y académicos (diagnóstico de datos abiertos en Bolivia, UMSA, entidades gubernamentales, falta de contratos de interfaz y formatos neutrales).
- **1.3 Planteamiento del Problema**
  - *1.3.1 Diagnóstico de la Situación Actual:* Diagrama de Causa-Efecto (Diagrama de Ishikawa / Árbol de Problemas de dispersión de datos, acoplamiento a plataformas propietarias y ausencia de un formato interoperable).
  - *1.3.2 Formulación del Problema de Ingeniería:* Pregunta rectora de investigación aplicada:  
    *¿De qué manera el diseño e implementación de un Formato de Conocimiento Abierto Orientado a Datos, agnóstico a plataformas y respaldado por una arquitectura hexagonal con estándares de la Web Semántica, permite resolver la fragmentación, acoplamiento y falta de soberanía en la gestión de datos analíticos distribuidos?*
- **1.4 Objetivos de la Investigación**
  - *1.4.1 Objetivo General:*  
    Diseñar e implementar el Formato de Conocimiento Abierto Orientado a Datos (OKF/ODKF) como una especificación formal y agnóstica a plataformas, junto con un SDK extensible basado en arquitectura hexagonal, que permita la modelación, publicación, verificación criptográfica, federación y consulta eficiente de productos de datos soberanos.
  - *1.4.2 Objetivos Específicos:*
    1. Sistematizar el estado del arte en formatos de datos abiertos, contratos de datos y estándares de la Web Semántica (W3C DCAT, PROV-O, SKOS).
    2. Formalizar la especificación agnóstica del Formato de Conocimiento Abierto (formalizada en `open-knowledge-format`), definiendo esquemas JSON, contratos YAML y reglas de interoperabilidad neutrales a cualquier framework.
    3. Diseñar la arquitectura hexagonal del SDK (`datamesh-sdk`), aislando el núcleo del dominio de los adaptadores de infraestructura física y persistencia.
    4. Implementar mecanismos de validación criptográfica (firmas SHA-256 / SSH keys) y motores de ejecución analítica embebida (DuckDB / Apache Arrow) con rendimiento de cero-copia.
    5. Evaluar rigurosamente el formato y el artefacto software mediante pruebas de integridad, verificación de contratos y casos de uso con datos del contexto boliviano.
- **1.5 Justificación de la Investigación**
  - *1.5.1 Justificación Técnica:* Neutralidad tecnológica del formato, desacoplamiento absoluto de storage y reproducibilidad analítica.
  - *1.5.2 Justificación Económica:* Ahorro en infraestructura cloud propietaria y reducción del costo de mantenimiento de pipelines rotos.
  - *1.5.3 Justificación Social y Académica:* Impulso a la soberanía de datos, acceso transparente a la información pública e interoperabilidad en universidades bolivianas.
  - *1.5.4 Justificación Metodológica:* Rigor en Design Science Research Methodology (DSRM) y registro formal de decisiones con ADRs.
- **1.6 Alcance y Delimitaciones**
  - *1.6.1 Alcance Conceptual / Formato:* Definición formal de la especificación de bundles, manifiestos de conceptos y esquemas de validación agnósticos en `open-knowledge-format`.
  - *1.6.2 Alcance Funcional / SDK:* Implementación del motor en Python, CLI interactivo, bindings de consulta, validación sintáctica y linaje.
  - *1.6.3 Alcance Geográfico y Temporal:* Aplicación en el ámbito de instituciones bolivianas y proyectos de investigación en el periodo 2025–2026.
  - *1.6.4 Límites y Restricciones:* El formato y el SDK proporcionan las especificaciones y herramientas; no administran la infraestructura física ni imponen tecnologías a los dominios soberanos.

---

### CAPÍTULO II: MARCO TEÓRICO Y CONCEPTUAL (ESTADO DEL ARTE)
*Este capítulo compila las bases teóricas rigurosas y la bibliografía técnica internacional que fundamenta el formato y su implementación.*

- **2.1 Paradigma Data Mesh y Datos como Producto (Data as a Product)**
  - Postulados de Zhamak Dehghani (2022): Descentralización por dominios y gobernanza computacional federada.
  - Evolución conceptual: Del Data Lake monolítico a la federación soberana de conocimiento.
- **2.2 Formatos Abiertos y Neutralidad de Plataforma**
  - Principios de formatos abiertos de conocimiento: Legibilidad humana y por máquinas (Markdown + YAML frontmatter).
  - Frictionless Data: Especificación Data Package y Table Schema.
  - Common Workflow Language (CWL v1.2) para ejecución reproducible de pipelines.
- **2.3 Contratos de Datos (Data Contracts)**
  - Fundamentos teóricos de Sanderson, Freeman y Schmidt (2025).
  - Formalización de esquemas sintácticos e invariantes de calidad en archivos declarativos.
- **2.4 La Web Semántica y Linked Open Data (LOD)**
  - W3C DCAT v2 (Data Catalog Vocabulary): Catálogos y distribuciones de datos.
  - W3C PROV-O (Provenance Ontology): Trazabilidad de entidades (`prov:Entity`), actividades (`prov:Activity`) y agentes (`prov:Agent`).
  - W3C SKOS (Simple Knowledge Organization System): Taxonomías y tesauros.
  - Ontologías RDF/OWL y vinculación mediante `owl:sameAs` (Wikidata / DBpedia).
- **2.5 Patrones de Arquitectura de Software**
  - Arquitectura Hexagonal o Puertos y Adaptadores (Dr. Alistair Cockburn, Garrido de Paz).
  - Domain-Driven Design (DDD) Estratégico y Táctico (Eric Evans, Vaughn Vernon).
  - Principios SOLID y Clean Architecture (Robert C. Martin).
- **2.6 Tecnologías de Procesamiento Analítico Embebido**
  - DuckDB: Motor relacional columnar embebido vectorizado.
  - Apache Arrow: Estándar de memoria columnar interoperable y transferencia cero-copia.

---

### CAPÍTULO III: MARCO METODOLÓGICO Y DE INGENIERÍA
*Este capítulo fundamenta el método científico aplicado (DSRM) y las prácticas de ingeniería de software empleadas.*

- **3.1 Metodología de Investigación: Design Science Research Methodology (DSRM)**
  - Fundamentación teórica: Peffers et al. (2008), Hevner et al. (2004, 2013) y March y Smith (1995).
  - Taxonomía de los 4 Artefactos producidos en el proyecto:
    1. *Constructos:* Lenguaje ubicuo de conocimiento abierto y soberanía de datos.
    2. *Modelos:* Especificación agnóstica de `open-knowledge-format`, arquitectura hexagonal y contratos de datos.
    3. *Métodos:* Protocolos de validación criptográfica SSH/SHA-256, linaje W3C y federación semántica.
    4. *Instanciaciones:* El artefacto de software `datamesh-sdk`, motor DuckDB y CLI.
  - El Ciclo de 6 Fases DSRM: Identificación, Objetivos, Diseño/Desarrollo, Demostración, Evaluación y Comunicación.
- **3.2 Metodología de Desarrollo de Software**
  - Ciclo de ingeniería ágil guiada por el dominio (DDD) y pruebas (TDD).
  - Registro de Decisiones de Arquitectura (ADRs) como mecanismo de trazabilidad y auditoría.
- **3.3 Técnicas e Instrumentos de Validación**
  - Técnicas de elicitación y especificación de requerimientos (FURPS+ / ISO/IEC 25010).
  - Instrumentos automatizados: Pytest, Mypy, Ruff, linters de seguridad criptográfica.

---

### CAPÍTULO IV: INGENIERÍA DEL PROYECTO (DISEÑO E IMPLEMENTACIÓN)
*Este capítulo detalla la solución arquitectónica del Formato de Conocimiento Abierto y su SDK.*

- **4.1 Especificación Agnóstica del Formato: `open-knowledge-format`**
  - Filosofía del formato: Independencia de plataformas, modelos de IA y frameworks propietarios.
  - Estructura canónica del Bundle OKF:
    - `metadata.yaml`: Declaración del dominio, licencias y autores.
    - `datapackage.json`: Contrato sintáctico de tablas y esquemas tipados.
    - `context.jsonld`: Vinculación semántica W3C (DCAT, PROV-O, SKOS).
    - Manifiestos de conceptos en Markdown con frontmatter estructurado.
  - Esquemas de validación JSON (`okf-concept.schema.json`).
- **4.2 Modelado de Dominio y Arquitectura Hexagonal del SDK: `datamesh-sdk`**
  - Delimitación de Bounded Contexts: Bundle, Trust, Contracts, Catalog, Registry.
  - Value Objects inmutables (`frozen=True`) y Entidades de Dominio.
  - Puertos de Salida (*Outbound Ports*): `StoragePort`, `MetadataRepositoryPort`, `SignatureVerifierPort`.
  - Adaptadores Secundarios: Adaptador FS Local, Remoto HTTPS, Kaggle, S3, DuckDB.
  - Puertos de Entrada (*Inbound Ports*) y Casos de Uso del SDK.
- **4.3 Fachada Unificada y Línea de Comandos (CLI)**
  - Diseño estilo Pandas/DuckDB (`import datamesh as dm; df = dm.read(...)`).
  - Comandos del CLI: `dm init`, `dm validate`, `dm query`, `dm publish`.
- **4.4 Seguridad y Gobernanza Criptográfica**
  - Mecanismo de hashing SHA-256 y firma criptográfica mediante llaves SSH institucionales.

---

### CAPÍTULO V: PRUEBAS, EVALUACIÓN DE RESULTADOS Y DISCUSIÓN
*Este capítulo demuestra con evidencia cuantitativa y cualitativa la validez del formato y del SDK.*

- **5.1 Estrategia y Pirámide de Pruebas**
  - Pruebas Unitarias de Dominio (herméticas, 100% aisladas de E/S).
  - Pruebas de Conformidad del Formato y Validación de Esquemas JSON.
  - Pruebas de Integración de Adaptadores.
- **5.2 Demostración de Casos de Uso Piloto**
  - Caso 1: Generación y empaquetamiento de datasets socioeconómicos y de calidad del aire de Bolivia en formato OKF.
  - Caso 2: Auditoría y trazabilidad de linaje automatizada (W3C PROV-O).
  - Caso 3: Consulta analítica federada con motor embebido DuckDB y cero-copia.
- **5.3 Evaluación según Criterios de Calidad ISO/IEC 25010**
  - Métricas de mantenibilidad y acoplamiento estructural.
  - Eficiencia de desempeño: Latencia de lectura, uso de memoria (Apache Arrow vs. Pandas) y tiempos de validación.
  - Evaluación de cumplimiento de principios FAIR.
- **5.4 Discusión de Resultados y Comparativa con Soluciones Existentes**
  - Contraste frente a CKAN, DVC, Dataverse y plataformas corporativas (Collibra, Dataplex).

---

### CAPÍTULO VI: CONCLUSIONES Y RECOMENDACIONES
- **6.1 Conclusiones**
  - Cumplimiento de los objetivos específicos y validación del objetivo general.
  - Conclusiones científicas sobre la viabilidad de formatos abiertos agnósticos para la soberanía de datos.
  - Impacto del artefacto desarrollado bajo la metodología DSRM.
- **6.2 Recomendaciones**
  - Pautas de adopción para la Universidad de Aquino Bolivia (UDABOL) y el Estado boliviano.
  - Trabajo futuro: Conectores peer-to-peer y agentes inteligentes de gobernanza.

---

### REFERENCIAS BIBLIOGRÁFICAS Y ANEXOS
- **Referencias Bibliográficas:** Normas APA (7ma Edición) e IEEE.
- **Anexo A:** Texto íntegro de la Especificación Normativa OKF v0.2 (`SPEC.md`).
- **Anexo B:** Esquemas JSON formales de validación.
- **Anexo C:** Catálogo de ADRs (Architecture Decision Records) del Proyecto.
- **Anexo D:** Manual de Referencia de la API y CLI del SDK.
