# Reglas e Instrucciones para Agentes de IA (AGENTS.md)

Este repositorio (`datamesh-sdk`) implementa la infraestructura base del Formato de Conocimiento Abierto Federado Orientado a Datos (OKF / ODKF v0.2), su arquitectura hexagonal en Python y su fachada unificada de 1 línea estilo Pandas / DuckDB.

---

## 1. Mandato de Documentación Técnica Avanzada

Cualquier cambio, adición de código, caso de uso o refactorización DEBE actualizar y mantener la documentación técnica en un estado riguroso, exhaustivo y sincronizado.

- **Sin código huérfano:** Cada puerto, caso de uso y adaptador debe estar documentado en [`docs/reference/CASOS_DE_USO.md`](docs/reference/CASOS_DE_USO.md) y [`docs/reference/ARQUITECTURA.md`](docs/reference/ARQUITECTURA.md).
- **Registro de Decisiones Arquitectónicas (ADRs):** Decisiones de diseño no triviales (nuevas dependencias, cambios de protocolo criptográfico, adición de contratos sintácticos) deben documentarse formalmente como un ADR en [`docs/decisions/`](docs/decisions/) siguiendo la plantilla de `documentation-and-adrs`.
- **Sincronización con la Especificación:** [`specificacion_knowledge.md`](specificacion_knowledge.md) es la fuente única de verdad normativa para OKF v0.2. Cualquier discrepancia técnica entre el código y la especificación es un error crítico.

---

## 2. Ecosistema de Skills y Coherencia Técnica

Para garantizar la coherencia arquitectónica y metodológica, los agentes deben apoyarse estrictamente en las directrices de los skills instalados en `.agents/skills/`:

| Skill                                 | Ubicación                                        | Principio Rector                                                                                                                                                                      |
| ------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`documentation-and-adrs`**          | `.agents/skills/documentation-and-adrs`          | Documentar el _por qué_ (contexto, compensaciones y alternativas) mediante ADRs y desglose formal de casos de uso.                                                                    |
| **`hexagonal-architecture`**          | `.agents/skills/hexagonal-architecture`          | Aislamiento estricto de capas: Dominio → Puertos → Casos de Uso → Adaptadores. Cero acoplamiento de infraestructura en el núcleo.                                                     |
| **`domain-driven-design`**            | `.agents/skills/domain-driven-design`            | Modelo unificado alrededor del lenguaje ubicuo, Bounded Contexts (Bundle, Semantic Catalog, Syntactic Contracts, Cryptographic Trust, Federated Registry) y Value Objects inmutables. |
| **`keep-it-simple`**                  | `.agents/skills/keep-it-simple`                  | Máxima simplicidad (KISS). Fachada de biblioteca de 1 línea (`import datamesh as dm; df = dm.read(...)`). Cero abstracciones especulativas innecesarias.                              |
| **`okf-knowledge-base`**              | `.agents/skills/okf-knowledge-base`              | Cumplimiento normativo del estándar OKF/ODKF v0.2 (PE1-PE5, OE1-OE5, metadata YAML, interoperabilidad semántica SKOS/Wikidata).                                                       |
| **`python-code-style`**               | `.agents/skills/python-code-style`               | Tipado estricto Python 3.10+ (`from __future__ import annotations`), dataclasses inmutables (`frozen=True`), manejo de errores explícito, pruebas con `pytest`.                       |
| **`python-testing-patterns`**         | `.agents/skills/python-testing-patterns`         | Patrones avanzados de pruebas en Pytest (fixtures, mocks para I/O/Kaggle, invariantes de Value Objects, parametrización).                                                             |
| **`security-review`**                 | `.agents/skills/security-review`                 | Auditoría de seguridad de código, protección contra path traversal, inyección YAML, validación criptográfica y manejo seguro de tokens.                                               |
| **`python-performance-optimization`** | `.agents/skills/python-performance-optimization` | Optimización de pipelines de datos en memoria, DuckDB streaming, cero copias con Apache Arrow y compresión columnar.                                                                  |
| **`agent-guardrails`**                | `.agents/skills/agent-guardrails`                | Cero alucinación: fundamentación estricta en datos de herramientas (`datamesh_sql_query`), citas obligatorias de tríadas y transparencia ante datos nulos o vacíos.                 |
| **`caveman`**                         | `.agents/skills/caveman`                         | Modo de salida ultra-comprimido para comunicación con el usuario y mensajes de estado (frases fragmentadas, eliminación de artículos y relleno sin perder exactitud técnica).         |

---

## 3. Protocolo de Verificación Antes de Finalizar Cambios

1. **Atomicidad:** Un archivo por clase/responsabilidad.
2. **Pruebas Automatizadas:** Ejecutar `pytest bindings/python/tests` asegurando 100% de éxito.
3. **Firma y Confianza:** Todo bundle generado o verificado debe respetar las políticas de integridad SHA-256 y verificación de autoría criptográfica SSH contra listas blancas y GitHub `.keys`.
4. **Documentación:** Actualizar diagramas, tablas de contratos y registros de decisiones en `docs/`.

---

## 4. Mandato de Guardrails Antialucinación para Agentes

Cualquier agente que ejecute herramientas o sintetice respuestas basadas en el DataMesh debe adherirse a los siguientes guardrails inquebrantables:

1. **Fundamentación Estricta:** Responder única y exclusivamente con los números y registros obtenidos en los resultados de las herramientas. Jamás inventar valores hipotéticos o redondeos distorsionados.
2. **Cita Obligatoria de Tríada:** Siempre indicar el origen del dato citando la tríada canónica `[catalogo:dataset:resource]` (ej. `air_quality:Compilación de datos de calidad del aire de Bolivia`).
3. **Transparencia ante Nulos:** Si una consulta devuelve 0 filas o valores `NULL`, reportarlo explícitamente sin extrapolar.
4. **Verificación de Esquema Previa:** No adivinar nombres de columnas; consultar el esquema con `datamesh_get_dataproduct` o consultas `LIMIT 1` antes de armar consultas SQL complejas.
