# Política y Guía de Despliegue y Distribución (DEPLOYMENT.md)

Este documento establece las políticas de versionado, automatización de compilaciones, distribución de artefactos multiplataforma y despliegue en producción del **DataMesh SDK** y su Servidor Soberano.

---

## 1. Estrategia de Versionado Semántico (SemVer)

El proyecto adopta rigurosamente [Semantic Versioning 2.0.0](https://semver.org/):

$$\text{v}\langle\text{MAJOR}\rangle.\langle\text{MINOR}\rangle.\langle\text{PATCH}\rangle$$

- **MAJOR (v1.0.0):** Cambios incompatibles en la API pública de 1 línea, el protocolo MCP JSON-RPC o en los modelos centrales de datos.
- **MINOR (v0.3.0):** Nuevos casos de uso, adaptadores de catálogo/almacenamiento, o nuevas herramientas MCP manteniendo compatibilidad retrospectiva.
- **PATCH (v0.2.1):** Corrección de defectos, mejoras de rendimiento o parches de seguridad.

---

## 2. Matriz de Artefactos de Release

El pipeline automatizado en [`.github/workflows/release.yml`](.github/workflows/release.yml) se dispara automáticamente al emitir etiquetas `v*` (ej. `v0.2.1`) y genera los siguientes artefactos en cada release oficial:

| Tipo | Artefacto | Ecosistema / Destino | Descripción |
| --- | --- | --- | --- |
| **Python Wheel** | `datamesh_sdk-*.whl` | PyPI / pip | Paquete binario universal Python 3.9+ |
| **Python Sdist** | `datamesh_sdk-*.tar.gz` | PyPI / pip | Distribución de código fuente Python con tests y adaptadores |
| **TypeScript / NPM** | `datosbolivia-datamesh-client-*.tgz` | npm / Node.js | Cliente SDK compilado en TypeScript para navegador y server |
| **R Binding** | `datamesh-r-*.tar.gz` | R / CRAN | Paquete fuente R estructurado para data science |
| **Integridad Criptográfica** | `SHA256SUMS.txt` | Universal | Firmas criptográficas SHA-256 de todos los artefactos de la release |

---

## 3. Procedimiento para Publicar un Nuevo Release por Tags

### Paso 1: Verificación Local Pre-Release
Asegurar que toda la suite de pruebas pase al 100%:
```bash
pytest bindings/python/tests -v
```

### Paso 2: Crear y Publicar el Tag de Versión
El pipeline de GitHub Actions se encarga de sincronizar dinámicamente el número de versión en `pyproject.toml`, `package.json` y `DESCRIPTION` a partir del tag:

```bash
VERSION="v0.2.1"

# 1. Crear tag anotado
git tag -a "$VERSION" -m "Release $VERSION: Curation commands, semantic MCP tools, and multi-catalog support"

# 2. Publicar tag en el repositorio remoto
git push origin "$VERSION"
```

Al subir la etiqueta, GitHub Actions:
1. Extrae el número SemVer limpio (`0.2.1`).
2. Sincroniza metadatos de empaquetado en Python, TypeScript y R.
3. Compila los paquetes (`wheel`, `sdist`, `npm pack`, `tar.gz`).
4. Valida los metadatos con `twine check`.
5. Calcula los checksums criptográficos `SHA256SUMS.txt`.
6. Crea el **GitHub Release** oficial con notas de cambios automáticas (`generate_release_notes: true`) y adjunta todos los paquetes compilados.

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
