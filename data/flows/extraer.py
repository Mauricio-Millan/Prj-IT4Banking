"""Extraccion desde el OLTP (bancocloud). Solo SELECT: la identidad del Job tiene db_datareader
nada mas (V6 de la HU) -- ninguna funcion de este modulo escribe en el OLTP."""
from datetime import date, datetime, time, timedelta

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from . import config


def _engine() -> Engine:
    return create_engine(config.oltp_url())


def extraer_transacciones(fecha: date, engine: Engine | None = None) -> pd.DataFrame:
    """Marca de agua: fecha_hora dentro del dia `fecha` (UTC, igual que se guarda en el OLTP).
    sql envuelto en text(): pd.read_sql solo enlaza parametros nombrados (:inicio) a traves de
    la capa de SQLAlchemy, no si el string se pasa crudo (paramstyle qmark de pyodbc)."""
    inicio = datetime.combine(fecha, time.min)
    fin = inicio + timedelta(days=1)
    sql = text("""
        SELECT transaccion_id, cuenta_origen_id, cuenta_destino_id, fecha_hora, tipo, monto,
               canal, estado, concepto, transaccion_origen_id
        FROM transaccion
        WHERE fecha_hora >= :inicio AND fecha_hora < :fin
    """)
    return pd.read_sql(sql, engine or _engine(), params={"inicio": inicio, "fin": fin})


def extraer_cuentas(engine: Engine | None = None) -> pd.DataFrame:
    """Snapshot completo (tabla pequeña): necesaria para validar cuenta_origen/destino existentes."""
    sql = "SELECT cuenta_id, cliente_id, numero_cuenta, cci, tipo_cuenta, moneda, saldo, fecha_apertura, estado FROM cuenta"
    return pd.read_sql(sql, engine or _engine())


def extraer_prestamos(engine: Engine | None = None) -> pd.DataFrame:
    sql = """
        SELECT prestamo_id, cliente_id, cuenta_desembolso_id, monto_original, saldo_capital, tasa,
               plazo, fecha_desembolso, dias_mora, bucket_mora, estado
        FROM prestamo
    """
    return pd.read_sql(sql, engine or _engine())


def extraer_cuotas(engine: Engine | None = None) -> pd.DataFrame:
    sql = """
        SELECT cuota_id, prestamo_id, numero, fecha_vencimiento, capital, interes, total,
               saldo_capital_despues, estado, fecha_pago, transaccion_id
        FROM cuota
    """
    return pd.read_sql(sql, engine or _engine())


def extraer_clientes(engine: Engine | None = None) -> pd.DataFrame:
    sql = """
        SELECT cliente_id, codigo_cliente, tipo_documento, numero_documento, razon_social,
               nombres, apellidos, region, segmento, fecha_alta, estado
        FROM cliente
    """
    return pd.read_sql(sql, engine or _engine())


def extraer_movimientos_ingreso(fecha: date, engine: Engine | None = None) -> pd.DataFrame:
    """Solo cuentas de ingreso (4101 comisiones, 4201 intereses): dato crudo para
    HU-Analitica-DW-PowerBI, sin agregar nada aqui (fuera de alcance de esta HU)."""
    sql = text("""
        SELECT m.movimiento_id, m.asiento_id, m.cuenta_contable_id, m.cuenta_cliente_id,
               m.tipo_movimiento, m.importe, m.moneda, cc.codigo AS codigo_cuenta_contable,
               a.fecha_contable, a.tipo_operacion, a.transaccion_id
        FROM movimiento_contable m
        JOIN cuenta_contable cc ON cc.cuenta_contable_id = m.cuenta_contable_id
        JOIN asiento_contable a ON a.asiento_id = m.asiento_id
        WHERE cc.codigo IN ('4101', '4201') AND a.fecha_contable = :fecha
    """)
    return pd.read_sql(sql, engine or _engine(), params={"fecha": fecha})


def extraer_todo(fecha: date) -> dict[str, pd.DataFrame]:
    engine = _engine()
    return {
        "transaccion": extraer_transacciones(fecha, engine),
        "cuenta": extraer_cuentas(engine),
        "prestamo": extraer_prestamos(engine),
        "cuota": extraer_cuotas(engine),
        "cliente": extraer_clientes(engine),
        "movimiento_contable": extraer_movimientos_ingreso(fecha, engine),
    }
