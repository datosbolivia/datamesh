# Guía de Contribución y Políticas de Colaboración (CONTRIBUTING.md)

Bienvenido al proyecto **DataMesh SDK**. Este documento define las políticas técnicas, arquitectónicas y procedimentales obligatorias para colaborar en este repositorio.

---

## 1. Principios Rectores y Filosofía de Diseño

1. **Go Core como Autoridad Canónica de Dominio:** El modelo de dominio (`DataProduct`, `Catalog`, `Policy`, `Crypto`, `Validator`) reside exclusivamente en `core-go`. Los bindings en Python, TypeScript o R son adaptadores delegados que consumen Go Core mediante C-ABI (`libdatamesh.so`), WebAssembly (`datamesh.wasm`) o llamadas de proceso.
2. **Cero Fallbacks Silenciosos (Fail-Fast):** Si un componente nativo o regla de integridad no puede ejecutarse, el sistema debe fallar de manera inmediata y explícita (`GoCoreUnavailableError`, `PolicyViolationError`). Nunca ocultar fallos con simulaciones o datos inventados.
3. **Arquitectura Hexagonal Estricta (Ports & Adapters):**
   - **Dominio:** Cero dependencias de infraestructura o red.
   - **Puertos:** Interfaces inmutables de entrada y salida.
   - **Casos de Uso:** Orquestación de flujos de negocio puros.
   - **Adaptadores:** Implementaciones intercambiables de I/O, almacenamiento, CLI, DuckDB y red.
4. **KISS & YAGNI:** Mínimo cambio completo que resuelve la tarea. La API pública debe ser de 1 línea (`import datamesh as dm; df = dm.sql(...)`). Evitar abstracciones especulativas.
5. **Guardrails Antialucinación:** Rigor epistémico absoluto. Cero cifras inventadas, citas obligatorias de la tríada canónica (`catalogo:dataset:resource`), y transparencia total ante datos nulos o vacíos.

---

## 2. Requisitos del Entorno de Desarrollo

- **Go:** 1.22 o superior.
- **Python:** 3.10 o superior (con `pip`, `venv` y `setuptools`).
- **Compilador C / CGO:** `gcc` o `clang` con `libc6-dev` (obligatorio para compilar la biblioteca compartida nativa).
- **Node.js (opcional para TypeScript):** 18.0 o superior con `npm`.
- **Git:** con soporte para firmas criptográficas (GPG o SSH recomendado).

---

## 3. Configuración del Entorno Local

```bash
# 1. Clonar el repositorio
git clone https://github.com/datosbolivia/datamesh.git
cd datamesh

# 2. Compilar la biblioteca compartida nativa de Go Core (C-Shared)
cd core-go
go build -buildmode=c-shared -o libdatamesh.so ./adapters/inbound/cshared/exports.go
cd ..

# 3. Configurar entorno virtual de Python
python3 -m venv .venv
source .venv/bin/activate

# 4. Instalar dependencias y bindings de Python en modo editable
pip install --upgrade pip
pip install -e bindings/python
pip install pytest pytest-cov

# 5. Ejecutar la suite completa de pruebas
go test -v -race ./core-go/...
DATAMESH_LIB_PATH="$(pwd)/core-go/libdatamesh.so" pytest bindings/python/tests -v
```

---

## 4. Convención de Commits y Ramas

### 4.1 Nomenclatura de Ramas
- `feat/<nombre-funcionalidad>`: Para nuevas capacidades o adaptadores.
- `fix/<nombre-correccion>`: Para corrección de errores o desajustes de invariantes.
- `docs/<tema>`: Para documentación técnica, ADRs o casos de uso.
- `refactor/<alcance>`: Para refactorizaciones que no alteran la API pública ni el comportamiento funcional.

### 4.2 Conventional Commits
Todos los mensajes de commit deben seguir la especificación [Conventional Commits](https://www.conventionalcommits.org/):

```text
<tipo>(<alcance opcional>): <descripción concisa en imperativo>

[cuerpo explicativo opcional del por qué y compensaciones]

[referencias a issues o ADRs]
```

**Tipos válidos:**
- `feat`: Nueva funcionalidad o capacidad.
- `fix`: Corrección de un defecto o fallo.
- `docs`: Modificación o adición de documentación.
- `refactor`: Refactorización interna sin cambio funcional.
- `test`: Adición o mejora de pruebas.
- `ci`: Modificaciones en workflows de GitHub Actions o scripts de build.
- `chore`: Mantenimiento general, dependencias o tooling.

---

## 5. Mandato de Documentación Técnica y ADRs

Cualquier cambio de código debe mantener la documentación sincronizada de forma exhaustiva:

1. **Sin Código Huérfano:** Cada puerto, caso de uso y adaptador nuevo debe documentarse en:
   - [`docs/reference/CASOS_DE_USO.md`](docs/reference/CASOS_DE_USO.md)
   - [`docs/reference/ARQUITECTURA.md`](docs/reference/ARQUITECTURA.md)
2. **Registro de Decisiones Arquitectónicas (ADRs):** Decisiones de diseño no triviales (nuevas dependencias, protocolos criptográficos, cambios en contratos) deben documentarse formalmente como un ADR en [`docs/decisions/`](docs/decisions/).
3. **Integridad de Referencia de la API Pública:** Los símbolos expuestos en `datamesh.__all__`, CLI y MCP deben estar respaldados por pruebas de integridad que verifiquen que ningún símbolo documentado quede roto (`bindings/python/tests/test_reference_integrity.py`).
4. **Grafo de Conocimiento del Repositorio:** Tras modificar archivos de código, actualizar el grafo ejecutando `graphify update .`.

---

## 6. Estándares de Código por Lenguaje

### 6.1 Go Core (`core-go/`)
- Código formateado con `gofmt` y validado sin warnings de compilación.
- Manejo de errores explícito; no descartar errores con `_` en flujos de dominio.
- El paquete `domain` no debe importar adaptadores, I/O externa ni bibliotecas de red.
- Cobertura de pruebas unitarias con detección de condiciones de carrera (`go test -race`).

### 6.2 Python (`bindings/python/`)
- Tipado estricto Python 3.10+ (`from __future__ import annotations`).
- Clases de datos inmutables (`@dataclass(frozen=True)`) para modelos de valor y eventos.
- Manejo de errores explícito importando desde `datamesh.domain.errors`.
- Conservar docstrings y documentación técnica según las directrices de `technical-reference-comments`.

---

## 7. Protocolo de Verificación Antes de Abrir un Pull Request

Antes de enviar un Pull Request, confirma la siguiente lista de verificación:

- [ ] `go test -v -race ./core-go/...` pasa al 100%.
- [ ] `libdatamesh.so` compila limpiamente con CGO sin advertencias.
- [ ] `pytest bindings/python/tests` pasa al 100% de éxito contra la biblioteca nativa.
- [ ] Pruebas de integridad de referencia ejecutadas (`test_reference_integrity.py`).
- [ ] Casos de uso actualizados en `docs/reference/CASOS_DE_USO.md`.
- [ ] Diagramas o secciones actualizadas en `docs/reference/ARQUITECTURA.md`.
- [ ] ADR formal registrado en `docs/decisions/` si aplica una decisión arquitectónica.
- [ ] Mensajes de commit conformes a Conventional Commits.
- [ ] Sin credenciales, tokens ni secretos embebidos en el código ni en fixtures de prueba.
