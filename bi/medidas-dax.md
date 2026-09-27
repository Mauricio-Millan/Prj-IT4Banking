# BancoCloud — Modelo Power BI (`gold.*`)

> No se generó un `bi/BancoCloud.pbix` binario: este entorno no tiene Power BI Desktop instalado
> ni forma de automatizarlo (no es un archivo que se pueda "escribir" como texto). Este documento
> es el plano completo para construirlo en Power BI Desktop en minutos — conexión, relaciones,
> medidas DAX y el contenido exacto de cada página. V7/V8 (Power BI solo contra `gold`, sin PII
> nueva) se cumplen por diseño: ninguna medida ni relación de abajo referencia `silver` ni el OLTP.

## 1. Conexión

- **Origen de datos**: Azure SQL Database → servidor `sql-bancocloud-utp.database.windows.net`,
  base `bancocloud-dw-<env>`.
- **Modo**: Import (el volumen de un proyecto académico no justifica DirectQuery).
- **Tablas a importar**: únicamente el esquema `gold` — `dim_cliente`, `dim_tiempo`,
  `dim_producto`, `dim_canal`, `dim_region`, `hecho_transaccion`, `hecho_cartera_diaria`,
  `hecho_rentabilidad_mensual`. **No** importar nada de `silver`, `dq` ni `ops` (V7).
- **Autenticación**: cuenta Entra del estudiante (mismo login usado para conectar SSMS/Azure
  Data Studio); el firewall del servidor debe tener la IP del equipo agregada
  (`az sql server firewall-rule create`, ver `Docs/ci-cd-estrategia.md`).

## 2. Relaciones del modelo

```
dim_tiempo (fecha) ──1───* hecho_transaccion (fecha)
dim_tiempo (fecha) ──1───* hecho_cartera_diaria (fecha)
dim_cliente (cliente_id) ──1───* hecho_transaccion (cliente_id)
dim_cliente (cliente_id) ──1───* hecho_cartera_diaria (cliente_id)
dim_canal (canal_id) ──1───* hecho_transaccion (canal_id)
dim_producto (producto_id) ──1───* hecho_cartera_diaria (producto_id)
dim_producto (producto_id) ──1───* hecho_rentabilidad_mensual (producto_id)
```

`hecho_rentabilidad_mensual.anio_mes` (texto `'YYYY-MM'`) no se relaciona con `dim_tiempo.fecha`
directamente (grano distinto: mes vs. día) — para el eje de tiempo de la página Dirección, crear
una columna calculada `dim_tiempo[AnioMes] = FORMAT(dim_tiempo[fecha], "YYYY-MM")` y relacionar
por ahí (muchos-a-uno, `dim_tiempo` del lado *muchos* ya que hay ~30 fechas por cada `anio_mes`).

`dim_region`/`hecho_*` no tienen relación directa (`gold.hecho_*` no guarda `region_id`); la
región se trae siempre a través de `dim_cliente.region` (texto), no de `dim_region` — suficiente
para agrupar/filtrar en las tres páginas. `dim_region` existe como catálogo completo (para que un
segmento "Puno: 0 clientes" no desaparezca de un gráfico de barras, `dim_cliente[region]` sola no
lo garantiza salvo que se fuerce `ALL()` sobre `dim_region` en las medidas que lo necesiten — no
usado en la v1 de este dashboard, documentado por si se agrega después).

## 3. Medidas DAX

```dax
-- Página Dirección (RF-11) --

Ingresos totales =
    SUM(hecho_rentabilidad_mensual[ingresos])

Costo total =
    SUM(hecho_rentabilidad_mensual[costo])

Margen total =
    SUM(hecho_rentabilidad_mensual[margen])
    -- Nota: hoy siempre igual a Ingresos totales (costo = 0) hasta que
    -- HU-Gastos-Operativos-Intereses-Pasivos exista en el OLTP (5101/5201).

% Margen =
    DIVIDE([Margen total], [Ingresos totales], 0)

Margen mes anterior =
    CALCULATE([Margen total], DATEADD(dim_tiempo[fecha], -1, MONTH))

Variación margen % =
    DIVIDE([Margen total] - [Margen mes anterior], [Margen mes anterior], BLANK())


-- Página Riesgos (RF-12) --

Saldo total cartera =
    SUM(hecho_cartera_diaria[saldo_capital])

Saldo en mora =
    CALCULATE([Saldo total cartera], hecho_cartera_diaria[bucket_mora] <> "0")

% Cartera en mora =
    DIVIDE([Saldo en mora], [Saldo total cartera], 0)

% Cartera por bucket =
    DIVIDE(
        [Saldo total cartera],
        CALCULATE([Saldo total cartera], ALL(hecho_cartera_diaria[bucket_mora])),
        0
    )
    -- Usar con hecho_cartera_diaria[bucket_mora] en el eje/leyenda del visual.

Préstamos vigentes =
    DISTINCTCOUNT(hecho_cartera_diaria[prestamo_id])

Cuotas vencidas (total) =
    SUM(hecho_cartera_diaria[cuotas_vencidas])


-- Página Marketing --

Clientes totales =
    DISTINCTCOUNT(dim_cliente[cliente_id])

Clientes empresa =
    CALCULATE([Clientes totales], dim_cliente[es_empresa] = TRUE)

Clientes persona natural =
    CALCULATE([Clientes totales], dim_cliente[es_empresa] = FALSE)

Transacciones del período =
    COUNTROWS(hecho_transaccion)

Monto transaccionado =
    SUM(hecho_transaccion[monto])

Clientes nuevos (mes) =
    CALCULATE(
        [Clientes totales],
        FILTER(ALL(dim_cliente), FORMAT(dim_cliente[fecha_alta], "YYYY-MM") = MAX(dim_tiempo[AnioMes]))
    )
```

## 4. Páginas

### Dirección (Gerencia) — RF-11

| Visual | Medidas / campos |
|---|---|
| Tarjetas KPI | `Ingresos totales`, `Costo total`, `Margen total`, `% Margen` |
| Línea de tiempo | `Margen total` por `dim_tiempo[AnioMes]` |
| Barras apiladas | `Ingresos totales` por `dim_producto[nombre]` × `dim_cliente[segmento]` |
| Tabla | `dim_producto[nombre]`, `dim_cliente[segmento]`, `Ingresos totales`, `Costo total`, `Margen total`, `% Margen`, ordenada por margen descendente ("top segmentos") |

### Riesgos (Área de riesgos) — RF-12

| Visual | Medidas / campos |
|---|---|
| Tarjetas KPI | `Saldo total cartera`, `Saldo en mora`, `% Cartera en mora`, `Préstamos vigentes` |
| Barras | `Saldo total cartera` por `hecho_cartera_diaria[bucket_mora]` (los 5 buckets: `0`, `1-30`, `31-60`, `61-90`, `>90`) |
| Tabla / mapa | `dim_cliente[region]`, `Saldo total cartera`, `Saldo en mora`, `% Cartera en mora` — un visual de mapa (Azure Map o Mapa de formas) si el catálogo de regiones de Power BI reconoce los nombres en español; si no, tabla con barra de datos |
| Línea de tiempo | `Saldo en mora` por `dim_tiempo[fecha]` (evolución diaria) |

### Marketing (Comercial)

| Visual | Medidas / campos |
|---|---|
| Tarjetas KPI | `Clientes totales`, `Clientes empresa`, `Clientes persona natural`, `Clientes nuevos (mes)` |
| Barras | `Clientes totales` por `dim_cliente[segmento]` × `dim_cliente[region]` |
| Dona | `Clientes totales` por `dim_cliente[es_empresa]` (personas naturales vs. empresas) |
| Línea de tiempo | `Transacciones del período` y `Monto transaccionado` por `dim_tiempo[fecha]` |

## 5. Seguridad por rol (RLS) — documentada, no implementada (fuera de alcance de la HU)

Regla propuesta para cuando se publique a Power BI Service:

```dax
-- Rol "Analista Regional": solo ve su propia región.
-- Tabla: dim_cliente. Expresión de filtro:
[region] = USERPRINCIPALNAME()
-- (requiere una tabla de mapeo email -> region, no existe hoy; documentado como
-- extensión futura, no bloquea el demo en Desktop sin publicar).
```

## 6. Verificación manual (DoD)

- [ ] Ninguna consulta de `gold.*` ni ninguna tabla importada en Power BI referencia `silver` o
  el OLTP — confirmado por diseño: el conector solo lista `gold.*` porque solo esas tablas se
  seleccionaron al importar.
- [ ] Las tres páginas muestran datos del seed tras conectar (ver conteo real verificado el
  2026-09-27: `dim_cliente` 21 filas, `hecho_transaccion` 8, `hecho_cartera_diaria` 1,
  `hecho_rentabilidad_mensual` 1 — pocas filas porque el seed de datos de prueba
  (`scripts/sembrar_datos_prueba.py`) no ha corrido contra este ambiente; los visuales
  igual renderizan, solo con series cortas).
