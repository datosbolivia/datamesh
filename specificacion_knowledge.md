# Open Knowledge Format (OKF) & Open Data Knowledge Format (ODKF)

**Versión:** 0.2 — Especificación Oficial Unificada
**Fecha:** 2026-09-07
**Estado:** Estándar Normativo

OKF (Open Knowledge Format) es un estándar abierto, agnóstico y amigable tanto para humanos como para agentes de Inteligencia Artificial para representar **conocimiento**: metadatos, contexto narrativo e interoperabilidad semántica alrededor de datos y sistemas.

**ODKF (Open Data Knowledge Format)** es la extensión oficial de OKF para el ecosistema DataMesh. Enlaza narrativas contextuales con esquemas sintácticos duros (**DataPackages**, **W3C DCAT**, **OpenAPI**, **Spring Boot docs** y **CWL CommandLineTool**), garantizando interoperabilidad semántica, linaje auditable y consultas analíticas federadas bajo el principio **Zero-Microdata**.

---

## 1. Motivación y Principios

Los sistemas tradicionales de catálogos de datos sufren de dos extremos:

1. **Silos cerrados o pesados:** Exigen registros centralizados, bases de datos complejas y tooling propietario.
2. **Ambigüedad y alucinaciones:** Documentación informal en wikis que los modelos de lenguaje (LLM) no pueden convertir en consultas de software confiables.

OKF/ODKF resuelve esto bajo la premisa: **"Si puedes usar `cat` y `git`, puedes operar ODKF"**.

### Principios Rectores:

- **Legible sin herramientas:** Archivos Markdown UTF-8 limpios con frontmatter YAML estándar.
- **Interoperabilidad Semántica (Contexto):** Anclaje ontológico explícito mediante vocabularios W3C (SKOS, Wikidata, Schema.org).
- **Interoperabilidad Sintáctica (Contratos Duros):** Definición explícita de esquemas de datos (Frictionless DataPackage, DCAT), servicios invocables (OpenAPI, Spring Boot `/v3/api-docs`) y tareas batch ejecutables (CWL CommandLineTool).
- **Gobernanza y Privacidad por Diseño (Zero-Microdata):** Los repositorios públicos solo almacenan metadatos y esquemas. Los microdatos pesados residen externamente y las consultas no autenticadas se restringen a estadísticas agregadas.
- **Trazabilidad Criptográfica (Integridad):** Verificación de procedencia mediante huellas SHA-256 y versionado Git.

---

## 2. Terminología

- **Knowledge Bundle:** Unidad de distribución. Directorio autocontenido de documentos de conocimiento y datos.
- **Concept Document:** Documento atómico `.md` que describe un activo de datos, servicio, métrica o política.
- **Concept ID:** Ruta relativa del documento dentro del bundle sin extensión `.md` (ej. `indicadores/pobreza`).
- **Semantic Anchor (`skos`):** URI canónica hacia una ontología externa para eliminar ambigüedad.
- **Syntactic Contract (`contracts`):** Declaración técnica de ejecución para datos estáticos (`datapackage`, `dcat`), APIs (`openapi`, `springdoc`) o tareas computacionales (`cwl`, `cli_tool`).
- **Lineage (`lineage`):** Registro de procedencia computacional: fuentes (`source`), transformaciones (`transformations`) y hash de integridad SHA-256.

---

## 3. Estructura de un Bundle ODKF

```text
mi_bundle/
├── index.md                      # Opcional. Índice del directorio para revelación progresiva.
├── log.md                        # Opcional. Registro cronológico de cambios (ISO 8601).
├── datasets/                     # Directorio temático
│   ├── censo_poblacion.md        # Concepto de datos
│   └── calidad_aire.md
├── services/
│   └── etl_diario.md             # Concepto de servicio / tarea batch
└── concepts/
    └── ref_departamentos.md      # Glosario / tesauro semántico
```

### Archivos Reservados

- `index.md`: Lista y describe los conceptos del directorio para descubrimiento jerárquico.
- `log.md`: Bitácora histórica de modificaciones en orden descendente.

---

## 4. Especificación del Documento de Concepto (Frontmatter + Body)

Cada documento `.md` (excepto `index.md` y `log.md`) se divide en:

1. **YAML Frontmatter:** Delimitado por `---`.
2. **Markdown Body:** Narrativa explicativa para humanos y agentes.

### 4.1 Campos del Frontmatter YAML

````yaml
---
# --- Metadatos Generales (OKF Base) ---
type: dataset                          # REQUERIDO. Tipo de concepto (dataset, catalog, service, indicator, playbook)
title: Censo Nacional de Población     # RECOMENDADO. Nombre legible
description: Microdatos anonimizados   # RECOMENDADO. Resumen en una sola línea
resource: https://datos.gob.bo/censo   # OPCIONAL. URI del recurso original
tags: [demografia, censo, hogares]    # OPCIONAL. Etiquetas de búsqueda
timestamp: 2026-05-01T00:00:00Z       # OPCIONAL. Última modificación ISO 8601

# --- Interoperabilidad Semántica (ODKF v0.2) ---
skos:                                  # REQUERIDO en ODKF. Anclajes ontológicos universales
  - http://www.wikidata.org/entity/Q39825    # Censo
  - https://schema.org/GovernmentData

dimensions:                            # OPCIONAL. Dimensiones para análisis OLAP
  - departamento
  - municipio
  - año

# --- Cobertura Espacio-Temporal y Calidad (W3C DCAT v3 / ISO 19115 / ISO 8601) ---
spatial:                               # OPCIONAL. Ámbito geoespacial
  country: BO                          # ISO 3166-1 alpha-2
  regions: [BO-L, BO-C, BO-S]          # ISO 3166-2
  bbox: [-69.64, -22.90, -57.45, -9.67] # [minX, minY, maxX, maxY] EPSG:4326
  granularity: municipality

temporal:                              # OPCIONAL. Ámbito cronológico
  start: 2020-01-01T00:00:00Z          # ISO 8601
  end: 2026-12-31T23:59:59Z
  frequency: annual                    # daily, weekly, monthly, annual, irregular
  timezone: America/La_Paz

quality:                               # OPCIONAL. Perfil y validación de calidad
  status: verified                     # raw, curated, verified, official
  completeness: 0.99                   # Ratio [0.0 - 1.0]

# --- Interoperabilidad Sintáctica / Contratos de Ejecución (ODKF v0.2) ---
contracts:                             # REQUERIDO para activos de datos y servicios
  - type: datapackage                  # Datos estáticos (Frictionless / Table Schema)
    path: datapackage.json
  - type: openapi                      # Servicios web REST / Spring Boot docs
    path: https://api.censo.gob.bo/v3/api-docs
  - type: cwl                          # Tareas batch / scripts ejecutables
    path: tasks/etl_limpieza.cwl.json

# --- Linaje y Trazabilidad Criptográfica (ODKF v0.2) ---
lineage:
  source:
    - url: https://fuente.ine.gob.bo/censo_raw.csv
  transformations:
    - tool: scripts/clean_data.py
      type: script
      hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  version: 1.2.0
  updated_at: 2026-05-01T12:00:00Z
---

# Metodología y Calidad de Datos

Narrativa contextual detallada. Explica supuestos estadísticos, advertencias de uso,
definiciones operativas de variables y procedimientos de anonimización.

## Consultas de Ejemplo

```sql
SELECT departamento, COUNT(*) as total_hogares
FROM censo_poblacion_hogares
GROUP BY departamento;
````

````

---

## 5. Tipos de Contratos Sintácticos Soportados

El bloque `contracts` desacopla la narrativa del formato físico:

| Tipo (`type`) | Estándares Compatibles | Propósito | Adaptador SDK |
| :--- | :--- | :--- | :--- |
| `datapackage` | Frictionless DataPackage, CSV dialect | Tablas físicas, columnas tipadas, restricciones y `x-policy`. | `DataPackageContractAdapter` |
| `dcat` | W3C DCAT v2/v3, DCAT-AP | Catálogos gubernamentales y distribuciones multipartición. | `DcatContractAdapter` |
| `openapi` | OpenAPI v3, Swagger, Springdoc (`/v3/api-docs`) | Endpoints REST, parámetros de consulta y schemas de respuesta. | `OpenApiContractAdapter` |
| `cwl` / `cli_tool` | Common Workflow Language, `CommandLineTool` | Tareas batch ejecutables, mapeo de argumentos CLI y salidas generadas. | `CwlCliContractAdapter` |

---

## 6. Política de Gobernanza Zero-Microdata

Para evitar la filtración involuntaria de datos sensibles, los recursos tabulares en `datapackage` o `dcat` pueden declarar `x-policy`:

- `allow_all`: Acceso público irrestricto (datos agregados o de referencia).
- `zero_microdata`: Restringe consultas a funciones estadísticas agregadas (`COUNT`, `AVG`, `SUM`, `MIN`, `MAX`, `GROUP BY`). Bloquea `SELECT *` para identidades públicas no autenticadas.
- `deny`: Oculto para accesos públicos; solo disponible para roles de administración interna.

---

## 7. Conformidad y Verificación

Un bundle es conforme a **OKF/ODKF v0.2** si:
1. Todo archivo `.md` (salvo `index.md` y `log.md`) tiene frontmatter YAML parseable.
2. Contiene el campo obligatorio `type`.
3. Para datasets ODKF, incluye al menos una URI semántica en `skos` y al menos un contrato en `contracts`.
4. Los hashes declarados en `lineage.transformations[].hash` coinciden con el cálculo SHA-256 de los artefactos.

---

## 8. Fachada de Consumo de 1 Línea (SDK)

```python
import datamesh

# 1. Leer cualquier bundle o documento ODKF
bundle = datamesh.get("https://datosbolivia.github.io/raw/nodes/air_quality/index.md")

# 2. Publicar bundle hacia múltiples plataformas simultáneamente
results = datamesh.publish("./nodes/air_quality", targets=["local", "portal", "kaggle"])

# 3. Extraer mapeo semántico para normalizar columnas y resolver joins
mappings = datamesh.align_semantics(datapackage_dict)

# 4. Consulta federada multi-nodo en DuckDB con tríadas soberanas
df = datamesh.sql("SELECT lugar_nombre, AVG(valor_ica) FROM 'air_quality:Compilación de datos de calidad del aire de Bolivia' GROUP BY 1")
```
