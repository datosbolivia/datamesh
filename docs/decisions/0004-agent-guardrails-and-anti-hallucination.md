# ADR 0004: Guardrails Antialucinación y Fidelidad de Datos para Agentes de IA

## Estado
Aceptado

## Contexto
Los modelos de lenguaje (LLMs) y agentes autónomos frecuentemente alucinan cuando analizan datos estructurados:
1. Adivinan nombres de columnas o tablas que no existen en el esquema físico.
2. Sintetizan números o tendencias plausibles cuando una consulta devuelve 0 registros o `NULL`.
3. Distorsionan los valores exactos mediante redondeos o aproximaciones no solicitadas.
4. Omiten la cita de la fuente y de la tríada de origen (`catalogo:dataset:resource`).

Dado que DataMesh SDK actúa como infraestructura de verdad para datos abiertos soberanos, es imperativo dotar al sistema de guardrails normativos tanto a nivel de skills como dentro del protocolo MCP.

## Decisión
1. **Skill `.agents/skills/agent-guardrails/SKILL.md`**:
   - Define los 6 guardrails obligatorios:
     1. Fundamentación Estricta (Grounding).
     2. Transparencia ante Nulos (cero invención de datos ficticios).
     3. Cita Obligatoria de Tríada (`[catalogo:dataset:resource]`).
     4. Verificación de Esquema Previa (inspección de esquema antes de queries).
     5. Separación nítida entre Hechos y Suposiciones/Hipótesis.
     6. Reporte transparente de errores sin silenciar fallos.
   - Lista de verificación previa para agentes.

2. **Inyección de Guardrails en el Servidor MCP (`datamesh.mcp_server`)**:
   - Campo `instructions` en la respuesta de `initialize` del servidor MCP con la política antialucinación vinculante.
   - Implementación de la capacidad `prompts` en MCP con los templates `grounded_sql_analysis` y `dataset_provenance_audit` para guiar la interacción de modelos de lenguaje hacia patrones libres de alucinación.

3. **Inclusión en `AGENTS.md`**:
   - Regla obligatoria aplicable a cualquier agente que trabaje en el repositorio o consuma sus herramientas.

## Consecuencias
- Respuestas 100% confiables y verificables contra los datos reales.
- Eliminación de errores sintácticos por columnas inventadas.
- Trazabilidad y procedencia garantizada en todas las respuestas analíticas.
