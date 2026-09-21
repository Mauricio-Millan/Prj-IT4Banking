"""Uso puntual: corre la query de reconciliacion contra Azure SQL para confirmar que
sql/consultas_validacion.sql es sintacticamente correcta y que el libro mayor real
reconcilia con cuenta.saldo."""
from sqlalchemy import text

from app.core.db import engine

with engine.connect() as c:
    filas = c.execute(text("""
        SELECT
            c.cuenta_id,
            c.saldo AS saldo_materializado,
            COALESCE(SUM(CASE WHEN mc.tipo_movimiento = 'H' THEN mc.importe ELSE -mc.importe END), 0) AS saldo_reconciliado
        FROM cuenta c
        LEFT JOIN movimiento_contable mc ON mc.cuenta_cliente_id = c.cuenta_id
        GROUP BY c.cuenta_id, c.saldo
        ORDER BY c.cuenta_id
    """)).all()
    for f in filas:
        estado = "OK" if f.saldo_materializado == f.saldo_reconciliado else "DIVERGE"
        print(f.cuenta_id, f.saldo_materializado, f.saldo_reconciliado, estado)
