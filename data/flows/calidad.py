"""Reglas de calidad (RNF-05). Cada validar_* recibe el DataFrame crudo de una tabla y devuelve
(validas, rechazos): rechazos es una lista de dicts {tabla, clave, regla, valor}, nunca lanza --
una fila mala no bloquea el dia (ver HU-Pipeline-ETL-Bronze-Silver.md, tabla de reglas)."""
import pandas as pd

from . import config


def _rechazo(tabla: str, clave, regla: str, valor) -> dict:
    return {"tabla": tabla, "clave": str(clave), "regla": regla, "valor": str(valor)}


def validar_transacciones(df: pd.DataFrame, ids_cuenta: set) -> tuple[pd.DataFrame, list[dict]]:
    rechazos: list[dict] = []
    if df.empty:
        return df, rechazos

    ahora = pd.Timestamp.utcnow().tz_localize(None)
    malo_monto = df["monto"] <= 0
    malo_canal = ~df["canal"].isin(config.CANALES)
    malo_fecha = df["fecha_hora"] > ahora
    malo_origen = df["cuenta_origen_id"].notna() & ~df["cuenta_origen_id"].isin(ids_cuenta)
    malo_destino = df["cuenta_destino_id"].notna() & ~df["cuenta_destino_id"].isin(ids_cuenta)
    duplicado = df["transaccion_id"].duplicated(keep="first")

    reglas = [
        (malo_monto, "monto_positivo", "monto"),
        (malo_canal, "canal_valido", "canal"),
        (malo_fecha, "fecha_no_futura", "fecha_hora"),
        (malo_origen, "cuenta_origen_existe", "cuenta_origen_id"),
        (malo_destino, "cuenta_destino_existe", "cuenta_destino_id"),
        (duplicado, "id_unico", "transaccion_id"),
    ]
    for mascara, regla, columna in reglas:
        for _, fila in df[mascara].iterrows():
            rechazos.append(_rechazo("transaccion", fila["transaccion_id"], regla, fila[columna]))

    mala = malo_monto | malo_canal | malo_fecha | malo_origen | malo_destino | duplicado
    return df[~mala].copy(), rechazos


def validar_cuentas(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    if df.empty:
        return df, []
    malo_moneda = ~df["moneda"].isin(("PEN", "USD"))
    rechazos = [_rechazo("cuenta", f["cuenta_id"], "moneda_valida", f["moneda"]) for _, f in df[malo_moneda].iterrows()]
    return df[~malo_moneda].copy(), rechazos


def validar_prestamos(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    if df.empty:
        return df, []
    malo_mora = df["dias_mora"] < 0
    malo_saldo = df["saldo_capital"] < 0
    rechazos = [_rechazo("prestamo", f["prestamo_id"], "dias_mora_no_negativo", f["dias_mora"]) for _, f in df[malo_mora].iterrows()]
    rechazos += [_rechazo("prestamo", f["prestamo_id"], "saldo_capital_no_negativo", f["saldo_capital"]) for _, f in df[malo_saldo].iterrows()]
    mala = malo_mora | malo_saldo
    return df[~mala].copy(), rechazos


def validar_cuotas(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Espejo del CHECK ck_cuota_total del OLTP -- defensa en profundidad, no deberia rechazar
    nunca en la practica si el OLTP ya lo garantiza."""
    if df.empty:
        return df, []
    malo_total = df["total"].round(2) != (df["capital"] + df["interes"]).round(2)
    rechazos = [_rechazo("cuota", f["cuota_id"], "total_igual_capital_mas_interes", f["total"]) for _, f in df[malo_total].iterrows()]
    return df[~malo_total].copy(), rechazos


def validar_movimientos(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    if df.empty:
        return df, []
    malo_importe = df["importe"] <= 0
    malo_tipo = ~df["tipo_movimiento"].isin(("D", "H"))
    rechazos = [_rechazo("movimiento_contable", f["movimiento_id"], "importe_positivo", f["importe"]) for _, f in df[malo_importe].iterrows()]
    rechazos += [_rechazo("movimiento_contable", f["movimiento_id"], "tipo_movimiento_valido", f["tipo_movimiento"]) for _, f in df[malo_tipo].iterrows()]
    mala = malo_importe | malo_tipo
    return df[~mala].copy(), rechazos


def validar_clientes(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Region oficial y CHECK ck_cliente_razon_social del OLTP, espejados aqui (defensa en
    profundidad, ver nota de duplicidad deliberada en config.py)."""
    if df.empty:
        return df, []
    malo_region = ~df["region"].isin(config.REGIONES)
    malo_ruc = (df["tipo_documento"] == "RUC") != df["razon_social"].notna()
    rechazos = [_rechazo("cliente", f["cliente_id"], "region_oficial", f["region"]) for _, f in df[malo_region].iterrows()]
    rechazos += [_rechazo("cliente", f["cliente_id"], "razon_social_segun_tipo_documento", f["tipo_documento"]) for _, f in df[malo_ruc].iterrows()]
    mala = malo_region | malo_ruc
    return df[~mala].copy(), rechazos


def validar(crudo: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    ids_cuenta = set(crudo["cuenta"]["cuenta_id"])
    validas: dict[str, pd.DataFrame] = {}
    rechazos: list[dict] = []

    validas["transaccion"], r = validar_transacciones(crudo["transaccion"], ids_cuenta)
    rechazos += r
    validas["cuenta"], r = validar_cuentas(crudo["cuenta"])
    rechazos += r
    validas["prestamo"], r = validar_prestamos(crudo["prestamo"])
    rechazos += r
    validas["cuota"], r = validar_cuotas(crudo["cuota"])
    rechazos += r
    validas["movimiento_contable"], r = validar_movimientos(crudo["movimiento_contable"])
    rechazos += r
    validas["cliente"], r = validar_clientes(crudo["cliente"])
    rechazos += r

    return validas, pd.DataFrame(rechazos, columns=["tabla", "clave", "regla", "valor"])


def advertencia_volumen(df_transacciones: pd.DataFrame) -> str | None:
    """No falla la corrida (puede ser real, ej. un feriado bancario) -- solo se registra."""
    if len(df_transacciones) == 0:
        return "0 transacciones leidas en el dia: verificar si es esperado"
    return None
