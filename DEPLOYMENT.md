# Política y Guía de Despliegue y Distribución (DEPLOYMENT.md)

Este documento establece las políticas de versionado, automatización de compilaciones, distribución de artefactos multiplataforma y despliegue en producción del **DataMesh SDK** y su Servidor Soberano.

---

## 1. Estrategia de Versionado Semántico (SemVer)

El proyecto adopta rigurosamente [Semantic Versioning 2.0.0](https://semver.org/):

$$\text{v}\langle\text{MAJOR}\rangle.\langle\text{MINOR}\rangle.\langle\text{PATCH}\rangle$$

- **MAJOR (v1.0.0):** Cambios incompatibles en la API pública de 1 línea, el protocolo C-ABI (`exports.go`), o en la especificación normativa OKF/ODKF.
- **MINOR (v0.3.0):** Nuevos casos de uso, adaptadores de catálogo/almacenamiento, o nuevas herramientas MCP manteniendo compatibilidad retrospectiva.
- **PATCH (v0.2.1):** Corrección de defectos, mejoras de rendimiento o parches de seguridad.

### 1.1 Regla de Doble Tagging para Monorepos en Go
Debido a que el módulo de Go se ubica en el subdirectorio `core-go/` (`module github.com/datosbolivia/datamesh-sdk/core-go`), cada versión debe emitir **dos etiquetas git sincronizadas**:
1. `vX.Y.Z` — Tag raíz que dispara los workflows de GitHub Actions para release general, Python wheels, WASM y binarios.
2. `core-go/vX.Y.Z` — Tag requerido por el proxy y gestor de dependencias de Go (`go get github.com/datosbolivia/datamesh-sdk/core-go@vX.Y.Z`).

---

## 2. Matriz de Artefactos de Release

El pipeline automatizado en [`.github/workflows/release.yml`](.github/workflows/release.yml) compila y genera los siguientes artefactos en cada release oficial:

| Tipo | Artefacto | Plataforma / Destino | Descripción |
| --- | --- | --- | --- |
| **CLI Go Nativo** | `datamesh-linux-amd64` | Linux x86_64 | Binario estático compilado con `-ldflags="-s -w"` |
| **CLI Go Nativo** | `datamesh-darwin-arm64` | macOS Apple Silicon | Binario nativo para arquitecturas ARM64 |
| **CLI Go Nativo** | `datamesh-windows-amd64.exe` | Windows x86_64 | Binario ejecutable para Windows |
| **C-Shared Library** | `libdatamesh.so` | Linux (CGO) | Biblioteca compartida C-ABI para Python y C |
| **C-Shared Library** | `libdatamesh.dylib` | macOS (CGO) | Biblioteca dinámica nativa para macOS |
| **C-Shared Library** | `datamesh.dll` | Windows (CGO) | Biblioteca compartida para Windows |
| **WebAssembly** | `datamesh.wasm` | Browser / Node.js | Módulo WASM para clientes web y TypeScript |
| **Python Wheel** | `datamesh_sdk-*.whl` | PyPI / pip | Paquete Python con `libdatamesh.so` incrustada |
| **Integridad** | `SHA256SUMS.txt` | Universal | Firmas criptográficas SHA-256 de todos los artefactos |

---

## 3. Procedimiento para Publicar un Nuevo Release

### Paso 1: Verificación Local Pre-Release
Asegurar que todas las pruebas pasen al 100%:
```bash
go test -v -race ./core-go/...
DATAMESH_LIB_PATH="$(pwd)/core-go/libdatamesh.so" pytest bindings/python/tests -v
```

### Paso 2: Actualizar Versiones en Metadatos
Sincronizar el número de versión en:
- `bindings/python/pyproject.toml` (`version = "X.Y.Z"`)
- `bindings/typescript/package.json` (`"version": "X.Y.Z"`)
- `bindings/python/datamesh/server.py` (`SERVER_VERSION = "X.Y.Z"`)
- `bindings/python/datamesh/mcp_server.py` (`SERVER_VERSION = "X.Y.Z"`)

### Paso 3: Crear y Publicar los Tags
```bash
VERSION="v0.2.1"

# 1. Crear tag raíz
git tag -a "$VERSION" -m "Release $VERSION: Go Core authority and granular policy engine"

# 2. Crear tag del submódulo Go
git tag -a "core-go/$VERSION" -m "Go Core Module Release $VERSION"

# 3. Publicar tags en el repositorio remoto
git push origin "$VERSION"
git push origin "core-go/$VERSION"
```

El pipeline de GitHub Actions se disparará automáticamente, compilando la matriz, empaquetando el wheel de Python y publicando el release en GitHub con sus checksums.

---

## 4. Despliegue del Servidor Soberano en Producción

El Servidor Soberano DataMesh provee simultáneamente endpoints REST, proxy CORS seguro, handshake de identidad OpenSSH/GitHub y servidor MCP JSON-RPC 2.0.

### 4.1 Despliegue con Docker y Docker Compose (Recomendado)
El proyecto incluye un [`Dockerfile`](Dockerfile) multi-etapa optimizado y un [`docker-compose.yml`](docker-compose.yml):

```bash
# Iniciar el servicio en segundo plano
docker compose up -d

# Verificar el estado y logs
docker compose ps
docker compose logs -f datamesh-server

# Comprobar el endpoint de salud
curl -f http://127.0.0.1:8000/health
```

### 4.2 Endpoints Expuestos por el Servidor
- **Salud y Latencia:** `GET /health` y `GET /ping`
- **Descubrimiento y Auth:** `GET /.well-known/datamesh.json`
- **Handshake Criptográfico:** `POST /api/v1/handshake`
- **Consulta SQL Directa:** `GET /api/sql?q=...` y `POST /api/sql`
- **Catálogo Federado:** `GET /api/catalog`
- **Servidor MCP para Agentes IA:** `POST /mcp` o `POST /rpc`
- **Proxy CORS con Protección SSRF:** `GET /proxy?url=...`

### 4.3 Endurecimiento (Hardening) de Seguridad en Producción
Para entornos expuestos a Internet o redes corporativas, configurar las siguientes variables de entorno:

1. **`DATAMESH_INSECURE_TLS=0`**: Obliga a verificar certificados TLS válidos en todas las peticiones salientes contra catálogos externos.
2. **`DATAMESH_CORS_ORIGIN`**: Restringir el origen permitido (ej. `https://portal.datosbolivia.org`) en lugar de `*`.
3. **`DATAMESH_PROXY_ALLOWED_HOSTS`**: Allowlist explícita de dominios soberanos autorizados para el proxy (ej. `datosbolivia.github.io,datos.gob.bo`).
4. **Protección Perimetral:** En despliegues públicos, colocar un proxy inverso (Nginx, Traefik o Caddy) al frente para terminación TLS HTTPS (puerto 443) y limitación de tasa de peticiones (rate limiting).

---

## 5. Publicación de la Documentación Técnica

La documentación técnica generada con **Quarto** se compila y publica automáticamente en GitHub Pages mediante el workflow [`.github/workflows/quarto-publish.yml`](.github/workflows/quarto-publish.yml) ante cualquier cambio en el directorio `docs/`.
