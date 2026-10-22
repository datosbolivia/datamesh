---
type: dcat:Dataset
id: censo_2024_cartografia
title: Cartografía Censal Digitalizada Bolivia 2024 (INE)
description: Paquete cartográfico compuesto en archivo ZIP con acceso selectivo a subarchivos departamentales vía fragment identifiers RFC 3986.
conformsTo: https://openknowledge.org/okf/v0.2
publisher:
  name: Instituto Nacional de Estadística (INE)
  email: censo2024@ine.gob.bo
resources:
  - name: cartografia_completa_zip
    path: data/censo_cartografia.zip
    format: zip
    packageFormat: application/zip
    hash: sha256:b346bcbda2bc4a74076862a5626828024f16ac57d4d9513d953dab67d11158b0
    supportsHttpRange: true
    subresources:
      - id: manzanas_santa_cruz
        fragment: "#scz_manzanas.parquet"
        format: parquet
      - id: manzanas_la_paz
        fragment: "#lpz_manzanas.parquet"
        format: parquet
---

# Cartografía Censal Digitalizada Bolivia 2024 (INE)

Este bundle compuesto resuelve el problema de la **transferencia innecesaria de archivos masivos** en Bolivia:

- **Fragment Identifiers RFC 3986:** Permite citar y extraer subarchivos específicos dentro de un archivo ZIP (`censo_cartografia.zip#scz_manzanas.parquet`).
- **HTTP Range Requests Zero-Copy:** Si el archivo está alojado en un servidor HTTP/S3, el SDK lee únicamente la tabla de directorios central del ZIP mediante cabeceras `Range: bytes=X-Y`, extrayendo el subarchivo solicitado sin descargar los gigabytes restantes.

## Uso en DataMesh SDK

```python
import datamesh as dm

# Extracción y carga directa del subarchivo sin descomprimir todo el archivo
df_scz = dm.read("examples/bundles/censo_2024_cartografia/data/censo_cartografia.zip#scz_manzanas.parquet")
print(df_scz.head())
```
