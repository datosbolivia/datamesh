# ADR 0010: Ingesta de Catálogos CKAN, Autenticación Generalizada (Keycloak/OAuth2/APIKey) y Descubrimiento Well-Known

- **Estado:** Aceptado
- **Fecha:** 2026-10-05
- **Contexto:**
  Numerosos portales de datos abiertos gubernamentales y empresariales (como `datos.gob.bo`, `catalog.data.gov` y repositorios institucionales) operan sobre CKAN (Comprehensive Knowledge Archive Network).
  Para integrar estos catálogos en la red soberana DataMesh sin requerir reescrituras manuales, es necesario un mecanismo automatizado que extraiga sus paquetes, recursos, esquemas de DataStore y metadatos extras, reconstruyéndolos en bundles y contratos estandarizados OKF / ODKF v0.2 (`datapackage.yaml` e `index.md`).
  Adicionalmente, muchos catálogos privados o protegidos operan detrás de capas de autenticación federada (Keycloak, OpenID Connect, OAuth2 Client Credentials, API Keys). Se requiere un estándar de descubrimiento abierto que permita a cualquier portal anunciar libremente sus capacidades y requerimientos de acceso.

- **Decisión:**
  1. **Protocolo Abierto de Descubrimiento Well-Known (`/.well-known/datamesh.json` / `/.well-known/okf.json`):**
     - Se definió el esquema universal de metadatos de descubrimiento que expone información del catálogo (`type`: ckan, okf, dcat), punto de enlace API (`api_endpoint`), especificaciones de autenticación (`keycloak`, `oauth2`, `api_key`, `none`) y capacidades analíticas (`search`, `sql_query`, `datastore`, `harvesting`).
     - Se implementó `WellKnownResolverAdapter` y `DiscoverWellKnownUseCase` con detección activa y fallback automático para portales CKAN legacy sin well-known configurado (sondeo de `/api/3/action/status_show`).
  2. **Arquitectura de Autenticación Desacoplada (`AuthProviderPort`):**
     - Se implementó `KeycloakAuthAdapter` para flujo OAuth 2.0 Client Credentials (`/protocol/openid-connect/token`) con refresco automático y caché en memoria de tokens JWT.
     - Se implementaron adaptadores para `APIKeyAuthAdapter` (inyección de headers configurables como `X-CKAN-API-Key`) y `BearerTokenAuthAdapter`.
  3. **Ingesta y Reconstrucción CKAN a OKF v0.2 (`HarvestCKANUseCase` & `CKANClientAdapter`):**
     - Interacción con CKAN Action API v3 (`package_search`, `package_show`, `datastore_search`).
     - Reconstrucción de `datapackage.yaml` / `.json` mapeando recursos, tipos de datos de DataStore, límites espaciales GeoJSON/BBox de `extras`, cobertura temporal y perfil de calidad.
     - Generación de documentación de conocimiento `index.md` con frontmatter conforme a ODKF v0.2 y catálogo de recursos.
  4. **Fachada Unificada y CLI:**
     - Métodos Python: `dm.discover_endpoint(url)` y `dm.harvest_ckan(url, ...)`.
     - Comandos CLI: `datamesh discover <url>` y `datamesh harvest-ckan <url> [--out-dir] [--token] [--client-id] [--client-secret]`.
     - Herramientas MCP: `datamesh_discover_endpoint` y `datamesh_harvest_ckan`.
     - Modelos de dominio y puertos homólogos en Go core (`core-go/domain/ckan.go`, `wellknown.go`, `ports/outbound/harvester.go`).

- **Consecuencias:**
  - **Positivas:**
    - Capacidad de ingerir cualquier portal CKAN público o protegido hacia la red soberana DataMesh con una sola línea de código o comando CLI.
    - Autodescubrimiento transparente de requerimientos de autenticación y endpoints.
    - Mapeo automático de esquemas DataStore hacia campos tipados en `datapackage.yaml`.
  - **Compensaciones:**
    - En portales CKAN sin extensión DataStore, los tipos de columnas de los recursos deben inferirse dinámicamente mediante DuckDB al momento de la consulta.
