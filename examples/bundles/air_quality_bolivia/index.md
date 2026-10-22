---
type: dcat:Dataset
id: air_quality_bolivia
title: Red Nacional de Monitoreo de Calidad del Aire de Bolivia
description: Medición horaria de material particulado (PM2.5, PM10) y gases en las ciudades del eje troncal boliviano (La Paz, Cochabamba, Santa Cruz).
conformsTo: https://openknowledge.org/okf/v0.2
publisher:
  name: Red MoniCA Bolivia / Viceministerio de Medio Ambiente
  email: contacto@medioambiente.gob.bo
spatial:
  country: BO
  regions: ["BO-L", "BO-C", "BO-S"]
temporal:
  start: 2024-06-01T08:00:00Z
  end: 2024-06-01T12:00:00Z
license: CC-BY-4.0
resources:
  - name: calidad_aire_parquet
    path: data/calidad_aire_2024.parquet
    format: parquet
    hash: sha256:4fbe382aa7e6c93502b33d37a67663209228293d6ab26c5b9670ac758477c619
    concepts:
      pm25: wd:Q5624508
      pm10: wd:Q207551
  - name: calidad_aire_csv
    path: data/calidad_aire_2024.csv
    format: csv
    hash: sha256:6b18332b587b7fdc2a024b50a6440a22660975ba358aaa9ade994d5cad62e6fa
---

# Red Nacional de Monitoreo de Calidad del Aire de Bolivia

Este bundle estático tabular implementa los principios **FAIR (Findable, Accessible, Interoperable, Reusable)** para datos ambientales en Bolivia:

1. **Findable:** Descriptor unificado en Markdown + Frontmatter YAML indexable por motores de búsqueda y catálogos distribuidos.
2. **Accessible:** Doble distribución en formato abierto Parquet (columnar comprimido) y CSV normalizado, disponible tanto en filesystem local como HTTP.
3. **Interoperable:** Esquema tipado con anclaje ontológico formal a Wikidata (`wd:Q5624508` para PM2.5, `wd:Q207551` para PM10) y códigos departamentales ISO 3166-2:BO.
4. **Reusable:** Licencia permisiva Creative Commons Atribución 4.0 Internacional (CC-BY-4.0) con sumas de verificación inmutables SHA-256.

## Ejemplo de Consulta Rápida con DataMesh SDK

```python
import datamesh as dm

# Carga de una línea con DuckDB embebido
df = dm.read("examples/bundles/air_quality_bolivia", resource="calidad_aire_parquet")
print(df.summary())

# Filtrado SQL directo
ciudades_alerta = dm.sql("""
    SELECT ciudad, estacion, AVG(pm25) as media_pm25, MAX(aqi) as max_aqi
    FROM df
    GROUP BY ciudad, estacion
    HAVING max_aqi > 100
""")
print(ciudades_alerta)
```
