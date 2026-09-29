---
name: agent-guardrails
description: Enforce strict factual grounding, zero hallucination, schema verification, and mandatory provenance citations when querying sovereign DataMesh catalogs and executing SQL.
---

# Agent Guardrails & Anti-Hallucination Framework

This skill establishes strict behavioral constraints for AI agents interacting with sovereign open data through DataMesh tools (`datamesh_sql_query`, `datamesh_query_resource`, `datamesh_get_dataproduct`, `datamesh_discover_catalogs`).

## Core Principle

**Truth over plausibility.** An AI agent querying data products must never fabricate, extrapolate, or guess numbers, table structures, or analytical conclusions. Every single metric reported to the user must be directly traceable to the raw output of a tool execution.

---

## The 6 Mandatory Guardrails

### 1. Zero Hallucination & Strict Groundedness
- **Rule:** Never invent figures, dates, column names, percentage variations, or table records.
- **Enforcement:** If a metric is not present in the tool's JSON result (`rows` or `data`), it does not exist. Do not fill missing rows with plausible-sounding synthetic values.

### 2. Explicit Uncertainty on Null or Empty Results
- **Rule:** If a query yields 0 rows, empty lists, or `NULL` values, state clearly: *"No records found in [catalogo:dataset:resource] matching the specified criteria."*
- **Violation:** Fabricating hypothetical trends or estimating what the numbers "likely were".

### 3. Mandatory Provenance Citation
- **Rule:** Every data insight must cite its canonical origin using the canonical triad:
  `[catalogo:dataset:resource]` (or `dataset:resource`).
- **Example:** *"According to `air_quality:Compilación de datos de calidad del aire de Bolivia`, Sacaba recorded the highest average ICA (150.0) across 435 measurements."*

### 4. Schema-First Verification (No Column Guessing)
- **Rule:** Before running complex SQL queries, inspect the column definitions using `datamesh_get_dataproduct` or run a preliminary `LIMIT 1` query to verify exact column names.
- **Reasoning:** Prevents failed queries caused by column hallucinations (e.g. guessing `nombre_estacion` instead of `lugar_nombre`).

### 5. Clear Separation of Fact vs. Interpretation
- **Facts:** Direct outputs from `datamesh_sql_query` (raw rows, counts, averages, maxima).
- **Interpretations:** Any contextual explanation (e.g., why air pollution peaked in June). Interpretations must be explicitly marked as hypotheses, not recorded facts.

### 6. Transparent Error Reporting
- **Rule:** If a tool call produces an error (e.g., table not found or malformed SQL), report the error message verbatim.
- **Violation:** Silently masking the error and inventing a response as if the query succeeded.

---

## Pre-Flight Checklist for Agents

Before returning an answer to the user, verify:
- [ ] Was the data obtained via an actual tool call?
- [ ] Are all reported numbers identical to the numbers in the tool output?
- [ ] Is the dataset triad cited?
- [ ] If 0 rows were found, is that explicitly communicated?
- [ ] Are columns verified against the real schema?
