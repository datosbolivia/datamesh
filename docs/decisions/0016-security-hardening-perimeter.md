# ADR 0016: Endurecimiento del Perímetro de Seguridad (SSRF, TLS, MCP y Secretos)

## Estado
Aceptado

## Fecha
2026-10-11

## Contexto
La auditoría crítica de `datamesh-sdk` detectó en los servidores HTTP/MCP (Python y Go) y en los adaptadores de red vulnerabilidades explotables si el servidor queda expuesto en una red o un navegador malicioso alcanza un `localhost` con cabeceras CORS permisivas:

1. **SSRF vía proxy y `read_resource`:** `/proxy?url=...` y la herramienta MCP `read_resource` reenviaban a **cualquier** destino (incluidos `127.0.0.1`, `169.254.169.254` link-local y rangos RFC 1918), permitiendo leer metadatos de infraestructura interna y exfiltrarlos con `Access-Control-Allow-Origin: *`.
2. **TLS deshabilitado en silencio:** los clientes HTTP de `bindings/python/datamesh/adapters/resolvers/http.py` y `server.py` degradaban a `ssl.CERT_NONE` ante cualquier error de certificado sin que el operador lo supiera (riesgo MITM).
3. **Lectura local arbitraria en MCP:** las herramientas `datamesh_query_resource` y `read_resource` aceptaban rutas absolutas (`/etc/passwd`) y URIs `file://`, de modo que una página maliciosa podía usar el MCP (JSON-RPC sin autenticación) para leer cualquier archivo local vía CSRF contra `127.0.0.1`.
4. **Inyección SQL por interpolación:** `core.py`, `server.py`, `mcp_server.py` y `publish_and_semantic_usecase.go` construían SQL con `f"..."` sin escapar literales ni identificadores.
5. **Fuga de secretos:** `datamesh config` y la respuesta de `DataMeshInit` serializaban `cfg.Adapters`, exponiendo tokens/API keys.
6. **Servidor sin timeouts y bind 0.0.0.0 por defecto.**

## Decisión
Aplicamos un endurecimiento **default-deny** en la capa de entrada, sin cambiar la superficie de la API documentada:

### 1. Política SSRF (`datamesh.net` en Python y `security.go` en Go)
- Solo `http`/`https` como esquema de destino.
- Se bloquean direcciones de host que resuelven a `loopback`, RFC 1918 (privadas), link-local (`169.254.x.x`), multicast, reservadas o no especificadas.
- **Escape hatches explícitos por env:**
  - `DATAMESH_PROXY_ALLOWED_HOSTS` (lista separada por comas): si está definida, solo esos hosts son permitidos.
  - `DATAMESH_PROXY_ALLOW_PRIVATE=1`: restaura el comportamiento permisivo (útil en federaciones de intranet).
- Aplica en: `/proxy`, MCP `read_resource` y cualquier fetch de URL de `datamesh_query_resource`.

### 2. TLS estricto por defecto (`insecure_tls_enabled` / `open_url`)
- Verificación de certificados SIEMPRE activa; el fallback a `ssl.CERT_NONE` es **opcional** mediante `DATAMESH_INSECURE_TLS=1` y solo se dispara ante errores de certificado, emitiendo `RuntimeError` con instrucciones en caso contrario.

### 3. Límite de lectura local en MCP
- Las herramientas `datamesh_query_resource` y `read_resource` solo aceptan `http(s)` o tríadas canónicas parseables (`datamesh://`/`odkf://`/`cat:ds:res`). Se rechazan rutas absolutas, `file://`, `..`, unidades Windows (`C:\`) y UNC.
- La lectura de archivos locales sigue disponible en la API del SDK (`dm.read`/`dm.query`), que es la vía legítima para el operador.

### 4. SQL seguro
- Python: `datamesh/adapters/engine/sql_utils.py` (`sql_string_literal`, `sql_identifier`, `read_expression`) aplicado en `core.py`, `server.py` y `mcp_server.py`.

### 5. Redacción de secretos
- `Config.Sanitized()` en `core-go/domain/config.go` enmascara claves de adaptador que contengan `token`, `secret`, `password`, `passwd`, `credential`, `api_key`/`apikey`, `client_secret`; usado en `datamesh config` (`main.go`) y `DataMeshInit` (`exports.go`).

### 6. Servidor
- `datamesh serve` y `run_server()` se vinculan a `127.0.0.1` por defecto; `--host 0.0.0.0` sigue disponible explícitamente.
- `http.Server` (Go) con `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout` e `IdleTimeout`.
- Cliente HTTP del caso de uso de consulta con `Timeout: 30s`.
- CORS configurable con `DATAMESH_CORS_ORIGIN` (default `*`).

## Alternativas Consideradas

### Token de autenticación compartido para HTTP/MCP
- **Pros:** bloquearía por completo el acceso cross-site sin autorización.
- **Contras:** cambia el mecanismo de conexión de clientes MCP existentes y requiere gestión de secretos en el cliente.
- **Rechazado para ADR 0016:** el bind a loopback + bloqueo SSRF/local-path cierra los vectores identificados; un token se evaluará juntamente con un esquema de autorización formal (ADR futuro).

### Eliminar el proxy CORS (`/proxy`) por completo
- **Pros:** el vector SSRF desaparece.
- **Contras:** rompe el caso de uso documentado de aplicaciones web soberanas que consumen catálogos federados desde el navegador (core del producto).
- **Rechazado:** se conserva con política default-deny y escape hatches.

### Bloquear toda ruta local en MCP sin excepción
- **Pros:** máxima contención.
- **Contras:** impide el uso legítimo de MCP por un agente local sobre bundletes locales ya existentes.
- **Rechazado parcialmente:** se permite la vía tríada/resolución y la API SDK; el MCP exige refs remotas o canónicas.

## Consecuencias

### Positivas
- Default-deny comprobable: los vectores SSRF/TLS/local-read y de fuga de secretos quedan cerrados de fábrica.
- Escape hatches explícitos y documentados para intranets y CAs gubernamentales.
- Tests específicos: `bindings/python/tests/test_security.py` y `core-go/adapters/inbound/cli/security_test.go`.

### Negativas
- Los `workshops`/agentes que llamaban a MCP con `file://` locales deben migrar a tríadas o a la API SDK.
- Entornos con catálogos en hosts privados requieren `DATAMESH_PROXY_ALLOWED_HOSTS` o `DATAMESH_PROXY_ALLOW_PRIVATE=1`.
- Cambio de comportamiento en `datamesh serve` (bind `127.0.0.1`) y en `datamesh config` (secretos enmascarados).

### Pruebas
- `pytest bindings/python/tests` y `go test ./...` en `core-go` (sin regresiones nuevas sobre la línea base).