---
type: dcat:DataService
id: cndc_despacho_electrico
title: Despacho y Operación en Tiempo Real del Sistema Interconectado Nacional (CNDC)
description: Telemetría y estado de operación en tiempo real de nodos de generación y transmisión del Sistema Interconectado Nacional de Bolivia.
conformsTo: https://openknowledge.org/okf/v0.2
publisher:
  name: Comité Nacional de Despacho de Carga (CNDC)
  email: soporte@cndc.bo
spatial:
  country: BO
provenance:
  wasGeneratedBy: urn:cndc:scada:collector_service_v3
  wasAttributedTo: urn:cndc:bolivia:operaciones
resources:
  - name: telemetria_stream
    type: dcat:DataService
    protocol: flight-sql
    endpoint: grpc://telemetria.cndc.bo:443
  - name: snapshot_despacho
    path: data/snapshot_despacho.parquet
    format: parquet
---

# Despacho y Operación en Tiempo Real del SIN (CNDC)

Este bundle dinámico ejemplifica la extensión de **W3C DCAT v3 `dcat:DataService`** en el Formato de Conocimiento Abierto:

- **Protocolo de Alta Eficiencia:** Acceso directo vía Apache Arrow Flight SQL streaming en gRPC.
- **Linaje Criptográfico (W3C PROV-O):** Certificación de origen del sistema SCADA con sello temporal inmutable.
- **Tolerancia a Fallos y Modo Offline:** En caso de corte de red exterior, el SDK conmuta al snapshot local cached `snapshot_despacho.parquet`.

## Uso en DataMesh SDK

```python
import datamesh as dm

# Conexión transparente al servicio o al snapshot offline
stream = dm.read("examples/bundles/cndc_despacho_electrico", resource="telemetria_stream")
df = stream.fetch(limit=100)
print(df)
```
