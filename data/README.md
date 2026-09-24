# Pipeline de datos BancoCloud (HU-Pipeline-ETL-Bronze-Silver)

Flujo Prefect que extrae del OLTP, escribe Bronze (Parquet inmutable) y carga Silver (Azure SQL DW)
con calidad y enmascarado de PII. Ver `Docs/Proyecto/Historias/HU-Pipeline-ETL-Bronze-Silver.md`
para el diseño completo y las reglas de negocio.

## Ejecución local

1. Desde la raíz del repo: `docker compose up -d` — levanta `sqlserver` (OLTP, igual que ya usa
   `backend/`) y `dw-init`, que crea la base `bancocloud_dw` y aplica `sql/ddl_silver.sql` la
   primera vez (idempotente: si ya existen las tablas, no hace nada).
2. `cd data && pip install -r requirements.txt`
3. Copiar `.env.example` a `.env` y ajustar si hace falta (por defecto ya apunta al SQL Server
   del paso 1).
4. Correr primero `python -m app.jobs.cierre_diario --fecha 2026-09-18` en `backend/` (V7: la
   carga siempre lee `dias_mora`/`bucket_mora`/`segmento` ya actualizados de esa fecha).
5. `python -m flows.carga_diaria --fecha 2026-09-18`

Sin `--fecha`, procesa el día de ayer (pensado para la corrida nocturna real). Repetir el mismo
`--fecha` es seguro: Bronze sobrescribe la partición y Silver hace `MERGE` (V1, idempotencia).

## Tests

```
cd data
python -m pytest -q
```

Son unitarios sobre `flows/calidad.py` con DataFrames fijos — no requieren base de datos ni
`.env`. La extracción (`flows/extraer.py`) y la carga (`flows/silver.py`) se verificaron a mano
contra el OLTP real de Azure (solo lectura) y contra la lógica de enmascarado; no tienen test
automatizado de integración en este repo porque requieren un SQL Server real (SQLite no soporta
`MERGE` ni el resto de la sintaxis T-SQL que usa `silver.py`).

## Qué falta para correr en Azure (fuera del alcance de este repo de código)

El tenant académico (`utp.edu.pe`) bloquea la creación de Service Principals y cualquier
asignación de rol (`Microsoft.Authorization`) — ver `Docs/ci-cd-estrategia.md` §2. Por eso este
pipeline **no usa Bicep ni Managed Identity** como proponía el diseño original de la HU; sigue el
mismo patrón ya adoptado para el backend (autenticación SQL con la sesión `az` heredada del
desarrollador, comandos `az` directos). El runbook completo de aprovisionamiento (storage ADLS,
segunda base SQL, Container Apps Job, Prefect Cloud) está en `Docs/ci-cd-estrategia.md` §7.
