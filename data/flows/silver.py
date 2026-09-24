"""Carga a silver.* (Azure SQL DW): MERGE por clave natural (idempotente, V1) + enmascarado de
PII (V2/V10) -- silver es la frontera de confianza, nada despues vuelve a ver un dato crudo."""
import hashlib

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from . import config

_COLUMNAS = {
    "transaccion": (
        "transaccion_id",
        ["transaccion_id", "cuenta_origen_id", "cuenta_destino_id", "fecha_hora", "tipo", "monto",
         "canal", "estado", "concepto", "transaccion_origen_id"],
    ),
    "cuenta": (
        "cuenta_id",
        ["cuenta_id", "cliente_id", "numero_cuenta", "cci", "tipo_cuenta", "moneda", "saldo",
         "fecha_apertura", "estado"],
    ),
    "prestamo": (
        "prestamo_id",
        ["prestamo_id", "cliente_id", "cuenta_desembolso_id", "monto_original", "saldo_capital",
         "tasa", "plazo", "fecha_desembolso", "dias_mora", "bucket_mora", "estado"],
    ),
    "cuota": (
        "cuota_id",
        ["cuota_id", "prestamo_id", "numero", "fecha_vencimiento", "capital", "interes", "total",
         "saldo_capital_despues", "estado", "fecha_pago", "transaccion_id"],
    ),
    "movimiento_contable": (
        "movimiento_id",
        ["movimiento_id", "asiento_id", "cuenta_contable_id", "cuenta_cliente_id", "tipo_movimiento",
         "importe", "moneda", "codigo_cuenta_contable", "fecha_contable", "tipo_operacion", "transaccion_id"],
    ),
    "cliente": (
        "cliente_id",
        ["cliente_id", "codigo_cliente", "iniciales", "documento_hash", "ruc", "razon_social",
         "segmento", "region", "fecha_alta", "estado"],
    ),
}


def _engine() -> Engine:
    return create_engine(config.dw_url())


def _hash_documento(numero_documento: str) -> str:
    return hashlib.sha256((config.SAL_DOCUMENTO + numero_documento).encode()).hexdigest()


def _iniciales(nombres: str, apellidos: str) -> str:
    partes = str(nombres).split() + str(apellidos).split()
    return " ".join(f"{p[0].upper()}." for p in partes if p)


def enmascarar_clientes(df: pd.DataFrame) -> pd.DataFrame:
    """V2: persona natural -> codigo_cliente, iniciales, documento_hash (nunca nombre/documento/
    correo/telefono en claro). V10: empresa (RUC) -> razon_social y RUC completo (es publico de
    SUNAT, HU-Segmentacion-Clientes V13); nombres/apellidos del representante igual a iniciales."""
    if df.empty:
        return pd.DataFrame(columns=_COLUMNAS["cliente"][1])
    filas = []
    for _, c in df.iterrows():
        es_ruc = c["tipo_documento"] == "RUC"
        filas.append({
            "cliente_id": c["cliente_id"],
            "codigo_cliente": c["codigo_cliente"],
            "iniciales": _iniciales(c["nombres"], c["apellidos"]),
            "documento_hash": None if es_ruc else _hash_documento(c["numero_documento"]),
            "ruc": c["numero_documento"] if es_ruc else None,
            "razon_social": c["razon_social"] if es_ruc else None,
            "segmento": c["segmento"],
            "region": c["region"],
            "fecha_alta": c["fecha_alta"],
            "estado": c["estado"],
        })
    return pd.DataFrame(filas)


def _merge(engine: Engine, df: pd.DataFrame, tabla: str, clave: str, columnas: list[str]) -> None:
    if df.empty:
        return
    staging = f"stg_{tabla}"
    df[columnas].to_sql(staging, engine, schema="silver", if_exists="replace", index=False)
    set_clause = ", ".join(f"tgt.{c} = src.{c}" for c in columnas if c != clave)
    insert_cols = ", ".join(columnas)
    insert_vals = ", ".join(f"src.{c}" for c in columnas)
    merge_sql = f"""
        MERGE silver.{tabla} AS tgt
        USING silver.{staging} AS src ON tgt.{clave} = src.{clave}
        WHEN MATCHED THEN UPDATE SET {set_clause}
        WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals});
    """
    with engine.begin() as conn:
        conn.execute(text(merge_sql))
        conn.execute(text(f"DROP TABLE silver.{staging}"))


def cargar_silver(validas: dict[str, pd.DataFrame], engine: Engine | None = None) -> None:
    engine = engine or _engine()
    for tabla in ("transaccion", "cuenta", "prestamo", "cuota", "movimiento_contable"):
        clave, columnas = _COLUMNAS[tabla]
        _merge(engine, validas[tabla], tabla, clave, columnas)

    clave, columnas = _COLUMNAS["cliente"]
    _merge(engine, enmascarar_clientes(validas["cliente"]), "cliente", clave, columnas)
