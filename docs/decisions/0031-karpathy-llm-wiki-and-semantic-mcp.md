# ADR 0031: Paradigma "LLM Wiki" de Karpathy, Markdown Knowledge Graph y Protocolo MCP Semántico de Doble Modo

## Estado
Aceptado

## Fecha
2026-10-22

## Contexto y Planteamiento del Problema
Los modelos de interacción entre agentes de Inteligencia Artificial (LLMs) y bases de datos o catálogos abiertos adolecen de dos limitaciones graves:
1. **La Pasividad Estática:** Los agentes se conciben únicamente como "lectores" que ejecutan consultas SQL o llamadas de solo lectura a través de APIs, mientras que los repositorios de datos sufren de obsolescencia rápida sin curación continua.
2. **La Verbosidad de Grafos Semánticos Tradicionales:** Los grafos ontológicos en RDF/SPARQL/OWL saturan la ventana de contexto de los modelos con sintaxis críptica de predicados, triplicando el consumo de tokens y haciéndose ininteligibles para los humanos.

Inspirados en la visión de **Andrej Karpathy (2023, 2024)** sobre el "LLM OS" y la "Personal LLM Wiki", se plantea que el repositorio de conocimiento deba ser una red de archivos Markdown navegables, donde el agente asume el rol de **curador y mantenedor activo**.

## Decisión Arquitectónica Adoptada

### 1. El Cuerpo Markdown como Grafo de Conocimiento (Knowledge Graph)
- **Nodos:** Cada archivo `.md` estructurado representa un concepto o producto de datos formal.
- **Aristas:** Los hipervínculos markdown relativos `[Texto del Enlace](otro_concepto.md)` y enlaces externos `https://...` definen las aristas dirigidas del grafo. El texto del ancla actúa como el rol semántico o predicado de la relación.
- **Subgrafos y Contexto:** Los títulos y encabezados (`#`, `##`, `###`) estructuran la jerarquía cognitiva (*Context Engineering*), permitiendo al agente inferir el contexto temático sin esquemas pesados.

### 2. El Agente como Mantenedor Activo (Paradigma LLM Wiki)
El agente de IA no se limita a leer pasivamente; tiene la capacidad y el mandato de:
- **Curar y Sintetizar:** Leer datos brutos y sintetizar nuevos conceptos en archivos Markdown.
- **Enlazar y Conectar:** Analizar similitudes conceptuales y agregar hipervínculos cruzados entre conceptos desconectados.
- **Auditar y Podar:** Detectar conceptos obsoletos (`freshness.expires`), enlaces rotos y referencias circulares (**RULE-12**).
- **Mantener Índices y Bitácoras:** Regenerar automáticamente el `index.md` con divulgación progresiva y asentar las acciones en el changelog inmutable `log.md`.

### 3. Protocolo Semántico de Doble Modo (MCP / CLI)
Se formaliza una arquitectura simétrica para herramientas de agente:
- **Modo Remoto (Consumidor / Read-Only):**
  - Herramientas: `okf inspect`, `okf graph`, `datamesh_sql_query`, `datamesh_get_dataproduct`.
  - Propósito: Extracción de metadatos, visualización de topología de relaciones y ejecución de consultas analíticas DuckDB.
- **Modo Propietario (Editor / Maintainer):**
  - Herramientas: `okf init`, `okf add`, `okf link`, `okf index`, `okf audit`, `okf sign`.
  - Propósito: Creación de nodos, inserción de hipervínculos semánticos, re-indexación progresiva y firma criptográfica del estado curado de la base.

### 4. Cuaderno Bibliográfico de Referencia
Se establece como base bibliográfica de consulta el cuaderno de **Google NotebookLM**:
- **ID:** `b7eb311b-0b64-4ba6-82b7-9dbb809e0f7c` (*LLM Wiki de Karpathy y Mantenimiento Agéntico de Bases de Conocimiento*).

## Consecuencias y Compensaciones

### Consecuencias Positivas
- **Ahorro Masivo de Tokens:** Markdown ahorra >70% de tokens frente a RDF/XML/JSON-LD, permitiendo que agentes carguen subgrafos completos en memoria RAM (contexto).
- **Mantenimiento Autónomo Continuo:** Las bases de conocimiento dejan de ser repositorios estáticos y se convierten en wikis que mejoran iterativamente con la acción de los agentes.
- **Simplicidad Absoluta (KISS):** Cualquier humano puede editar la wiki con un editor de texto plano o visor Obsidian, mientras que los agentes la manipulan mediante MCP/CLI.

### Compensaciones y Mitigaciones
- *Riesgo de alucinación o enlaces rotos por agentes autónomos:* Mitigado mediante la regla determinista **RULE-12** (detección de ciclos en compilación) y el comando `okf audit`.
