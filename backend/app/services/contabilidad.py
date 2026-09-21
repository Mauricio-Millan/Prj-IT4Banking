"""Primitivas de libro mayor compartidas por transacciones.py, prestamos.py y comisiones.py.
Separadas en su propio modulo (en vez de vivir solo en transacciones.py, como en la version
original de HU-Libro-Mayor-Partida-Doble) porque ahora tres servicios las necesitan: si
transacciones.py llamara a comisiones.py y comisiones.py importara de transacciones.py para
estas funciones, se forma un ciclo (transacciones cobra RET-RED via comisiones; prestamos
tambien la necesita para PRE-ATR). Este modulo no importa de ninguno de los tres, asi que
todos pueden depender de el sin ciclos.
"""
from decimal import Decimal

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import AsientoDesbalanceado, SaldoInsuficiente
from app.models import AsientoContable, Cuenta, MovimientoContable
from app.models.contabilidad import CuentaContable


def debitar(db: Session, cuenta_id: int, monto: Decimal) -> None:
    # ponytail: guardia atomica a nivel de fila (UPDATE ... WHERE saldo >= monto); el motor
    # serializa updates concurrentes sobre la misma fila, no hace falta un lock explicito.
    resultado = db.execute(
        update(Cuenta).where(Cuenta.cuenta_id == cuenta_id, Cuenta.saldo >= monto).values(saldo=Cuenta.saldo - monto)
    )
    if resultado.rowcount == 0:
        raise SaldoInsuficiente()


def acreditar(db: Session, cuenta_id: int, monto: Decimal) -> None:
    db.execute(update(Cuenta).where(Cuenta.cuenta_id == cuenta_id).values(saldo=Cuenta.saldo + monto))


def verificar_balance(movimientos: list[MovimientoContable]) -> None:
    """Pura: Sigma DEBE debe ser igual a Sigma HABER."""
    suma_debe = sum(m.importe for m in movimientos if m.tipo_movimiento == "D")
    suma_haber = sum(m.importe for m in movimientos if m.tipo_movimiento == "H")
    if suma_debe != suma_haber:
        raise AsientoDesbalanceado()


def cuenta_contable_id(db: Session, codigo: str) -> int:
    id_ = db.scalar(select(CuentaContable.cuenta_contable_id).where(CuentaContable.codigo == codigo))
    if id_ is None:
        raise RuntimeError(f"Plan de cuentas incompleto: falta el codigo {codigo!r} (ver seed en la migracion)")
    return id_


def registrar_asiento(
    db: Session, tipo_operacion: str, transaccion_id: int | None, movimientos: list[MovimientoContable],
) -> AsientoContable:
    """Generico: N movimientos que suman cero, cualquiera sea la operacion (2 lineas para
    deposito/retiro/transferencia/desembolso/comision, 3 para pago de cuota)."""
    verificar_balance(movimientos)

    asiento = AsientoContable(tipo_operacion=tipo_operacion, transaccion_id=transaccion_id, estado="contabilizado")
    db.add(asiento)
    db.flush()  # asiento_contable no tiene trigger: el OUTPUT normal de SQLAlchemy funciona aqui.

    # ponytail: Core insert().values([...]) con las filas ya "horneadas" en el statement (no
    # como parametros de .execute()) a proposito. movimiento_contable SI tiene trigger
    # (trg_asiento_balanceado) y SQL Server prohibe OUTPUT sin INTO en una tabla con triggers
    # habilitados. Esta forma compila un solo INSERT multi-fila sin OUTPUT.
    db.execute(insert(MovimientoContable).values([
        {
            "asiento_id": asiento.asiento_id,
            "cuenta_contable_id": m.cuenta_contable_id,
            "cuenta_cliente_id": m.cuenta_cliente_id,
            "tipo_movimiento": m.tipo_movimiento,
            "importe": m.importe,
            "moneda": m.moneda,
        }
        for m in movimientos
    ]))
    return asiento
