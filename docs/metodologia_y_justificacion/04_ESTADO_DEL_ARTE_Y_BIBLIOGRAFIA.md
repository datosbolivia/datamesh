# ESTADO DEL ARTE Y REVISIÓN BIBLIOGRÁFICA
## Base Teórica, Normativa y Referencias Académicas Formales

**Título del Proyecto de Grado:**  
# "Diseño e Implementación del Formato de Conocimiento Abierto Orientado a Datos"

**Postulante:** Andres Humberto Chirinos Lizondo  
**Carrera:** Ingeniería de Sistemas — Universidad de Aquino Bolivia (UDABOL)  
**Formato de Citas:** Normas APA (7ma Edición) e IEEE para Trabajos de Grado en Ingeniería  
**Articulación de Repositorios:**
- **Estándar Agnóstico y Especificación Normativa:** [`open-knowledge-format`](file:///home/andreschirinos/Proyectos/open-knowledge-format)
- **Implementación del SDK y Motor Hexagonal:** [`datamesh-sdk`](file:///home/andreschirinos/Proyectos/datamesh-sdk)

---

## 1. Especificaciones de Formatos Abiertos y Estándares de Conocimiento

* **Chirinos Lizondo, A. H. (2025).** *Open Knowledge Format (OKF) Specification — Version 0.2*. Repositorio de especificación abierta. https://github.com/andreschirinos/open-knowledge-format
  * **Aporte a la Tesis:** Define la especificación formal del Formato de Conocimiento Abierto Orientado a Datos (`SPEC.md`), estructurando el conocimiento en bundles portables con documentos de conceptos en Markdown, frontmatter YAML, esquemas JSON y linaje agnóstico a cualquier plataforma.
* **Open Knowledge Foundation. (2024).** *Frictionless Data Specifications: Data Package & Table Schema*. Frictionless Standards. https://datapackage.org/
  * **Aporte a la Tesis:** Establece la base para la validación sintáctica de estructuras tabulares y empaquetamiento de metadatos en archivos `datapackage.json`.
* **Common Workflow Language (CWL) Working Group. (2020).** *Common Workflow Language Specifications (v1.2)*. CWL Consortium. https://w3id.org/cwl/v1.2/
  * **Aporte a la Tesis:** Especificación estándar para modelar los pasos de transformación (servicios/ETL) como grafos reproducibles y agnósticos al motor de ejecución.
* **Wilkinson, M. D., et al. (2016).** The FAIR Guiding Principles for scientific data management and stewardship. *Scientific Data*, 3, 160018. https://doi.org/10.1038/sdata.2016.18
  * **Aporte a la Tesis:** Fundamenta el cumplimiento de los principios FAIR (Localizable, Accesible, Interoperable, Reutilizable) en la especificación y en el SDK.

---

## 2. Paradigma Data Mesh y Arquitectura de Software

* **Dehghani, Z. (2022).** *Data Mesh: Delivering Data-Driven Value at Scale*. O'Reilly Media.
  * **Aporte a la Tesis:** Obra seminal que define los 4 pilares rectores del Data Mesh: propiedad de datos orientada al dominio (*Domain Ownership*), datos como producto (*Data as a Product*), plataforma de autoservicio (*Self-serve Platform*) y gobernanza computacional federada (*Federated Computational Governance*).
* **Sanderson, C., Freeman, M., & Schmidt, B. E. (2025).** *Data Contracts: Developing Production-Grade Pipelines at Scale*. O'Reilly Media.
  * **Aporte a la Tesis:** Fundamenta la formalización de contratos de datos (*Data Contracts*) como especificaciones declarativas estrictas (YAML/JSON Schema) para garantizar compatibilidad y calidad antes de que los datos fluyan en redes distribuidas.
* **Cockburn, A., & Garrido de Paz, J. M. (2024).** *Hexagonal Architecture Explained: Ports and Adapters in Practice*. Add-Wesley / Cockburn Consulting.
  * **Cockburn, A. (2005).** *Hexagonal Architecture (Ports and Adapters)*. Alistair.Cockburn.us.
  * **Aporte a la Tesis:** Patrón arquitectónico matriz del SDK que aísla de forma absoluta el núcleo de negocio de los adaptadores de infraestructura física (bases de datos, Kaggle, Google Drive, S3, interfaces CLI).
* **Evans, E. (2003).** *Domain-Driven Design: Tackling Complexity in the Heart of Software*. Addison-Wesley Professional.
  * **Vernon, V. (2013).** *Implementing Domain-Driven Design*. Addison-Wesley.
  * **Aporte a la Tesis:** Metodología de diseño estratégico y táctico: delimitación de *Bounded Contexts*, creación del Lenguaje Ubicuo y diferenciación formal entre *Entities* y *Value Objects* inmutables.
* **Martin, R. C. (2017).** *Clean Architecture: A Craftsman's Guide to Software Structure and Design*. Prentice Hall.
  * **Palermo, J. (2008).** *The Onion Architecture*. JeffreyPalermo.com.
  * **Aporte a la Tesis:** Regla de inversión de dependencias hacia el centro del software y principios SOLID aplicados al aislamiento del dominio.
* **Hunt, A., & Thomas, D. (1999).** *The Pragmatic Programmer: From Journeyman to Master*. Addison-Wesley.
  * **Aporte a la Tesis:** Principios de simplicidad pragmática, modularidad, diseño ortogonal y rechazo de la sobreingeniería (KISS / DRY / YAGNI).

---

## 3. Metodología de Investigación Científica en Ingeniería (DSRM)

* **Peffers, K., Tuunanen, T., Rothenberger, M. A., & Chatterjee, S. (2008).** A Design Science Research Methodology for Information Systems Research. *Journal of Management Information Systems*, 24(3), 45-77. https://doi.org/10.2753/MIS0742-1222240302
  * **Aporte a la Tesis:** Provee el modelo de proceso nominal de 6 fases que guía metodológicamente la investigación y fundamenta la defensa ante el tribunal de grado.
* **Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004).** Design Science in Information Systems Research. *MIS Quarterly*, 28(1), 75-105.
  * **Gregor, S., & Hevner, A. R. (2013).** Positioning and Presenting Design Science Research for Maximum Impact. *MIS Quarterly*, 37(2), 337-355.
  * **Aporte a la Tesis:** Marco de tres ciclos (Relevancia, Rigor y Diseño) y matrices de contribución científica para justificar que el artefacto produce conocimiento generalizable.
* **March, S. T., & Smith, G. F. (1995).** Design and natural science research on technology. *Decision Support Systems*, 15(4), 251-266.
  * **Aporte a la Tesis:** Clasificación taxonómica de los 4 tipos de artefactos producidos en ingeniería: Constructos, Modelos, Métodos e Instanciaciones.
* **Engström, E., Storey, M. A., Runeson, P., Höst, M., & Baldassarre, M. T. (2020).** How software engineering research aligns with design science: A review. *Empirical Software Engineering*, 25(4), 2630-2660. https://doi.org/10.1007/s10664-020-09818-7
  * **Wieringa, R. J. (2014).** *Design Science Methodology for Information Systems and Software Engineering*. Springer.
  * **Aporte a la Tesis:** Valida la aplicación estricta de DSRM a la ingeniería de software como formulación de "reglas tecnológicas" comprobables empíricamente.
* **Vaishnavi, V., & Kuechler, B. (2015).** *Design Science Research in Information Systems*. Association for Information Systems (AIS).

---

## 4. Estándares Internacionales y Recomendaciones del W3C

* **World Wide Web Consortium (W3C). (2020).** *Data Catalog Vocabulary (DCAT) - Version 2* (W3C Recommendation). W3C. https://www.w3.org/TR/vocab-dcat-2/
  * **Aporte a la Tesis:** Fundamenta el modelado del Catálogo de Datos Semántico (`dcat:Dataset`, `dcat:Distribution`, `dcat:accessURL`) en el archivo `context.jsonld`.
* **World Wide Web Consortium (W3C). (2013).** *PROV-O: The PROV Ontology* (W3C Recommendation). W3C. https://www.w3.org/TR/prov-o/
  * **Aporte a la Tesis:** Respalda el módulo de linaje y trazabilidad de ejecuciones mediante la relación entre entidades (`prov:Entity`), actividades de cómputo (`prov:Activity`) y agentes responsables (`prov:Agent` / `prov:wasGeneratedBy`).
* **World Wide Web Consortium (W3C). (2009).** *SKOS Simple Knowledge Organization System Reference* (W3C Recommendation). W3C. https://www.w3.org/TR/skos-reference/
  * **Aporte a la Tesis:** Justifica la estructuración de conceptos, tesauros y clasificaciones semánticas (`skos:Concept`) para desambiguar variables estadísticas.
* **World Wide Web Consortium (W3C). (2014).** *RDF 1.1 Concepts and Abstract Syntax* & *OWL 2 Web Ontology Language Document Overview*. W3C.
  * **Aporte a la Tesis:** Permite la vinculación federada con grafos de conocimiento globales (Wikidata, DBpedia) mediante la propiedad formal `owl:sameAs`.

---

## 5. Tecnologías de Ejecución Analítica y Cero-Copia

* **Raasveldt, M., & Mühleisen, H. (2019).** DuckDB: an Embeddable Analytical Database. In *Proceedings of the 2019 International Conference on Management of Data (SIGMOD '19)* (pp. 1981-1987). ACM. https://doi.org/10.1145/3299869.3320212
  * **Aporte a la Tesis:** Fundamenta la selección del motor analítico embebido DuckDB para ejecutar SQL columnar de alto rendimiento en el cliente sin requerir servidores de base de datos dedicados.
* **Apache Software Foundation. (2023).** *Apache Arrow: A cross-language development platform for in-memory analytics*. Apache Software Foundation. https://arrow.apache.org/
  * **Aporte a la Tesis:** Permite el intercambio de datos entre procesos y lenguajes con cero copias (*zero-copy data sharing*), reduciendo drásticamente la huella de memoria.

---

## 6. Seguridad, Criptografía y Gobernanza Federada

* **Open Policy Agent (OPA). (2024).** *Policy-based control for cloud native environments using Rego*. Cloud Native Computing Foundation (CNCF). https://www.openpolicyagent.org/
  * **Aporte a la Tesis:** Implementación del principio de gobernanza computacional federada mediante políticas expresadas como código declarativo.
* **National Institute of Standards and Technology (NIST). (2015).** *FIPS PUB 180-4: Secure Hash Standard (SHS)*. U.S. Department of Commerce.
  * **Aporte a la Tesis:** Garantía de inmutabilidad e integridad mediante el cálculo de huellas digitales SHA-256 para archivos, contratos y artefactos de datos.
* **Ylönen, T., & Lonvick, C. (2006).** *The Secure Shell (SSH) Protocol Architecture* (RFC 4251). IETF.
  * **Aporte a la Tesis:** Verificación criptográfica de autoría y soberanía en el SDK basada en llaves públicas SSH (Ed25519/RSA) y listas blancas institucionales.

---

## 7. Antecedentes Nacionales y Casos de Estudio

* **Chirinos Lizondo, A. H. (2025).** *DataMesh Bolivia: Hacia un Ecosistema de Datos Colaborativo y Abierto*. Documento Técnico y Propuesta Arquitectónica. La Paz, Bolivia.
  * **Aporte a la Tesis:** Propuesta precursora que formuló la necesidad del nodo soberano y el grafo uPKG para Bolivia.
* **Agencia de Gobierno Electrónico y Tecnologías de Información y Comunicación (AGETIC). (2018).** *Guía de Publicación de Datos Abiertos para Entidades Públicas de Bolivia*. Estado Plurinacional de Bolivia.
  * **Aporte a la Tesis:** Diagnóstico sobre la carencia de formatos abiertos normalizados en las entidades públicas bolivianas.
* **Our World in Data (OWID). (2024).** *Open-source data catalog and chart architecture*. Global Change Data Lab. https://ourworldindata.org/
  * **Aporte a la Tesis:** Modelo de referencia de publicación de catálogos estructurados y reproducibles basados en Git y metadatos transparentes.

---

## 8. Investigación Crítica: Consistencia en Redes Distribuidas, Inconsistencias de Metadatos y Desafíos FAIR

* **Ma, F., et al. (2025).** Finding Metadata Inconsistencies in Distributed File Systems via Cross-Node Operation Modeling. In *Proceedings of the 34th USENIX Security Symposium (USENIX Security '25)*. USENIX Association.
  * **Aporte a la Tesis:** Análisis empírico fundamental que demuestra que el 63.64% de las inconsistencias en metadatos distribuidos ocurren durante la resolución de conflictos en operaciones cruzadas (cross-node), provocando hasta un 54.55% de pérdida de datos. Justifica la elección de inmutabilidad estricta por direccionamiento de contenido (CID SHA-256) en OKF v0.2.
* **Nair, S. S., Marino, N. E., Pascucci, N., Brown, R., Silva, A. P. R., Cummings, T., & Power, C. M. (2026).** A framework to reason about consistency and atomicity guarantees in a sparsely-connected, partially-replicated peer-to-peer system. *arXiv preprint arXiv:2603.03899*.
  * **Aporte a la Tesis:** Formalización del modelo de consistencia causal transaccional (TCC+) y garantías acotadas (`IntersectionAtomicity` e `IntersectionCC`) para redes P2P donde los nodos tienen vistas parciales (*interest sets*). Fundamenta el comportamiento del SDK ante cortes de red y replicación jerárquica.
* **Dolhopolov, A., et al. (2024).** Metadata Management in Data Mesh: Toward Federated Discovery and Governance. In *Proceedings of the 40th Brazilian Symposium on Databases (SBBD '24)*. SBC.
  * **Aporte a la Tesis:** Identificación de la "paradoja del catálogo centralizado" en implementaciones corporativas de Data Mesh y análisis de catálogos distribuidos mediante registros criptográficos inmutables.
* **Aslam, R. (2026).** Awareness and Integration of FAIR principles in Research Data Management by LIS researchers in developing countries. *Qualitative and Quantitative Methods in Libraries*, 15(3), 519-543.
  * **Aporte a la Tesis:** Evidencia empírica sobre las barreras socioculturales para FAIR en el sur global: brecha de alfabetización técnica en metadatos (media 2.85/5), desconfianza institucional (42.3% teme mal uso) y prevalencia de canales privados (48.9% email, 9.5% USB). Justifica la adopción del formato tri-legible (Markdown + Frontmatter YAML) de coste cero y despliegue inmediato en GitHub Pages (`llms.txt`).
* **Njike, D., & Mushati, K. (2005).** The Challenges of Implementing Metadata in Developing Countries: A Case Study. *FIG Working Week & GSDI-8*, Cairo, Egypt.
  * **Aporte a la Tesis:** Diagnóstico histórico sobre la escasez de repositorios estructurados y la falta de incentivos formales para la creación de metadatos en economías en desarrollo.
