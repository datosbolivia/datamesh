# Guía de Versionado, Testing y Ciclo de Vida de Lanzamientos

Este documento detalla la gobernanza de **Semantic Versioning 2.0 (SemVer)**, la estrategia de pruebas automatizadas y el ciclo de pre-lanzamientos para el **DataMesh Sovereign SDK** (`datamesh-sdk`).

---

## 1. Políticas de Versionado Semántico (SemVer 2.0)

El SDK sigue la nomenclatura:
`MAJOR.MINOR.PATCH[-PRERELEASE]` (ej. `v0.2.0`, `v0.2.1`, `v0.3.0-rc.1`, `v1.0.0`)

### 1.1 Versión Principal (MAJOR - `X.0.0`)
Se incrementa cuando se producen **cambios incompatibles que rompen la API pública existente (Breaking Changes)**:
- **Fachada Unificada de 1 Línea:** Modificación en la firma de funciones núcleo (`datamesh.read`, `datamesh.sql`, `datamesh.discover`).
- **Eliminación o Cambio de Contratos:** Eliminación de puertos o adaptadores públicos (`GenericStorageManager`, `AbstractQueryEngine`, `ManifestParser`).
- **Compatibilidad de Entorno:** Aumento en la versión mínima requerida de Python (ej. abandonar soporte para Python 3.10) o cambios mayores en el motor DuckDB que impidan la lectura de tablas existentes.
- **Protocolo de Lanzamiento:** Requiere un ADR formal en `docs/decisions/`, ciclo previo de deprecación con advertencias explícitas (`DeprecationWarning`) y guía de migración.

### 1.2 Versión Secundaria (MINOR - `x.Y.0`)
Se incrementa cuando se añaden **nuevas capacidades, adaptadores o resolutores de forma retrocompatible**:
- Adición de nuevos adaptadores de almacenamiento o protocolos (ej. soporte para nuevos catálogos CKAN, conectores MEFP, almacenamiento en la nube).
- Nuevas extensiones o funciones SQL registradas en el runtime DuckDB.
- Incorporación de nuevas herramientas o recursos en el servidor MCP (`datamesh-mcp`).
- Soporte para nuevas versiones de Python (ej. Python 3.13 / 3.14).
- **Protocolo de Lanzamiento:** Requiere pruebas unitarias herméticas, tests de integración y actualización en `docs/reference/CASOS_DE_USO.md`.

### 1.3 Versión de Parche (PATCH - `x.y.Z`)
Se incrementa cuando se corrigen **errores (Bug Fixes) o vulnerabilidades de seguridad sin alterar la interfaz**:
- Corrección de bugs en la resolución de rutas relativas o manipulación de URLs.
- Ajustes de seguridad (prevención de SQL injection o path traversal).
- Corrección de tipado estricto o manejo de excepciones de conexión.
- **Protocolo de Lanzamiento:** Cada parche debe incorporar un test de regresión en `bindings/python/tests` que impida la reaparición del bug.

---

## 2. Versiones de Prueba y Pre-lanzamientos

Para validar versiones con usuarios, investigadores y sistemas autónomos antes de un lanzamiento masivo, se emplean sufijos SemVer:

| Sufijo | Fase | Definición | Consumo Recomendado |
| :--- | :--- | :--- | :--- |
| `-alpha.N` | Alfa | Funcionalidades experimentales; API sujeta a cambios. | Entornos de laboratorio y pruebas de concepto. |
| `-beta.N` | Beta | **Feature Freeze**: Todas las funciones implementadas; validación de estabilidad con múltiples catálogos. | Pruebas de integración y agentes de prueba. |
| `-rc.N` | Release Candidate | **Code Freeze**: Idéntico a producción; sólo se admiten correcciones a bugs bloqueantes (*showstoppers*). | Pruebas de aceptación finales. |

### Instalación de Versiones de Prueba
- **Instalación desde Git tag:**
  ```bash
  pip install git+https://github.com/datosbolivia/datamesh-sdk.git@v0.2.1-rc.1
  ```
- **Instalación desde PyPI (con bandera de pre-release):**
  ```bash
  pip install --pre datamesh-sdk
  ```

---

## 3. Pirámide y Protocolo de Testing

Todo cambio en el SDK debe superar el 100% de la suite de pruebas automatizadas antes de cualquier merge o release:

```bash
# 1. Configurar entorno
python3 -m venv .venv
source .venv/bin/activate
pip install -e bindings/python
pip install pytest pytest-cov

# 2. Ejecutar suite hermética completa (121+ tests)
PYTHONPATH=bindings/python pytest bindings/python/tests -v --strict-markers

# 3. Verificación de cobertura
PYTHONPATH=bindings/python pytest bindings/python/tests --cov=datamesh --cov-report=term-missing
```

---

## 4. Pipeline de CI/CD Automatizado

1. **Integración Continua ([`ci.yml`](.github/workflows/ci.yml)):**
   - Ejecuta la suite de pruebas completa en matriz multiplataforma para Python 3.10, 3.11, 3.12 y 3.13 en cada `push` y `pull_request`.
2. **Entrega Continua ([`release.yml`](.github/workflows/release.yml)):**
   - Al crear un tag (`v*`), compila los paquetes de distribución (`wheel` y `sdist`).
   - Calcula sumas criptográficas SHA-256 (`SHA256SUMS.txt`).
   - Si el tag contiene un guion (`-`), marca la release en GitHub automáticamente como **Pre-release**.
