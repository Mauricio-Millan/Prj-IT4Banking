# Azure Data Factory — extracción/Bronze/Silver en paralelo a Prefect

Estado: **Bronze y Silver desplegados en `rg-bancocloud`, corren en paralelo a Prefect**. Prefect (`bcloud-carga-dev`, Container Apps Job) sigue siendo el orquestador principal y no fue tocado. Ver comparación en `Docs/Proyecto/Propuesta-Migracion-ADF-DW.md`.

## Qué cubre esta carpeta

### Pipeline `pl_carga_bronze`: extracción OLTP → Bronze
Equivalente a `extraer.py` + `escribir_bronze()` en `data/flows/carga_diaria.py`. Las 6 tablas (`transaccion`, `cuenta`, `prestamo`, `cuota`, `cliente`, `movimiento_contable`) se copian con las mismas queries que usa Prefect, al mismo contenedor/partición (`bronze-dev/<tabla>/fecha=AAAA-MM-DD/part-0.parquet`), binariamente compatible con lo que ya consumen `calidad.py`/`silver.py`.

### Pipeline `pl_carga_silver`: Bronze → Silver
Equivalente a `silver.py::cargar_silver()`. Las 5 tablas sin transformación (`transaccion`, `cuenta`, `prestamo`, `cuota`, `movimiento_contable`) se cargan con Copy Activity + `writeBehavior: upsert` (equivalente nativo al MERGE por clave natural que hace `data/flows/db.py::merge`). `cliente` necesita enmascarado de PII antes de tocar `silver.cliente` — eso **no tiene equivalente nativo en Copy Activity**, así que:
1. Copy Activity carga el Bronze crudo de `cliente` a una tabla de staging (`stg.cliente_bronze`, ver `data/sql/ddl_adf_staging.sql`).
2. Un Stored Procedure Activity llama a `silver.sp_cargar_cliente` (T-SQL), que reimplementa exactamente `silver.py::enmascarar_clientes()` — hash SHA-256 del documento vía `HASHBYTES`, iniciales vía `STRING_SPLIT`/`STRING_AGG`, lógica RUC vs DNI — y hace el MERGE hacia `silver.cliente`.

**Verificado bit a bit**: para un cliente DNI de prueba, `HASHBYTES('SHA2_256', ...)` en T-SQL produjo exactamente el mismo hash que `hashlib.sha256(...)` en Python (`abb7126d...4623c`), y las iniciales calculadas coincidieron ("J. C. P. L." para "Juan Carlos"/"Perez Lopez"). Caso RUC también probado (hash NULL, ruc/razón social poblados). Filas de prueba (`cliente_id` 999001/999002) insertadas y borradas en la misma sesión de prueba, no quedaron en la base.

**No cubre ninguno de los dos pipelines** (sigue siendo responsabilidad exclusiva de Prefect/Container Apps Job hoy):
- Validación de calidad (RNF-05, `calidad.py`) — Bronze se copia tal cual, sin filtrar filas invalidas
- Manifest con hash SHA-256 por partición (integridad del archivo, no del dato)
- Carga a Gold (`analitica.py`, esquema estrella)
- Registro en `ops.pipeline_runs` / `dq.rechazos`

## Recursos en Azure

| Recurso | Nombre |
|---|---|
| Data Factory | `adf-bancocloud-utp` (`rg-bancocloud`, Canada Central) |
| Linked Service OLTP | `ls_oltp_sql` → `bancocloud-dev` (SQL auth, mismo patrón sin Managed Identity) |
| Linked Service DW | `ls_dw_sql` → `bancocloud-dw-dev` (SQL auth) |
| Linked Service ADLS | `ls_adls_bronze` → `stbancocloudbronze` (account key) |
| Dataset origen OLTP | `ds_oltp_query` (tabla genérica, la query la define cada Copy Activity) |
| Dataset Bronze | `ds_bronze_parquet` (parametrizado por `tabla` y `fecha`) |
| Dataset DW | `ds_dw_table` (parametrizado por `esquema` y `tabla`) |
| Pipeline | `pl_carga_bronze` (6 Copy Activities, parámetro `fecha`) |
| Pipeline | `pl_carga_silver` (5 upsert + 1 copy-a-staging + 1 stored procedure, parámetro `fecha`) |
| Trigger | `tr_diario_carga_bronze` — diario 02:00 UTC, **creado en estado Stopped a propósito**. Solo dispara `pl_carga_bronze`; `pl_carga_silver` queda sin trigger, solo invocable a mano |
| Stored procedure (en el DW, no en ADF) | `silver.sp_cargar_cliente` — ver `data/sql/ddl_adf_staging.sql` |

## Por qué el trigger está detenido

Para no correr en paralelo sin supervisión mientras Prefect sigue siendo la fuente de verdad. Activarlo cuando se decida probar en paralelo:

```bash
az datafactory trigger start --resource-group rg-bancocloud --factory-name adf-bancocloud-utp --trigger-name tr_diario_carga_bronze
```

Para detenerlo de nuevo:

```bash
az datafactory trigger stop --resource-group rg-bancocloud --factory-name adf-bancocloud-utp --trigger-name tr_diario_carga_bronze
```

## Verificación manual ya hecha

- `pl_carga_bronze`, corrida 2026-10-02 para `fecha=2026-10-01`: las 6 actividades terminaron en `Succeeded`, archivos confirmados en `bronze-dev/<tabla>/fecha=2026-10-01/part-0.parquet` vía `az storage fs file list` (account-key auth; el login AAD normal no tiene permiso, mismo bloqueo de RBAC de siempre).
- `pl_carga_silver`, misma fecha: las 7 actividades terminaron en `Succeeded`. Confirmado vía `sqlcmd` que `silver.cliente/.cuenta/.prestamo/.cuota/.transaccion/.movimiento_contable` tienen filas reales, y que el enmascarado de `cliente` (hash y RUC) es bit-a-bit idéntico al de `silver.py` (ver sección anterior).

## Redeploy desde cero

Los archivos `linked_service_*.template.json` tienen placeholders (`<SQL_USER>`, `<SQL_PASSWORD>`, `<STORAGE_ACCOUNT_KEY>`) — nunca se commitean credenciales reales, mismo patrón que los Container App secrets. Para recrear:

```bash
# 1. Reemplazar los placeholders de linked_service_*.template.json con los valores reales
#    (desde las secrets del Job: oltp-url, dw-url, storage-key)
# 2. az datafactory linked-service create -g rg-bancocloud --factory-name adf-bancocloud-utp --linked-service-name ls_oltp_sql --properties @linked_service_oltp.json
# 3. az datafactory linked-service create -g rg-bancocloud --factory-name adf-bancocloud-utp --linked-service-name ls_dw_sql --properties @linked_service_dw.json
# 4. az datafactory linked-service create -g rg-bancocloud --factory-name adf-bancocloud-utp --linked-service-name ls_adls_bronze --properties @linked_service_adls_bronze.json
# 5. az datafactory dataset create -g rg-bancocloud --factory-name adf-bancocloud-utp --dataset-name ds_oltp_query --properties @dataset_oltp_query.json
# 6. az datafactory dataset create -g rg-bancocloud --factory-name adf-bancocloud-utp --dataset-name ds_bronze_parquet --properties @dataset_bronze_parquet.json
# 7. az datafactory dataset create -g rg-bancocloud --factory-name adf-bancocloud-utp --dataset-name ds_dw_table --properties @dataset_dw_table.json
# 8. az datafactory pipeline create -g rg-bancocloud --factory-name adf-bancocloud-utp --pipeline-name pl_carga_bronze --pipeline @pipeline_carga_bronze.json
# 9. az datafactory pipeline create -g rg-bancocloud --factory-name adf-bancocloud-utp --pipeline-name pl_carga_silver --pipeline @pipeline_carga_silver.json
# 10. az datafactory trigger create -g rg-bancocloud --factory-name adf-bancocloud-utp --trigger-name tr_diario_carga_bronze --properties @trigger_diario_carga_bronze.json
# 11. Ejecutar data/sql/ddl_adf_staging.sql UNA vez contra bancocloud-dw-<env> (crea stg.cliente_bronze + silver.sp_cargar_cliente)
```

## Correr manualmente (sin trigger)

```bash
echo '{"fecha":"2026-10-01"}' > params.json
az datafactory pipeline create-run -g rg-bancocloud --factory-name adf-bancocloud-utp --pipeline-name pl_carga_bronze --parameters @params.json
# esperar a que termine, luego:
az datafactory pipeline create-run -g rg-bancocloud --factory-name adf-bancocloud-utp --pipeline-name pl_carga_silver --parameters @params.json
```
