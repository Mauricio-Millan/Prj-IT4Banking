"""HU-Analitica-DW-PowerBI: construccion de gold.* desde silver.* (nunca desde el OLTP ni
Bronze -- V1). Funciones puras (reciben/devuelven DataFrames, testeables sin SQL Server) +
tareas de orquestacion que sí hacen I/O contra el DW."""
from datetime import date

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from . import config
from .db import merge

CANAL_A_ID = {canal: i + 1 for i, canal in enumerate(config.CANALES)}
PRODUCTO_AHORRO, PRODUCTO_CORRIENTE, PRODUCTO_TARJETA, PRODUCTO_PRESTAMO = 1, 2, 3, 4
_TIPO_CUENTA_A_PRODUCTO = {"ahorro": PRODUCTO_AHORRO, "corriente": PRODUCTO_CORRIENTE}

_COL_DIM_CLIENTE = ["cliente_id", "codigo_cliente", "es_empresa", "segmento", "region", "fecha_alta", "estado"]
_COL_HECHO_TRANSACCION = ["transaccion_id", "fecha", "cliente_id", "cuenta_origen_id",
                          "cuenta_destino_id", "canal_id", "tipo", "monto", "concepto"]
_COL_HECHO_CARTERA = ["prestamo_id", "fecha", "cliente_id", "producto_id", "saldo_capital",
                      "dias_mora", "bucket_mora", "cuotas_pagadas", "cuotas_vencidas"]
_COL_HECHO_RENTABILIDAD = ["producto_id", "segmento", "anio_mes", "ingresos", "costo", "margen"]


def _engine() -> Engine:
    return create_engine(config.dw_url())


# ── Transformaciones puras (DoD: testeadas con DataFrames fijos, sin SQL Server real) ──────

def construir_dim_cliente(df_cliente_silver: pd.DataFrame) -> pd.DataFrame:
    """V8: no agrega PII que silver.cliente ya no tuviera, solo reorganiza. es_empresa se
    deriva de 'ruc' (silver.cliente ya no guarda tipo_documento; V10 de la HU del pipeline
    dejo el RUC como la unica marca de que un cliente es una empresa)."""
    if df_cliente_silver.empty:
        return pd.DataFrame(columns=_COL_DIM_CLIENTE)
    df = df_cliente_silver.copy()
    df["es_empresa"] = df["ruc"].notna()
    return df[["cliente_id", "codigo_cliente", "es_empresa", "segmento", "region", "fecha_alta", "estado"]]


def construir_hecho_transaccion(df_transaccion_silver: pd.DataFrame, df_cuenta_silver: pd.DataFrame) -> pd.DataFrame:
    """V3: solo transacciones aplicadas. cliente_id: dueño de cuenta_origen, o de
    cuenta_destino si no hay origen (deposito)."""
    if df_transaccion_silver.empty:
        return pd.DataFrame(columns=_COL_HECHO_TRANSACCION)
    df = df_transaccion_silver[df_transaccion_silver["estado"] == "aplicada"].copy()
    if df.empty:
        return pd.DataFrame(columns=_COL_HECHO_TRANSACCION)

    cuenta_a_cliente = df_cuenta_silver.set_index("cuenta_id")["cliente_id"]
    df["cliente_id"] = df["cuenta_origen_id"].map(cuenta_a_cliente)
    df["cliente_id"] = df["cliente_id"].fillna(df["cuenta_destino_id"].map(cuenta_a_cliente))
    df["fecha"] = pd.to_datetime(df["fecha_hora"]).dt.date
    df["canal_id"] = df["canal"].map(CANAL_A_ID)
    return df[["transaccion_id", "fecha", "cliente_id", "cuenta_origen_id", "cuenta_destino_id",
               "canal_id", "tipo", "monto", "concepto"]]


def construir_hecho_cartera_diaria(df_prestamo_silver: pd.DataFrame, df_cuota_silver: pd.DataFrame, fecha: date) -> pd.DataFrame:
    """V4: dias_mora/bucket_mora/saldo_capital son copia exacta de silver.prestamo (ya los
    calculo cierre_diario en el OLTP); esta funcion solo organiza el grano de hecho."""
    if df_prestamo_silver.empty:
        return pd.DataFrame(columns=_COL_HECHO_CARTERA)
    conteo = df_cuota_silver.groupby(["prestamo_id", "estado"]).size().unstack(fill_value=0)
    df = df_prestamo_silver.copy()
    df["fecha"] = fecha
    df["producto_id"] = PRODUCTO_PRESTAMO
    df["cuotas_pagadas"] = df["prestamo_id"].map(conteo.get("pagada", pd.Series(dtype=int))).fillna(0).astype(int)
    df["cuotas_vencidas"] = df["prestamo_id"].map(conteo.get("vencida", pd.Series(dtype=int))).fillna(0).astype(int)
    return df[["prestamo_id", "fecha", "cliente_id", "producto_id", "saldo_capital",
               "dias_mora", "bucket_mora", "cuotas_pagadas", "cuotas_vencidas"]]


def _producto_de_ingreso(tipo_transaccion: str, tipo_cuenta: str | None) -> int:
    if tipo_transaccion == "pago_prestamo":
        return PRODUCTO_PRESTAMO
    return _TIPO_CUENTA_A_PRODUCTO.get(tipo_cuenta, PRODUCTO_AHORRO)


def construir_rentabilidad_mensual(
    df_movimiento_silver: pd.DataFrame, df_transaccion_silver: pd.DataFrame, df_cuenta_silver: pd.DataFrame,
    df_cliente_silver: pd.DataFrame,
) -> pd.DataFrame:
    """V5: ingresos = HABER en 4101 (comisiones) + 4201 (intereses); costo = DEBE en 5101/5201
    (HU-Gastos-Operativos-Intereses-Pasivos, aun no implementada en el OLTP -> costo sale en 0,
    nunca estimado a mano). Grano producto x segmento x mes.

    Atribucion de producto: pago_prestamo -> prestamo; cualquier otro ingreso (hoy solo
    'comision') -> el tipo de la cuenta que origino el cobro (ahorro/corriente). El segmento
    siempre es el del dueño de esa cuenta (quien paga la comision o la cuota es su propio
    cliente, ver services/prestamos.py::pagar_cuota)."""
    codigos_ingreso = ("4101", "4201")
    codigos_costo = ("5101", "5201")

    ingresos_h = df_movimiento_silver[
        df_movimiento_silver["codigo_cuenta_contable"].isin(codigos_ingreso)
        & (df_movimiento_silver["tipo_movimiento"] == "H")
    ].copy()
    costo_d = df_movimiento_silver[
        df_movimiento_silver["codigo_cuenta_contable"].isin(codigos_costo)
        & (df_movimiento_silver["tipo_movimiento"] == "D")
    ].copy()

    if ingresos_h.empty and costo_d.empty:
        return pd.DataFrame(columns=_COL_HECHO_RENTABILIDAD)

    tx = df_transaccion_silver.set_index("transaccion_id")[["tipo", "cuenta_origen_id"]]
    cuenta_info = df_cuenta_silver.set_index("cuenta_id")[["cliente_id", "tipo_cuenta"]]
    cliente_segmento = df_cliente_silver.set_index("cliente_id")["segmento"]

    def _agregar(df: pd.DataFrame, columna_monto: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["producto_id", "segmento", "anio_mes", columna_monto])
        df = df.join(tx, on="transaccion_id")
        df = df.join(cuenta_info, on="cuenta_origen_id")
        df["segmento"] = df["cliente_id"].map(cliente_segmento)
        df["producto_id"] = df.apply(lambda f: _producto_de_ingreso(f["tipo"], f["tipo_cuenta"]), axis=1)
        df["anio_mes"] = pd.to_datetime(df["fecha_contable"]).dt.strftime("%Y-%m")
        return df.groupby(["producto_id", "segmento", "anio_mes"])["importe"].sum().reset_index(name=columna_monto)

    ingresos = _agregar(ingresos_h, "ingresos")
    costos = _agregar(costo_d, "costo")

    combinado = pd.merge(ingresos, costos, on=["producto_id", "segmento", "anio_mes"], how="outer")
    combinado["ingresos"] = pd.to_numeric(combinado["ingresos"], errors="coerce").fillna(0.0)
    combinado["costo"] = pd.to_numeric(combinado["costo"], errors="coerce").fillna(0.0)
    combinado["margen"] = combinado["ingresos"] - combinado["costo"]
    return combinado[_COL_HECHO_RENTABILIDAD]


# ── Orquestacion (I/O contra el DW; lee exclusivamente silver.*, V1) ───────────────────────

def _leer_silver(engine: Engine, tabla: str) -> pd.DataFrame:
    return pd.read_sql(f"SELECT * FROM silver.{tabla}", engine)


def construir_gold(fecha: date, engine: Engine | None = None) -> None:
    engine = engine or _engine()

    df_cliente = _leer_silver(engine, "cliente")
    df_cuenta = _leer_silver(engine, "cuenta")
    df_prestamo = _leer_silver(engine, "prestamo")
    df_cuota = _leer_silver(engine, "cuota")
    df_transaccion = _leer_silver(engine, "transaccion")
    df_movimiento = _leer_silver(engine, "movimiento_contable")

    merge(engine, construir_dim_cliente(df_cliente), "gold", "dim_cliente", "cliente_id", _COL_DIM_CLIENTE)
    merge(engine, construir_hecho_transaccion(df_transaccion, df_cuenta), "gold", "hecho_transaccion",
          "transaccion_id", _COL_HECHO_TRANSACCION)
    merge(engine, construir_hecho_cartera_diaria(df_prestamo, df_cuota, fecha), "gold", "hecho_cartera_diaria",
          ["prestamo_id", "fecha"], _COL_HECHO_CARTERA)
    merge(engine, construir_rentabilidad_mensual(df_movimiento, df_transaccion, df_cuenta, df_cliente),
          "gold", "hecho_rentabilidad_mensual", ["producto_id", "segmento", "anio_mes"], _COL_HECHO_RENTABILIDAD)


def conteo_filas_gold(engine: Engine | None = None) -> dict[str, int]:
    """Usado por el smoke test del CI (data.yml) para verificar que la corrida dejo datos."""
    engine = engine or _engine()
    tablas = ("dim_cliente", "dim_producto", "dim_canal", "dim_region", "hecho_transaccion",
              "hecho_cartera_diaria", "hecho_rentabilidad_mensual")
    with engine.connect() as conn:
        return {t: conn.execute(text(f"SELECT COUNT(*) FROM gold.{t}")).scalar() for t in tablas}
