# MARCO METODOLÓGICO DE INVESTIGACIÓN E INGENIERÍA
## Metodología de Ciencia del Diseño (DSRM) y Prácticas Avanzadas de Ingeniería de Software

**Título del Proyecto de Grado:**  
# "Diseño e Implementación del Formato de Conocimiento Abierto Orientado a Datos"

**Postulante:** Andres Humberto Chirinos Lizondo  
**Carrera:** Ingeniería de Sistemas — Universidad de Aquino Bolivia (UDABOL)  
**Ecosistema de Artefactos de la Investigación:**
- **Estándar y Especificación Agnóstica:** [`open-knowledge-format`](file:///home/andreschirinos/Proyectos/open-knowledge-format)
- **SDK e Infraestructura Hexagonal:** [`datamesh-sdk`](file:///home/andreschirinos/Proyectos/datamesh-sdk)

---

## 1. Enfoque Epistemológico y Justificación Metodológica

En el campo de la Ingeniería de Sistemas, la investigación aplicada enfrenta a menudo el reto de fundamentar por qué la concepción de un formato de datos y la construcción de su SDK no constituyen un mero desarrollo empírico o comercial rutinario, sino un **acto de investigación científica rigurosa**.

Para responder a esta exigencia en la Universidad de Aquino Bolivia (UDABOL), este proyecto adopta la **Metodología de Investigación en Ciencia del Diseño** (*Design Science Research Methodology* - **DSRM**), articulada por **Peffers et al. (2008)** y cimentada en las directrices de **Hevner et al. (2004, 2013)** y **March y Smith (1995)**.

### 1.1. Diferenciación entre Diseño Rutinario e Investigación en Ciencia del Diseño
- **Desarrollo Rutinario:** Aplica conocimientos, formatos y librerías preexistentes para resolver un problema operativo particular en una organización, sin generar especificaciones normativas ni aportar nuevo conocimiento transferible.
- **Investigación en Ciencia del Diseño (DSRM):** Crea y evalúa sistemáticamente artefactos tecnológicos innovadores dirigidos a solucionar clases de problemas complejos (en este caso, la fragmentación, fragilidad y falta de neutralidad en la gestión de datos analíticos), derivando **reglas tecnológicas, patrones de diseño y estándares abiertos** formalmente verificados (Engström et al., 2020; Wieringa, 2014).

```
  +-------------------------------------------------------------------------+
  |              MARCO DE INVESTIGACIÓN DSRM (Hevner et al., 2004)          |
  +-------------------------------------------------------------------------+
  |  ENTORNO (Relevancia)  |   CICLO DE DISEÑO (DSRM)   |  CONOCIMIENTO (Rigor)|
  |                        |                            |                      |
  | * Silos de datos       | 1. Identificar Problema    | * Paradigma DataMesh |
  | * Universidades y gob. | 2. Definir Objetivos       | * Formatos Abiertos  |
  | * Falta de estándares  | 3. Diseñar Formato y SDK   | * Arq. Hexagonal     |
  | * Ruptura de pipelines | 4. Demostrar en Pilotos    | * Estándares W3C     |
  |                        | 5. Evaluar Rigurosamente   | * Domain-Driven      |
  |                        | 6. Comunicar Resultados    |   Design (DDD)       |
  +-------------------------------------------------------------------------+
```

---

## 2. Tipología de Artefactos Producidos (Taxonomía de March y Smith, 1995)

DSRM establece que la investigación aplicada produce cuatro tipos de artefactos. El presente proyecto distribuye y formaliza sus resultados a través de la articulación entre el estándar agnóstico y el SDK operativo:

| Tipo de Artefacto | Definición Conceptual | Concreción en el Proyecto | Repositorio de Respaldo |
| :--- | :--- | :--- | :--- |
| **1. Constructos (Constructs)** | Vocabulario conceptual, conceptos especializados y lenguaje compartido del dominio. | El **Lenguaje Ubicuo (DDD)** de Conocimiento Abierto: *Open Knowledge Bundle*, *Concept Document*, *Resource Binding*, *Trust Tiers*, *Sovereign Domain*, *Semantic Triad*. | [`open-knowledge-format`](file:///home/andreschirinos/Proyectos/open-knowledge-format) / [`datamesh-sdk`](file:///home/andreschirinos/Proyectos/datamesh-sdk) |
| **2. Modelos (Models)** | Representaciones semánticas, especificaciones normativas y esquemas formales. | La especificación agnóstica de dominios **`SPEC.md`**, los esquemas JSON (`okf-concept.schema.json`), ontologías **W3C (DCAT v2, PROV-O, SKOS)** y el diagrama de **Arquitectura Hexagonal**. | [`open-knowledge-format`](file:///home/andreschirinos/Proyectos/open-knowledge-format) (Especificación) / [`datamesh-sdk`](file:///home/andreschirinos/Proyectos/datamesh-sdk) (Arquitectura) |
| **3. Métodos (Methods)** | Algoritmos, guías procedurales y protocolos de validación y cómputo. | Protocolos de verificación criptográfica de firmas SSH/SHA-256, mecanismos de resolución federada, validación sintáctica de contratos y pipelines de transformación estilo **CWL**. | [`datamesh-sdk`](file:///home/andreschirinos/Proyectos/datamesh-sdk) |
| **4. Instanciaciones (Instantiations)** | Implementación física y operativa del sistema en código ejecutable. | El paquete Python de código abierto `datamesh-sdk`, interfaz de línea de comandos (CLI), adaptadores de almacenamiento y el motor de consultas embebido con **DuckDB y Apache Arrow**. | [`datamesh-sdk`](file:///home/andreschirinos/Proyectos/datamesh-sdk) |

---

## 3. Las Seis Fases del Ciclo Metodológico DSRM (Peffers et al., 2008)

El ciclo de desarrollo se estructura rigurosamente en las seis fases de Peffers et al.:

```
  [Fase 1]        [Fase 2]        [Fase 3]        [Fase 4]        [Fase 5]        [Fase 6]
 Identificación  Definición de    Diseño y       Demostración    Evaluación      Comunicación
 del Problema    Objetivos de   Desarrollo de     en Casos de     Científica      Académica
 y Motivación    la Solución    Formato y SDK      Estudio       y Métricas      (Tesis/ADRs)
      |               |               |               |               |               |
      +---------------+---------------+---------------+---------------+---------------+
                                      ^                               |
                                      +--- Retroalimentación / -------+
                                           Circunscripción (Takeda et al.)
```

### Fase 1: Identificación del Problema y Motivación
- **Actividades:** Diagnóstico del estado actual de los datos analíticos en Bolivia y a nivel global; identificación de la fragilidad de pipelines centralizados, acoplamiento a nubes propietarias y pérdida de linaje.
- **Salida:** Árbol de problemas, formulación de la pregunta de investigación y justificación formal para la Universidad de Aquino Bolivia.

### Fase 2: Definición de los Objetivos de la Solución (Metarrevisión)
- **Actividades:** Determinación de los requisitos cualitativos y cuantitativos que la solución debe satisfacer:
  - *R1 (Neutralidad):* El formato debe expresarse de forma agnóstica a cualquier framework o vendor en `open-knowledge-format`.
  - *R2 (Aislamiento Arquitectónico):* El SDK debe aislar la lógica de dominio respecto a librerías de infraestructura física mediante Arquitectura Hexagonal.
  - *R3 (Inmutabilidad y Calidad):* Tipado estricto en Python 3.10+ con dataclasses `frozen=True` y validación de esquemas JSON.
  - *R4 (Trazabilidad):* Registro de procedencia con W3C PROV-O y confianza criptográfica (SHA-256 / llaves SSH).
  - *R5 (Rendimiento):* Consultas analíticas locales de latencia reducida con DuckDB y Apache Arrow (cero-copia).
- **Salida:** Matriz de requerimientos FURPS+ y especificación funcional.

### Fase 3: Diseño y Desarrollo de los Artefactos
- **Actividades en `open-knowledge-format`:** Redacción de la especificación normativa `SPEC.md`, estructuración de bundles agnósticos (`bundles/`), esquemas JSON formales (`schemas/okf-concept.schema.json`) y validadores agnósticos.
- **Actividades en `datamesh-sdk`:** Delimitación de Bounded Contexts (DDD), modelado de puertos de entrada/salida (Hexagonal), implementación de adaptadores de E/S (Kaggle, S3, Drive, Local), motor DuckDB y fachada de 1 línea (`import datamesh as dm; df = dm.read(...)`).
- **Salida:** Repositorios sincronizados con documentación técnica exhaustiva.

### Fase 4: Demostración
- **Actividades:** Aplicación de los artefactos en escenarios representativos:
  - Ingesta y modelado de conjuntos de datos bolivianos (calidad del aire, datos económicos y demográficos).
  - Validación de bundles OKF contra esquemas sintácticos y semánticos.
  - Ejecución de consultas federadas distribuidas a través del CLI y scripts de Python.
- **Salida:** Bundles de prueba validados y cuadernos interactivos de demostración.

### Fase 5: Evaluación
- **Actividades:** Medición empírica y rigurosa del desempeño:
  - *Evaluación de Corrección:* Suite de pruebas automatizadas Pytest (unitarias, contratos e integración) con 100% de éxito.
  - *Evaluación de Rendimiento:* Comparativa de consumo de memoria y tiempo de respuesta entre DuckDB/Arrow vs. Pandas tradicional.
  - *Evaluación de Seguridad:* Verificación de detección y bloqueo de paquetes manipulados (hashing SHA-256 e integridad SSH).
- **Salida:** Informes cuantitativos de pruebas y benchmarks de desempeño.

### Fase 6: Comunicación
- **Actividades:** Publicación y difusión del conocimiento generado:
  - Redacción del documento formal de Proyecto de Grado para UDABOL.
  - Documentación de especificación abierta en GitHub y portales académicos.
  - Registro formal de Decisiones de Arquitectura (ADRs) para auditoría histórica.
- **Salida:** Tesis de Licenciatura en Ingeniería de Sistemas y repositorios públicos.

---

## 4. Metodología de Desarrollo de Software Complementaria

Para gobernar la construcción del software, DSRM se articula con principios de calidad de software:

### 4.1. Domain-Driven Design (DDD) Estratégico y Táctico
- **Diseño Estratégico:**
  - El sistema se divide en **Bounded Contexts** claramente delimitados: *Bundle Context*, *Semantic Catalog Context*, *Syntactic Contracts Context*, *Cryptographic Trust Context* y *Federated Registry Context*.
  - Las dependencias entre contextos se gobiernan mediante capas anticorrupción (*Anti-Corruption Layers*).
- **Diseño Táctico:**
  - Separación entre **Entities** con identidad persistente y **Value Objects** inmutables (`frozen=True`).
  - Representación explícita de transiciones de estado mediante **Domain Events**.

### 4.2. Inversión de Dependencias y Arquitectura Hexagonal
- Las dependencias apuntan estrictamente hacia el centro:
  $$\text{Adaptadores (Infraestructura)} \longrightarrow \text{Casos de Uso (Aplicación)} \longrightarrow \text{Puertos} \longrightarrow \text{Dominio (Núcleo Puro)}$$
- El dominio no importa bibliotecas externas ni adaptadores de red o almacenamiento.

### 4.3. Simplicidad Pragmática: KISS y YAGNI
- Cero abstracciones especulativas: se implementa la solución completa más simple que satisfaga los casos de uso.
- Fachada minimalista para máxima experiencia de usuario y desarrollador (DX).

### 4.4. Registro de Decisiones de Arquitectura (ADRs)
Cualquier alteración de contratos, introducción de dependencias o decisión estructural se documenta formalmente mediante ADRs (Michael Nygard), registrando contexto, alternativas evaluadas y compensaciones (*trade-offs*).
