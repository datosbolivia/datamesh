# ADR 0027: Protocolo de Handshake, Verificación de Identidad OpenSSH con DID de GitHub y Motor de Políticas Granulares

## Estado
Aceptado

## Fecha
2026-10-13

## Contexto
Tras la consolidación de Go Core como autoridad única (ADR 0026), se requerían capacidades avanzadas de autenticación, descubrimiento y gobernanza dinámica de datos:
1. **Identidad Federada sin Servidor Central de Cuentas:** Los analistas y agentes necesitan autenticarse de forma soberana. El uso de llaves OpenSSH (`ssh-ed25519`) asociadas a perfiles públicos de GitHub (`did:github:<usuario>`) permite verificación criptográfica inmediata contra `https://github.com/<usuario>.keys`.
2. **Reconocimiento y Handshake del Servidor:** Al conectar con un servidor soberano DataMesh, debe existir un protocolo formal de descubrimiento y negociación (`GET /.well-known/datamesh.json` y `POST /api/v1/handshake`) que informe al usuario de sus credenciales efectivas.
3. **Políticas Granulares Dinámicas:** Las políticas no pueden ser únicamente estáticas (`allow_all`, `zero_microdata`, `deny`), sino colecciones extensibles de reglas (`PolicyRule`) que declaran restricciones específicas para cada rol o nivel de confianza:
   - `AggregateOnly`: Restricción a agregaciones estadísticas (`COUNT`, `SUM`, `GROUP BY`).
   - `HiddenColumns`: Ocultación total de identificadores sensibles (e.g. CI, DNI, nombres).
   - `HashedColumns`: Enmascaramiento criptográfico irreversible con SHA-256 (e.g. correos, teléfonos).
   - `RowFilters`: Filtrado de filas (e.g. `gestion >= 2026` o `fecha >= '2026-01-01'`).
   - `DenyAccess`: Bloqueo total salvo para administradores.

## Decisión

### 1. Soporte Criptográfico OpenSSH y GitHub DID en Go Core
En `core-go/domain/crypto.go`:
- **`ParseOpenSSHEd25519PublicKey(line)`**: Decodificador del wire format binario RFC 4253 de OpenSSH para llaves `ssh-ed25519` en Go puro (`encoding/base64`, `encoding/binary`, `crypto/ed25519`).
- **`MatchesGitHubSSHKey(claimedKey, githubKeysRaw)`**: Comprobación estricta de la llave provista contra las llaves públicas autorizadas obtenidas de GitHub.
- **`VerifyGitHubDID(did, claimedKey, githubKeysRaw)`**: Validación sintáctica y de pertenencia del esquema `did:github:<usuario>`.
- Exportados a la interfaz C-ABI en `exports.go`:
  - `DataMeshParseOpenSSHKey`
  - `DataMeshVerifyGitHubIdentity`

### 2. Motor de Políticas Granulares y Perfil Efectivo
En `core-go/domain/policy.go`:
- **`PolicyRule`**: Representa una regla con `AppliesTo`, `AggregateOnly`, `HiddenColumns`, `HashedColumns`, `RowFilters` y `DenyAccess`.
- **`GranularPolicy`**: Agrupación formal de reglas para un recurso o catálogo.
- **`ComputeEffectivePolicy(policy, identity)`**: Calcula el `EffectivePolicyProfile` personalizado para el usuario según su rol y nivel de confianza (`UserIdentity`).
- **`EvaluateQueryWithProfile(profile, sqlQuery)`**: Verifica si una consulta ANSI SQL viola el perfil efectivo (rechazo de columnas ocultas o exigencia de agregación).
- Exportado a la interfaz C-ABI en `DataMeshComputeEffectivePolicy`.

### 3. Protocolo de Handshake en el Servidor Soberano y MCP
En `bindings/python/datamesh/server.py` y `bindings/python/datamesh/mcp_server.py`:
- **`GET /.well-known/datamesh.json`**: Anuncia capacidades del servidor, esquemas de autenticación (`did:github`, `openssh`, `ed25519`) y endpoints.
- **`POST /api/v1/handshake`**: Endpoint de negociación. Verifica el DID de GitHub, contrasta la llave OpenSSH contra las llaves públicas de GitHub (con caché de 5 minutos), valida la firma de desafío (challenge) y retorna el perfil de política efectivo.
- **Herramienta MCP `datamesh_handshake`**: Permite a agentes de IA autenticarse dinámicamente y consultar sus permisos antes de consultar datos.

### 4. Enforcement Activo en DuckDB (Vistas Virtuales Aseguradas)
En `bindings/python/datamesh/adapters/engine/duckdb_engine.py`:
- Al ejecutar consultas SQL bajo una identidad, se calcula su `EffectivePolicyProfile`.
- Si la consulta referencia columnas en `hidden_columns`, se aborta inmediatamente con `PolicyViolationError`.
- Si `aggregate_only` está activo y la consulta hace volcado directo de microdatos (`SELECT *`), se aborta con `PolicyViolationError`.
- Reescritura reactiva de vistas virtuales en DuckDB:
  - `EXCLUDE (hidden_columns)`: Excluye completamente columnas restringidas del esquema virtual.
  - `REPLACE (sha256(CAST(col AS VARCHAR)) AS col)`: Enmascara dinámicamente columnas sensibles.
  - `WHERE <row_filters>`: Inyecta los predicados de particionamiento y fecha autorizados.

## Consecuencias
- **Positivas:**
  - Identidad criptográfica descentralizada sin depender de infraestructura propietaria de autenticación.
  - Transparencia total para el usuario: el handshake le revela exactamente qué reglas le aplican.
  - Privacidad por diseño: las columnas ocultas o hasheadas y los filtros de filas se aplican a nivel de vista virtual en DuckDB.
  - Go Core mantiene el 100% de la autoridad de arbitraje criptográfico y de gobernanza.
- **Coste / Limitaciones:**
  - La resolución de `did:github:<user>` requiere acceso a GitHub o provisión explícita del caché de llaves públicas.
