# ADR 0026: Autoridad Única de Go Core, Workflows de CI/CD para Compilaciones/Releases y Motor Mancomunado de Políticas e Integridad

## Estado
Aceptado

## Fecha
2026-10-13

## Contexto
La auditoría arquitectónica del SDK reveló tres brechas estructurales:
1. **Ficción de autoridad de dominio:** Pese a lo prescrito en ADR 0008 y ADR 0017, la ausencia de workflows de compilación automatizados para `libdatamesh.so` obligaba al runtime de Python a operar mediante fallbacks silenciosos y duplicación completa del modelo de dominio.
2. **Políticas sin enforcement en runtime:** La especificación normativa OKF v0.2 definía la política `zero_microdata` para restringir el acceso a agregaciones estadísticas y bloquear `SELECT *`, pero en la capa de ejecución SQL (DuckDB/Go) no existía ninguna intercepción.
3. **Ausencia de verificación criptográfica real:** La confianza epistémica y las firmas de autoría (Ed25519 / SSH) eran meras estructuras de datos sin validación criptográfica en Go Core.

## Decisión

### 1. Workflows de CI/CD y Empaquetado Multiplataforma
Se implementan workflows automatizados de GitHub Actions:
- **`.github/workflows/ci.yml`**: Compila `libdatamesh.so` con CGO en cada PR y push, ejecuta `go test ./...` y corre la suite completa de `pytest bindings/python/tests` contra la biblioteca compartida nativa real.
- **`.github/workflows/release.yml`**: Se dispara con tags de versión (`v*.*.*`). Compila matrices multiplataforma para CLI (`datamesh-linux-amd64`, `datamesh-darwin-arm64`, `datamesh-windows-amd64.exe`), bibliotecas compartidas (`libdatamesh.so`, `libdatamesh.dylib`, `datamesh.dll`), WebAssembly (`datamesh.wasm`), empaqueta el wheel de Python con la biblioteca nativa incrustada mediante `package-data` y publica el release en GitHub con sumas de verificación `SHA256SUMS.txt`.

### 2. Motor Mancomunado de Políticas en Go Core
Se eleva la gobernanza de acceso a `core-go/domain/policy.go`:
- Define `PolicyType` (`allow_all`, `zero_microdata`, `deny`), `Permission` y `UserIdentity`.
- `ClassifyQueryIntent`: Analiza consultas ANSI SQL determinando si son agregaciones estadísticas puras (`COUNT`, `SUM`, `AVG`, `GROUP BY`) o intentos de volcado directo de microdatos (`SELECT *`, columnas desglosadas).
- `EvaluateQueryAccess`: Árbitro de dominio único. Si la política es `zero_microdata`, bloquea volcados no agregados para identidades públicas o no autenticadas, exigiendo agregaciones o credenciales de analista/administrador autorizadas.
- Se expone mediante C-ABI en `DataMeshEvaluatePolicy`.

### 3. Integridad Criptográfica en Go Core
En `core-go/domain/crypto.go`:
- Implementación canónica de `VerifyEd25519Signature(pubKeyHex, message, sigHex)` utilizando `crypto/ed25519` estándar.
- Verificación de integridad SHA-256 (`ComputeSHA256`, `VerifySHA256`).
- Se expone mediante C-ABI en `DataMeshVerifySignature`.

### 4. Enforcement Activo en DuckDB y Servidor (Cero Fallbacks Silenciosos)
- **`DuckDBQueryEngine`**: Registra la política asociada a cada recurso (`x-policy`). Antes de ejecutar `conn.sql()`, valida la consulta contra el motor de políticas de Go Core. Si la consulta viola `zero_microdata` o `deny`, aborta inmediatamente con `PolicyViolationError`.
- **Fail Fast:** Cuando se exige la autoridad de Go Core y la biblioteca no está disponible, el sistema falla de manera explícita con `GoCoreUnavailableError` en lugar de enmascarar la ausencia con simulaciones no verificadas.

### 5. Corrección de Invariantes de Dominio
- **`dataproduct.go`**: Se incluye el tipo `"catalog"` en `Validate()` y se flexibiliza `Dimensions` como opcional según la especificación OKF v0.2.
- **`validator.go`**: Se soporta de forma equivalente `ref` y `path` en `ContractSpec`, unificando contratos sintácticos declarados por referencia (`ref: ./datapackage.yaml`).

## Consecuencias
- **Positivas:**
  - Go Core ejerce como autoridad normativa única y ejecutable.
  - La privacidad `zero_microdata` es real y efectiva en el motor de consultas DuckDB.
  - El proceso de empaquetado y entrega está 100% automatizado por tags y releases.
  - Transparencia radical: si falta la autoridad nativa o se violan las políticas, el sistema falla de forma predecible y explícita.
- **Negativas / Coste:**
  - Los wheels de Python dependen de la plataforma de la biblioteca C-ABI o requieren compilar con CGO en entornos personalizados.
