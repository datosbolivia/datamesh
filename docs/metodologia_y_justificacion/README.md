# METODOLOGÍA, JUSTIFICACIÓN Y FUNDAMENTACIÓN ACADÉMICA
## Proyecto de Grado — Licenciatura en Ingeniería de Sistemas
### Universidad de Aquino Bolivia (UDABOL)

**Título del Proyecto de Grado:**  
# "Diseño e Implementación del Formato de Conocimiento Abierto Orientado a Datos"
*(Subtítulo / Mención Técnica: Arquitectura Hexagonal, Gobernanza Federada y Estándares Semánticos para Ecosistemas Descentralizados de Datos)*

**Postulante:** Andres Humberto Chirinos Lizondo  
**Carrera:** Ingeniería de Sistemas  
**Área de Especialidad:** Arquitectura de Software Distribuido, Formatos Abiertos y Web Semántica  
**Fecha:** Octubre 2026

---

## 1. Articulación de Repositorios y Separación de Responsabilidades

El proyecto de grado se articula a través de dos repositorios complementarios, respetando el principio de **separación estricta entre especificación agnóstica e implementación tecnológica**:

```
  +-------------------------------------------------------------------------+
  |              ESPECIFICACIÓN NORMATIVA Y ESTÁNDAR AGNÓSTICO              |
  |             /home/andreschirinos/Proyectos/open-knowledge-format        |
  +-------------------------------------------------------------------------+
  | * SPEC.md (Especificación OKF v0.2 universal y vendor-neutral)          |
  | * Schemas JSON (okf-concept.schema.json)                                |
  | * Bundles de dominios agnósticos (Markdown + YAML Frontmatter)          |
  | * Semántica W3C agnóstica (DCAT v2, PROV-O, SKOS)                       |
  +-------------------------------------------------------------------------+
                                     |
                                     | Implementa y ejecuta
                                     v
  +-------------------------------------------------------------------------+
  |                SDK DE INFRAESTRUCTURA Y MOTOR DE EJECUCIÓN              |
  |                 /home/andreschirinos/Proyectos/datamesh-sdk             |
  +-------------------------------------------------------------------------+
  | * Arquitectura Hexagonal (Ports & Adapters) en Python                   |
  | * Motor analítico embebido DuckDB y Apache Arrow (cero-copia)           |
  | * Verificación criptográfica de confianza (SHA-256 / llaves SSH)        |
  | * Fachada de 1 línea (`import datamesh as dm; df = dm.read(...)`)        |
  | * Interfaz de línea de comandos (CLI `dm init`, `dm query`)              |
  +-------------------------------------------------------------------------+
```

---

## 2. Mapa de Documentos en esta Carpeta

Los documentos han sido estructurados de acuerdo con los estándares y reglamentos académicos de titulación de UDABOL:

| Documento | Descripción y Contenido Principal |
| :--- | :--- |
| **[`01_ESTRUCTURA_CAPITULAR_TESIS_UDABOL.md`](01_ESTRUCTURA_CAPITULAR_TESIS_UDABOL.md)** | **Estructura Capitular Oficial:** Desglose pormenorizado de los 6 capítulos de la tesis (Marco Introductorio, Marco Teórico, Marco Metodológico DSRM, Ingeniería del Proyecto, Evaluación y Resultados, Conclusiones y Recomendaciones), incluyendo preliminares, secciones y anexos normativos. |
| **[`02_JUSTIFICACION_DEL_PROYECTO.md`](02_JUSTIFICACION_DEL_PROYECTO.md)** | **Justificación Integral:** Formulación del problema de ingeniería, árbol de problemas, justificación técnica (separación estándar/motor), económica (reducción de costos cloud), social/académica (soberanía de datos en Bolivia y reproducibilidad FAIR) y matriz de coherencia metodológica. |
| **[`03_MARCO_METODOLOGICO_DSRM_Y_SOFTWARE.md`](03_MARCO_METODOLOGICO_DSRM_Y_SOFTWARE.md)** | **Metodología de Investigación y Desarrollo:** Adopción formal de la metodología *Design Science Research Methodology* (DSRM - Peffers et al., Hevner et al., March & Smith), sus 6 fases, la taxonomía de los 4 artefactos producidos, y su integración con Domain-Driven Design (DDD), Arquitectura Hexagonal y pirámide de pruebas. |
| **[`04_ESTADO_DEL_ARTE_Y_BIBLIOGRAFIA.md`](04_ESTADO_DEL_ARTE_Y_BIBLIOGRAFIA.md)** | **Revisión Bibliográfica y Estado del Arte:** Compilación comentada y categorizada de la especificación OKF, libros fundacionales (Dehghani, Sanderson, Cockburn, Evans, Martin), estándares internacionales W3C (DCAT v2, PROV-O, SKOS), CWL, Frictionless, tecnologías analíticas (DuckDB, Arrow) y referencias en formato APA 7ma / IEEE. |

---

## 3. Claves de Defensa ante el Tribunal Calificador de Grado (UDABOL)

Al defender el proyecto ante el tribunal de titulación de la Universidad de Aquino Bolivia, el postulante debe apoyarse en los siguientes fundamentos esenciales:

1. **¿Por qué este proyecto es una Tesis y no un desarrollo comercial rutinario?**  
   *Argumento:* Porque sigue el marco **DSRM (Peffers et al., 2008)**. No se limita a codificar una aplicación funcional (instanciación), sino que formula y evalúa **constructos** (lenguaje ubicuo de conocimiento abierto y soberanía), **modelos** (la especificación normativa agnóstica de `open-knowledge-format`, esquemas JSON y arquitectura hexagonal) y **métodos** (protocolos de validación criptográfica y linaje W3C), generando nuevo conocimiento técnico generalizable para la ingeniería de sistemas distribuidos.
2. **¿Por qué el estándar agnóstico reside en un repositorio separado (`open-knowledge-format`)?**  
   *Argumento:* Por rigor de neutralidad tecnológica. Un formato de conocimiento debe trascender cualquier implementación; debe poder ser producido y consumido por cualquier lenguaje (Python, Go, Rust, Java), cualquier agente o cualquier sistema de catálogo sin estar atado al código interno de un SDK específico.
3. **¿Por qué Data Mesh y no un Data Lake o Data Warehouse centralizado tradicional?**  
   *Argumento:* Los Data Lakes centralizados crean cuellos de botella organizacionales: un equipo centralizado de TI no puede comprender la semántica de múltiples dominios heterogéneos. Data Mesh descentraliza la responsabilidad hacia los dominios dueños del dato (*Domain Ownership*) y trata los datos como un producto consumible con contratos estrictos (*Data as a Product*), reduciendo costos y evitando puntos únicos de fallo.
4. **¿Cómo se garantiza la soberanía y la seguridad sin una entidad central que controle todo?**  
   *Argumento:* Mediante **gobernanza computacional federada**. Las reglas se embeben en el código y en el protocolo: firmas criptográficas SHA-256 e identidades SSH (Ed25519) que aseguran inmutabilidad y autoría verificable sin necesidad de un custodio central monolítico.
5. **¿Cuál es el beneficio de la Arquitectura Hexagonal frente a una arquitectura en capas tradicional?**  
   *Argumento:* En la arquitectura en capas convencional, la lógica de negocio suele acoplarse directamente al ORM o a las APIs de almacenamiento. Con la Arquitectura Hexagonal de Cockburn, el dominio es totalmente independiente del almacenamiento físico; podemos leer de Google Drive, Kaggle, S3 o disco local intercambiando adaptadores sin tocar una sola regla de negocio.
