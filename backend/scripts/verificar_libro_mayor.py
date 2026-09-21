"""Uso puntual: confirma que la migracion del libro mayor aplico correctamente en Azure SQL."""
from sqlalchemy import text

from app.core.db import engine

with engine.connect() as c:
    tablas = c.execute(text(
        "SELECT name FROM sys.tables WHERE name IN ('cuenta_contable','asiento_contable','movimiento_contable')"
    )).all()
    print("tablas:", [t[0] for t in tablas])

    plan = c.execute(text("SELECT codigo, nombre, naturaleza, tipo FROM dbo.cuenta_contable ORDER BY codigo")).all()
    print("plan de cuentas:", plan)

    trig = c.execute(text("SELECT name FROM sys.triggers WHERE name = 'trg_asiento_balanceado'")).all()
    print("trigger:", trig)

    idx = c.execute(text(
        "SELECT name, is_unique, filter_definition FROM sys.indexes WHERE name = 'ux_asiento_transaccion_original'"
    )).all()
    print("indice filtrado:", idx)
