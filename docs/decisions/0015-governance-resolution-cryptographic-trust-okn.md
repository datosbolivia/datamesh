# ADR 0015: Gobernanza, Resolución Canónica, Firmas Criptográficas y Confianza Federada en ODKF / OKN

## Estado
Aceptado

## Contexto
Para transformar el ecosistema descentralizado de Open Knowledge Format (ODKF) en una Open Knowledge Network (OKN) federada —donde instituciones, empresas y ciudadanos producen y consumen conocimiento validado por agentes de IA vía Model Context Protocol (MCP)— se requiere un modelo de gobernanza distribuida y sin puntos únicos de fallo.

Este modelo debe garantizar:
1. **Resolución Uniforme de Activos:** Un sistema de direccionamiento universal para localizar fragmentos de conocimiento, contratos y microdatos de manera determinista.
2. **Identidad Soberana y Firmas Criptográficas:** Mecanismos de no repudio donde los roles epistémicos (`emitter`, `attester`) están respaldados por claves criptográficas y cadenas de custodia auditables.
3. **Gobernanza Federada y Falsabilidad:** Protocolos para la actualización, refutación algorítmica y propagación de confianza entre nodos independientes.

## Decisión

Establecemos los siguientes pilares de diseño e infraestructura para la red federada ODKF / OKN:

### 1. Sistema de Resolución y Direccionamiento Canónico (`AddressingContext`)
Adoptamos un esquema de URI estricto y unificado para identificar cualquier activo de conocimiento dentro de la red federada:

$$\text{odkf}://\langle\text{namespace}\rangle/\langle\text{catalog}\rangle/\langle\text{dataset-slug}\rangle[:\text{version}]$$

- **`namespace`:** Identificador descentralizado (DID) o dominio jerárquico de la organización emisora (ej. `org.gob.bolivia`, `com.acme.research`).
- **`catalog`:** Contexto delimitado o catálogo lógico.
- **`dataset-slug`:** Nombre del concepto de conocimiento normalizado en minúsculas y guiones (`cat:ds-name:res-name`).
- **`version`:** Etiqueta semántica o hash SHA-256 (ej. `v1.2.0`).

El resolutor en `core-go/` (`ResourceTriad`, `ParseTriad`) y los bindings reconocen transparentemente `odkf://`, `datamesh://` y la sintaxis clásica de tríadas `[catalog:]dataset:resource`.

### 2. Firmas Criptográficas y Roles Epistémicos Verificables (`ProvenanceContext`)
Todo activo de conocimiento de alto impacto debe incluir un bloque de firmas digitales en el YAML Frontmatter:
- **El Emisor (`emitter`):** Genera los datos y paradatos, firmando el hash del contenido con su clave asimétrica (Ed25519 / SSH / RSA / OpenPGP).
- **El Validador / Atestador (`attester`):** Revisa la metodología, emite un dictamen (`verdict: verified` o `refuted`) y adjunta su firma digital creando un DAG de confianza.
- **Validación en Core:** El motor en Go rechaza o degrada el *Trust Tier* de cualquier conocimiento cuya cadena de firmas sea inválida o esté ausente.

### 3. Falsabilidad y Actualización Dinámica
Siguiendo los principios de Karl Popper:
- El conocimiento es evolutivo y falsable; los nodos son inmutables por versión.
- Si nueva evidencia científica o empírica invalida un postulado previo, se emite un nuevo nodo con el metadato:
  ```yaml
  status: refuted
  supersedes: odkf://org.gob.bolivia/salud/estudio-preliminar:v1.0
  ```
- Los agentes MCP que consultan la red alertan automáticamente del estado de refutación o desactualización a los sistemas consumidores.

### 4. Gobernanza del Monorepo y Extensibilidad del Core
- **Un Solo Core (`core-go/`):** Contiene la lógica de negocio pura, la validación de la Pila Ontológica, la ejecución de DuckDB y la resolución criptográfica.
- **Bindings Delgados (`bindings/`):** Python, TypeScript y R actúan como adaptadores de borde que invocan las funciones del Core (vía C-ABI / WASM) con prefijo `_`, asegurando cero discrepancia de reglas de gobernanza entre lenguajes.

## Consecuencias

### Positivas
- Seguridad criptográfica de extremo a extremo y trazabilidad absoluta de la evidencia científica.
- Interoperabilidad B2B/B2G sin confianza ciega.
- Compatibilidad absoluta con implementaciones anteriores mediante normalización simétrica de URIs y esquemas.

### Negativas
- Sobrecarga de cómputo en la verificación de firmas distribuidas, mitigada mediante almacenamiento en caché atómica local (`~/datamesh/cache/`).
