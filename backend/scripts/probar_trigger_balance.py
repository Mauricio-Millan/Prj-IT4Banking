"""Uso puntual: fuerza un asiento desbalanceado con SQL crudo para confirmar que
trg_asiento_balanceado (defensa en profundidad, no alcanzable via pytest/SQLite) realmente
rechaza la insercion en Azure SQL/SQL Server. Todo dentro de una transaccion sin commit:
no deja rastro sin importar si el trigger dispara o no."""
from sqlalchemy import text

from app.core.db import engine

with engine.connect() as c:
    tx = c.begin()
    try:
        asiento_id = c.execute(text(
            "INSERT INTO asiento_contable (tipo_operacion, estado) OUTPUT inserted.asiento_id "
            "VALUES ('deposito', 'contabilizado')"
        )).scalar()
        # 100.00 vs 99.00: deliberadamente desbalanceado
        c.execute(text(
            "INSERT INTO movimiento_contable (asiento_id, cuenta_contable_id, tipo_movimiento, importe, moneda) "
            "VALUES (:a, 1, 'D', 100.00, 'PEN'), (:a, 2, 'H', 99.00, 'PEN')"
        ), {"a": asiento_id})
        print("ERROR: el trigger NO disparo — esto no deberia pasar")
    except Exception as e:
        print("trigger disparo correctamente:", str(e)[:160])
    finally:
        tx.rollback()
