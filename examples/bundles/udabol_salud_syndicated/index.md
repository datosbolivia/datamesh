---
type: dcat:CatalogRecord
id: udabol_salud_syndicated
title: Vigilancia Epidemiológica de Arbovirosis en Bolivia (UDABOL - Ministerio de Salud)
description: Conjunto de datos sindicado con co-referencia multicatálogo entre repositorios académicos y estatales, deduplicado por CID inmutable.
conformsTo: https://openknowledge.org/okf/v0.2
publisher:
  name: Carrera de Medicina e Ingeniería de Sistemas - UDABOL
  email: investigacion@udabol.edu.bo
sovereignAddress: dengue_2024.series_tiempo@udabol_salud
syndication:
  sameAs:
    - https://datos.umsa.bo/epidemiologia/dengue_2024
    - https://snis.minsalud.gob.bo/datasets/arbovirosis_2024
  cid: sha256:1e3d08745ed6318430da1f2892b4a9fe57db6b1152c2015db406e3f77bcec3e3
resources:
  - name: dengue_parquet
    path: data/dengue_bolivia_2024.parquet
    format: parquet
    hash: sha256:1e3d08745ed6318430da1f2892b4a9fe57db6b1152c2015db406e3f77bcec3e3
---

# Vigilancia Epidemiológica de Arbovirosis en Bolivia (UDABOL)

Este bundle sindicado resuelve la **problemática de la duplicación y desactualización en múltiples catálogos (Many-to-Many)**:

- **Co-referencia `owl:sameAs` y `dcat:CatalogRecord`:** El dataset publicado originalmente por la UDABOL puede ser referenciado idénticamente por la UMSA o el Ministerio de Salud sin duplicar el almacenamiento físico.
- **Content-Addressing Deduplication (CID SHA-256):** Ambas instituciones referencian el mismo hash inmutable `sha256:1e3d08745ed6318430da1f2892b4a9fe57db6b1152c2015db406e3f77bcec3e3`. Si el usuario ya descargó el dato desde la UMSA, la consulta al catálogo de UDABOL utiliza la caché local sin consumir ancho de banda.
- **DNS Soberano:** Se resuelve transparentemente mediante `dengue_2024.series_tiempo@udabol_salud`.

## Uso en DataMesh SDK

```python
import datamesh as dm

# Resolución a través del DNS Soberano P2P
df_dengue = dm.read("dengue_2024.series_tiempo@udabol_salud")
print(df_dengue.filter("casos_confirmados > 50"))
```
