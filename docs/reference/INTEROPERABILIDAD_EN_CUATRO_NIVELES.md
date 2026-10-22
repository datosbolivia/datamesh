# Marco de Interoperabilidad en Cuatro Niveles (EIF & FAIR) en OKF/ODKF v0.2

**Fecha:** 2026-10-22  
**Autor:** Arquitecto Principal de Software & Metodólogo de Calidad  
**Referencia Normativa:** European Interoperability Framework (EIF), Principios FAIR (Wilkinson et al., 2016), W3C DCAT v3, RFC 7233.  
**Repositorios:** `open-knowledge-format` & `datamesh-sdk`

---

## 1. Fundamentación y Arquitectura de Interoperabilidad

La interoperabilidad en el **Formato de Conocimiento Abierto Orientado a Datos (OKF / ODKF v0.2)** se concibe no como un mero intercambio de archivos, sino como una **arquitectura holística de cuatro capas** alineada con el *Marco Europeo de Interoperabilidad (EIF)* y los *Principios FAIR* (Findable, Accessible, Interoperable, Reusable):

```
+-----------------------------------------------------------------------------------+
| 4. INTEROPERABILIDAD ORGANIZATIVA Y JURÍDICA (Gobernanza, Privacidad y Confianza) |
|    Licencias FAIR, Políticas Zero-Microdata (Habeas Data), Firmas OpenSSH/Ed25519 |
+-----------------------------------------------------------------------------------+
| 3. INTEROPERABILIDAD SEMÁNTICA (Significado Inequívoco del Conocimiento)          |
|    Anclajes Ontológicos SKOS/Wikidata, Dimensiones OLAP, Tríadas Canónicas        |
+-----------------------------------------------------------------------------------+
| 2. INTEROPERABILIDAD SINTÁCTICA (Estructuración y Gramática Formal de Datos)      |
|    YAML Frontmatter, Frictionless Data Package, OpenAPI 3.1, Apache Parquet       |
+-----------------------------------------------------------------------------------+
| 1. INTEROPERABILIDAD TÉCNICA (Conectividad, Transporte y Flujos Físicos)          |
|    HTTP/HTTPS, HTTP Range Requests (Zero-Copy), Kademlia DHT P2P, Arrow Flight SQL|
+-----------------------------------------------------------------------------------+
```

---

## 2. Nivel 1: Interoperabilidad Técnica (Technical Interoperability)

### 2.1 Definición y Alcance
Garantiza que los sistemas, hardware y redes se conecten e intercambien flujos binarios y mensajes de forma fiable, escalable y soberana.

### 2.2 Implementación en OKF / DataMesh SDK
1. **Transporte Abierto y Estándar (FAIR A1):**
   - Acceso universal mediante protocolos web estándar: **HTTP / HTTPS (RFC 7230)** y **WebSockets / Arrow Flight SQL**.
   - Integración nativa con sistemas de objetos y cloud: **Amazon S3 / MinIO (`s3://`)**, Google Drive y Kaggle API.
2. **Lectura Parcial Cero-Copia (*Zero-Copy Range Fetch* - RFC 7233):**
   - El adaptador [`HttpRange`](SPEC.md#1621-storageport) permite leer metadatos de cabecera y footers de compresión (ej. footers de Parquet o directorios centrales de archivos ZIP) sin descargar el archivo completo de varios gigabytes.
3. **Red P2P y Direccionamiento Soberano (OKF-P2P):**
   - Enrutamiento distribuido mediante **Kademlia DHT** con métrica de distancia XOR.
   - Eliminación de puntos únicos de fallo y dependencia de DNS centralizado (ICANN) mediante identidades criptográficas `did:okf:<ed25519_pubkey>`.

---

## 3. Nivel 2: Interoperabilidad Sintáctica (Syntactic Interoperability)

### 3.1 Definición y Alcance
Garantiza que los datos viajen en formatos estructurados, analizables computacionalmente (*machine-actionable*), con tipos de datos formalmente definidos y gramáticas libres de ambigüedad.

### 3.2 Implementación en OKF / DataMesh SDK
1. **Formato Base Universal y Agnóstico:**
   - Documentos de concepto en **Markdown UTF-8** con bloques delimitados de frontmatter **YAML** (`---`). Si un sistema puede ejecutar `cat` o un parser YAML básico, puede procesar OKF.
2. **Contratos de Datos Sintácticos por Referencia (`contracts:`):**
   - **Frictionless Data Package / Table Schema:** Define tipos de datos estrictos (`integer`, `number`, `string`, `date`), restricciones (`constraints`), claves foráneas y delimitadores.
   - **OpenAPI 3.1:** Para recursos dinámicos y microservicios analíticos.
   - **Common Workflow Language (CWL):** Para contratos de herramientas CLI y reproducibilidad computacional.
3. **Formatos de Almacenamiento Columnar Eficientes:**
   - Serialización nativa en **Apache Parquet (Snappy/ZSTD)** y **Apache Arrow IPC**, garantizando cero copias en memoria durante consultas SQL complejas con DuckDB.

---

## 4. Nivel 3: Interoperabilidad Semántica (Semantic Interoperability)

### 4.1 Definición y Alcance
Asegura que el **significado conceptual, el vocabulario y el contexto** de los datos sean interpretados con exactitud matemática idéntica tanto en el emisor como en el receptor, eliminando la polisemia y sinonimia.

### 4.2 Implementación en OKF / DataMesh SDK
1. **Anclajes Ontológicos Formales (`skos:`):**
   - Cada concepto enlaza URIs desreferenciables a autoridades globales de conocimiento:
     - **W3C DCAT v3:** `http://www.w3.org/ns/dcat#Dataset`
     - **Wikidata:** `http://www.wikidata.org/entity/Q39825` (Censo / Elecciones)
     - **Schema.org:** `https://schema.org/GovernmentData`
     - Tesauros especializados (ej. AGROVOC de la FAO, DeCS/MeSH para salud).
2. **Dimensiones de Dominio (`dimensions:`):**
   - Estandarización de variables categóricas compartidas para agregaciones federadas (ej. `departamento`, `municipio`, `año`, `sexo`).
3. **Espacio de Nombres Jerárquico (Tríada Canónica):**
   - Identificación unívoca global mediante la sintaxis `catalogo:dataset:recurso`, permitiendo joins SQL cross-catalog sin ambigüedades de nombres de columna.
4. **Mapeo Semántico de Campos (`SemanticFieldMapping`):**
   - Vinculación explícita entre columnas tabulares crudas y conceptos normalizados en el grafo de conocimiento.

---

## 5. Nivel 4: Interoperabilidad Organizativa y Jurídica (Legal & Organizational)

### 5.1 Definición y Alcance
Regula los procesos institucionales, los permisos, las licencias legales de uso, el cumplimiento ético, la soberanía de la información y la protección jurídica de la privacidad (Habeas Data).

### 5.2 Implementación en OKF / DataMesh SDK
1. **Licenciamiento Abierto Explícito (FAIR R1.1):**
   - Declaración obligatoria de licencias estandarizadas en metadatos (`CC-BY-4.0`, `ODbL-1.0`, `Apache-2.0`), garantizando certeza jurídica sobre los derechos de reutilización.
2. **Gobernanza Cero-Microdatos (`policy: zero_microdata`):**
   - Cumplimiento normativo de protección de datos personales. El motor de consulta intercepta y deniega consultas `SELECT *` sobre registros individualizados a actores externos no autorizados, autorizando únicamente agregaciones estadísticas anónimas (`COUNT`, `AVG`, `SUM`, `GROUP BY`).
3. **Confianza Criptográfica y Firma Institucional (No Repudio):**
   - Firma digital de manifiestos y bundles con claves **Ed25519** y **OpenSSH** (`ssh-keygen -Y sign/verify`).
   - Validación de identidad contra listas blancas institucionales o endpoints públicos GitHub (`https://github.com/<organización>.keys`).
4. **Linaje y Atestación Metodológica (Auditoría Legal):**
   - Registro cronológico inmutable en `log.md` (§9).
   - Atribución de autoría epistémica (`generated.by`, `verified[].by`).
   - Hash SHA-256 de herramientas y datos en cada paso de transformación (`lineage.transformations`), garantizando la trazabilidad forense exigida por auditorías de estado.

---

## 6. Matriz de Síntesis de Interoperabilidad

| Nivel de Interoperabilidad | Pregunta Clave | Mecanismo en OKF / ODKF v0.2 | Componente en el SDK / Motor |
| :--- | :--- | :--- | :--- |
| **1. Técnica** | ¿Se pueden conectar y transferir los bits? | HTTP/S, S3, Range Requests (RFC 7233), Kademlia P2P, Arrow Flight. | `StoragePort`, `HttpRangeAdapter`, `DuckDB Streaming`. |
| **2. Sintáctica** | ¿Se comprende la gramática y estructura del archivo? | Markdown + YAML frontmatter, Frictionless Data Package, OpenAPI, Parquet. | `ManifestParser`, `DataPackageParser`, `Validator (RULE-01, 04, 05)`. |
| **3. Semántica** | ¿El dato significa exactamente lo mismo en ambos extremos? | Anclas SKOS, Wikidata URIs, dimensiones analíticas, tríadas canónicas. | `Validator (RULE-03, 08)`, `SemanticAligner`, `UnifiedCatalog`. |
| **4. Organizativa / Jurídica** | ¿Es legal, ético y seguro compartir y usar este dato? | Licencias FAIR, gobernanza Zero-Microdata, firmas SSH/Ed25519, linaje SHA-256. | `PolicyEngine (RULE-06)`, `CryptoEngine (Ed25519/SSH)`, `LineageAuditor`. |
