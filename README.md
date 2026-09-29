# DataMesh SDK

[![Status](https://img.shields.io/badge/status-active-brightgreen.svg)]()
[![Specification](https://img.shields.io/badge/spec-OKF%20v0.2-blue.svg)](specificacion_knowledge.md)
[![License](https://img.shields.io/badge/license-MIT%20with%20Attribution-green.svg)](LICENSE)
[![Engine](https://img.shields.io/badge/engine-DuckDB%20%7C%20Go-yellow.svg)]()
[![Protocol](https://img.shields.io/badge/agent-MCP%202024--11--05-purple.svg)](docs/reference/MCP_SERVER.md)

SDK Soberano y Descentralizado para el Formato de Conocimiento Abierto Federado (**OKF / ODKF v0.2**). Diseñado bajo **Arquitectura Hexagonal (Ports & Adapters)** y **Domain Driven Design (DDD)** con núcleo en **Go**, puertos en **Python** y **TypeScript**, motor analítico **DuckDB** y servidor **Model Context Protocol (MCP)** para agentes de Inteligencia Artificial.

Repositorio: [https://github.com/datosbolivia/datamesh.git](https://github.com/datosbolivia/datamesh.git)

---

## Características Principales

- 🌐 **Federación Descentralizada de Catálogos**: Lee el catálogo soberano base (`https://datosbolivia.github.io/llms.txt`) y permite federar múltiples catálogos institucionales concurrentemente.
- 🦆 **Motor SQL Columnar Embebido (DuckDB)**: Ejecuta consultas ANSI SQL completas (JOINs, agregaciones, CTEs) sobre recursos tabulares.
- 🔄 **Normalización de Heterogeneidad**: Unifica automáticamente archivos CSV, TSV, Parquet, JSON y JSON Lines en representaciones columnares en memoria.
- 🏷️ **Tríada Canónica Universal**: Direcciona cualquier tabla o recurso mediante `"catalogo:dataset:resource"`.
- 🤖 **Servidor MCP Nativo para Agentes**: Protocolo JSON-RPC 2.0 sobre `stdio` para Claude Desktop, Cursor, Antigravity y otros asistentes de IA.
- ⚙️ **Configuración Jerárquica Determinista**: Soporte para `datamesh.json`, `datamesh.yaml`, variables de entorno `DATAMESH_{{BASE_VAR}}` y adaptadores `DATAMESH__{{ADAPTADOR}}_{{VAR}}`.

---

## Inicio Rápido

Consulta la guía completa paso a paso en [**QUICKSTART.md**](QUICKSTART.md).

### Instalación Rápida (Python)
```bash
pip install git+https://github.com/datosbolivia/datamesh.git#subdirectory=bindings/python
```

### Consultas SQL en 1 Línea
```python
import datamesh as dm

# Descubrir datasets disponibles en la federación
catalogo = dm.discover()

# Ejecutar consulta SQL completa
df = dm.sql("SELECT departamento, SUM(votos_validos) FROM 'bolivia:elecciones:votos' GROUP BY departamento")
```

### Servidor MCP para Agentes
```bash
datamesh mcp-serve
```

---

## Estructura del Proyecto

```text
datamesh/
├── core-go/                  # Núcleo Go (Dominio puro, Puertos, Casos de Uso, WASM y C-Shared)
│   ├── domain/               # DataProduct, ResourceTriad, Catalog, Config
│   ├── ports/                # Puertos Inbound y Outbound
│   ├── usecases/             # Casos de uso de descubrimiento, resolución y consultas
│   └── adapters/             # CLI nativa, resolutores HTTP llms.txt, motor CSV
├── bindings/
│   ├── python/               # Librería Python, CLI (`datamesh`), DuckDB y servidor MCP
│   └── typescript/           # Cliente browser/WASM ligero en TypeScript
├── docs/
│   ├── decisions/            # ADRs formales (0001, 0002, 0003)
│   └── reference/            # Arquitectura, Casos de Uso, CLI, MCP Server
├── QUICKSTART.md             # Guía práctica paso a paso
└── specificacion_knowledge.md # Especificación normativa OKF v0.2
```

---

## Documentación Técnica

- [Guía de Inicio Rápido (QUICKSTART.md)](QUICKSTART.md)
- [Arquitectura Hexagonal (ARQUITECTURA.md)](docs/reference/ARQUITECTURA.md)
- [Casos de Uso del SDK (CASOS_DE_USO.md)](docs/reference/CASOS_DE_USO.md)
- [Referencia de Comandos CLI (CLI.md)](docs/reference/CLI.md)
- [Servidor Model Context Protocol (MCP_SERVER.md)](docs/reference/MCP_SERVER.md)
- [Registro de Decisiones Arquitectónicas (ADRs)](docs/decisions/)

---

## Licencia

Distribuido bajo la Licencia **MIT con Requisito de Atribución**.

Las empresas y particulares tienen total libertad de uso comercial, privado, modificación y distribución, sujeto a incluir el aviso de copyright original y la debida **referencia/atribución a Datos Bolivia** y a este repositorio ([https://github.com/datosbolivia/datamesh.git](https://github.com/datosbolivia/datamesh.git)). Consulta el archivo [`LICENSE`](LICENSE) para más detalles.
